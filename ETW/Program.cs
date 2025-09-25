using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using Microsoft.Diagnostics.Tracing.Session;

namespace CursorProcessTree
{
    class Program
    {
        class ProcessInfo
        {
            public int Pid { get; set; }
            public int ParentPid { get; set; }
            public string Name { get; set; } = "";
            public string CmdLine { get; set; } = "";
        }

        // --- 관리용 맵 ---
        static readonly Dictionary<int, ProcessInfo> processMap = new();
        static readonly Dictionary<int, List<int>> treeMap = new();
        static readonly Dictionary<ulong, string> fileKeyPath = new();
        static readonly HashSet<int> mcpPids = new();

        static readonly ConcurrentDictionary<int, string> _pidTypeMap = new();

        static int rootPid = -1;
        static string targetProcess = "";

        static readonly string logPath = "etw_events_log.txt";
        static StreamWriter logWriter;
        static readonly object logLock = new();

        static readonly ConcurrentDictionary<string, long> fileOffsets = new();
        static readonly ConcurrentDictionary<int, string> pidConnections = new();
        static readonly ConcurrentDictionary<int, HashSet<string>> seenConnections = new();

        static readonly string userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        static readonly string[] excludePrefixes = new[]
        {
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Cursor") + Path.DirectorySeparatorChar,
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "cursor") + Path.DirectorySeparatorChar,
            Path.Combine(userProfile, ".cursor", "extensions") + Path.DirectorySeparatorChar
        };

        // ===================== MCP 콜 스코프 추적 =====================
        class TagState
        {
            public int UnknownDepth;
            public HashSet<string> ActiveIds = new(StringComparer.OrdinalIgnoreCase);
            public int EffectiveDepth => UnknownDepth + ActiveIds.Count;
        }

        static readonly ConcurrentDictionary<int, ConcurrentDictionary<string, TagState>> tagStates =
            new();

        static readonly ConcurrentDictionary<int, ConcurrentDictionary<string, string>> activeRemoteByPidTag =
            new();

        static readonly Regex ReStartAction = new(@"Handling\s+CallTool\s+action\s+for\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReCallingWithId = new(@"Calling\s+tool\s+'([^']+)'\s+with\s+toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReSuccess = new(@"Successfully\s+called\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReFail = new(@"Failed\s+to\s+call\s+tool\s+'([^']+)'",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReSuccessWithId = new(@"Successfully.*toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        static readonly Regex ReFailWithId = new(@"Failed.*toolCallId:\s*([^\s]+)",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);
        // ===============================================================

        static void Main(string[] args)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("Enter target process name (e.g., Cursor.exe, Claude.exe): ");
            Console.ResetColor();
            targetProcess = Console.ReadLine()?.Trim() ?? "";

            if (string.IsNullOrEmpty(targetProcess))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] No process name entered. Exiting...");
                Console.ResetColor();
                return;
            }

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[+] Monitoring {targetProcess}, MCP file + network events...");
            Console.WriteLine($"[+] Logging events to: {Path.GetFullPath(logPath)} (append mode)");
            Console.ResetColor();

            if (!(TraceEventSession.IsElevated() ?? false))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] Please run as Administrator!");
                Console.ResetColor();
                return;
            }

            logWriter = new StreamWriter(logPath, false, System.Text.Encoding.UTF8) { AutoFlush = true };

            using var session = new TraceEventSession("ProcessTreeSession");
            session.EnableKernelProvider(
                KernelTraceEventParser.Keywords.Process |
                KernelTraceEventParser.Keywords.FileIO |
                KernelTraceEventParser.Keywords.FileIOInit |
                KernelTraceEventParser.Keywords.NetworkTCPIP |
                KernelTraceEventParser.Keywords.ImageLoad
            );

            // --- Process start ---
            session.Source.Kernel.ProcessStart += data =>
            {
                var info = new ProcessInfo
                {
                    Pid = data.ProcessID,
                    ParentPid = data.ParentID,
                    Name = data.ImageFileName ?? "",
                    CmdLine = data.CommandLine ?? ""
                };

                lock (processMap)
                {
                    processMap[info.Pid] = info;
                    if (!treeMap.ContainsKey(info.ParentPid))
                        treeMap[info.ParentPid] = new List<int>();
                    treeMap[info.ParentPid].Add(info.Pid);
                }

                string inferredType = InferType(info.Name, info.CmdLine) ?? "unknown";
                _pidTypeMap[info.Pid] = inferredType;

                LogLine($"[Process Start] PID={info.Pid}, PPID={info.ParentPid}, Name={info.Name}, Type={inferredType}, Cmd={info.CmdLine}");

                if (rootPid == -1 &&
                    info.Name.Equals(targetProcess, StringComparison.OrdinalIgnoreCase))
                {
                    rootPid = info.Pid;
                    PrintProcessEvent("[ROOT FOUND]", info, inferredType, ConsoleColor.Cyan);
                }

                if (IsChildOfTarget(info.Pid))
                    PrintProcessEvent("[START]", info, inferredType, ConsoleColor.Green);
            };

            // --- Process stop ---
            session.Source.Kernel.ProcessStop += data =>
            {
                var pid = data.ProcessID;
                lock (processMap)
                {
                    if (processMap.TryGetValue(pid, out var info))
                    {
                        string typeLabel = _pidTypeMap.TryRemove(pid, out var storedType) ? storedType : "unknown";
                        LogLine($"[Process Stop ] PID={pid}, Name={info.Name}, Type={typeLabel}");

                        if (IsChildOfTarget(pid))
                            PrintProcessEvent("[EXIT]", info, typeLabel, ConsoleColor.DarkGray);

                        processMap.Remove(pid);
                        mcpPids.Remove(pid);
                        tagStates.TryRemove(pid, out _);
                        activeRemoteByPidTag.TryRemove(pid, out _);
                        pidConnections.TryRemove(pid, out _);
                        seenConnections.TryRemove(pid, out _);
                    }
                }
            };

            // --- Image Load ---
            session.Source.Kernel.ImageLoad += data =>
            {
                try
                {
                    if (IsChildOfTarget(data.ProcessID))
                    {
                        _pidTypeMap.TryGetValue(data.ProcessID, out var knownType);
                        LogLine($"[Image Load   ] PID={data.ProcessID}, DLL={data.FileName}, Type={(knownType ?? "unknown")}");
                    }
                }
                catch { }
            };

            // --- File Create/Open ---
            session.Source.Kernel.FileIOCreate += data =>
            {
                if (!IsChildOfTarget(data.ProcessID)) return;

                string eventType = "[OPEN/CREATE]";
                try
                {
                    object dispObj = null;
                    if (data.PayloadNames.Contains("CreateDisposition"))
                        dispObj = data.PayloadByName("CreateDisposition");
                    else if (data.PayloadNames.Contains("Disposition"))
                        dispObj = data.PayloadByName("Disposition");

                    if (dispObj != null)
                    {
                        uint disp = Convert.ToUInt32(dispObj);
                        switch (disp)
                        {
                            case 0: eventType = "[CREATE]"; break;
                            case 1: eventType = "[OPEN]"; break;
                            case 2: eventType = "[CREATE]"; break;
                            case 3: eventType = "[OPEN_IF]"; break;
                            case 4: eventType = "[OVERWRITE]"; break;
                            case 5: eventType = "[TRUNCATE]"; break;
                            default: eventType = $"[OPEN/CREATE:{disp}]"; break;
                        }
                    }
                }
                catch { }

                HandleFileEvent(eventType, data.ProcessID, data.FileName);
            };

            // --- File Read / Write / Delete ---
            session.Source.Kernel.FileIORead += data =>
                HandleFileEvent("[READ]", data.ProcessID, data.FileName);
            session.Source.Kernel.FileIOWrite += data =>
                HandleFileEvent("[WRITE]", data.ProcessID, data.FileName);
            session.Source.Kernel.FileIOFileDelete += data =>
                HandleFileEvent("[DELETE]", data.ProcessID, data.FileName);

            // --- File Rename ---
            session.Source.Kernel.FileIORename += data =>
            {
                if (!IsChildOfTarget(data.ProcessID)) return;

                var fk = TryGetULong(data, "FileKey") ?? 0UL;
                string newPath = data.FileName;
                string oldPath = null;

                if (fk != 0 && fileKeyPath.TryGetValue(fk, out var prev))
                    oldPath = prev;

                if (string.Equals(newPath, logPath, StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(oldPath, logPath, StringComparison.OrdinalIgnoreCase))
                    return;

                if (IsPathExcluded(oldPath) || IsPathExcluded(newPath)) return;

                int indent = GetIndentLevel(data.ProcessID);
                string spaces = new string(' ', indent * 2);

                Console.ForegroundColor = ConsoleColor.Yellow;
                if (!string.IsNullOrEmpty(oldPath))
                    Console.WriteLine($"{spaces}[RENAME] {oldPath} -> {newPath} (PID={data.ProcessID})");
                else
                    Console.WriteLine($"{spaces}[RENAME] (unknown_old) -> {newPath} (PID={data.ProcessID})");
                Console.ResetColor();

                LogLine($"[RENAME] PID={data.ProcessID}, {oldPath} -> {newPath}");

                if (fk != 0) fileKeyPath[fk] = newPath;
            };

            // --- Network events ---
            session.Source.Kernel.TcpIpSend += data =>
                HandleNetworkEvent("[TCP SEND]", data.ProcessID, data);
            session.Source.Kernel.TcpIpRecv += data =>
                HandleNetworkEvent("[TCP RECV]", data.ProcessID, data);
            session.Source.Kernel.UdpIpSend += data =>
                HandleNetworkEvent("[UDP SEND]", data.ProcessID, data);
            session.Source.Kernel.UdpIpRecv += data =>
                HandleNetworkEvent("[UDP RECV]", data.ProcessID, data);

            try
            {
                session.Source.Process();
            }
            catch (Exception ex)
            {
                try { LogLine("[FATAL] " + ex.Message); } catch { }
            }
        }

        static void LogLine(string line)
        {
            string tsLocal = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            lock (logLock)
            {
                logWriter.WriteLine($"[{tsLocal}] {line}");
            }
        }

        static bool IsChildOfTarget(int pid)
        {
            if (rootPid == -1) return false;

            int current = pid;
            while (processMap.ContainsKey(current))
            {
                if (current == rootPid) return true;
                current = processMap[current].ParentPid;
            }
            return false;
        }

        static bool TryNormalizePath(string path, out string normPath, out string fileName)
        {
            normPath = null;
            fileName = null;
            if (string.IsNullOrWhiteSpace(path)) return false;

            try
            {
                if (path.IndexOfAny(Path.GetInvalidPathChars()) >= 0) return false;
                normPath = path.Replace('/', '\\');
                fileName = Path.GetFileName(normPath);
                return !string.IsNullOrEmpty(fileName);
            }
            catch { return false; }
        }

        static string ExtractServerTag(string normPath)
        {
            try
            {
                string lower = Path.GetFileNameWithoutExtension(normPath).ToLowerInvariant();
                var match = Regex.Match(lower, @"user-([a-z0-9]+)", RegexOptions.IgnoreCase);
                if (match.Success)
                    return match.Groups[1].Value;
                return "mcp";
            }
            catch { return "mcp"; }
        }

        static void HandleFileEvent(string eventType, int pid, string path)
        {
            if (!IsChildOfTarget(pid)) return;
            if (!TryNormalizePath(path, out var normPath, out var fileName)) return;

            if (string.Equals(normPath, logPath, StringComparison.OrdinalIgnoreCase))
                return;

            bool isMcpLog = fileName.EndsWith(".log", StringComparison.OrdinalIgnoreCase) &&
                            fileName.IndexOf("MCP", StringComparison.OrdinalIgnoreCase) >= 0;

            if (!isMcpLog && IsPathExcluded(normPath)) return;

            if (eventType == "[WRITE]" && isMcpLog)
            {
                lock (mcpPids) mcpPids.Add(pid);

                try
                {
                    long lastOffset = fileOffsets.GetOrAdd(normPath, 0);
                    using (var fs = new FileStream(normPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    {
                        fs.Seek(lastOffset, SeekOrigin.Begin);
                        using (var reader = new StreamReader(fs))
                        {
                            string newContent = reader.ReadToEnd();
                            if (!string.IsNullOrWhiteSpace(newContent))
                            {
                                string tag = ExtractServerTag(normPath);
                                UpdateTagStateFromLog(pid, tag, newContent);

                                pidConnections.TryGetValue(pid, out var connInfo);

                                Console.ForegroundColor = ConsoleColor.Magenta;
                                Console.WriteLine($"[LOG CONTENT] {normPath} (PID={pid}{(connInfo != null ? $", Remote={connInfo}" : "")})");
                                Console.ResetColor();
                                Console.WriteLine(newContent);

                                LogLine($"[LOG CONTENT] {normPath} (PID={pid}{(connInfo != null ? $", Remote={connInfo}" : "")})\n{newContent}");
                            }
                        }
                        fileOffsets[normPath] = fs.Length;
                    }
                }
                catch (Exception ex)
                {
                    LogLine($"[ERROR] Failed to read {normPath}: {ex.Message}");
                }
            }

            LogLine($"{eventType} File {normPath} (PID={pid})");

            if (eventType == "[WRITE]" || eventType == "[DELETE]" || eventType.StartsWith("[RENAME]"))
            {
                int indent = GetIndentLevel(pid);
                string spaces = new string(' ', indent * 2);

                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"{spaces}{eventType} File {normPath} (PID={pid})");
                Console.ResetColor();
            }
        }

        static void UpdateTagStateFromLog(int pid, string tag, string content)
        {
            var pidMap = tagStates.GetOrAdd(pid, _ => new ConcurrentDictionary<string, TagState>());
            var state = pidMap.GetOrAdd(tag, _ => new TagState());

            int startUnknown = ReStartAction.Matches(content).Count;
            if (startUnknown > 0)
                state.UnknownDepth += startUnknown;

            foreach (Match m in ReCallingWithId.Matches(content))
            {
                var id = m.Groups[2]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Add(id);
            }

            foreach (Match m in ReSuccessWithId.Matches(content))
            {
                var id = m.Groups[1]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Remove(id);
            }
            foreach (Match m in ReFailWithId.Matches(content))
            {
                var id = m.Groups[1]?.Value;
                if (!string.IsNullOrWhiteSpace(id))
                    state.ActiveIds.Remove(id);
            }

            int endGeneric = ReSuccess.Matches(content).Count + ReFail.Matches(content).Count;
            for (int i = 0; i < endGeneric; i++)
            {
                if (state.UnknownDepth > 0) state.UnknownDepth--;
                else if (state.ActiveIds.Count > 0)
                {
                    var any = state.ActiveIds.First();
                    state.ActiveIds.Remove(any);
                }
            }

            // === 추가된 부분: 성공/실패 시 태그 완전 종료 ===
            if (ReSuccess.IsMatch(content) || ReFail.IsMatch(content))
            {
                state.ActiveIds.Clear();
                state.UnknownDepth = 0;
                if (activeRemoteByPidTag.TryGetValue(pid, out var tagMap))
                {
                    tagMap.TryRemove(tag, out _);
                }
            }

            if (state.EffectiveDepth <= 0)
            {
                if (activeRemoteByPidTag.TryGetValue(pid, out var tagMap))
                {
                    tagMap.TryRemove(tag, out _);
                }
            }
        }

        static void HandleNetworkEvent(string eventType, int pid, dynamic data)
        {
            if (!IsChildOfTarget(pid)) return;

            lock (mcpPids)
            {
                if (!mcpPids.Contains(pid)) return;
            }

            string saddr = "", daddr = "";
            int sport = -1, dport = -1, size = -1;

            try
            {
                saddr = data.saddr?.ToString() ?? "";
                daddr = data.daddr?.ToString() ?? "";
                sport = Convert.ToInt32(data.sport);
                dport = Convert.ToInt32(data.dport);
                size = Convert.ToInt32(data.size);
            }
            catch { }

            if (string.IsNullOrEmpty(daddr) || dport <= 0) return;
            string dest = $"{daddr}:{dport}";

            if (!tagStates.TryGetValue(pid, out var pidTagMap) || pidTagMap.Count == 0) return;

            var activeTags = pidTagMap.Where(kv => kv.Value.EffectiveDepth > 0)
                                      .Select(kv => kv.Key)
                                      .ToList();
            if (activeTags.Count == 0) return;

            string chosenTag = null;

            if (activeRemoteByPidTag.TryGetValue(pid, out var remoteMap))
            {
                foreach (var t in activeTags)
                {
                    if (remoteMap.TryGetValue(t, out var bound) && string.Equals(bound, dest, StringComparison.OrdinalIgnoreCase))
                    {
                        chosenTag = t;
                        break;
                    }
                }
            }

            if (chosenTag == null)
            {
                if (activeTags.Count == 1)
                {
                    chosenTag = activeTags[0];
                    var map = activeRemoteByPidTag.GetOrAdd(pid, _ => new ConcurrentDictionary<string, string>());
                    map[chosenTag] = dest;
                }
                else
                {
                    return;
                }
            }

            if (!pidTagMap.TryGetValue(chosenTag, out var state) || state.EffectiveDepth <= 0)
                return;

            var tagRemoteMap = activeRemoteByPidTag.GetOrAdd(pid, _ => new ConcurrentDictionary<string, string>());
            if (tagRemoteMap.TryGetValue(chosenTag, out var boundDest))
            {
                if (!string.Equals(boundDest, dest, StringComparison.OrdinalIgnoreCase))
                {
                    return;
                }
            }
            else
            {
                tagRemoteMap[chosenTag] = dest;
            }

            pidConnections[pid] = dest;

            int indent = GetIndentLevel(pid);
            string spaces = new string(' ', indent * 2);

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"{spaces}{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size} [tag={chosenTag}]");
            Console.ResetColor();

            LogLine($"{eventType} PID={pid} {saddr}:{sport} -> {daddr}:{dport}, Size={size} [tag={chosenTag}]");
        }

        static void PrintProcessEvent(string type, ProcessInfo info, string typeLabel, ConsoleColor color)
        {
            int indent = GetIndentLevel(info.Pid);
            string spaces = new string(' ', indent * 2);

            Console.ForegroundColor = color;
            Console.WriteLine($"{spaces}{type} {info.Name} (PID={info.Pid}, PPID={info.ParentPid}, Type={typeLabel})");
            Console.ResetColor();

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine($"{spaces}   Cmd: {info.CmdLine}");
            Console.ResetColor();
        }

        static string InferType(string imageName, string cmd)
        {
            string lowerCmd = (cmd ?? "").ToLowerInvariant();
            string lowerName = Path.GetFileName(imageName ?? "").ToLowerInvariant();

            if (lowerName == "cmd.exe") return "cmd";
            if (lowerName == "conhost.exe") return "conhost";
            if (lowerName == "reg.exe") return "reg";
            if (lowerName == "git.exe") return "git";

            if (lowerCmd.Contains("--type=renderer")) return "renderer";
            if (lowerCmd.Contains("--type=gpu")) return "gpu";
            if (lowerCmd.Contains("crashpad")) return "crashpad";
            if (lowerCmd.Contains("network")) return "network";
            if (lowerCmd.Contains("node")) return "node";
            if (lowerCmd.Contains("--type=utility")) return "utility";
            if (lowerCmd.Contains("--type=zygote")) return "zygote";

            if (lowerCmd.Contains("--type="))
            {
                int idx = lowerCmd.IndexOf("--type=");
                int start = idx + 7;
                int end = lowerCmd.IndexOf(' ', start);
                if (end == -1) end = lowerCmd.Length;
                try
                {
                    string t = lowerCmd.Substring(start, end - start).Trim();
                    if (!string.IsNullOrEmpty(t) && t != "main")
                        return t;
                }
                catch { }
            }
            return null;
        }

        static bool IsPathExcluded(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) return false;
            foreach (var prefix in excludePrefixes)
                if (path.IndexOf(prefix, StringComparison.OrdinalIgnoreCase) >= 0)
                    return true;
            return false;
        }

        static ulong? TryGetULong(TraceEvent e, string name)
        {
            if (e.PayloadNames == null) return null;
            if (!e.PayloadNames.Any(n => string.Equals(n, name, StringComparison.OrdinalIgnoreCase)))
                return null;
            try
            {
                var v = e.PayloadByName(name);
                return v switch
                {
                    ulong ul => ul,
                    long l => unchecked((ulong)l),
                    uint u => u,
                    int i => unchecked((ulong)i),
                    _ => null
                };
            }
            catch { return null; }
        }

        static int GetIndentLevel(int pid)
        {
            int depth = 0;
            while (processMap.ContainsKey(pid))
            {
                int parent = processMap[pid].ParentPid;
                if (!processMap.ContainsKey(parent)) break;
                pid = parent;
                depth++;
            }
            return depth;
        }
    }
}

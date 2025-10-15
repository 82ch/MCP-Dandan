using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.IO;

namespace ETW
{
    public static class ProcessEventRegistrar
    {
        public static void Register(TraceEventSource source)
        {
            // -------------------------------
            // 프로세스 이벤트
            // -------------------------------
            source.Kernel.ProcessStart += ev =>
            {
                // 커맨드라인 복원 (ETW → WMI)
                string cmdline = RecoverCmdline(ev.ProcessID, ev.CommandLine);

                if (ev.ImageFileName != null &&
                    ev.ImageFileName.EndsWith(ProcessTracker.TargetProcName, StringComparison.OrdinalIgnoreCase))
                {
                    // Claude 메인 프로세스
                    ProcessTracker.RootPid = ev.ProcessID;
                    ProcessTracker.TrackedPids[ev.ProcessID] = ev.ImageFileName;

                    var rawTag = McpHelper.TagFromCommandLine(cmdline);
                    var canonical = McpHelper.CanonicalizeMcpTag(rawTag, ev.ImageFileName, cmdline);
                    ProcessTracker.ProcCmdline[ev.ProcessID] = canonical;

                    ProcessTracker.LastResolvedHostByPid[ev.ProcessID] = cmdline;

                    string runtime = ProcessHelper.GuessRuntime(ev.ImageFileName, cmdline);

                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.Out.WriteLine($"[PROC START] PID={ev.ProcessID} Runtime={runtime} {ev.ImageFileName} CMD={cmdline}");
                    Console.ResetColor();

                    // JSON 출력 
                    Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Process", cmdline));

                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.Out.WriteLine("    ├─ Image=" + ShortPath(ev.ImageFileName));
                    PrintWrapped("    └─ CMD", cmdline);
                    Console.ResetColor();
                }
                else if (ProcessTracker.RootPid > 0 && ProcessTracker.TrackedPids.ContainsKey(ev.ParentID))
                {
                    // Claude 자손 프로세스
                    ProcessTracker.TrackedPids[ev.ProcessID] = ev.ImageFileName;

                    var rawTag = McpHelper.TagFromCommandLine(cmdline);
                    var canonical = McpHelper.CanonicalizeMcpTag(rawTag, ev.ImageFileName, cmdline);
                    ProcessTracker.ProcCmdline[ev.ProcessID] = canonical;

                    ProcessTracker.LastResolvedHostByPid[ev.ProcessID] = cmdline;

                    string runtime = ProcessHelper.GuessRuntime(ev.ImageFileName, cmdline);

                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.Out.WriteLine($"[MCP CHILD] PID={ev.ProcessID} Parent={ev.ParentID} Runtime={runtime} {ev.ImageFileName} CMD={cmdline}");
                    Console.ResetColor();

                    // JSON 출력 
                    Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Process", cmdline));

                    string mcpName = McpHelper.ExtractMcpFromCmd(cmdline);

                    if (string.IsNullOrEmpty(mcpName))
                    {
                        if (cmdline.IndexOf("node.mojom.NodeService", StringComparison.OrdinalIgnoreCase) >= 0 &&
                            cmdline.IndexOf("anthropic.filesystem", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            mcpName = "Filesystem";
                        }
                    }

                    if (!string.IsNullOrEmpty(mcpName))
                    {
                        Console.ForegroundColor = ConsoleColor.Magenta;
                        Console.Out.WriteLine($"[MCP MAP] PID={ev.ProcessID} Name={mcpName}");
                        Console.ResetColor();

                        ProcessTracker.ProcCmdline[ev.ProcessID] = mcpName;
                    }

                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.Out.WriteLine("    ├─ Image=" + ShortPath(ev.ImageFileName));
                    PrintWrapped("    └─ CMD", cmdline);
                    Console.ResetColor();

                    ProcessInspector.DumpProcessDetails(ev.ProcessID, "child-start");
                }
            };

            source.Kernel.ProcessStop += ev =>
            {
                if (ProcessTracker.TrackedPids.TryRemove(ev.ProcessID, out _))
                {
                    ProcessTracker.ProcCmdline.TryRemove(ev.ProcessID, out _);
                    ProcessTracker.LastResolvedHostByPid.TryRemove(ev.ProcessID, out var lastCmd);

                    if (ev.ProcessID == ProcessTracker.RootPid)
                        ProcessTracker.RootPid = -1;

                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.Out.WriteLine($"[PROC STOP] PID={ev.ProcessID}");
                    Console.ResetColor();

                    // JSON 출력
                    Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Process", lastCmd));

                    string mcpName = McpHelper.ExtractMcpFromCmd(lastCmd);
                    if (!string.IsNullOrEmpty(mcpName))
                    {
                        Console.ForegroundColor = ConsoleColor.Magenta;
                        Console.Out.WriteLine($"[MCP MAP] PID={ev.ProcessID} Name={mcpName} (stopped)");
                        Console.ResetColor();
                    }

                    if (!string.IsNullOrEmpty(lastCmd))
                    {
                        Console.ForegroundColor = ConsoleColor.Yellow;
                        PrintWrapped("    └─ LastCMD", lastCmd);
                        Console.ResetColor();
                    }
                }
            };

            // -------------------------------
            // 파일 I/O 이벤트
            // -------------------------------
            source.Kernel.FileIOFileCreate += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("CREATE", ev.ProcessID, ev.FileName, ev.FileKey); };
            source.Kernel.FileIOWrite += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("WRITE", ev.ProcessID, ev.FileName, ev.FileKey); };
            source.Kernel.FileIOFileDelete += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("DELETE", ev.ProcessID, ev.FileName, ev.FileKey); };
            source.Kernel.FileIORead += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                FileEventHandler.LogEvent("READ", ev.ProcessID, ev.FileName, ev.FileKey);
            };
            source.Kernel.FileIODirEnum += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("DIRENUM", ev.ProcessID, ev.FileName, ev.FileKey); };
            source.Kernel.FileIORename += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("RENAME", ev.ProcessID, ev.FileName, ev.FileKey); };
            source.Kernel.FileIOClose += ev => { if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) FileEventHandler.LogEvent("CLOSE", ev.ProcessID, ev.FileName, ev.FileKey); };

            // -------------------------------
            // 네트워크 이벤트
            // -------------------------------
            source.Kernel.TcpIpConnect += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;

                string mcp = ProcessTracker.ProcCmdline.TryGetValue(ev.ProcessID, out var m) ? m : "";
                string img = ProcessTracker.TrackedPids.TryGetValue(ev.ProcessID, out var imgPath) ? imgPath : "";

                Console.ForegroundColor = ConsoleColor.Green;
                Console.Out.WriteLine($"[NET-CONNECT] PID={ev.ProcessID} MCP={mcp} -> {ev.daddr}:{ev.dport}");
                Console.ResetColor();

                Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Network", m));

                Console.ForegroundColor = ConsoleColor.Green;
                Console.Out.WriteLine($"    ├─ Image={ShortPath(img)}");
                if (!string.IsNullOrEmpty(ev.saddr?.ToString()))
                    Console.Out.WriteLine($"    ├─ Src={ev.saddr}");
                Console.Out.WriteLine($"    └─ Dst={ev.daddr}:{ev.dport}");
                Console.ResetColor();
            };

            source.Kernel.TcpIpSend += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Network", null));
            };

            source.Kernel.TcpIpRecv += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                Console.WriteLine(EventDataFormatter.ToStandardJson(ev, "Network", null));
            };

            // -------------------------------
            // Local Mcp Server IPC 이벤트
            // -------------------------------
            if (source is ETWTraceEventSource etwSource)
            {
                var parser = new DynamicTraceEventParser(etwSource);
                parser.All += data =>
                {
                    if (data.ProviderGuid == new Guid("7d38387a-bf0b-4dcf-8d8e-b8558542d874"))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkGreen;
                        Console.WriteLine($"[Local Mcp Server Ipc] {data.ProviderName}.{data.EventName}");

                        foreach (var name in data.PayloadNames)
                        {
                            object value = data.PayloadByName(name);
                            if (name == "data" && value is byte[] bytes)
                            {
                                string decoded = System.Text.Encoding.UTF8.GetString(bytes);
                                Console.WriteLine($"    ├─ {name}  = {decoded}");
                            }
                            else
                            {
                                Console.WriteLine($"    ├─ {name} = {value}");
                            }
                        }
                        Console.ResetColor();

                        Console.WriteLine(EventDataFormatter.ToStandardJson(data, "MCP", null));
                    }
                };
            }
        }

        // -------------------------------
        // Helper methods
        // -------------------------------
        static string RecoverCmdline(int pid, string etwCmdline)
        {
            // ETW에서 온 값이 정상적이면 그대로 사용
            if (!string.IsNullOrWhiteSpace(etwCmdline) && etwCmdline.Length > 10)
                return etwCmdline;

            // 짤렸거나 null일 때 WMI로 복원
            var wmi = ProcessHelper.TryGetCommandLineForPid(pid);
            if (!string.IsNullOrWhiteSpace(wmi))
                return wmi;

            // 그래도 없으면 빈 문자열 반환
            return string.Empty;
        }

        static string ShortPath(string path) =>
            string.IsNullOrEmpty(path) ? "" : Path.GetFileName(path);

        static void PrintWrapped(string key, string text, int maxWidth = 120)
        {
            if (text == null) text = "";
            var label = $"{key}=";
            if (label.Length + text.Length <= maxWidth)
            {
                Console.Out.WriteLine($"{label}{text}");
                return;
            }
            int remain = text.Length, idx = 0;
            int firstCap = Math.Max(0, maxWidth - label.Length);
            Console.Out.WriteLine($"{label}{text.Substring(0, Math.Min(firstCap, remain))}");
            idx += firstCap; remain -= firstCap;
            string indent = new string(' ', key.Length + 1);
            while (remain > 0)
            {
                int take = Math.Min(maxWidth - indent.Length, remain);
                Console.Out.WriteLine($"{indent}{text.Substring(idx, take)}");
                idx += take; remain -= take;
            }
        }
    }
}

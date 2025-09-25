using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;

namespace CursorProcessTree
{
    public static class FileEventHandler
    {
        public static void HandleCreateEvent(FileIOCreateTraceData data)
        {
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
        }

        // ⬇️ 여기만 수정됨
        public static void HandleRenameEvent(TraceEvent data)
        {
            if (!ProcessTracker.IsChildOfTarget(data.ProcessID)) return;

            var fk = ProcessTracker.TryGetULong(data, "FileKey") ?? 0UL;
            string newPath = data.PayloadByName("FileName")?.ToString();
            string oldPath = null;

            if (fk != 0 && ProcessTracker.fileKeyPath.TryGetValue(fk, out var prev))
                oldPath = prev;

            if (string.Equals(newPath, ProcessTracker.logPath, StringComparison.OrdinalIgnoreCase) ||
                string.Equals(oldPath, ProcessTracker.logPath, StringComparison.OrdinalIgnoreCase))
                return;

            if (ProcessTracker.IsPathExcluded(oldPath) || ProcessTracker.IsPathExcluded(newPath)) return;

            int indent = ProcessTracker.GetIndentLevel(data.ProcessID);
            string spaces = new string(' ', indent * 2);

            Console.ForegroundColor = ConsoleColor.Yellow;
            if (!string.IsNullOrEmpty(oldPath))
                Console.WriteLine($"{spaces}[RENAME] {oldPath} -> {newPath} (PID={data.ProcessID})");
            else
                Console.WriteLine($"{spaces}[RENAME] (unknown_old) -> {newPath} (PID={data.ProcessID})");
            Console.ResetColor();

            ProcessTracker.LogLine($"[RENAME] PID={data.ProcessID}, {oldPath} -> {newPath}");

            if (fk != 0) ProcessTracker.fileKeyPath[fk] = newPath;
        }

        public static void HandleFileEvent(string eventType, int pid, string path)
        {
            if (!ProcessTracker.IsChildOfTarget(pid)) return;
            if (!TryNormalizePath(path, out var normPath, out var fileName)) return;

            if (string.Equals(normPath, ProcessTracker.logPath, StringComparison.OrdinalIgnoreCase))
                return;

            bool isMcpLog = fileName.EndsWith(".log", StringComparison.OrdinalIgnoreCase) &&
                            fileName.IndexOf("MCP", StringComparison.OrdinalIgnoreCase) >= 0;

            if (!isMcpLog && ProcessTracker.IsPathExcluded(normPath)) return;

            if (eventType == "[WRITE]" && isMcpLog)
            {
                lock (ProcessTracker.mcpPids) ProcessTracker.mcpPids.Add(pid);

                try
                {
                    long lastOffset = ProcessTracker.fileOffsets.GetOrAdd(normPath, 0);
                    using (var fs = new FileStream(normPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    {
                        fs.Seek(lastOffset, SeekOrigin.Begin);
                        using (var reader = new StreamReader(fs))
                        {
                            string newContent = reader.ReadToEnd();
                            if (!string.IsNullOrWhiteSpace(newContent))
                            {
                                string tag = ExtractServerTag(normPath);
                                McpTagManager.UpdateTagStateFromLog(pid, tag, newContent);

                                ProcessTracker.pidConnections.TryGetValue(pid, out var connInfo);

                                Console.ForegroundColor = ConsoleColor.Magenta;
                                Console.WriteLine($"[LOG CONTENT] {normPath} (PID={pid}{(connInfo != null ? $", Remote={connInfo}" : "")})");
                                Console.ResetColor();
                                Console.WriteLine(newContent);

                                ProcessTracker.LogLine($"[LOG CONTENT] {normPath} (PID={pid}{(connInfo != null ? $", Remote={connInfo}" : "")})\n{newContent}");
                            }
                        }
                        ProcessTracker.fileOffsets[normPath] = fs.Length;
                    }
                }
                catch (Exception ex)
                {
                    ProcessTracker.LogLine($"[ERROR] Failed to read {normPath}: {ex.Message}");
                }
            }

            ProcessTracker.LogLine($"{eventType} File {normPath} (PID={pid})");

            if (eventType == "[WRITE]" || eventType == "[DELETE]" || eventType.StartsWith("[RENAME]"))
            {
                int indent = ProcessTracker.GetIndentLevel(pid);
                string spaces = new string(' ', indent * 2);

                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine($"{spaces}{eventType} File {normPath} (PID={pid})");
                Console.ResetColor();
            }
        }

        public static bool TryNormalizePath(string path, out string normPath, out string fileName)
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

        public static string ExtractServerTag(string normPath)
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
    }
}

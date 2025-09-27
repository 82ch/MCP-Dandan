using System;
using System.IO;
using System.Threading;

namespace ETW
{
    public static class LogWatcher
    {
        public static readonly string ClaudeLogsDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData) ?? "",
            "Claude", "logs");

        public static void InitializeLogOffsets()
        {
            try
            {
                if (!Directory.Exists(ClaudeLogsDir)) return;
                foreach (var f in Directory.GetFiles(ClaudeLogsDir, "*.*"))
                {
                    ProcessTracker.LogFileOffsets[f] = new FileInfo(f).Length;
                }
            }
            catch { }
        }

        public static void TryStartLogDirectoryWatcher()
        {
            if (!Directory.Exists(ClaudeLogsDir)) return;

            var fsw = new FileSystemWatcher(ClaudeLogsDir)
            {
                NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.Size | NotifyFilters.FileName,
                IncludeSubdirectories = false,
                EnableRaisingEvents = true
            };

            fsw.Changed += (s, e) => TailLogFileSafe(e.FullPath);
            fsw.Created += (s, e) => { ProcessTracker.LogFileOffsets[e.FullPath] = 0; TailLogFileSafe(e.FullPath); };
            fsw.Renamed += (s, e) =>
            {
                ProcessTracker.LogFileOffsets.TryRemove(e.OldFullPath, out _);
                ProcessTracker.LogFileOffsets[e.FullPath] = 0;
                TailLogFileSafe(e.FullPath);
            };
            fsw.Deleted += (s, e) => ProcessTracker.LogFileOffsets.TryRemove(e.FullPath, out _);

            Console.ForegroundColor = ConsoleColor.Magenta;
            Console.WriteLine($"[+] Started watching Claude log files in: {ClaudeLogsDir}");
            Console.ResetColor();
        }

        private static void TailLogFileSafe(string fullPath)
        {
            ThreadPool.QueueUserWorkItem(_ =>
            {
                try
                {
                    if (!File.Exists(fullPath)) return;
                    using var fs = new FileStream(fullPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                    long len = fs.Length;
                    if (len == 0) return;

                    fs.Seek(Math.Max(0, len - 1024), SeekOrigin.Begin); // 마지막 1KB만 출력
                    using var sr = new StreamReader(fs);
                    string appended = sr.ReadToEnd();

                    if (!string.IsNullOrEmpty(appended))
                    {
                        Console.ForegroundColor = ConsoleColor.DarkGray;
                        Console.WriteLine($"[LOG TAIL] {Path.GetFileName(fullPath)}");
                        Console.ResetColor();
                        Console.WriteLine(appended.TrimEnd('\r', '\n'));
                    }
                }
                catch { }
            });
        }

        public static bool IsClaudeLogFile(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) return false;
            try
            {
                string dir = Path.GetDirectoryName(path) ?? "";
                if (!dir.Equals(ClaudeLogsDir, StringComparison.OrdinalIgnoreCase)) return false;
                string lower = Path.GetFileName(path).ToLowerInvariant();
                return lower.EndsWith(".log") || lower.Contains("mcp") || lower.Contains("server") || lower.EndsWith(".tmp") || lower.Contains("network");
            }
            catch { }
            return false;
        }
    }
}

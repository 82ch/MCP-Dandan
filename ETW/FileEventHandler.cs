using System;
using System.IO;
using System.Text;
using System.Threading;

namespace ETW
{
    public static class FileEventHandler
    {
        private const int MAX_READ_BYTES = 64 * 1024;

        public static void LogEvent(string kind, int pid, string path, ulong fileKey = 0)
        {
            if (string.IsNullOrWhiteSpace(path)) return;

            path = SanitizePath(path);

            // --- 통합 필터 적용 ---
            int repeatCount;
            if (EtwFilters.ShouldIgnore(kind, pid, path, out repeatCount))
                return;

            string ext = string.Empty;
            try { ext = Path.GetExtension(path)?.ToLowerInvariant(); }
            catch { ext = string.Empty; }

            // MCP 확인
            string mcpName = "";
            if (ProcessTracker.ProcCmdline.TryGetValue(pid, out var tag))
            {
                if (!string.IsNullOrEmpty(tag) &&
                    tag.IndexOf("claude.exe", StringComparison.OrdinalIgnoreCase) < 0 &&
                    tag.IndexOf(@"\AnthropicClaude\", StringComparison.OrdinalIgnoreCase) < 0)
                {
                    mcpName = tag;
                }
            }

            if (string.IsNullOrEmpty(mcpName) &&
                path.IndexOf("anthropic.filesystem", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                mcpName = "Filesystem";
                ProcessTracker.ProcCmdline[pid] = mcpName;
            }

            // 색상 선택
            ConsoleColor color;
            if (!string.IsNullOrEmpty(mcpName))
                color = ConsoleColor.Magenta;
            else
            {
                switch (kind.ToUpperInvariant())
                {
                    case "CREATE": color = ConsoleColor.Cyan; break;
                    case "WRITE": color = ConsoleColor.Cyan; break;
                    case "READ": color = ConsoleColor.Green; break;
                    case "DIRENUM":
                    case "RENAME": color = ConsoleColor.DarkYellow; break;
                    case "DELETE": color = ConsoleColor.Red; break;
                    case "CLOSE": color = ConsoleColor.DarkGray; break;
                    default: color = ConsoleColor.Gray; break;
                }
            }

            // 출력
            Console.ForegroundColor = color;
            Console.Write($"[{DateTime.Now:HH:mm:ss.fff}] [{kind}] PID={pid} PATH={path}");
            if (repeatCount > 0)
                Console.Write($" (x{repeatCount})");
            Console.WriteLine();
            if (!string.IsNullOrEmpty(mcpName))
                Console.WriteLine($"   └─ [MCP] {mcpName}");
            Console.ResetColor();

            // data_* 파일 요약
            string fileName = Path.GetFileName(path).ToLowerInvariant();
            if (fileName.StartsWith("data_"))
                return;

            // 파일 내용 덤프
            if ((kind.Equals("WRITE", StringComparison.OrdinalIgnoreCase) ||
                 kind.Equals("READ", StringComparison.OrdinalIgnoreCase)) &&
                ShouldDumpContents(ext))
            {
                ThreadPool.QueueUserWorkItem(_ => TryReadFileContents(path));
            }
        }

        private static bool ShouldDumpContents(string ext)
        {
            if (string.IsNullOrEmpty(ext)) return false;
            if (ext == ".log" || ext == ".json") return false;
            if (ext == ".tmp") return true;
            return false;
        }

        private static string SanitizePath(string path)
        {
            if (string.IsNullOrEmpty(path)) return path;
            var sb = new StringBuilder(path.Length);
            foreach (char c in path)
            {
                if (!char.IsControl(c))
                    sb.Append(c);
            }
            string cleaned = sb.ToString();
            foreach (var bad in Path.GetInvalidPathChars())
                cleaned = cleaned.Replace(bad, '?');
            return cleaned;
        }

        private static void TryReadFileContents(string path)
        {
            try
            {
                if (!File.Exists(path)) return;
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                long fileLen = fs.Length;
                if (fileLen == 0) return;

                long toReadFrom = Math.Max(0, fileLen - MAX_READ_BYTES);
                fs.Seek(toReadFrom, SeekOrigin.Begin);

                byte[] buf = new byte[fileLen - toReadFrom];
                int read = fs.Read(buf, 0, buf.Length);

                Console.ForegroundColor = ConsoleColor.DarkGray;
                Console.WriteLine($"[FILE READ] {Path.GetFileName(path)} +{read} bytes:");
                Console.ResetColor();

                string text = Encoding.UTF8.GetString(buf, 0, read);
                Console.WriteLine(text.TrimEnd('\r', '\n'));
            }
            catch
            {
                // 무시
            }
        }
    }
}

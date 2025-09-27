using System;
using System.IO;
using System.Text;
using System.Threading;

namespace ETW
{
    public static class FileEventHandler
    {
        private static readonly string[] IgnorePathPatterns = new[]
        {
            @"\cache\cache_data\",
            @"\gpucache\",
            @"\code cache\"
        };

        private const int MAX_READ_BYTES = 64 * 1024;

        public static void LogEvent(string kind, int pid, string path, ulong fileKey = 0)
        {
            if (string.IsNullOrWhiteSpace(path)) return;

            // 무시 패턴 필터링
            foreach (var ignore in IgnorePathPatterns)
                if (path.ToLowerInvariant().Contains(ignore)) return;

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {kind} PID={pid} PATH={path}");
            Console.ResetColor();

            // Claude 자식 프로세스가 Downloads 같은 경로에 파일을 쓸 때도 출력됨
            if (kind.Equals("WRITE", StringComparison.OrdinalIgnoreCase))
            {
                if (path.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase) || path.EndsWith(".json", StringComparison.OrdinalIgnoreCase))
                    ThreadPool.QueueUserWorkItem(_ => TryReadFileContents(path));
            }
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
            catch { }
        }
    }
}

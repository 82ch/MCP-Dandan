using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace MCPProxy
{
    public class Program
    {
        private static TcpClient? collectorClient;
        private static StreamWriter? collectorWriter;
        private static Process? targetProcess;

        public static void Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;

            // 디버깅: 시작 메시지
            File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                $"[{DateTime.Now:HH:mm:ss}] MCPProxy started, PID={Process.GetCurrentProcess().Id}\n");

            InitCollector();
            StartProxy(args);
        }

        /// <summary>
        /// Collector TCP 연결
        /// </summary>
        private static void InitCollector()
        {
            try
            {
                File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                    $"[{DateTime.Now:HH:mm:ss}] Attempting to connect to 127.0.0.1:8888...\n");

                collectorClient = new TcpClient();
                collectorClient.Connect("127.0.0.1", 8888);

                var stream = collectorClient.GetStream();
                collectorWriter = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };

                File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                    $"[{DateTime.Now:HH:mm:ss}] Successfully connected to Collector!\n");
            }
            catch (Exception ex)
            {
                File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                    $"[{DateTime.Now:HH:mm:ss}] Failed to connect: {ex.GetType().Name}: {ex.Message}\n");

                collectorWriter = null;
            }
        }

        /// <summary>
        /// 실제 MCP 서버 실행 및 STDIO 중계
        /// </summary>
        private static void StartProxy(string[] args)
        {
            string command = args[0];
            string arguments = args.Length > 1 ? string.Join(" ", args.Skip(1)) : "";

            var startInfo = new ProcessStartInfo
            {
                FileName = command,
                Arguments = arguments,
                RedirectStandardInput = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            targetProcess = new Process { StartInfo = startInfo };
            targetProcess.Start();

            File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                $"[{DateTime.Now:HH:mm:ss}] Started target process: PID={targetProcess.Id}, Command={command}\n");

            // STDIO 중계 스레드
            new Thread(ForwardStdin) { IsBackground = true }.Start();
            new Thread(ForwardStdout) { IsBackground = true }.Start();
            new Thread(ForwardStderr) { IsBackground = true }.Start();

            targetProcess.WaitForExit();
            SendToCollector("proxy_exit", $"Process exited with code {targetProcess.ExitCode}");
        }

        /// <summary>
        /// Claude → Proxy → Target stdin
        /// </summary>
        private static void ForwardStdin()
        {
            using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8);
            using var writer = targetProcess!.StandardInput;
            string? line;
            while ((line = reader.ReadLine()) != null)
            {
                writer.WriteLine(line);
                writer.Flush();
                SendToCollector("client_to_server", line);
            }
        }

        /// <summary>
        /// Target stdout → Proxy → Claude
        /// </summary>
        private static void ForwardStdout()
        {
            using var reader = targetProcess!.StandardOutput;
            string? line;
            while ((line = reader.ReadLine()) != null)
            {
                Console.WriteLine(line);
                SendToCollector("server_to_client", line);
            }
        }

        /// <summary>
        /// Target stderr → Proxy stderr + Collector
        /// </summary>
        private static void ForwardStderr()
        {
            using var reader = targetProcess!.StandardError;
            string? line;
            while ((line = reader.ReadLine()) != null)
            {
                Console.Error.WriteLine(line);
                SendToCollector("server_stderr", line);
            }
        }

        /// <summary>
        /// Collector로 로그 전송
        /// </summary>
        private static void SendToCollector(string type, string message)
        {
            try
            {
                if (collectorWriter == null)
                {
                    return;
                }

                var json = JsonSerializer.Serialize(new
                {
                    timestamp = DateTime.UtcNow.ToString("o"),
                    source = "proxy",
                    type,
                    data = new
                    {
                        pid = targetProcess?.Id ?? 0,
                        message
                    }
                });

                // 길이 헤더 추가
                collectorWriter.WriteLine($"{json.Length}");
                collectorWriter.WriteLine(json);
            }
            catch (Exception ex)
            {
                File.AppendAllText("C:\\Users\\ey896\\mcpproxy_debug.log",
                    $"[{DateTime.Now:HH:mm:ss}] Send error: {ex.Message}\n");

                collectorWriter = null;
            }
        }
    }
}
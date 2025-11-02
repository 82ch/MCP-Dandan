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
        private static readonly object _collectorLock = new object();
        private static bool collectorAvailable = false;

        public static void Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;

            // Collector 연결 시도 (비동기, 실패해도 계속 진행)
            TryInitCollector();

            // MCP 서버는 무조건 시작
            StartProxy(args);
        }

        /// <summary>
        /// Collector TCP 연결 시도 (실패해도 프로그램 계속 진행)
        /// </summary>
        private static void TryInitCollector()
        {
            try
            {
                Console.Error.WriteLine($"[MCPProxy PID={Process.GetCurrentProcess().Id}] Attempting to connect to Collector...");

                collectorClient = new TcpClient();
                // 짧은 타임아웃으로 빠르게 시도
                var result = collectorClient.BeginConnect("127.0.0.1", 8888, null, null);
                var success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(500));

                if (success)
                {
                    collectorClient.EndConnect(result);
                    var stream = collectorClient.GetStream();
                    collectorWriter = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };
                    collectorAvailable = true;
                    Console.Error.WriteLine($"[MCPProxy PID={Process.GetCurrentProcess().Id}] Connected to Collector ✓");
                }
                else
                {
                    collectorClient.Close();
                    collectorAvailable = false;
                    Console.Error.WriteLine($"[MCPProxy] Collector not available (timeout) - continuing without logging");
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[MCPProxy] Collector connection failed: {ex.Message} - continuing without logging");
                collectorAvailable = false;
                collectorWriter = null;
            }
        }

        /// <summary>
        /// Collector 연결 확인 및 재연결 (실패해도 false 반환하고 계속)
        /// </summary>
        private static bool EnsureCollectorConnection()
        {
            lock (_collectorLock)
            {
                // 이미 연결되어 있으면 OK
                if (collectorAvailable && collectorClient?.Connected == true && collectorWriter != null)
                    return true;

                // 한 번 실패했으면 더 이상 시도하지 않음 (오버헤드 방지)
                if (!collectorAvailable)
                    return false;

                // 재연결 시도 (한 번만)
                try
                {
                    collectorClient?.Close();
                    collectorClient = new TcpClient();

                    var result = collectorClient.BeginConnect("127.0.0.1", 8888, null, null);
                    var success = result.AsyncWaitHandle.WaitOne(TimeSpan.FromMilliseconds(200));

                    if (success)
                    {
                        collectorClient.EndConnect(result);
                        var stream = collectorClient.GetStream();
                        collectorWriter = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };
                        Console.Error.WriteLine($"[MCPProxy PID={Process.GetCurrentProcess().Id}] Reconnected to Collector");
                        return true;
                    }
                    else
                    {
                        collectorClient.Close();
                        collectorAvailable = false;
                        collectorWriter = null;
                        return false;
                    }
                }
                catch
                {
                    collectorAvailable = false;
                    collectorWriter = null;
                    return false;
                }
            }
        }

        /// <summary>
        /// 실제 MCP 서버 실행 및 STDIO 중계
        /// </summary>
        private static void StartProxy(string[] args)
        {
            if (args.Length == 0)
            {
                Console.Error.WriteLine("[MCPProxy] Error: No command specified");
                Environment.Exit(1);
                return;
            }

            string command = args[0];
            string arguments = args.Length > 1 ? string.Join(" ", args.Skip(1)) : "";

            Console.Error.WriteLine($"[MCPProxy] Starting MCP server: {command} {arguments}");

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

            try
            {
                targetProcess = new Process { StartInfo = startInfo };
                targetProcess.Start();

                Console.Error.WriteLine($"[MCPProxy] MCP server started successfully (PID: {targetProcess.Id})");

                // STDIO 중계 스레드
                new Thread(ForwardStdin) { IsBackground = true }.Start();
                new Thread(ForwardStdout) { IsBackground = true }.Start();
                new Thread(ForwardStderr) { IsBackground = true }.Start();

                targetProcess.WaitForExit();

                Console.Error.WriteLine($"[MCPProxy] MCP server exited with code {targetProcess.ExitCode}");
                SendToCollector("proxy_exit", $"Process exited with code {targetProcess.ExitCode}");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[MCPProxy] Failed to start MCP server: {ex.Message}");
                Environment.Exit(1);
            }
        }

        /// <summary>
        /// Claude → Proxy → Target stdin
        /// </summary>
        private static void ForwardStdin()
        {
            try
            {
                using var reader = new StreamReader(Console.OpenStandardInput(), Encoding.UTF8);
                using var writer = targetProcess!.StandardInput;
                string? line;
                while ((line = reader.ReadLine()) != null)
                {
                    writer.WriteLine(line);
                    writer.Flush();

                    // MCP 형식으로 전송 (SEND) - Collector 연결 여부와 무관
                    try
                    {
                        var message = JsonSerializer.Deserialize<JsonElement>(line);
                        SendMCPEvent("SEND", message);
                    }
                    catch
                    {
                        // JSON이 아니면 무시
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[MCPProxy] ForwardStdin error: {ex.Message}");
            }
        }

        /// <summary>
        /// Target stdout → Proxy → Claude
        /// </summary>
        private static void ForwardStdout()
        {
            try
            {
                using var reader = targetProcess!.StandardOutput;
                string? line;
                while ((line = reader.ReadLine()) != null)
                {
                    Console.WriteLine(line);

                    // MCP 형식으로 전송 (RECV) - Collector 연결 여부와 무관
                    try
                    {
                        var message = JsonSerializer.Deserialize<JsonElement>(line);
                        SendMCPEvent("RECV", message);
                    }
                    catch
                    {
                        // JSON이 아니면 무시
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[MCPProxy] ForwardStdout error: {ex.Message}");
            }
        }

        /// <summary>
        /// Target stderr → Proxy stderr + Collector
        /// </summary>
        private static void ForwardStderr()
        {
            try
            {
                using var reader = targetProcess!.StandardError;
                string? line;
                while ((line = reader.ReadLine()) != null)
                {
                    Console.Error.WriteLine(line);
                    SendToCollector("server_stderr", line);
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[MCPProxy] ForwardStderr error: {ex.Message}");
            }
        }

        /// <summary>
        /// MCP 이벤트를 명세서 형식으로 Collector에 전송 (연결 실패 시 무시)
        /// </summary>
        private static void SendMCPEvent(string task, JsonElement message)
        {
            try
            {
                if (targetProcess == null) return;

                // 연결 확인 (실패해도 계속 진행)
                if (!EnsureCollectorConnection()) return;

                // 명세서에 맞는 형식
                var envelope = new
                {
                    ts = (DateTimeOffset.UtcNow.Ticks - DateTimeOffset.UnixEpoch.Ticks) * 100,
                    producer = "local",
                    pid = targetProcess.Id,
                    pname = targetProcess.ProcessName,
                    eventType = "MCP",
                    data = new
                    {
                        task,
                        transPort = "stdio",
                        src = task == "SEND" ? "client" : "server",
                        dst = task == "SEND" ? "server" : "client",
                        message
                    }
                };

                var json = JsonSerializer.Serialize(envelope);

                lock (_collectorLock)
                {
                    // 길이 헤더 추가
                    collectorWriter?.WriteLine($"{json.Length}");
                    collectorWriter?.WriteLine(json);
                }
            }
            catch
            {
                // Collector 전송 실패는 무시 (MCP 서버 동작에 영향 없음)
                collectorWriter = null;
                collectorAvailable = false;
            }
        }

        /// <summary>
        /// 일반 이벤트를 Collector로 전송 (연결 실패 시 무시)
        /// </summary>
        private static void SendToCollector(string type, string message)
        {
            try
            {
                // 연결 확인 (실패해도 계속 진행)
                if (!EnsureCollectorConnection()) return;

                var envelope = new
                {
                    ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1000000,
                    producer = "local",
                    pid = targetProcess?.Id ?? 0,
                    pname = targetProcess?.ProcessName ?? "unknown",
                    eventType = "ProxyLog",
                    data = new
                    {
                        type,
                        message
                    }
                };

                var json = JsonSerializer.Serialize(envelope);

                lock (_collectorLock)
                {
                    // 길이 헤더 추가
                    collectorWriter?.WriteLine($"{json.Length}");
                    collectorWriter?.WriteLine(json);
                }
            }
            catch
            {
                // Collector 전송 실패는 무시
                collectorWriter = null;
                collectorAvailable = false;
            }
        }
    }
}
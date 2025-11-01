using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;

namespace Collector
{
    class Program
    {
        private static StreamWriter? logWriter;
        private static Process? mcpTraceProcess;

        static async Task Main(string[] args)
        {
            Console.OutputEncoding = Encoding.UTF8;

            // 로그 파일 초기화
            var logDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "logs");
            Directory.CreateDirectory(logDir);
            var logFile = Path.Combine(logDir, $"events_{DateTime.Now:yyyyMMdd_HHmmss}.jsonl");
            logWriter = new StreamWriter(logFile, append: true) { AutoFlush = true };

            Console.WriteLine("=".PadRight(80, '='));
            Console.WriteLine("MCP Observer - Event Collector");
            Console.WriteLine("=".PadRight(80, '='));
            Console.WriteLine();
            Console.WriteLine($"[*] Logging to: {logFile}");
            Console.WriteLine();

            // 사용자 선택 받기
            Console.WriteLine("모니터링할 프로세스를 선택하세요:");
            Console.WriteLine("1. Claude");
            Console.WriteLine("2. Cursor");
            Console.Write("\n선택 (1 또는 2): ");

            string? choice = Console.ReadLine()?.Trim();
            // 숫자가 아닌 입력 처리
            if (choice != null && choice.Length > 0 && !char.IsDigit(choice[0]))
            {
                choice = choice.Substring(choice.Length - 1);
            }

            string targetProcess = choice == "2" ? "cursor" : "claude";

            Console.WriteLine();
            Console.WriteLine($"[+] 선택된 프로세스: {targetProcess}");
            Console.WriteLine();

            // Ctrl+C 처리
            Console.CancelKeyPress += (s, e) =>
            {
                Console.WriteLine("\n[*] Shutting down...");
                StopMCPTrace();
                e.Cancel = false;
                Environment.Exit(0);
            };

            // MCPTrace 자동 실행
            StartMCPTrace(targetProcess);

            Console.WriteLine("[*] Starting TCP server on localhost:8888...");
            Console.WriteLine("[*] Waiting for MCPTrace and MCPProxy connections...");
            Console.WriteLine();

            var listener = new TcpListener(IPAddress.Loopback, 8888);
            listener.Start();

            int connectionId = 0;

            while (true)
            {
                var client = await listener.AcceptTcpClientAsync();
                int currentId = connectionId++;

                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[Connection #{currentId}] Client connected from {client.Client.RemoteEndPoint}");
                Console.ResetColor();

                _ = Task.Run(() => HandleClient(client, currentId));
            }
        }

        static void StartMCPTrace(string targetProcess)
        {
            try
            {
                // MCPTrace.exe 경로 찾기
                string mcpTracePath = FindMCPTraceExecutable();

                if (string.IsNullOrEmpty(mcpTracePath))
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("[WARNING] MCPTrace.exe not found. Please run it manually.");
                    Console.WriteLine("[WARNING] Expected path structure: src/MCPTrace/bin/Debug|Release/net*.0/MCPTrace.exe");
                    Console.ResetColor();
                    return;
                }

                // MCPTrace 실행 (관리자 권한 필요)
                var startInfo = new ProcessStartInfo
                {
                    FileName = mcpTracePath,
                    Arguments = targetProcess, // "claude" 또는 "cursor"
                    UseShellExecute = true, // 관리자 권한 요청을 위해 필요
                    Verb = "runas", // 관리자 권한으로 실행
                    CreateNoWindow = false,
                    WindowStyle = ProcessWindowStyle.Normal
                };

                mcpTraceProcess = Process.Start(startInfo);

                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[+] MCPTrace started successfully (targeting: {targetProcess})");
                Console.WriteLine($"[+] MCPTrace path: {mcpTracePath}");
                Console.ResetColor();
                Console.WriteLine();
            }
            catch (System.ComponentModel.Win32Exception ex)
            {
                // 사용자가 UAC 프롬프트를 취소한 경우
                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.WriteLine("[WARNING] MCPTrace requires administrator privileges.");
                Console.WriteLine("Please run MCPTrace.exe manually as administrator.");
                Console.ResetColor();
                Console.WriteLine();
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[ERROR] Failed to start MCPTrace: {ex.Message}");
                Console.WriteLine("Please run MCPTrace.exe manually.");
                Console.ResetColor();
                Console.WriteLine();
            }
        }

        static string FindMCPTraceExecutable()
        {
            // 현재 실행 파일의 디렉토리 정보
            string currentDir = AppDomain.CurrentDomain.BaseDirectory;

            // 1. 같은 디렉토리에서 찾기
            string localPath = Path.Combine(currentDir, "MCPTrace.exe");
            if (File.Exists(localPath))
                return localPath;

            // 2. 현재 디렉토리의 구조 파악
            try
            {
                DirectoryInfo? currentDirInfo = new DirectoryInfo(currentDir);

                // bin 디렉토리까지 올라가기
                DirectoryInfo? binDir = null;
                DirectoryInfo? configDir = null;
                DirectoryInfo? frameworkDir = null;

                if (currentDirInfo.Parent?.Parent?.Name.Equals("bin", StringComparison.OrdinalIgnoreCase) == true)
                {
                    frameworkDir = currentDirInfo;
                    configDir = currentDirInfo.Parent;
                    binDir = currentDirInfo.Parent.Parent;
                }
                else if (currentDirInfo.Parent?.Name.Equals("bin", StringComparison.OrdinalIgnoreCase) == true)
                {
                    configDir = currentDirInfo;
                    binDir = currentDirInfo.Parent;
                }
                else if (currentDirInfo.Name.Equals("bin", StringComparison.OrdinalIgnoreCase))
                {
                    binDir = currentDirInfo;
                }

                if (binDir != null)
                {
                    DirectoryInfo? projectDir = binDir.Parent;
                    DirectoryInfo? srcDir = projectDir?.Parent;

                    if (srcDir != null && srcDir.Exists)
                    {
                        string mcpTraceProjectDir = Path.Combine(srcDir.FullName, "MCPTrace");

                        if (Directory.Exists(mcpTraceProjectDir))
                        {
                            // 같은 빌드 설정으로 찾기
                            if (configDir != null && frameworkDir != null)
                            {
                                string mcpTracePath = Path.Combine(
                                    mcpTraceProjectDir,
                                    "bin",
                                    configDir.Name,
                                    frameworkDir.Name,
                                    "MCPTrace.exe"
                                );

                                if (File.Exists(mcpTracePath))
                                    return mcpTracePath;
                            }

                            // 모든 빌드 구성 검색
                            string binPath = Path.Combine(mcpTraceProjectDir, "bin");
                            if (Directory.Exists(binPath))
                            {
                                foreach (var config in new[] { "Debug", "Release" })
                                {
                                    string configPath = Path.Combine(binPath, config);
                                    if (Directory.Exists(configPath))
                                    {
                                        foreach (var fwDir in Directory.GetDirectories(configPath))
                                        {
                                            string exePath = Path.Combine(fwDir, "MCPTrace.exe");
                                            if (File.Exists(exePath))
                                                return exePath;
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 3. 재귀적으로 상위 디렉토리 탐색
                DirectoryInfo? searchDir = new DirectoryInfo(currentDir);
                for (int i = 0; i < 5 && searchDir != null; i++)
                {
                    string srcPath = Path.Combine(searchDir.FullName, "src");
                    if (Directory.Exists(srcPath))
                    {
                        string mcpTraceDir = Path.Combine(srcPath, "MCPTrace");
                        if (Directory.Exists(mcpTraceDir))
                        {
                            string[] foundFiles = Directory.GetFiles(
                                mcpTraceDir,
                                "MCPTrace.exe",
                                SearchOption.AllDirectories
                            );

                            if (foundFiles.Length > 0)
                            {
                                return foundFiles
                                    .OrderByDescending(f => File.GetLastWriteTime(f))
                                    .First();
                            }
                        }
                    }

                    searchDir = searchDir.Parent;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Error while searching for MCPTrace.exe: {ex.Message}");
            }

            return string.Empty;
        }

        static void StopMCPTrace()
        {
            try
            {
                if (mcpTraceProcess != null && !mcpTraceProcess.HasExited)
                {
                    Console.WriteLine("[*] Stopping MCPTrace...");
                    mcpTraceProcess.Kill(true);
                    mcpTraceProcess.WaitForExit(2000);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Failed to stop MCPTrace: {ex.Message}");
            }
        }

        static async Task HandleClient(TcpClient client, int connectionId)
        {
            try
            {
                using (client)
                using (var stream = client.GetStream())
                using (var reader = new StreamReader(stream, Encoding.UTF8))
                {
                    while (true)
                    {
                        string? lengthStr = await reader.ReadLineAsync();
                        if (lengthStr == null) break;

                        if (!int.TryParse(lengthStr, out int length))
                        {
                            Console.WriteLine($"[Connection #{connectionId}] Invalid length: {lengthStr}");
                            continue;
                        }

                        char[] buffer = new char[length];
                        int totalRead = 0;
                        while (totalRead < length)
                        {
                            int read = await reader.ReadAsync(buffer, totalRead, length - totalRead);
                            if (read == 0) break;
                            totalRead += read;
                        }

                        if (totalRead == length)
                        {
                            string json = new string(buffer);
                            await reader.ReadLineAsync();
                            ProcessEvent(json, connectionId);
                        }
                    }
                }

                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[Connection #{connectionId}] Client disconnected");
                Console.ResetColor();
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[Connection #{connectionId} ERROR] {ex.Message}");
                Console.ResetColor();
            }
        }

        static void ProcessEvent(string json, int connectionId)
        {
            try
            {
                logWriter?.WriteLine(json);

                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string producer = "unknown";
                if (root.TryGetProperty("producer", out var producerElement))
                {
                    producer = producerElement.GetString() ?? "unknown";
                }

                string eventType = root.GetProperty("eventType").GetString() ?? "";

                if (eventType == "ProxyLog")
                {
                    if (root.TryGetProperty("data", out var dataElement))
                    {
                        if (dataElement.TryGetProperty("message", out var msgElement))
                        {
                            string msg = msgElement.GetString() ?? "";
                            string trimmed = msg.Trim();
                            if (trimmed.Length > 10)
                            {
                                Console.ForegroundColor = ConsoleColor.DarkGray;
                                Console.WriteLine($"[PROXY-LOG] {trimmed}");
                                Console.ResetColor();
                            }
                        }
                    }
                    return;
                }

                ConsoleColor color = producer switch
                {
                    "etw" => ConsoleColor.Green,
                    "proxy" => ConsoleColor.Cyan,
                    "mitm" => ConsoleColor.Blue,
                    _ => ConsoleColor.White
                };

                Console.ForegroundColor = color;
                Console.Write($"[{producer.ToUpper()}] ");
                Console.ResetColor();

                Console.ForegroundColor = ConsoleColor.Yellow;
                Console.Write($"{eventType}: ");
                Console.ResetColor();

                if (root.TryGetProperty("data", out var dataElement2))
                {
                    var options = new JsonSerializerOptions
                    {
                        WriteIndented = true,
                        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
                    };
                    string formattedData = JsonSerializer.Serialize(dataElement2, options);

                    var lines = formattedData.Split('\n');
                    foreach (var line in lines)
                    {
                        Console.WriteLine(line);
                    }
                }
                else
                {
                    Console.WriteLine("(no data)");
                }

                Console.WriteLine();
            }
            catch
            {
                Console.WriteLine($"[RAW #{connectionId}] {json}");
                logWriter?.WriteLine(json);
            }
        }
    }
}
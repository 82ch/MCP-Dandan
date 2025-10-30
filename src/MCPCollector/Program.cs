using System;
using System.Collections.Generic;
using System.IO;
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
                        // 1. 길이 읽기
                        string? lengthStr = await reader.ReadLineAsync();
                        if (lengthStr == null) break;

                        if (!int.TryParse(lengthStr, out int length))
                        {
                            Console.WriteLine($"[Connection #{connectionId}] Invalid length: {lengthStr}");
                            continue;
                        }

                        // 2. 정확한 길이만큼 읽기
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

                            // 3. 개행 문자 소비 (\n)
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
                // 파일에 저장
                logWriter?.WriteLine(json);

                // 콘솔에 출력
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;

                string source = root.GetProperty("source").GetString() ?? "unknown";
                string type = root.GetProperty("type").GetString() ?? "";

                // 색상 지정
                ConsoleColor color = source switch
                {
                    "etw" => ConsoleColor.Green,
                    "proxy" => ConsoleColor.Cyan,
                    "mitm" => ConsoleColor.Blue,
                    _ => ConsoleColor.White
                };

                Console.ForegroundColor = color;
                Console.Write($"[{source.ToUpper()}] ");
                Console.ResetColor();

                // 데이터 출력 - 유니코드 디코딩하고 전체 출력
                if (root.TryGetProperty("data", out var dataElement))
                {
                    string dataStr = dataElement.ToString();

                    // 유니코드 이스케이프 시퀀스 디코딩 (\u0022 → ")
                    dataStr = DecodeUnicodeEscapes(dataStr);

                    // 잘라내지 않고 전체 출력
                    Console.WriteLine($"{type}: {dataStr}");
                }
                else
                {
                    Console.WriteLine(type);
                }
            }
            catch
            {
                Console.WriteLine($"[RAW #{connectionId}] {json}");
                logWriter?.WriteLine(json);
            }
        }

        /// <summary>
        /// 유니코드 이스케이프 시퀀스를 실제 문자로 디코딩
        /// \u0022 → "
        /// \u003C → <
        /// </summary>
        static string DecodeUnicodeEscapes(string input)
        {
            return Regex.Replace(input, @"\\u([0-9A-Fa-f]{4})", match =>
            {
                int codePoint = Convert.ToInt32(match.Groups[1].Value, 16);
                return ((char)codePoint).ToString();
            });
        }
    }
}
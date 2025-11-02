using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Management;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

public partial class Program
{
    public static string TargetProcName = "";
    public static HashSet<int> TrackedPids = new();
    private static readonly HashSet<int> RootPids = new();

    private static TcpClient? collectorClient;
    private static StreamWriter? collectorWriter;
    private static TraceEventSession? currentSession;

    static async Task Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;

        // 시작 전에 기존 세션 정리
        CleanupETWSessions();
        Thread.Sleep(500); // 정리 후 대기

        // 명령줄 인자에서 프로세스 이름 받기
        if (args.Length > 0)
        {
            string arg = args[0].ToLower();
            if (arg == "claude" || arg == "1")
            {
                TargetProcName = "claude";
            }
            else if (arg == "cursor" || arg == "2")
            {
                TargetProcName = "cursor";
            }
            else
            {
                Console.WriteLine($"[ERROR] 잘못된 인자: {args[0]}");
                Console.WriteLine("사용법: MCPTrace.exe [claude|cursor|1|2]");
                return;
            }
        }
        else
        {
            Console.WriteLine("[ERROR] 프로세스 이름이 지정되지 않았습니다.");
            Console.WriteLine("사용법: MCPTrace.exe [claude|cursor|1|2]");
            return;
        }

        // Collector 연결
        InitCollectorWithRetry();

        var cts = new CancellationTokenSource();

        // 종료 시 세션 정리 & 정상 종료 처리
        AppDomain.CurrentDomain.ProcessExit += (s, e) =>
        {
            Proxy.StopProxy();
            cts.Cancel();
            CleanupETWSessions();
        };
        
        Console.CancelKeyPress += (s, e) =>
        {
            Console.WriteLine("\n[*] Ctrl+C detected. Stopping ...");
            Proxy.StopProxy();
            cts.Cancel();
            CleanupETWSessions();
            e.Cancel = false;
            Environment.Exit(0);
        };

        Console.WriteLine("=".PadRight(80, '='));
        Console.WriteLine("MCPTrace Agent (ETW Collector)");
        Console.WriteLine("=".PadRight(80, '='));
        Console.WriteLine();

        Console.WriteLine($"[+] 선택된 프로세스: {TargetProcName}");
        Console.WriteLine($"[+] {TargetProcName}이(가) 실행될 때까지 대기 중...");
        Console.WriteLine("Note: 반드시 관리자 권한으로 실행해야 합니다.\n");

        // MCP Config 로드
        MCPRegistry.LoadConfig();

        // Proxy watcher 시작
        Proxy.StartWatcherAsync(cts.Token);

        await Task.Run(() => StartETWMonitoring(cts.Token));

        Console.WriteLine("[*] MCPTrace Agent 종료됨.");
    }

    private static void InitCollectorWithRetry()
    {
        int maxRetries = 10;
        int retryDelay = 500;

        for (int i = 0; i < maxRetries; i++)
        {
            try
            {
                collectorClient = new TcpClient("127.0.0.1", 8888);
                var stream = collectorClient.GetStream();
                collectorWriter = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };
                Console.WriteLine("[+] Connected to Collector");
                return;
            }
            catch
            {
                if (i == 0)
                {
                    Console.WriteLine($"[-] Waiting for Collector... (attempt {i + 1}/{maxRetries})");
                }
                Thread.Sleep(retryDelay);
            }
        }

        Console.WriteLine("[-] Failed to connect to Collector after multiple attempts");
        Console.WriteLine("[-] Will run without logging");
        collectorWriter = null;
    }

    private static void StartETWMonitoring(CancellationToken cancellationToken)
    {
        string sessionName = "MCPTraceSession_" + Process.GetCurrentProcess().Id;

        try
        {
            currentSession = new TraceEventSession(sessionName);

            try
            {
                currentSession.EnableKernelProvider(
                    KernelTraceEventParser.Keywords.FileIOInit |
                    KernelTraceEventParser.Keywords.FileIO |
                    KernelTraceEventParser.Keywords.Process);

                Console.WriteLine("[+] ETW Kernel provider attached successfully");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARNING] Kernel provider attach failed: {ex.Message}");
                Console.WriteLine("[*] Continuing without ETW file/process monitoring...");
                Console.WriteLine("[*] Only MITM proxy monitoring will be active.");

                // ETW 없이도 계속 실행 (MITM만 사용)
                cancellationToken.WaitHandle.WaitOne();
                return;
            }

            // 이벤트 핸들러 등록
            currentSession.Source.Kernel.ProcessStart += HandleProcessStart;
            currentSession.Source.Kernel.ProcessStop += HandleProcessStop;
            currentSession.Source.Kernel.FileIORead += HandleFileIORead;
            currentSession.Source.Kernel.FileIOWrite += HandleFileIOWrite;
            currentSession.Source.Kernel.FileIOCreate += HandleFileIOCreate;

            // File Rename (Dynamic)
            var dynamicParser = new DynamicTraceEventParser(currentSession.Source);
            dynamicParser.All += traceEvent =>
            {
                if (traceEvent.ProviderName.Equals("Microsoft-Windows-Kernel-File", StringComparison.OrdinalIgnoreCase) &&
                    traceEvent.EventName.Equals("FileIORename", StringComparison.OrdinalIgnoreCase))
                {
                    HandleFileIORenameDynamic(traceEvent);
                }
            };

            Task.Run(() =>
            {
                try
                {
                    currentSession.Source.Process();
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[ETW ERROR] {ex.GetType().Name}: {ex.Message}");
                }
            });

            cancellationToken.WaitHandle.WaitOne();
            Console.WriteLine("[*] ETW session stopped.");
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR] Failed to create ETW session: {ex.Message}");
            Console.WriteLine("[*] Continuing without ETW monitoring...");
            cancellationToken.WaitHandle.WaitOne();
        }
        finally
        {
            currentSession?.Dispose();
            currentSession = null;
        }
    }

    private static void SendToCollector(string eventType, object eventData)
    {
        try
        {
            var envelope = new
            {
                ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1000000,
                producer = "etw",
                pid = Process.GetCurrentProcess().Id,
                pname = Process.GetCurrentProcess().ProcessName,
                eventType,
                data = eventData
            };

            var json = JsonSerializer.Serialize(envelope);

            collectorWriter?.WriteLine($"{json.Length}");
            collectorWriter?.WriteLine(json);
        }
        catch
        {
            // 무시
        }
    }

    private static void CleanupETWSessions()
    {
        Console.WriteLine("[*] Cleaning up ETW sessions...");

        // 현재 세션 정리
        try
        {
            currentSession?.Dispose();
            currentSession = null;
        }
        catch { }

        // 프로세스 ID 기반 세션 정리
        int currentPid = Process.GetCurrentProcess().Id;
        string[] sessionNames = new[]
        {
            $"MCPTraceSession_{currentPid}",
            $"MCPMonitorSession_{currentPid}",
            "MCPTraceSession",
            "MCPMonitorSession"
        };

        foreach (var sessionName in sessionNames)
        {
            try
            {
                using var session = new TraceEventSession(sessionName, null);
                session.Stop();
                Console.WriteLine($"[Cleanup] Stopped session: {sessionName}");
            }
            catch
            {
                // 세션이 없거나 이미 정리됨
            }
        }

        // 모든 MCPTrace 관련 세션 정리 (추가)
        try
        {
            var allSessions = TraceEventSession.GetActiveSessionNames();
            foreach (var session in allSessions)
            {
                if (session.StartsWith("MCPTrace", StringComparison.OrdinalIgnoreCase) ||
                    session.StartsWith("MCPMonitor", StringComparison.OrdinalIgnoreCase))
                {
                    try
                    {
                        using var s = new TraceEventSession(session, null);
                        s.Stop();
                        Console.WriteLine($"[Cleanup] Stopped orphaned session: {session}");
                    }
                    catch { }
                }
            }
        }
        catch { }

        Console.WriteLine("[Cleanup] ETW sessions cleanup completed.");
    }
}
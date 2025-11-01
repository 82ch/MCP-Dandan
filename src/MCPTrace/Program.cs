using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
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

    static async Task Main()
    {
        Console.OutputEncoding = Encoding.UTF8;

        // Collector 연결
        InitCollector();

        var cts = new CancellationTokenSource();
        Proxy.StartWatcherAsync(cts.Token);
        // 종료 시 세션 정리 & 정상 종료 처리
        AppDomain.CurrentDomain.ProcessExit += (s, e) => CleanupETWSessions();
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

        Console.WriteLine("모니터링할 프로세스를 선택하세요:");
        Console.WriteLine("1. Claude");
        Console.WriteLine("2. Cursor");
        Console.Write("\n선택 (1 또는 2): ");

        string choice = Console.ReadLine();
        TargetProcName = choice == "2" ? "cursor" : "claude";

        Console.WriteLine($"\n[+] 선택된 프로세스: {TargetProcName}");
        Console.WriteLine("[+] ETW 수집 중...");
        Console.WriteLine("Note: 반드시 관리자 권한으로 실행해야 합니다.\n");

        // MCP Config 로드
        MCPRegistry.LoadConfig();

        await Task.Run(() => StartETWMonitoring(cts.Token));

        Console.WriteLine("[*] MCPTrace Agent 종료됨.");
    }

    private static void InitCollector()
    {
        try
        {
            collectorClient = new TcpClient("127.0.0.1", 8888);
            var stream = collectorClient.GetStream();
            collectorWriter = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };
            Console.WriteLine("[+] Connected to Collector");
        }
        catch
        {
            Console.WriteLine("[-] Failed to connect to Collector (will run without logging)");
            collectorWriter = null;
        }
    }

    private static void StartETWMonitoring(CancellationToken cancellationToken)
    {
        using var session = new TraceEventSession("MCPTraceSession_" + Process.GetCurrentProcess().Id);

        try
        {
            session.EnableKernelProvider(
                KernelTraceEventParser.Keywords.FileIOInit |
                KernelTraceEventParser.Keywords.FileIO |
                KernelTraceEventParser.Keywords.Process);
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR] Kernel provider attach failed: {ex.Message}");
        }

        // 이벤트 핸들러 등록
        session.Source.Kernel.ProcessStart += HandleProcessStart;
        session.Source.Kernel.ProcessStop += HandleProcessStop;
        session.Source.Kernel.FileIORead += HandleFileIORead;
        session.Source.Kernel.FileIOWrite += HandleFileIOWrite;
        session.Source.Kernel.FileIOCreate += HandleFileIOCreate;

        // File Rename (Dynamic)
        var dynamicParser = new DynamicTraceEventParser(session.Source);
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
                session.Source.Process();
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ETW ERROR] {ex.GetType().Name}: {ex.Message}");
            }
        });

        cancellationToken.WaitHandle.WaitOne();
        Console.WriteLine("[*] ETW session stopped.");
    }

    private static void SendToCollector(string eventType, object eventData)
    {
        try
        {
            // 명세서에 맞는 형식으로 변경
            var envelope = new
            {
                ts = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1000000, // nanoseconds
                producer = "etw",
                pid = Process.GetCurrentProcess().Id,
                pname = Process.GetCurrentProcess().ProcessName,
                eventType,
                data = eventData  // 여기에 실제 이벤트 데이터가 들어감
            };

            var json = JsonSerializer.Serialize(envelope);

            // 길이 헤더 추가
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
        try
        {
            using var s1 = new TraceEventSession("MCPTraceSession_" + Process.GetCurrentProcess().Id, null);
            s1.Stop();
        }
        catch { }

        try
        {
            using var s2 = new TraceEventSession("MCPMonitorSession_" + Process.GetCurrentProcess().Id, null);
            s2.Stop();
        }
        catch { }

        Console.WriteLine("[Cleanup] ETW sessions cleaned up.");
    }
}
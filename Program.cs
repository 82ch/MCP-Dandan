using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using System.Xml.Linq;


public partial class Program
{
    public static string TargetProcName = "";
    public static HashSet<int> TrackedPids = new HashSet<int>();
    // 루트 프로세스(claude 등)를 별도로 저장 — 루트 자체의 File I/O는 추적에서 제외
    private static readonly HashSet<int> RootPids = new HashSet<int>();


    private static readonly Guid GowonMonGuid = new Guid("7d38387a-bf0b-4dcf-8d8e-b8558542d874");

    static void Main(string[] args)
    {
        Console.WriteLine("Note: This program must be run with Administrator privileges.");
        var cts = new CancellationTokenSource();

        Console.Write("Enter process name to monitor (ex: claude.exe): ");
        TargetProcName = (Console.ReadLine() ?? "").Trim().ToLowerInvariant().Replace(".exe", "");
        if (string.IsNullOrWhiteSpace(TargetProcName))
        {
            Console.WriteLine("[!] Invalid process name entered. Exiting.");
            return;
        }
        MCPRegistry.LoadConfig();
        // 선택적 초기화: 이미 실행중인 타겟 프로세스가 있으면 루트로 등록
        try
        {
            var existing = System.Diagnostics.Process.GetProcessesByName(TargetProcName);
            foreach (var p in existing)
            {
                // 루트로 등록 (File I/O 추적 대상이 아님)
                RootPids.Add(p.Id);
                // 태깅(나중에 부모-자식 관계에 사용)
                try { MCPRegistry.SetNameTag(p.Id, Program.TargetProcName); } catch { }
                Console.WriteLine($"[INFO] Found existing root process: {TargetProcName}.exe (PID: {p.Id})");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[WARN] Could not enumerate existing processes: {ex.Message}");
        }


        Console.WriteLine($"[+] Monitoring will start when {TargetProcName}.exe is launched.");

        // Create a real-time kernel ETW session using TraceEventSession.
        using (var session = new TraceEventSession("SeungwonSession"))
        {
            // Set up the Ctrl+C event handler.
            Console.CancelKeyPress += (sender, eventArgs) =>
            {
                // Prevent the process from terminating immediately.
                eventArgs.Cancel = true;
                Console.WriteLine("\n[*] Ctrl+C pressed. Stopping the session...");
                // Signal the CancellationTokenSource to cancel.
                cts.Cancel();
                // Stop the ETW session, which will unblock the session.Source.Process() call.
                session.Stop();
            };

            // Request the kernel to provide Process, FileIO, and FileIOInit events.
            var keywords =
            KernelTraceEventParser.Keywords.FileIOInit |
            KernelTraceEventParser.Keywords.FileIO|
            KernelTraceEventParser.Keywords.Process;


            try
            {
                session.EnableKernelProvider(keywords);
                session.EnableProvider(GowonMonGuid, TraceEventLevel.Verbose, ulong.MaxValue);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Kernel provider attach failed: {ex.GetType().Name} - {ex.Message}");
            }


            // Register handlers for each event.
            session.Source.Kernel.ProcessStart += HandleProcessStart;
            session.Source.Kernel.ProcessStop += HandleProcessStop;
            session.Source.Kernel.FileIORead += HandleFileIORead;
            session.Source.Kernel.FileIOWrite += HandleFileIOWrite;
            session.Source.Kernel.FileIOCreate += HandleFileIOCreate;

            // -------------------------------
            // MCP Send/Recv 이벤트 처리 
            // -------------------------------
            if (session.Source is ETWTraceEventSource ETWSource)
            {
                var parser = new DynamicTraceEventParser(ETWSource);
                parser.All += HandleMCP;
            }
            // FileIORename 이벤트를 동적으로 감지하기 (TraceEvent 최신 버전 호환)
            if (session.Source is ETWTraceEventSource etwSource)
            {
                var dynamicParser = new DynamicTraceEventParser(etwSource);
                dynamicParser.All += traceEvent =>
                {
                    // Microsoft-Windows-Kernel-File 프로바이더의 FileIORename 이벤트만 필터링
                    if (traceEvent.ProviderName.Equals("Microsoft-Windows-Kernel-File", StringComparison.OrdinalIgnoreCase) &&
                        traceEvent.EventName.Equals("FileIORename", StringComparison.OrdinalIgnoreCase))
                    {
                        HandleFileIORenameDynamic(traceEvent);
                    }
                };
            }

            // Start the asynchronous task for event processing.
            // This task will run until session.Stop() is called.
            var processingTask = Task.Run(() =>
            {
                try
                {
                    session.Source.Process();
                }
                catch (Exception ex)
                {
                    // This might catch an exception if the session is disposed of abruptly.
                    Console.ForegroundColor = ConsoleColor.Red;
                    Console.WriteLine($"[ETW ERROR] {ex.GetType().Name}: {ex.Message}");
                    Console.ResetColor();
                }
            });

            // Wait here until cancellation is requested via Ctrl+C.
            try
            {
                cts.Token.WaitHandle.WaitOne();
            }
            catch (OperationCanceledException)
            {
                // This is expected on shutdown, no action needed.
            }

            Console.WriteLine("[*] Session stopped. Exiting.");
        }
    }

}

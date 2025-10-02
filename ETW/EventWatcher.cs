using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.Threading;

namespace ETW
{
    public static class EventWatcher
    {
        private static readonly string[] NetProviders = new[]
        {
            "Microsoft-Windows-WinINet",
            "Microsoft-Windows-WinHTTP",
            "Microsoft-Windows-DNS-Client",
            "Microsoft-Windows-TCPIP",
            "Microsoft-Windows-Kernel-Network",
        };

        public static void RunEtw(ManualResetEventSlim stopEvt)
        {
            const string sessionName = "TargetedWatcherSession";

            try
            {
                foreach (var s in TraceEventSession.GetActiveSessionNames())
                {
                    if (string.Equals(s, sessionName, StringComparison.OrdinalIgnoreCase))
                    {
                        using var old = new TraceEventSession(s);
                        old.Stop();
                        break;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] Failed to clean old session: {ex.GetType().Name} - {ex.Message}");
            }

            using var session = new TraceEventSession(sessionName);

            var keywords =
                KernelTraceEventParser.Keywords.Process |
                KernelTraceEventParser.Keywords.FileIOInit |
                KernelTraceEventParser.Keywords.FileIO |
                KernelTraceEventParser.Keywords.DiskIO |
                KernelTraceEventParser.Keywords.NetworkTCPIP;

            try
            {
                session.EnableKernelProvider(keywords);
                session.EnableProvider("Microsoft-Windows-Kernel-File", Microsoft.Diagnostics.Tracing.TraceEventLevel.Verbose, ulong.MaxValue);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Kernel provider attach failed: {ex.GetType().Name} - {ex.Message}");
            }

            // 기본 네트워크 관련 프로바이더
            foreach (var p in NetProviders)
            {
                try
                {
                    session.EnableProvider(p, Microsoft.Diagnostics.Tracing.TraceEventLevel.Informational, ulong.MaxValue);
                    Console.WriteLine($"[+] NetProvider {p} enabled");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[WARN] NetProvider {p} attach failed: {ex.GetType().Name} - {ex.Message}");
                }
            }

            // NamedPipe
            try
            {
                session.EnableProvider("Microsoft-Windows-NamedPipe", Microsoft.Diagnostics.Tracing.TraceEventLevel.Informational, ulong.MaxValue);
                Console.WriteLine("[+] NamedPipe provider enabled");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] NamedPipe provider attach failed: {ex.GetType().Name} - {ex.Message}");
            }

            // --- 추가 프로바이더들 ---
            try
            {
                session.EnableProvider("Microsoft-Windows-Schannel", Microsoft.Diagnostics.Tracing.TraceEventLevel.Informational, ulong.MaxValue);
                Console.WriteLine("[+] Schannel provider enabled (TLS handshake/SNI)");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] Schannel provider attach failed: {ex.GetType().Name} - {ex.Message}");
            }

            try
            {
                session.EnableProvider("Microsoft-Quic", Microsoft.Diagnostics.Tracing.TraceEventLevel.Informational, ulong.MaxValue);
                Console.WriteLine("[+] MsQuic provider enabled (QUIC/HTTP3)");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[WARN] MsQuic provider attach failed: {ex.GetType().Name} - {ex.Message}");
            }

            var source = session.Source;

            try
            {
                ProcessEventRegistrar.Register(source);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Registrar registration failed: {ex.GetType().Name} - {ex.Message}");
            }

            Console.WriteLine("[*] ETW session started. Monitoring...");

            try
            {
                source.Process(); // try/catch로 보호
            }
            catch (Exception ex)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"[ETW ERROR] {ex.GetType().Name}: {ex.Message}");
                Console.ResetColor();
            }
        }
    }
}

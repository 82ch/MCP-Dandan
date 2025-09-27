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
            catch { }

            using var session = new TraceEventSession(sessionName);

            var keywords =
                KernelTraceEventParser.Keywords.Process |
                KernelTraceEventParser.Keywords.FileIOInit |
                KernelTraceEventParser.Keywords.FileIO |
                KernelTraceEventParser.Keywords.DiskIO |
                KernelTraceEventParser.Keywords.NetworkTCPIP;

            session.EnableKernelProvider(keywords);
            session.EnableProvider("Microsoft-Windows-Kernel-File", Microsoft.Diagnostics.Tracing.TraceEventLevel.Verbose, ulong.MaxValue);

            foreach (var p in NetProviders)
                try { session.EnableProvider(p); } catch { }

            try { session.EnableProvider("Microsoft-Windows-NamedPipe"); }
            catch { }

            var source = session.Source;
            ProcessEventRegistrar.Register(source);

            Console.WriteLine("[*] ETW session started. Monitoring...");
            source.Process();
        }
    }
}

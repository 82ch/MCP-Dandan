using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.IO;

namespace CursorProcessTree
{
    public static class CursorRunner
    {
        public static void Run(string targetProcess)
        {
            ProcessTracker.targetProcess = targetProcess;

            var userProfile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            ProcessTracker.excludePrefixes = new[]
            {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Cursor") + Path.DirectorySeparatorChar,
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "cursor") + Path.DirectorySeparatorChar,
                Path.Combine(userProfile, ".cursor", "extensions") + Path.DirectorySeparatorChar
            };

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[+] Monitoring {targetProcess}, MCP file + network events...");
            Console.WriteLine($"[+] Logging events to: {Path.GetFullPath(ProcessTracker.logPath)} (append mode)");
            Console.ResetColor();

            if (!(TraceEventSession.IsElevated() ?? false))
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine("[-] Please run as Administrator!");
                Console.ResetColor();
                return;
            }

            ProcessTracker.logWriter = new StreamWriter(ProcessTracker.logPath, false, System.Text.Encoding.UTF8)
            {
                AutoFlush = true
            };

            using var session = new TraceEventSession("CursorObserverSession");

            session.EnableKernelProvider(
                KernelTraceEventParser.Keywords.Process |
                KernelTraceEventParser.Keywords.FileIO |
                KernelTraceEventParser.Keywords.FileIOInit |
                KernelTraceEventParser.Keywords.NetworkTCPIP
            );

            // 등록
            ProcessEventRegistrar.Register(session);

            try
            {
                session.Source.Process();
            }
            catch (Exception ex)
            {
                try { ProcessTracker.LogLine("[FATAL] " + ex.Message); } catch { }
            }
        }
    }
}

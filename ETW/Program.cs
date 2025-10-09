using System;
using System.Diagnostics;
using System.IO;
using System.Threading;


namespace ETW
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.Write("Enter process name to monitor (ex: claude.exe): ");
            Console.ResetColor();
            ProcessTracker.TargetProcName = (Console.ReadLine() ?? "").Trim().ToLowerInvariant();

            if (string.IsNullOrWhiteSpace(ProcessTracker.TargetProcName))
            {
                Console.WriteLine("[!] No process name entered. Exiting.");
                return;
            }

            ProcessHelper.InitializeTargetProcesses(ProcessTracker.TargetProcName);

            Console.ForegroundColor = ConsoleColor.Yellow;
            Console.WriteLine($"[+] Monitoring process: {ProcessTracker.TargetProcName}");
            Console.WriteLine($"[+] Also tailing logs under: {LogWatcher.ClaudeLogsDir}");
            Console.WriteLine("[+] Run as Administrator.");
            Console.ResetColor();

            LogWatcher.InitializeLogOffsets();

            var stopEvent = new ManualResetEventSlim(false);
            Console.CancelKeyPress += (s, e) =>
            {
                e.Cancel = true;
                stopEvent.Set();
                Console.WriteLine("[*] Stop requested...");
            };

            var etwThread = new Thread(() => EventWatcher.RunEtw(stopEvent)) { IsBackground = true };
            etwThread.Start();

            LogWatcher.TryStartLogDirectoryWatcher();

            stopEvent.Wait();
            Console.WriteLine("[*] Exiting.");
        }
    }
}

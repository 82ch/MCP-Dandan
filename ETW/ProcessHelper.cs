using System;
using System.Diagnostics;
using System.IO;
using System.Management;

namespace ETW
{
    public static class ProcessHelper
    {
        public static void InitializeTargetProcesses(string targetProcName)
        {
            string baseName = Path.GetFileNameWithoutExtension(targetProcName);
            foreach (var p in Process.GetProcessesByName(baseName))
            {
                ProcessTracker.TrackedPids[p.Id] = p.ProcessName + ".exe";
                string cmd = TryGetCommandLineForPid(p.Id);
                ProcessTracker.ProcCmdline[p.Id] = McpHelper.TagFromCommandLine(cmd);
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[INIT] Found running PID={p.Id} {p.ProcessName}.exe CMD={cmd}");
                Console.ResetColor();
            }
        }

        public static string TryGetCommandLineForPid(int pid)
        {
            try
            {
                string query = $"SELECT CommandLine FROM Win32_Process WHERE ProcessId = {pid}";
                using var searcher = new ManagementObjectSearcher(query);
                foreach (ManagementObject mo in searcher.Get())
                    return mo["CommandLine"] as string;
            }
            catch { }
            return null;
        }
    }
}

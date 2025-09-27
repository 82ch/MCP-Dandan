using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;

namespace ETW
{
    public static class ProcessEventRegistrar
    {
        public static void Register(TraceEventSource source)
        {
            // -------------------------------
            // 프로세스 이벤트
            // -------------------------------
            source.Kernel.ProcessStart += ev =>
            {
                if (ev.ImageFileName != null &&
                    ev.ImageFileName.EndsWith(ProcessTracker.TargetProcName, StringComparison.OrdinalIgnoreCase))
                {
                    // Claude 메인 프로세스
                    ProcessTracker.RootPid = ev.ProcessID;
                    ProcessTracker.TrackedPids[ev.ProcessID] = ev.ImageFileName;

                    string cmdline = ev.CommandLine ?? ProcessHelper.TryGetCommandLineForPid(ev.ProcessID);
                    ProcessTracker.ProcCmdline[ev.ProcessID] = McpHelper.TagFromCommandLine(cmdline);

                    Console.ForegroundColor = ConsoleColor.Green;
                    Console.WriteLine($"[PROC START] PID={ev.ProcessID} {ev.ImageFileName} CMD={McpHelper.TruncateCmd(cmdline)}");
                    Console.ResetColor();
                }
                else if (ProcessTracker.RootPid > 0 && ev.ParentID == ProcessTracker.RootPid)
                {
                    // Claude 자식 프로세스
                    ProcessTracker.TrackedPids[ev.ProcessID] = ev.ImageFileName;

                    string cmdline = ev.CommandLine ?? ProcessHelper.TryGetCommandLineForPid(ev.ProcessID);
                    ProcessTracker.ProcCmdline[ev.ProcessID] = McpHelper.TagFromCommandLine(cmdline);

                    Console.ForegroundColor = ConsoleColor.DarkGreen;
                    Console.WriteLine($"[PROC START - CHILD] PID={ev.ProcessID} Parent={ev.ParentID} {ev.ImageFileName} CMD={McpHelper.TruncateCmd(cmdline)}");
                    Console.ResetColor();
                }
            };

            source.Kernel.ProcessStop += ev =>
            {
                if (ProcessTracker.TrackedPids.TryRemove(ev.ProcessID, out _))
                {
                    ProcessTracker.ProcCmdline.TryRemove(ev.ProcessID, out _);
                    ProcessTracker.LastResolvedHostByPid.TryRemove(ev.ProcessID, out _);

                    if (ev.ProcessID == ProcessTracker.RootPid)
                        ProcessTracker.RootPid = -1; // Claude 메인 종료 시 초기화

                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine($"[PROC STOP] PID={ev.ProcessID}");
                    Console.ResetColor();
                }
            };

            // -------------------------------
            // 파일 I/O 이벤트
            // -------------------------------
            source.Kernel.FileIOFileCreate += ev =>
            {
                if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID))
                    FileEventHandler.LogEvent("CREATE", ev.ProcessID, ev.FileName, ev.FileKey);
            };

            source.Kernel.FileIOWrite += ev =>
            {
                if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID))
                    FileEventHandler.LogEvent("WRITE", ev.ProcessID, ev.FileName, ev.FileKey);
            };

            source.Kernel.FileIOFileDelete += ev =>
            {
                if (ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID))
                    FileEventHandler.LogEvent("DELETE", ev.ProcessID, ev.FileName, ev.FileKey);
            };

            // -------------------------------
            // 네트워크 이벤트 (MCP 태그 제거)
            // -------------------------------
            source.Kernel.TcpIpConnect += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[NET-CONNECT] PID={ev.ProcessID} -> {ev.daddr}:{ev.dport}");
                Console.ResetColor();
            };

            source.Kernel.TcpIpSend += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[NET-SEND] PID={ev.ProcessID} -> {ev.daddr}:{ev.dport} Bytes={ev.size}");
                Console.ResetColor();
            };

            source.Kernel.TcpIpRecv += ev =>
            {
                if (!ProcessTracker.TrackedPids.ContainsKey(ev.ProcessID)) return;
                Console.ForegroundColor = ConsoleColor.Green;
                Console.WriteLine($"[NET-RECV] PID={ev.ProcessID} <- {ev.saddr}:{ev.sport} Bytes={ev.size}");
                Console.ResetColor();
            };
        }
    }
}

using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using Microsoft.Diagnostics.Tracing.Session;
using System;
using System.Collections.Generic;
using System.Linq;

namespace CursorProcessTree
{
    public static class ProcessEventRegistrar
    {
        public static void Register(TraceEventSession session)
        {
            // --- Process start ---
            session.Source.Kernel.ProcessStart += data =>
            {
                var info = new ProcessTracker.ProcessInfo
                {
                    Pid = data.ProcessID,
                    ParentPid = data.ParentID,
                    Name = data.ImageFileName ?? "",
                    CmdLine = data.CommandLine ?? ""
                };

                lock (ProcessTracker.processMap)
                {
                    ProcessTracker.processMap[info.Pid] = info;
                    if (!ProcessTracker.treeMap.ContainsKey(info.ParentPid))
                        ProcessTracker.treeMap[info.ParentPid] = new List<int>();
                    ProcessTracker.treeMap[info.ParentPid].Add(info.Pid);
                }

                string inferredType = ProcessTracker.InferType(info.Name, info.CmdLine) ?? "unknown";
                ProcessTracker._pidTypeMap[info.Pid] = inferredType;

                ProcessTracker.LogLine(
                    $"[Process Start] PID={info.Pid}, PPID={info.ParentPid}, Name={info.Name}, Type={inferredType}, Cmd={info.CmdLine}");

                if (ProcessTracker.rootPid == -1 &&
                    info.Name.Equals(ProcessTracker.targetProcess, StringComparison.OrdinalIgnoreCase))
                {
                    ProcessTracker.rootPid = info.Pid;
                    ProcessTracker.PrintProcessEvent("[ROOT FOUND]", info, inferredType, ConsoleColor.Cyan);
                }

                if (ProcessTracker.IsChildOfTarget(info.Pid))
                    ProcessTracker.PrintProcessEvent("[START]", info, inferredType, ConsoleColor.Green);
            };

            // --- Process stop ---
            session.Source.Kernel.ProcessStop += data =>
            {
                var pid = data.ProcessID;
                lock (ProcessTracker.processMap)
                {
                    if (ProcessTracker.processMap.TryGetValue(pid, out var info))
                    {
                        string typeLabel = ProcessTracker._pidTypeMap.TryRemove(pid, out var storedType) ? storedType : "unknown";
                        ProcessTracker.LogLine($"[Process Stop ] PID={pid}, Name={info.Name}, Type={typeLabel}");

                        if (ProcessTracker.IsChildOfTarget(pid))
                            ProcessTracker.PrintProcessEvent("[EXIT]", info, typeLabel, ConsoleColor.DarkGray);

                        ProcessTracker.processMap.Remove(pid);
                        ProcessTracker.mcpPids.Remove(pid);
                        McpTagManager.tagStates.TryRemove(pid, out _);
                        McpTagManager.activeRemoteByPidTag.TryRemove(pid, out _);
                        ProcessTracker.pidConnections.TryRemove(pid, out _);
                        ProcessTracker.seenConnections.TryRemove(pid, out _);
                    }
                }
            };

            // --- Image Load ---
            session.Source.Kernel.ImageLoad += data =>
            {
                try
                {
                    if (ProcessTracker.IsChildOfTarget(data.ProcessID))
                    {
                        ProcessTracker._pidTypeMap.TryGetValue(data.ProcessID, out var knownType);
                        ProcessTracker.LogLine(
                            $"[Image Load   ] PID={data.ProcessID}, DLL={data.FileName}, Type={(knownType ?? "unknown")}");
                    }
                }
                catch { }
            };

            // --- File Create/Open ---
            session.Source.Kernel.FileIOCreate += data =>
            {
                if (!ProcessTracker.IsChildOfTarget(data.ProcessID)) return;
                FileEventHandler.HandleCreateEvent(data);
            };

            // --- File Read / Write / Delete ---
            session.Source.Kernel.FileIORead += data =>
                FileEventHandler.HandleFileEvent("[READ]", data.ProcessID, data.FileName);
            session.Source.Kernel.FileIOWrite += data =>
                FileEventHandler.HandleFileEvent("[WRITE]", data.ProcessID, data.FileName);
            session.Source.Kernel.FileIOFileDelete += data =>
                FileEventHandler.HandleFileEvent("[DELETE]", data.ProcessID, data.FileName);

            // --- File Rename ---
            session.Source.Kernel.FileIORename += data =>
                FileEventHandler.HandleRenameEvent(data);

            // --- Network events (Kernel TCP/UDP) ---
            session.Source.Kernel.TcpIpSend += data =>
                NetworkEventHandler.HandleNetworkEvent("[TCP SEND]", data.ProcessID, data);
            session.Source.Kernel.TcpIpRecv += data =>
                NetworkEventHandler.HandleNetworkEvent("[TCP RECV]", data.ProcessID, data);
            session.Source.Kernel.UdpIpSend += data =>
                NetworkEventHandler.HandleNetworkEvent("[UDP SEND]", data.ProcessID, data);
            session.Source.Kernel.UdpIpRecv += data =>
                NetworkEventHandler.HandleNetworkEvent("[UDP RECV]", data.ProcessID, data);
        }
    }
}

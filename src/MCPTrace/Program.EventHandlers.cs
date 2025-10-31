using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

public partial class Program
{
    /// 새 프로세스가 시작될 때 호출되는 이벤트 핸들러입니다.
    private static void HandleProcessStart(ProcessTraceData data)
    {
        bool isTargetProcess = data.ProcessName.Equals(TargetProcName, StringComparison.OrdinalIgnoreCase);
        bool isChildOfTarget = TrackedPids.Contains(data.ParentID);

        if (isChildOfTarget || isTargetProcess)
        {
            string mcpNameTag = MCPRegistry.GetNameTag(data.ParentID);
            if (string.IsNullOrEmpty(mcpNameTag))
            {
                mcpNameTag = MCPRegistry.SetNameTag(data.ProcessID, Program.TargetProcName);
            }
            else if (mcpNameTag == Program.TargetProcName)
            {
                mcpNameTag = MCPRegistry.Submit(data.ProcessID, data.CommandLine);
            }
            else
            {
                mcpNameTag = MCPRegistry.SetNameTag(data.ProcessID, mcpNameTag);
            }

            TrackedPids.Add(data.ProcessID);

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[PROCESS Start] " +
                              $"Time: {data.TimeStamp.ToLocalTime()}, " +
                              $"Name: {data.ProcessName}.exe, " +
                              $"PID: {data.ProcessID}, " +
                              $"Parent PID: {data.ParentID}, " +
                              $"Command Line: {data.CommandLine} ");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine($"└─ MCP Name Tag: '{mcpNameTag}'");
            Console.ResetColor();

            // Collector로 전송
            SendToCollector("process_start", new
            {
                time = data.TimeStamp.ToLocalTime(),
                name = data.ProcessName,
                pid = data.ProcessID,
                parent_pid = data.ParentID,
                cmdline = data.CommandLine,
                mcp_tag = mcpNameTag
            });
        }
    }

    /// <summary>
    /// 프로세스가 중지될 때 호출되는 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleProcessStop(ProcessTraceData data)
    {
        if (TrackedPids.Remove(data.ProcessID))
        {
            MCPRegistry.Remove(data.ProcessID);
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"[PROCESS Stop] Process stopped: {data.ProcessName} (PID: {data.ProcessID})");
            Console.ResetColor();

            // Collector로 전송
            SendToCollector("process_stop", new
            {
                name = data.ProcessName,
                pid = data.ProcessID
            });
        }
    }

    private static void HandleFileIORead(FileIOReadWriteTraceData data)
    {
        // File I/O Read 처리 로직 (필요시 구현)
    }

    /// <summary>
    /// 파일 쓰기 이벤트에 대한 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleFileIOWrite(FileIOReadWriteTraceData data)
    {
        // File I/O Write 처리 로직 (필요시 구현)
    }

    /// <summary>
    /// 파일 생성 이벤트에 대한 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleFileIOCreate(FileIOCreateTraceData data)
    {
        // File I/O Create 처리 로직 (필요시 구현)
    }

    /// <summary>
    /// 파일 이름 변경 이벤트에 대한 동적 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleFileIORenameDynamic(TraceEvent data)
    {
        // File I/O Rename 처리 로직 (필요시 구현)
    }
}
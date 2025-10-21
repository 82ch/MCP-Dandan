using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;
using static System.Runtime.InteropServices.JavaScript.JSType;


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
            Console.ForegroundColor = ConsoleColor.DarkCyan; // 태그는 다른 색상으로 
            Console.WriteLine($"└─ MCP Name Tag: '{mcpNameTag}'");
            Console.ResetColor();
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
        }
    }
    private static void HandleFileIORead(FileIOReadWriteTraceData data)
    {
        //if (TrackedPids.Contains(data.ProcessID))
        //{
        //    Console.ForegroundColor = ConsoleColor.Yellow;
        //    Console.WriteLine($"[FILE Read] PID: {data.ProcessID} -> '{data.FileName}' ({data.IoSize} bytes)");
        //    Console.ResetColor();
        //}
        //PrintAllFields(data, "READ");

    }

    /// <summary>
    /// 파일 쓰기 이벤트에 대한 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleFileIOWrite(FileIOReadWriteTraceData data)
    {
        //if (TrackedPids.Contains(data.ProcessID))
        //{
        //    Console.ForegroundColor = ConsoleColor.Yellow;
        //    Console.WriteLine($"[FILE Write] PID: {data.ProcessID} -> '{data.FileName}' ({data.IoSize} bytes)");
        //    Console.ResetColor();
        //}
    }
    private static void HandleMCP(TraceEvent data)
    {
        if (data.ProviderGuid == GowonMonGuid)
        {
            bool task = Convert.ToBoolean(data.PayloadByName("task"));
            string taskname = task ? "Send" : "Recv";
            UInt32 len = Convert.ToUInt32(data.PayloadByName("tototalLen"));
            bool flag = Convert.ToBoolean(data.PayloadByName("truncated"));
            var raw = (byte[])data.PayloadByName("data");
            string msg = System.Text.Encoding.UTF8.GetString(raw);
            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[MCP {taskname}] " +
                $"Time: {data.TimeStamp.ToLocalTime()}, " +
                $"Name: {data.ProcessName}.exe, " +
                $"PID: {data.ProcessID}, " +
                $"Length: {len} bytes, " +
                $"Flag: {flag}, " +
                $"Message: {msg}");
            Console.ResetColor();
        }

    }
}


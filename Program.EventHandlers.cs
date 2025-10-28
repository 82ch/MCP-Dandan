using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Threading.Tasks;

public partial class Program
{
    /// <summary>
    /// 새 프로세스가 시작될 때 호출되는 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleProcessStart(ProcessTraceData data)
    {
        bool isTargetProcess = data.ProcessName.Equals(TargetProcName, StringComparison.OrdinalIgnoreCase);
        bool isChildOfTarget = TrackedPids.Contains(data.ParentID) || RootPids.Contains(data.ParentID);

        // 루트 프로세스(claude.exe 등) 시작 시
        if (isTargetProcess)
        {
            RootPids.Add(data.ProcessID);
            MCPRegistry.SetNameTag(data.ProcessID, Program.TargetProcName);

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[PROCESS Root Start] Time: {data.TimeStamp.ToLocalTime()}, " +
                              $"Name: {data.ProcessName}.exe, " +
                              $"PID: {data.ProcessID}, Parent PID: {data.ParentID}, " +
                              $"Command Line: {data.CommandLine}");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine("└─ Root registered (File I/O not tracked).");
            Console.ResetColor();
            return; // 루트 자체는 추적하지 않음
        }

        // 루트 또는 추적 중인 프로세스의 자식이라면 MCP 서버 후보로 처리
        if (isChildOfTarget)
        {
            string parentTag = MCPRegistry.GetNameTag(data.ParentID) ?? string.Empty;
            string mcpNameTag;

            // 부모가 루트거나 태그가 루트면 Submit으로 MCP 서버명 판정
            if (string.IsNullOrEmpty(parentTag) || parentTag == Program.TargetProcName)
                mcpNameTag = MCPRegistry.Submit(data.ProcessID, data.CommandLine);
            else
                mcpNameTag = MCPRegistry.SetNameTag(data.ProcessID, parentTag); // 부모 태그 상속

            TrackedPids.Add(data.ProcessID);

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[PROCESS Start] Time: {data.TimeStamp.ToLocalTime()}, " +
                              $"Name: {data.ProcessName}.exe, PID: {data.ProcessID}, " +
                              $"Parent PID: {data.ParentID}, Command Line: {data.CommandLine}");
            Console.ForegroundColor = ConsoleColor.DarkCyan;
            Console.WriteLine($"└─ MCP Name Tag: '{mcpNameTag}' (tracked)");
            Console.ResetColor();
            return;
        }

        // 그 외의 프로세스는 무시
    }

    /// <summary>
    /// 프로세스가 중지될 때 호출되는 이벤트 핸들러입니다.
    /// </summary>
    private static void HandleProcessStop(ProcessTraceData data)
    {
        if (TrackedPids.Remove(data.ProcessID) || RootPids.Remove(data.ProcessID))
        {
            MCPRegistry.Remove(data.ProcessID);
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine($"[PROCESS Stop] Process stopped: {data.ProcessName} (PID: {data.ProcessID})");
            Console.ResetColor();
        }
    }

    /// <summary>
    /// 파일 읽기 이벤트 핸들러
    /// </summary>
    private static void HandleFileIORead(FileIOReadWriteTraceData data)
    {
        // 루트 프로세스는 무시
        if (RootPids.Contains(data.ProcessID)) return;
        // 추적 중인 MCP 프로세스만
        if (!TrackedPids.Contains(data.ProcessID)) return;

        string tag = MCPRegistry.GetNameTag(data.ProcessID);
        Console.ForegroundColor = ConsoleColor.Yellow;
        Console.WriteLine($"[FILE Read] Time: {data.TimeStamp.ToLocalTime()}, " +
                          $"PID: {data.ProcessID}, MCP: {tag}, Path: {data.FileName}, Size: {data.IoSize} bytes");
        Console.ResetColor();
    }

    /// <summary>
    /// 파일 쓰기 이벤트 핸들러
    /// </summary>
    private static void HandleFileIOWrite(FileIOReadWriteTraceData data)
    {
        if (RootPids.Contains(data.ProcessID)) return;
        if (!TrackedPids.Contains(data.ProcessID)) return;

        string tag = MCPRegistry.GetNameTag(data.ProcessID);
        Console.ForegroundColor = ConsoleColor.Magenta;
        Console.WriteLine($"[FILE Write] Time: {data.TimeStamp.ToLocalTime()}, " +
                          $"PID: {data.ProcessID}, MCP: {tag}, Path: {data.FileName}, Size: {data.IoSize} bytes");
        Console.ResetColor();
    }
    private static void HandleFileIOCreate(FileIOCreateTraceData data)
    {
        if (RootPids.Contains(data.ProcessID)) return;
        if (!TrackedPids.Contains(data.ProcessID)) return;

        Console.ForegroundColor = ConsoleColor.DarkYellow;
        Console.WriteLine($"[FILE Create] PID: {data.ProcessID}, Name: {data.FileName}, Options: {data.CreateOptions}");
        Console.ResetColor();
    }

    private static void HandleFileIORenameDynamic(TraceEvent data)
    {
        int pid = data.ProcessID;
        if (RootPids.Contains(pid)) return;
        if (!TrackedPids.Contains(pid)) return;

        string oldName = data.PayloadNames.Contains("FileName")
            ? data.PayloadByName("FileName")?.ToString() ?? "" : "";
        string newName = data.PayloadNames.Contains("TargetFileName")
            ? data.PayloadByName("TargetFileName")?.ToString() ?? ""
            : data.PayloadNames.Contains("NewFileName")
                ? data.PayloadByName("NewFileName")?.ToString() ?? "" : "";

        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine($"[FILE Rename] PID: {pid}, Old: {oldName}, New: {newName}");
        Console.ResetColor();
    }



    /// <summary>
    /// 커스텀 ETW Provider(GowonMonGuid)에서 발생하는 MCP Send/Recv 이벤트 처리
    /// </summary>
    private static void HandleMCP(TraceEvent data)
    {
        if (data.ProviderGuid != GowonMonGuid)
            return;

        bool task = Convert.ToBoolean(data.PayloadByName("task"));
        string taskname = task ? "Send" : "Recv";
        UInt32 len = Convert.ToUInt32(data.PayloadByName("totalLen"));
        bool flag = Convert.ToBoolean(data.PayloadByName("truncated"));

        object payloadData = data.PayloadByName("data");
        string msg;
        if (payloadData is byte[] bytes)
            msg = Encoding.UTF8.GetString(bytes);
        else if (payloadData is string s)
            msg = s;
        else
            msg = $"[Unsupported data type: {payloadData?.GetType().Name}]";

        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.WriteLine($"[MCP {taskname}] Time: {data.TimeStamp.ToLocalTime()}, " +
                          $"Name: {data.ProcessName}.exe, PID: {data.ProcessID}, " +
                          $"Length: {len} bytes, Flag: {flag}, Message: {msg}");
        Console.ResetColor();
    }
}

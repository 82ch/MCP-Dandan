using Microsoft.Diagnostics.Tracing;
using Microsoft.Diagnostics.Tracing.Parsers;
using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using System;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace ETW
{
    public static class EventDataFormatter
    {
        // ---------------------------------------------------------------------
        // 기본 버전
        // ---------------------------------------------------------------------
        public static string ToStandardJson(TraceEvent data, string eventType)
        {
            long tsNano = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1_000_000L;

            int pid = data.ProcessID;
            string pname = data.ProcessName ?? string.Empty;

            // ProcCmdline에 저장된 값
            string cmd = ProcessTracker.ProcCmdline.TryGetValue(pid, out var recordedCmd) ? recordedCmd : null;

            var result = new
            {
                ts = tsNano,
                producer = "agent-core",
                pid = pid,
                pname = pname,
                eventType = eventType,
                data = eventType switch
                {
                    "Process" => BuildProcess(data, pid, pname, cmd),
                    "File" => BuildFile(data, pid),
                    "NetWork" => BuildNetwork(data, pid, pname, cmd),
                    "MCP" => BuildMcp(data),
                    _ => new { }
                }
            };

            return JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = false });
        }

        // ---------------------------------------------------------------------
        // 오버로드 버전
        // ---------------------------------------------------------------------
        public static string ToStandardJson(TraceEvent data, string eventType, string recoveredCmdline)
        {
            long tsNano = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1_000_000L;

            int pid = data.ProcessID;
            string pname = data.ProcessName ?? string.Empty;

            string cmd = recoveredCmdline ?? string.Empty;

            var result = new
            {
                ts = tsNano,
                producer = "agent-core",
                pid = pid,
                pname = pname,
                eventType = eventType,
                data = eventType switch
                {
                    "Process" => BuildProcess(data, pid, pname, cmd),
                    "File" => BuildFile(data, pid),
                    "NetWork" => BuildNetwork(data, pid, pname, cmd),
                    "MCP" => BuildMcp(data),
                    _ => new { }
                }
            };

            return JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = false });
        }

        // ---------------------------------------------------------------------
        // Process 이벤트 JSON 구성
        // ---------------------------------------------------------------------
        private static object BuildProcess(TraceEvent data, int pid, string pname, string cmd)
        {
            var proc = data as ProcessTraceData;
            int parentPid = proc?.ParentID ?? -1;
            string parentName = ProcessTracker.TrackedPids.TryGetValue(parentPid, out var pName) ? pName : "<unknown>";
            string imageFilename = proc?.ImageFileName ?? string.Empty;

            bool isStart = data.EventName.IndexOf("Start", StringComparison.OrdinalIgnoreCase) >= 0;

            return new
            {
                task = isStart ? "Start" : "Stop",
                pid = pid,
                pname = pname,
                parent = new { pid = parentPid, name = parentName },
                imageFilename = imageFilename,
                commandLine = cmd ?? string.Empty,
                mcpTag = McpHelper.DetermineMcp(pid, cmd, null)
            };
        }

        // ---------------------------------------------------------------------
        // File 이벤트 JSON 구성
        // ---------------------------------------------------------------------
        private static object BuildFile(TraceEvent data, int pid)
        {
            string filePath = string.Empty;

            if (data.PayloadNames.Contains("FileName"))
                filePath = data.PayloadByName("FileName")?.ToString() ?? string.Empty;

            string mcpTag = string.Empty;
            if (ProcessTracker.ProcCmdline.TryGetValue(pid, out var tag))
                mcpTag = McpHelper.DetermineMcp(pid, tag, filePath);

            return new
            {
                task = data.EventName.ToUpperInvariant(),
                pid = pid,
                filePath = filePath,
                mcpTag = mcpTag
            };
        }

        // ---------------------------------------------------------------------
        // Network 이벤트 JSON 구성
        // ---------------------------------------------------------------------
        private static object BuildNetwork(TraceEvent data, int pid, string pname, string cmd)
        {
            var net = data as TcpIpTraceData;
            string mcpTag = McpHelper.DetermineMcp(pid, cmd, null);

            string task;
            if (data.EventName.IndexOf("Send", StringComparison.OrdinalIgnoreCase) >= 0)
                task = "SEND";
            else if (data.EventName.IndexOf("Recv", StringComparison.OrdinalIgnoreCase) >= 0)
                task = "RECV";
            else
                task = "CONNECT";

            return new
            {
                task = task,
                pid = pid,
                pname = pname,
                mcpTag = mcpTag,
                transPort = "tcp",
                src = net?.saddr?.ToString() ?? string.Empty,
                sport = net?.sport ?? 0,
                dst = net?.daddr?.ToString() ?? string.Empty,
                dport = net?.dport ?? 0,
                bytes = net?.size ?? 0
            };
        }

        // ---------------------------------------------------------------------
        // MCP 이벤트 JSON 구성
        // ---------------------------------------------------------------------
        private static object BuildMcp(TraceEvent data)
        {
            // 안전 처리: payload가 없는 경우 방어
            byte[] rawBytes = Array.Empty<byte>();
            if (data.PayloadNames.Contains("data") && data.PayloadByName("data") is byte[] b)
                rawBytes = b;

            string decoded = Encoding.UTF8.GetString(rawBytes);

            bool isRecv = false;
            if (data.PayloadNames.Contains("task") && data.PayloadByName("task") is bool t)
                isRecv = t;

            string task = isRecv ? "SEND" : "RECV"; // 0=recv, 1=send

            return new
            {
                task = task,
                transport = "stdio", //TODO: This is hard coding
                src = data.PayloadByName("SrcPid"),
                message = decoded
            };
        }
    }
}

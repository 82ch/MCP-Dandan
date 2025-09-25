using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Microsoft.Diagnostics.Tracing;

namespace CursorProcessTree
{
    public static class ProcessTracker
    {
        public class ProcessInfo
        {
            public int Pid { get; set; }
            public int ParentPid { get; set; }
            public string Name { get; set; } = "";
            public string CmdLine { get; set; } = "";
        }

        public static readonly Dictionary<int, ProcessInfo> processMap = new();
        public static readonly Dictionary<int, List<int>> treeMap = new();
        public static readonly Dictionary<ulong, string> fileKeyPath = new();
        public static readonly HashSet<int> mcpPids = new();

        public static readonly ConcurrentDictionary<int, string> _pidTypeMap = new();

        public static int rootPid = -1;
        public static string targetProcess = "";

        public static string logPath = "etw_events_log.txt";
        public static StreamWriter logWriter;
        public static readonly object logLock = new();

        public static readonly ConcurrentDictionary<string, long> fileOffsets = new();
        public static readonly ConcurrentDictionary<int, string> pidConnections = new();
        public static readonly ConcurrentDictionary<int, HashSet<string>> seenConnections = new();

        public static string[] excludePrefixes = Array.Empty<string>();

        public static void LogLine(string line)
        {
            string tsLocal = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff");
            lock (logLock)
            {
                logWriter.WriteLine($"[{tsLocal}] {line}");
            }
        }

        public static bool IsChildOfTarget(int pid)
        {
            if (rootPid == -1) return false;

            int current = pid;
            while (processMap.ContainsKey(current))
            {
                if (current == rootPid) return true;
                current = processMap[current].ParentPid;
            }
            return false;
        }

        public static void PrintProcessEvent(string type, ProcessInfo info, string typeLabel, ConsoleColor color)
        {
            int indent = GetIndentLevel(info.Pid);
            string spaces = new string(' ', indent * 2);

            Console.ForegroundColor = color;
            Console.WriteLine($"{spaces}{type} {info.Name} (PID={info.Pid}, PPID={info.ParentPid}, Type={typeLabel})");
            Console.ResetColor();

            Console.ForegroundColor = ConsoleColor.DarkGray;
            Console.WriteLine($"{spaces}   Cmd: {info.CmdLine}");
            Console.ResetColor();
        }

        public static string InferType(string imageName, string cmd)
        {
            string lowerCmd = (cmd ?? "").ToLowerInvariant();
            string lowerName = Path.GetFileName(imageName ?? "").ToLowerInvariant();

            if (lowerName == "cmd.exe") return "cmd";
            if (lowerName == "conhost.exe") return "conhost";
            if (lowerName == "reg.exe") return "reg";
            if (lowerName == "git.exe") return "git";

            if (lowerCmd.Contains("--type=renderer")) return "renderer";
            if (lowerCmd.Contains("--type=gpu")) return "gpu";
            if (lowerCmd.Contains("crashpad")) return "crashpad";
            if (lowerCmd.Contains("network")) return "network";
            if (lowerCmd.Contains("node")) return "node";
            if (lowerCmd.Contains("--type=utility")) return "utility";
            if (lowerCmd.Contains("--type=zygote")) return "zygote";

            if (lowerCmd.Contains("--type="))
            {
                int idx = lowerCmd.IndexOf("--type=");
                int start = idx + 7;
                int end = lowerCmd.IndexOf(' ', start);
                if (end == -1) end = lowerCmd.Length;
                try
                {
                    string t = lowerCmd.Substring(start, end - start).Trim();
                    if (!string.IsNullOrEmpty(t) && t != "main")
                        return t;
                }
                catch { }
            }
            return null;
        }

        public static bool IsPathExcluded(string path)
        {
            if (string.IsNullOrWhiteSpace(path)) return false;
            foreach (var prefix in excludePrefixes)
                if (path.IndexOf(prefix, StringComparison.OrdinalIgnoreCase) >= 0)
                    return true;
            return false;
        }

        public static ulong? TryGetULong(TraceEvent e, string name)
        {
            if (e.PayloadNames == null) return null;
            if (!e.PayloadNames.Any(n => string.Equals(n, name, StringComparison.OrdinalIgnoreCase)))
                return null;
            try
            {
                var v = e.PayloadByName(name);
                return v switch
                {
                    ulong ul => ul,
                    long l => unchecked((ulong)l),
                    uint u => u,
                    int i => unchecked((ulong)i),
                    _ => null
                };
            }
            catch { return null; }
        }

        public static int GetIndentLevel(int pid)
        {
            int depth = 0;
            while (processMap.ContainsKey(pid))
            {
                int parent = processMap[pid].ParentPid;
                if (!processMap.ContainsKey(parent)) break;
                pid = parent;
                depth++;
            }
            return depth;
        }
    }
}

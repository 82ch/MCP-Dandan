using System;
using System.Net;

namespace ETW
{
    public static class McpHelper
    {
        private static readonly (string pattern, string mcp)[] CmdlineToMcp = new[]
        {
            ("weather.py", "weather"),
            ("--mcp=weather", "weather"),
            ("filesystem-server", "filesystem"),
            ("filesystem.py", "filesystem"),
            ("gmail", "gmail"),
            ("oauth", "auth"),
            ("uv.exe", "local-tool"),
        };

        public static string DetermineMcpForNetwork(int pid, string ip, int port)
        {
            if (IPAddress.TryParse(ip, out var addr) && IPAddress.IsLoopback(addr))
            {
                if (ProcessTracker.ProcCmdline.TryGetValue(pid, out var existingTag))
                {
                    var local = ExtractLocalMcpFromTag(existingTag);
                    if (!string.IsNullOrEmpty(local)) return local;
                }
                string cmd = ProcessHelper.TryGetCommandLineForPid(pid);
                if (!string.IsNullOrEmpty(cmd))
                {
                    var byCmd = MapCmdlineToMcp(cmd);
                    if (!string.IsNullOrEmpty(byCmd)) return byCmd;
                }
                return "local";
            }
            return "unknown";
        }

        public static string ExtractLocalMcpFromTag(string tag)
        {
            if (string.IsNullOrEmpty(tag)) return null;
            var lower = tag.ToLowerInvariant();
            if (lower.Contains("(local mcp:"))
            {
                int s = lower.IndexOf("(local mcp:");
                int e = lower.IndexOf(')', s);
                if (s >= 0 && e > s)
                {
                    return tag.Substring(s + "(Local MCP:".Length, e - s - "(Local MCP:".Length).Trim().Trim(':', ' ');
                }
            }
            return null;
        }

        public static string MapCmdlineToMcp(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return null;
            string lower = cmd.ToLowerInvariant();
            foreach (var (pattern, mcp) in CmdlineToMcp)
                if (lower.Contains(pattern.ToLowerInvariant())) return mcp;
            return null;
        }

        public static string TagFromCommandLine(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return "<no-cmd>";
            var mapped = MapCmdlineToMcp(cmd);
            if (!string.IsNullOrEmpty(mapped)) return $"(Local MCP: {mapped}) {TruncateCmd(cmd)}";

            string lower = cmd.ToLowerInvariant();
            if (lower.Contains("--type=utility")) return $"(UtilityProcess) {TruncateCmd(cmd)}";
            if (lower.Contains("--type=gpu")) return $"(GPU) {TruncateCmd(cmd)}";
            if (lower.Contains("--type=renderer")) return $"(Renderer) {TruncateCmd(cmd)}";
            return TruncateCmd(cmd);
        }

        public static string TruncateCmd(string cmd, int max = 120)
        {
            if (string.IsNullOrEmpty(cmd)) return "<no-cmd>";
            return cmd.Length <= max ? cmd : cmd.Substring(0, max) + "...";
        }
    }
}

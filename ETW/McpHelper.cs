using System;
using System.Collections.Generic;
using System.Net;
using System.IO;

namespace ETW
{
    public static class McpHelper
    {
        // PID → MCP 이름 캐시
        private static readonly Dictionary<int, string> McpMap = new();

        /// <summary>
        /// 네트워크 이벤트에서 MCP 추정
        /// </summary>
        public static string DetermineMcpForNetwork(int pid, string ip, int port)
        {
            if (IPAddress.TryParse(ip, out var addr) && IPAddress.IsLoopback(addr))
            {
                // 이미 태그에 Local MCP 이름이 있으면 재사용
                if (ProcessTracker.ProcCmdline.TryGetValue(pid, out var existingTag))
                {
                    var local = ExtractLocalMcpFromTag(existingTag);
                    if (!string.IsNullOrEmpty(local)) return local;
                }

                // 커맨드라인에서 추출
                string cmd = ProcessHelper.TryGetCommandLineForPid(pid);
                if (!string.IsNullOrEmpty(cmd))
                {
                    var byCmd = ExtractMcpFromCmd(cmd);
                    if (!string.IsNullOrEmpty(byCmd)) return byCmd;
                }
                return "local";
            }
            return "unknown";
        }

        /// <summary>
        /// [MCP MAP] 라인에서 직접 등록 (PID → Name)
        /// </summary>
        public static void RegisterMcp(int pid, string name)
        {
            if (!string.IsNullOrEmpty(name))
                McpMap[pid] = name;
        }

        /// <summary>
        /// MCP 이름 결정 (PID/CommandLine/Path 기반)
        /// </summary>
        public static string DetermineMcp(int pid, string cmd, string path)
        {
            // 1) 캐시된 것 있으면 그대로
            if (McpMap.TryGetValue(pid, out var cached))
                return cached;

            // 2) 파일명 기반 (mcp-server-<name>.log) → 가장 신뢰도 높음
            if (!string.IsNullOrEmpty(path))
            {
                var file = Path.GetFileName(path).ToLowerInvariant();
                if (file.StartsWith("mcp-server-"))
                {
                    var name = file.Replace("mcp-server-", "").Replace(".log", "");
                    McpMap[pid] = name;
                    return name;
                }
            }

            // 3) 커맨드라인 기반 (--mcp=xxx) → 확실
            var fromCmd = ExtractMcpFromCmd(cmd);
            if (!string.IsNullOrEmpty(fromCmd))
            {
                McpMap[pid] = fromCmd;
                return fromCmd;
            }

            // 4) 경로 기반 (Claude Extensions\ant.dir.ant.anthropic.<mcp>\...) 
            //    단, "filesystem"은 무조건 지정하지 않고 fallback으로만 사용
            var fromPath = ExtractMcpFromPath(path);
            if (!string.IsNullOrEmpty(fromPath) && fromPath != "filesystem")
            {
                McpMap[pid] = fromPath;
                return fromPath;
            }

            // 5) Filesystem은 특수 규칙 (NodeService + anthropic.filesystem 조합일 때만)
            if (!string.IsNullOrEmpty(cmd) &&
                cmd.IndexOf("node.mojom.NodeService", StringComparison.OrdinalIgnoreCase) >= 0 &&
                cmd.IndexOf("anthropic.filesystem", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                McpMap[pid] = "Filesystem";
                return "Filesystem";
            }

            // 6) 기본 분류
            if (!string.IsNullOrEmpty(cmd))
            {
                var lower = cmd.ToLowerInvariant();
                if (lower.Contains("--type=utility")) return "UtilityProcess";
                if (lower.Contains("--type=gpu")) return "GPU";
                if (lower.Contains("--type=renderer")) return "Renderer";
            }

            return "unknown";
        }

        /// <summary>
        /// "(Local MCP: xxx)" 문자열에서 xxx 추출
        /// </summary>
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
                    return tag.Substring(
                        s + "(Local MCP:".Length,
                        e - s - "(Local MCP:".Length
                    ).Trim().Trim(':', ' ');
                }
            }
            return null;
        }

        /// <summary>
        /// Claude Extensions 경로에서 MCP 이름 추출
        /// </summary>
        public static string ExtractMcpFromPath(string path)
        {
            if (string.IsNullOrEmpty(path)) return null;
            var lower = path.ToLowerInvariant();
            var marker = "claude extensions\\ant.dir.ant.anthropic.";
            int idx = lower.IndexOf(marker);
            if (idx >= 0)
            {
                string after = lower.Substring(idx + marker.Length);
                return after.Split('\\', '/')[0];
            }
            return null;
        }

        /// <summary>
        /// --mcp=xxx 옵션에서 MCP 이름 추출
        /// </summary>
        public static string ExtractMcpFromCmd(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return null;
            var lower = cmd.ToLowerInvariant();
            int idx = lower.IndexOf("--mcp=");
            if (idx >= 0)
            {
                return lower.Substring(idx + 6).Split(' ', '"')[0];
            }
            return null;
        }

        /// <summary>
        /// 로그에 출력될 MCP 태그 (CommandLine 포함)
        /// </summary>
        public static string TagFromCommandLine(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return "<no-cmd>";
            var mapped = ExtractMcpFromCmd(cmd);
            if (!string.IsNullOrEmpty(mapped)) return $"(Local MCP: {mapped}) {TruncateCmd(cmd)}";

            string lower = cmd.ToLowerInvariant();
            if (lower.Contains("--type=utility")) return $"(UtilityProcess) {TruncateCmd(cmd)}";
            if (lower.Contains("--type=gpu")) return $"(GPU) {TruncateCmd(cmd)}";
            if (lower.Contains("--type=renderer")) return $"(Renderer) {TruncateCmd(cmd)}";
            return TruncateCmd(cmd);
        }

        /// <summary>
        /// 긴 CommandLine 줄임
        /// </summary>
        public static string TruncateCmd(string cmd, int max = 120)
        {
            if (string.IsNullOrEmpty(cmd)) return "<no-cmd>";
            return cmd.Length <= max ? cmd : cmd.Substring(0, max) + "...";
        }
    }
}

using System;
using System.Collections.Generic;
using System.Net;
using System.IO;
using System.Text.RegularExpressions;

namespace ETW
{
    public static class McpHelper
    {
        // PID + 파일경로 기반 MCP 캐시
        private static readonly Dictionary<(int, string), string> McpMap = new();

        // 네트워크 이벤트에서 MCP 추정
        public static string DetermineMcpForNetwork(int pid, string ip, int port)
        {
            if (IPAddress.TryParse(ip, out var addr) && IPAddress.IsLoopback(addr))
            {
                string cmd = ProcessHelper.TryGetCommandLineForPid(pid);
                if (!string.IsNullOrEmpty(cmd))
                {
                    var byCmd = ExtractMcpFromCmd(cmd);
                    if (!string.IsNullOrEmpty(byCmd)) return byCmd;
                }
            }
            return "unknown";
        }

        public static void RegisterMcp(int pid, string name, string path = null)
        {
            if (!string.IsNullOrEmpty(name))
            {
                var key = (pid, NormalizePathKey(path));
                McpMap[key] = name;
            }
        }

        // ----------------------------------------------------------------------
        // MCP 판별 로직 (경로 → 캐시 → 커맨드라인 → 확장 → Claude 기본 로그 순)
        // ----------------------------------------------------------------------
        public static string DetermineMcp(int pid, string cmd, string path)
        {
            var key = (pid, NormalizePathKey(path));
            string result = null;

            // Claude 확장 MCP 로그 (mcp-server-*.log) — 가장 우선
            if (!string.IsNullOrEmpty(path))
            {
                var lower = path.ToLowerInvariant();
                var match = Regex.Match(lower, @"\\logs\\mcp-server-([a-z0-9_\-]+)\.log");
                if (match.Success)
                {
                    result = Capitalize(match.Groups[1].Value);
                    McpMap[key] = result;
                    return result;
                }
            }

            // 2캐시 조회 (PID+Path 단위)
            if (McpMap.TryGetValue(key, out var cached))
                return cached;

            // 커맨드라인 기반 (--mcp=xxx)
            var fromCmd = ExtractMcpFromCmd(cmd);
            if (!string.IsNullOrEmpty(fromCmd))
                result = fromCmd;

            // Claude Extensions 내부 anthropic.<mcp>
            if (string.IsNullOrEmpty(result))
            {
                var fromPath = ExtractMcpFromPath(path);
                if (!string.IsNullOrEmpty(fromPath))
                    result = fromPath;
            }

            // Claude 자체 로그만 (main.log, mcp.log, claude.ai-web.log)
            if (string.IsNullOrEmpty(result) && !string.IsNullOrEmpty(path))
            {
                var lower = path.ToLowerInvariant();
                if (Regex.IsMatch(lower, @"\\logs\\(mcp|main|claude\.ai-web)\.log$"))
                {
                    result = "Claude";
                }
            }

            // 기본 프로세스 분류
            if (string.IsNullOrEmpty(result) && !string.IsNullOrEmpty(cmd))
            {
                var lower = cmd.ToLowerInvariant();
                if (lower.Contains("--type=utility")) result = "UtilityProcess";
                else if (lower.Contains("--type=gpu")) result = "GPU";
                else if (lower.Contains("--type=renderer")) result = "Renderer";
            }

            // fallback 정규화
            result = CanonicalizeMcpTag(result, path, cmd);

            McpMap[key] = result ?? "unknown";
            return result ?? "unknown";
        }

        // -----------------------------------------------------------
        // MCP 이름 자동 추출 (언어 무관, 실행 대상 기반)
        // -----------------------------------------------------------
        public static string CanonicalizeMcpTag(string currentTag, string filePath = null, string cmdLine = null)
        {
            // mcp-server-<tool>.log
            var s = filePath ?? "";
            var m = Regex.Match(s.ToLowerInvariant(), @"\bmcp[-_](?:server[-_])?([a-z0-9_\-]+)\.log\b");
            if (m.Success)
                return Capitalize(m.Groups[1].Value);

            // run <tool>.<ext>
            s = cmdLine ?? "";
            m = Regex.Match(s.ToLowerInvariant(), @"\brun\s+([a-z0-9][a-z0-9_\-]{0,63})\.[a-z0-9]{1,6}\b");
            if (m.Success)
                return Capitalize(m.Groups[1].Value);

            // 명령줄 전체에서 실행 가능한 파일(.py, .js, .ts, .exe 등) 자동 탐지
            string combined = ((cmdLine ?? "") + " " + (filePath ?? "") + " " + (currentTag ?? "")).ToLowerInvariant();
            var matches = Regex.Matches(combined, @"([a-z0-9_\-]+)\.(py|js|ts|mjs|exe|bin|wasm|sh|go|rb|jar|dll|pl)");
            if (matches.Count > 0)
            {
                var last = matches[matches.Count - 1].Groups[1].Value;
                return Capitalize(last);
            }

            // anthropic.<tool> 패턴
            m = Regex.Match(combined, @"anthropic\.([a-z0-9_\-]+)");
            if (m.Success)
                return Capitalize(m.Groups[1].Value);

            // fallback - currentTag / filePath에서 추출
            if (!string.IsNullOrWhiteSpace(currentTag))
            {
                var clean = currentTag.Trim('"', ' ', '\\');
                var last = Path.GetFileNameWithoutExtension(clean);
                if (!string.IsNullOrEmpty(last))
                    return Capitalize(last);
            }

            return "unknown";
        }

        // Claude Extensions 내부 MCP 자동 인식
        public static string ExtractMcpFromPath(string path)
        {
            if (string.IsNullOrEmpty(path))
                return null;

            var lower = path.ToLowerInvariant();

            // Claude Extensions 내부의 MCP 확장 자동 식별
            // ex) Claude Extensions\ant.dir.ant.anthropic.filesystem\server\index.js
            var match = Regex.Match(
                lower,
                @"claude extensions[\\/][^\\\/]*anthropic\.([a-z0-9_\-]+)(?=[\\/])",
                RegexOptions.IgnoreCase
            );

            if (match.Success)
                return Capitalize(match.Groups[1].Value);

            return null;
        }

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

        public static string TagFromCommandLine(string cmd)
        {
            if (string.IsNullOrEmpty(cmd)) return "<no-cmd>";

            var mapped = ExtractMcpFromCmd(cmd);
            if (!string.IsNullOrEmpty(mapped)) return TruncateCmd(cmd);

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

        private static string Capitalize(string name)
        {
            if (string.IsNullOrEmpty(name)) return name;
            return char.ToUpperInvariant(name[0]) + name.Substring(1);
        }

        // 파일 경로를 캐시 키로 안정적으로 만들기 위한 정규화
        private static string NormalizePathKey(string path)
        {
            if (string.IsNullOrEmpty(path)) return "<no-path>";
            try
            {
                var file = Path.GetFileName(path).ToLowerInvariant();
                return string.IsNullOrEmpty(file) ? "<no-path>" : file;
            }
            catch
            {
                return "<no-path>";
            }
        }
    }
}

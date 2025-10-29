using Microsoft.Diagnostics.Tracing.Parsers.Kernel;
using Microsoft.Diagnostics.Utilities;
using Microsoft.Win32;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading.Tasks;

public static class MCPRegistry
{
    // 기본적으로 호스트별 예상 config 파일 경로
    private static readonly Dictionary<string, string> ConfigFilePath = new Dictionary<string, string>
    {
        { "claude", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Claude", "claude_desktop_config.json") },
        { "cursor", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".cursor", "mcp.json") }
    };

    // CommandLine (키) -> ServerName (값)
    // 대소문자 무시
    private static readonly Dictionary<string, string> Config = new(StringComparer.OrdinalIgnoreCase);

    // PID -> name tag
    private static readonly Dictionary<int, string> MCPNameTag = new();

    // 간단한 락 객체 (동시성 안전)
    private static readonly object _lock = new object();

    public static string? GetFullCommandLine(string cmd)
    {
        // Try to resolve to a full path; if not possible, return null to let caller handle fallback.
        string? fullPath = GetFullPath(cmd);
        if (fullPath == null)
        {
            return null;
        }

        return WrapWithLauncherIfNeeded(fullPath);
    }

    /// <summary>
    /// PATH에서 명령어의 전체 경로를 찾습니다.
    /// </summary>
    static string? GetFullPath(string command)
    {
        if (string.IsNullOrEmpty(command))
            return null;

        // 이미 경로를 포함하면 바로 반환
        try
        {
            if (File.Exists(command))
                return Path.GetFullPath(command);
        }
        catch { /* 경로 권한 등 이유로 실패할 수 있음 */ }

        string? pathEnv = Environment.GetEnvironmentVariable("PATH");
        if (string.IsNullOrEmpty(pathEnv))
            return null;

        string[] paths = pathEnv.Split(Path.PathSeparator, StringSplitOptions.RemoveEmptyEntries);

        // PATHEXT 환경 변수에서 실행 가능 확장자 목록 가져오기
        string[] exts = (Environment.GetEnvironmentVariable("PATHEXT") ?? ".EXE;.CMD;.BAT")
                                .ToLowerInvariant()
                                .Split(';', StringSplitOptions.RemoveEmptyEntries);

        foreach (string dir in paths)
        {
            string trimmed = dir.Trim();
            if (trimmed.Length == 0) continue;

            string candidate = Path.Combine(trimmed, command);

            foreach (string ext in exts)
            {
                string candidateWithExt = candidate + ext;
                try
                {
                    if (File.Exists(candidateWithExt))
                        return Path.GetFullPath(candidateWithExt);
                }
                catch { }
            }
        }

        return null;
    }

    /// <summary>
    /// 스크립트 파일(.cmd, .bat)을 런처(cmd.exe)로 감쌉니다.
    /// </summary>
    static string WrapWithLauncherIfNeeded(string fullPath)
    {
        var ext = Path.GetExtension(fullPath).ToLowerInvariant();
        var systemDir = Environment.GetFolderPath(Environment.SpecialFolder.System);

        if (ext == ".cmd" || ext == ".bat")
        {
            var cmdExe = Path.Combine(systemDir, "cmd.exe");
            return $"{cmdExe} /c \"{fullPath}\"";
        }

        return fullPath;
    }

    public static void LoadConfig()
    {
        try
        {
            if (!ConfigFilePath.TryGetValue(Program.TargetProcName, out string? config) || config == null)
            {
                Console.WriteLine($"[INFO] MCP config file not specified for '{Program.TargetProcName}'.");
                return;
            }

            if (!File.Exists(config))
            {
                Console.WriteLine($"[ERROR] MCP Config file not found: {config}");
                return;
            }

            string json = File.ReadAllText(config);
            var root = JsonNode.Parse(json);
            var mcpServers = root?["mcpServers"]?.AsObject();
            if (mcpServers == null) return;

            // 각 서버 설정을 순회하며 처리
            foreach (var server in mcpServers)
            {
                string name = server.Key ?? ""; // "weather", "filesystem" 등
                var cmd_args = server.Value;

                string? cmd = cmd_args?["command"]?.GetValue<string>();
                var args = cmd_args?["args"]?.AsArray();

                if (!string.IsNullOrEmpty(cmd) && args != null)
                {
                    // GetFullCommandLine 실패시 원본 cmd로 대체
                    string? full = GetFullCommandLine(cmd);
                    if (string.IsNullOrEmpty(full))
                        full = cmd;

                    string[] safeArgs = args.Select(a => a?.ToString() ?? string.Empty).ToArray();
                    string cmdline = $"{full} {string.Join(" ", safeArgs)}".Trim();

                    lock (_lock)
                    {
                        Config[cmdline] = name;
                    }
                    Console.WriteLine($"[INFO] Loaded MCP server config from '{config}': {name} <- {cmdline}");
                }
            }

            // --- 2. Claude의 경우, Claude Extensions 폴더 추가로 스캔 ---
            if (Program.TargetProcName == "claude")
            {
                LoadClaudeExtensions();
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[ERROR] Exception while reading config file: {ex.Message}");
        }
    }

    private static string ExpandVariables(string input, string dir)
    {
        if (string.IsNullOrEmpty(input))
            return input;
        string expanded = input.Replace("${__dirname}", dir, StringComparison.OrdinalIgnoreCase);

        if (expanded.Contains(" ") && !expanded.StartsWith("\""))
        {
            return $"\"{expanded}\"";
        }
        return expanded;
    }

    private static void LoadClaudeExtensions()
    {
        string extensionsPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Claude", "Claude Extensions");
        if (!Directory.Exists(extensionsPath))
        {
            Console.WriteLine($"[INFO] Claude extensions directory not found: {extensionsPath}");
            return;
        }

        foreach (string dir in Directory.GetDirectories(extensionsPath))
        {
            string manifestPath = Path.Combine(dir, "manifest.json");
            try
            {
                string json = File.ReadAllText(manifestPath);
                var root = JsonNode.Parse(json);

                var config = root?["server"]?["mcp_config"];
                string? name = root?["name"]?.GetValue<string>();

                string? cmd = config?["command"]?.GetValue<string>();
                var args = config?["args"]?.AsArray();

                if (!string.IsNullOrEmpty(cmd) && args != null)
                {
                    string? full = GetFullCommandLine(cmd);
                    if (string.IsNullOrEmpty(full))
                        full = cmd;

                    string[] expArgs = args.Select(arg =>
                        ExpandVariables(arg?.ToString() ?? string.Empty, dir)
                    ).ToArray();
                    string cmdline = $"{full} {string.Join(" ", expArgs)}".Trim();

                    lock (_lock)
                    {
                        Config[cmdline] = name ?? "";
                    }
                    Console.WriteLine($"[INFO] Loaded MCP extension config from '{manifestPath}': {name} <- {cmdline}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Failed to process extensions '{manifestPath}': {ex.Message}");
            }
        }
    }

    /// <summary>
    /// 주어진 PID와 커맨드라인을 기반으로 MCP 서버인지 판정하고, 태그를 설정합니다.
    /// </summary>
    public static string Submit(int pid, string cmd)
    {
        if (cmd == null) cmd = "";

        // 1) 정규식 기반 자동 감지 (가장 명확한 매칭이므로 먼저 시도)
        var match = System.Text.RegularExpressions.Regex.Match(
            cmd,
            @"@modelcontextprotocol[/\\]server-([a-zA-Z0-9_-]+)",
            System.Text.RegularExpressions.RegexOptions.IgnoreCase
        );

        if (match.Success)
        {
            string serverName = match.Groups[1].Value;
            Console.WriteLine($"[INFO] Registered MCP server by regex: PID={pid}, Server='{serverName}'");
            SetNameTag(pid, serverName);
            return serverName;
        }

        // 2) Config 딕셔너리의 키들을 돌면서 매칭으로 탐색 (대소문자 무시)
        lock (_lock)
        {
            foreach (var kv in Config)
            {
                string knownCmd = kv.Key ?? "";
                string serverName = kv.Value ?? "";

                if (string.IsNullOrWhiteSpace(knownCmd))
                    continue;

                try
                {
                    // 전체 매칭 (완전 일치 또는 포함 관계)
                    if (!string.IsNullOrEmpty(cmd) &&
                        cmd.IndexOf(knownCmd, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        Console.WriteLine($"[INFO] Registered MCP server by config match: PID={pid}, Server='{serverName}'");
                        SetNameTag(pid, serverName);
                        return serverName;
                    }

                    // 실행 파일명 기반 매칭 (예: python.exe, node.exe 등)
                    // knownCmd에서 주요 실행 파일 추출
                    var knownTokens = knownCmd.Split(new[] { ' ', '/', '\\' }, StringSplitOptions.RemoveEmptyEntries);

                    // 의미있는 토큰만 필터링 (최소 길이 5자 이상, 경로 구분자나 인자가 아닌 것)
                    var significantTokens = knownTokens.Where(t =>
                        t.Length >= 5 &&
                        !t.StartsWith("-") &&
                        !t.StartsWith("/") &&
                        (t.Contains(".exe") || t.Contains(".py") || t.Contains(".js") || t.Contains("server"))
                    ).ToList();

                    foreach (var token in significantTokens)
                    {
                        if (cmd.IndexOf(token, StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            Console.WriteLine($"[INFO] Registered MCP server by token match: PID={pid}, Server='{serverName}', Token='{token}'");
                            SetNameTag(pid, serverName);
                            return serverName;
                        }
                    }
                }
                catch { /* 비교 실패는 무시하고 계속 */ }
            }
        }

        // 3) 호스트별 전용 로직 (확장 포인트)
        if (Program.TargetProcName == "claude")
        {
            // 필요하면 claude 전용 heuristic 을 추가
        }
        if (Program.TargetProcName == "cursor")
        {
            // 필요하면 cursor 전용 heuristic 을 추가
        }

        // 4) 어떤 것도 매칭되지 않으면 기본적으로 Host 이름으로 태그를 설정
        var finalName = SetNameTag(pid, Program.TargetProcName);
        return finalName;
    }

    public static void Remove(int pid)
    {
        lock (_lock)
        {
            if (MCPNameTag.ContainsKey(pid))
                MCPNameTag.Remove(pid);
        }
    }

    public static string SetNameTag(int pid, string name)
    {
        lock (_lock)
        {
            MCPNameTag[pid] = name ?? string.Empty;
        }
        return name ?? string.Empty;
    }

    public static string GetNameTag(int pid)
    {
        lock (_lock)
        {
            if (MCPNameTag.TryGetValue(pid, out string? name))
            {
                return name ?? string.Empty;
            }
        }
        return string.Empty;
    }
}

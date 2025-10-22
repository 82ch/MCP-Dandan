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
    private static readonly Dictionary<string, string> ConfigFilePath = new Dictionary<string, string>
    {
        { "claude", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Claude", "claude_desktop_config.json") },
        { "cursor", Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".cursor", "mcp.json") }
    };
    private static readonly Dictionary<string, string> Config = new(StringComparer.OrdinalIgnoreCase); // CommandLine(대소문자 무시) to ServerName
    private static readonly Dictionary<int, string> MCPNameTag = new(); // PID to Name Tag

    public static string? GetFullCommandLine(string cmd)
    {
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
        // 명령어가 이미 경로를 포함하면 바로 반환
        if (File.Exists(command))
            return Path.GetFullPath(command);

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

            // e.g., "C:\Program Files\nodejs\npx"
            string candidate = Path.Combine(trimmed, command);

            // 확장자 붙여서 검사
            foreach (string ext in exts)
            {
                string candidateWithExt = candidate + ext;
                if (File.Exists(candidateWithExt))
                    return Path.GetFullPath(candidateWithExt);
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

        // .cmd, .bat -> cmd.exe /c "<path>"
        if (ext == ".cmd" || ext == ".bat")
        {
            var cmdExe = Path.Combine(systemDir, "cmd.exe");
            return $"{cmdExe} /c \"{fullPath}\"";
        }

        // 그 외(.exe, .com 등)는 그대로 반환
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
                string name = server.Key; // "weather", "filesystem" 등
                var cmd_args = server.Value;

                string? cmd = cmd_args?["command"]?.GetValue<string>();
                var args = cmd_args?["args"]?.AsArray();

                if (!string.IsNullOrEmpty(cmd) && args != null)
                {
                    // "full"와 "args" 배열을 합쳐 하나의 전체 커맨드라인 문자열로 만듭니다.
                    string? full = GetFullCommandLine(cmd);
                    string cmdline = $"{full} {string.Join(" ", args.Select(arg => arg.ToString()))}";

                    // MCPServers 딕셔너리에 저장합니다.
                    Config[cmdline] = name;
                    Console.WriteLine($"[INFO] Loaded MCP server config from '{config}': {name} <- {cmdline}");
                }
            }
            // --- 2. Claude의 경우, Claude Extentions 폴더 추가로 스캔 ---
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
        string expanded = input
            .Replace("${__dirname}", dir, StringComparison.OrdinalIgnoreCase);

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
                    string[] expArgs = args.Select(arg =>
                        ExpandVariables(arg?.ToString() ?? string.Empty, dir)
                    ).ToArray();
                    string cmdline = $"{full} {string.Join(" ", expArgs)}";
                    Config[cmdline] = name;
                    Console.WriteLine($"[INFO] Loaded MCP extension config from '{manifestPath}': {name} <- {cmdline}");
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[ERROR] Failed to process extentions '{manifestPath}': {ex.Message}");
            }
        }
    }

    public static string Submit(int pid, string cmd)
    {
        // 1) Config 파일에 정의된 커맨드라인과 일치하는지 먼저 확인
        if (Config.TryGetValue(cmd, out string? ServerName))
        {
            Console.WriteLine($"[INFO] Registered MCP server by config: PID={pid}, Server='{ServerName}'");
            return SetNameTag(pid, ServerName);
        }

        // 2) Config 파일에 매칭되는 것이 없을 경우, MCP Host에 따라 전용 로직 수행
        if (Program.TargetProcName == "claude")
        {

        }
        if (Program.TargetProcName == "cursor")
        {

        }

        // 3) 어느 것도 매칭되지 않으면 MCPHost로 기본 설정 
        return SetNameTag(pid, Program.TargetProcName);
    }

    public static void Remove(int pid)
    {
        MCPNameTag.Remove(pid);
    }

    public static string SetNameTag(int pid, string name)
    {
        MCPNameTag[pid] = name;
        return name;
    }

    public static string GetNameTag(int pid)
    {
        if (MCPNameTag.TryGetValue(pid, out string? name))
        {
            return name;
        }
        return string.Empty; // 찾지 못하면 빈 문자열 반환
    }
}

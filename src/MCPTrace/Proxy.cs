using System;
using System.Diagnostics;
using System.Linq;
using System.Management;
using System.Threading;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;

public static class Proxy
{
    private static Process? _mitmProcess;
    private static int _currentPid = 0;
    private static TcpClient? _collectorClient;

    private const string TARGET_SUBSTR = "network.mojom.NetworkService";
    private const string MITM_EXE = "mitmdump";
    private const string MITM_ADDON = "./Logger.py";
    private const int MITM_PORT = 8080;
    private const string COLLECTOR_HOST = "127.0.0.1";
    private const int COLLECTOR_PORT = 8888;

    // Program.cs에서 cts.Token 넘겨서 호출하는 진입점 (유지)
    public static void StartWatcherAsync(CancellationToken token)
    {
        // 기존 동작을 유지하기 위해 약간의 지연(초기화 시간)
        Thread.Sleep(3000);

        // Collector에 연결 시도
        ConnectToCollector();

        var th = new Thread(() => WatchLoop(token));
        th.IsBackground = true;
        th.Start();
    }

    private static void ConnectToCollector()
    {
        try
        {
            _collectorClient = new TcpClient();
            _collectorClient.Connect(COLLECTOR_HOST, COLLECTOR_PORT);
            Console.WriteLine($"[ProxyRunner] Connected to Collector at {COLLECTOR_HOST}:{COLLECTOR_PORT}");
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to connect to Collector: {ex.Message}");
            _collectorClient = null;
        }
    }

    private static void SendToCollector(string jsonData)
    {
        if (_collectorClient == null || !_collectorClient.Connected)
        {
            // 재연결 시도
            ConnectToCollector();
            if (_collectorClient == null || !_collectorClient.Connected)
                return;
        }

        try
        {
            var stream = _collectorClient.GetStream();
            var bytes = Encoding.UTF8.GetBytes(jsonData);

            // 길이 전송 (CRLF 대신 LF만 사용)
            var lengthLine = Encoding.UTF8.GetBytes($"{bytes.Length}\n");
            stream.Write(lengthLine, 0, lengthLine.Length);

            // 데이터 전송
            stream.Write(bytes, 0, bytes.Length);

            // 구분자 전송
            var separator = Encoding.UTF8.GetBytes("\n");
            stream.Write(separator, 0, separator.Length);

            stream.Flush();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to send to Collector: {ex.Message}");
            _collectorClient?.Close();
            _collectorClient = null;
        }
    }

    // 대상 프로세스를 WMI(Win32_Process.CommandLine)로만 찾음
    private static Process? FindTargetProcess()
    {
        try
        {
            string target = Program.TargetProcName.ToLowerInvariant();

            foreach (var p in Process.GetProcesses())
            {
                try
                {
                    string name = p.ProcessName.ToLowerInvariant();
                    if (!name.Contains(target))
                        continue;

                    string cmdline = GetCommandLine(p);
                    if (string.IsNullOrEmpty(cmdline))
                        continue;

                    if (cmdline.IndexOf(TARGET_SUBSTR, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        // 대상 발견
                        return p;
                    }
                }
                catch
                {
                    // 프로세스 접근 불가 등은 무시
                    continue;
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] FindTargetProcess error: {ex.Message}");
        }
        return null;
    }

    // Windows WMI 기반 CommandLine 조회
    private static string GetCommandLine(Process p)
    {
        try
        {
            if (!OperatingSystem.IsWindows())
                return "";

            using var searcher = new ManagementObjectSearcher(
                $"SELECT CommandLine FROM Win32_Process WHERE ProcessId = {p.Id}");

            foreach (var obj in searcher.Get().Cast<ManagementObject>())
            {
                string? cmd = obj["CommandLine"]?.ToString();
                if (!string.IsNullOrEmpty(cmd))
                    return cmd;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner:WMI] Error for PID {p.Id}: {ex.Message}");
        }
        return "";
    }

    private static void StartMitmDump(int targetPid)
    {
        var psi = new ProcessStartInfo
        {
            FileName = MITM_EXE,
            Arguments = $"--mode local:{targetPid} -p {MITM_PORT} -s \"{MITM_ADDON}\" --set http2=true --set stream_large_bodies=1 -v",
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding = System.Text.Encoding.UTF8
        };

        _mitmProcess = new Process { StartInfo = psi, EnableRaisingEvents = true };

        _mitmProcess.OutputDataReceived += (s, e) =>
        {
            if (!string.IsNullOrEmpty(e.Data) && e.Data.Contains("\"eventType\":\"MCP\""))
            {
                // MCP 이벤트를 Collector로 전송
                try
                {
                    var mitmData = JsonSerializer.Deserialize<JsonElement>(e.Data);
                    var collectorEvent = new
                    {
                        source = "mitm",
                        type = "MCP",
                        timestamp = DateTime.UtcNow.ToString("o"),
                        data = mitmData
                    };
                    string json = JsonSerializer.Serialize(collectorEvent);
                    SendToCollector(json);
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"[ProxyRunner] Failed to parse MCP event: {ex.Message}");
                }
            }
        };

        _mitmProcess.ErrorDataReceived += (s, e) =>
        {
            if (!string.IsNullOrWhiteSpace(e.Data))
                Console.Error.WriteLine($"[mitmdump:ERR] {e.Data}");
        };

        _mitmProcess.Exited += (s, e) =>
        {
            Console.WriteLine($"[ProxyRunner] mitmdump exited (PID={_currentPid})");
            _mitmProcess = null;
            _currentPid = 0;
        };

        Console.WriteLine($"[ProxyRunner] Launching mitmdump for PID {targetPid}...");
        try
        {
            _mitmProcess.Start();
            _mitmProcess.BeginOutputReadLine();
            _mitmProcess.BeginErrorReadLine();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to start mitmdump: {ex.Message}");
            _mitmProcess = null;
            _currentPid = 0;
        }
    }

    private static void KillProcessTreeSafely(int pid)
    {
        try
        {
            var proc = Process.GetProcessById(pid);
            string pname = proc.ProcessName.ToLowerInvariant();
            if (pname != "mitmdump" && pname != "mitmproxy_windows" && pname != "windows-redirector")
            {
                Console.WriteLine($"[ProxyRunner] refusing to kill {pname} (PID={pid})");
                return;
            }

            if (!proc.HasExited)
            {
                proc.CloseMainWindow();
                if (!proc.WaitForExit(1500))
                    proc.Kill(true);
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] KillProcessTreeSafely error: {ex.Message}");
        }
    }

    public static void StopProxy()
    {
        if (_mitmProcess == null || _mitmProcess.HasExited)
        {
            _mitmProcess = null;
            _currentPid = 0;
            return;
        }

        try
        {
            Console.WriteLine($"[ProxyRunner] Stopping mitmdump (PID={_mitmProcess.Id}) safely...");
            KillProcessTreeSafely(_mitmProcess.Id);
            _mitmProcess.WaitForExit(3000);
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] StopProxy error: {ex.Message}");
        }
        finally
        {
            _mitmProcess = null;
            _currentPid = 0;
        }
    }

    private static void WatchLoop(CancellationToken token)
    {
        Console.WriteLine("[ProxyRunner] Started WMI-driven proxy watcher loop.");

        while (!token.IsCancellationRequested)
        {
            try
            {
                var proc = FindTargetProcess();
                int pid = proc?.Id ?? 0;

                if (pid == 0)
                {
                    if (_mitmProcess != null && !_mitmProcess.HasExited)
                    {
                        Console.WriteLine($"[ProxyRunner] No valid target → stopping mitmdump.");
                        StopProxy();
                    }

                    Thread.Sleep(1000);
                    continue;
                }

                if (_mitmProcess == null || _mitmProcess.HasExited)
                {
                    Console.WriteLine($"[ProxyRunner] Target PID {pid} detected → starting mitmdump.");
                    StartMitmDump(pid);
                    _currentPid = pid;
                }
                else if (pid != _currentPid)
                {
                    Console.WriteLine($"[ProxyRunner] Target PID changed {_currentPid} → {pid}, restarting mitmdump.");
                    StopProxy();
                    StartMitmDump(pid);
                    _currentPid = pid;
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ProxyRunner] Loop error: {ex.Message}");
            }

            Thread.Sleep(1000);
        }

        StopProxy();
        Console.WriteLine("[ProxyRunner] Loop terminated.");
    }
}

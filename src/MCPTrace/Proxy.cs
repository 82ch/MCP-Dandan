using System;
using System.Diagnostics;
using System.Linq;
using System.Management;
using System.Threading;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

public static class Proxy
{
    private static Process? _mitmProcess;
    private static int _currentPid = 0; // transparent 모드: 의미 없음(보조용)
    private static TcpClient? _collectorClient;
    private static readonly object _procLock = new object();

    private const string TARGET_SUBSTR = "network.mojom.NetworkService";
    private const string MITM_EXE = "mitmdump";
    private const string MITM_ADDON = "./Logger.py";
    private const int MITM_PORT = 8080;
    private const string COLLECTOR_HOST = "127.0.0.1";
    private const int COLLECTOR_PORT = 8888;

    private static Thread? _watchThread;

    public static void StartWatcherAsync(CancellationToken token)
    {
        ConnectToCollector();
        EnsureTransparentMitmRunning();

        _watchThread = new Thread(() => WatchLoop(token));
        _watchThread.IsBackground = true;
        _watchThread.Start();
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
            ConnectToCollector();
            if (_collectorClient == null || !_collectorClient.Connected)
                return;
        }

        try
        {
            var stream = _collectorClient.GetStream();
            var bytes = Encoding.UTF8.GetBytes(jsonData);
            var lengthLine = Encoding.UTF8.GetBytes($"{bytes.Length}\n");
            stream.Write(lengthLine, 0, lengthLine.Length);
            stream.Write(bytes, 0, bytes.Length);
            stream.WriteByte((byte)'\n');
            stream.Flush();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to send to Collector: {ex.Message}");
            try { _collectorClient?.Close(); } catch { }
            _collectorClient = null;
        }
    }

    // NOTE: 기존 FindTargetProcess는 유지(필요 시 사용). transparent 모드에선 PID별 mitmdump를 띄우지 않습니다.
    private static Process? FindTargetProcess()
    {
        try
        {
            string targetName = Program.TargetProcName;
            if (!targetName.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))
                targetName += ".exe";

            string wql = $"SELECT ProcessId, CommandLine FROM Win32_Process WHERE Name = '{targetName}'";
            using var searcher = new ManagementObjectSearcher(wql);
            var results = searcher.Get();

            foreach (ManagementObject mo in results)
            {
                try
                {
                    int pid = Convert.ToInt32(mo["ProcessId"]);
                    string? cmd = mo["CommandLine"]?.ToString();

                    if (!string.IsNullOrEmpty(cmd) &&
                        cmd.IndexOf(TARGET_SUBSTR, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        return Process.GetProcessById(pid);
                    }
                }
                catch { continue; }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] FindTargetProcess error: {ex.Message}");
        }
        return null;
    }

    // transparent 미리 띄우기
    private static void EnsureTransparentMitmRunning()
    {
        lock (_procLock)
        {
            if (_mitmProcess != null && !_mitmProcess.HasExited) return;
        }

        var psi = new ProcessStartInfo
        {
            FileName = MITM_EXE,
            Arguments = $"--mode transparent -p {MITM_PORT} -s \"{MITM_ADDON}\" -v",
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            RedirectStandardOutput = true,
            StandardOutputEncoding = System.Text.Encoding.UTF8,
            StandardErrorEncoding = System.Text.Encoding.UTF8
        };

        var proc = new Process { StartInfo = psi, EnableRaisingEvents = true };

        proc.OutputDataReceived += (s, e) =>
        {
            if (string.IsNullOrEmpty(e.Data)) return;
            var line = e.Data.Trim();
            if (!line.Contains("\"eventType\":\"MCP\"")) return;

            try
            {
                using var mitmDoc = JsonDocument.Parse(line);
                var mitmRoot = mitmDoc.RootElement;

                var collectorEvent = new Dictionary<string, object>();

                // ts (ns 단위)
                if (mitmRoot.TryGetProperty("ts", out var tsElement))
                {
                    collectorEvent["ts"] = tsElement.GetInt64();
                }
                else
                {
                    collectorEvent["ts"] = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() * 1000000;
                }

                // producer
                collectorEvent["producer"] = "mitm";

                // pid/pname (transparent 모드에서는 연결로부터 추론)
                int pid = 0;
                string pname = "unknown";
                if (mitmRoot.TryGetProperty("data", out var dataElem))
                {
                    if (dataElem.TryGetProperty("src", out var srcElem))
                    {
                        string? src = srcElem.GetString();
                        if (!string.IsNullOrEmpty(src))
                        {
                            var m = Regex.Match(src, @"(?<ip>[\d\.]+):(?<port>\d+)");
                            if (m.Success)
                            {
                                string ip = m.Groups["ip"].Value;
                                int port = int.Parse(m.Groups["port"].Value);
                                pid = GetPidByLocalEndpoint(ip, port);
                                if (pid != 0)
                                {
                                    try
                                    {
                                        pname = Process.GetProcessById(pid).ProcessName;
                                    }
                                    catch { pname = "unknown"; }
                                }
                            }
                        }
                    }
                }

                collectorEvent["pid"] = pid;
                collectorEvent["pname"] = pname;

                // eventType
                collectorEvent["eventType"] = "MCP";

                // data
                if (mitmRoot.TryGetProperty("data", out var dataElement))
                {
                    collectorEvent["data"] = JsonSerializer.Deserialize<object>(dataElement.GetRawText());
                }

                string json = JsonSerializer.Serialize(collectorEvent);
                SendToCollector(json);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ProxyRunner] Failed to parse MCP event: {ex.Message}");
            }
        };


        proc.ErrorDataReceived += (s, e) =>
        {
            if (!string.IsNullOrWhiteSpace(e.Data))
                Console.Error.WriteLine($"[mitmdump:ERR] {e.Data}");
        };

        proc.Exited += (sender, args) =>
        {
            try
            {
                var exitedProc = sender as Process;
                int exitedPid = exitedProc?.Id ?? -1;
                Console.WriteLine($"[ProxyRunner] transparent mitmdump exited (PID={exitedPid})");

                lock (_procLock)
                {
                    if (ReferenceEquals(_mitmProcess, exitedProc))
                    {
                        _mitmProcess = null;
                        _currentPid = 0;
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ProxyRunner] Exited handler error: {ex.Message}");
            }
        };

        Console.WriteLine("[ProxyRunner] Launching transparent mitmdump...");
        try
        {
            lock (_procLock)
            {
                proc.Start();
                proc.BeginOutputReadLine();
                proc.BeginErrorReadLine();
                _mitmProcess = proc;
                _currentPid = 0;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to start transparent mitmdump: {ex.Message}");
            lock (_procLock) { _mitmProcess = null; _currentPid = 0; }
        }
    }

    // Fallback method: netstat -ano parsing to map local endpoint -> pid (quick & dirty)
    // NOTE: for production, replace with GetExtendedTcpTable P/Invoke for speed/accuracy.
    private static int GetPidByLocalEndpoint(string ip, int port)
    {
        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = "netstat",
                Arguments = "-ano",
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };
            using var p = Process.Start(psi);
            if (p == null) return 0;
            string output = p.StandardOutput.ReadToEnd();
            p.WaitForExit(1000);

            // parse lines like:
            //  TCP    192.168.0.15:51779    160.79.104.10:443    ESTABLISHED    12345
            var lines = output.Split(new[] { "\r\n", "\n" }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var line in lines)
            {
                var trimmed = line.Trim();
                if (!trimmed.StartsWith("TCP", StringComparison.OrdinalIgnoreCase) &&
                    !trimmed.StartsWith("UDP", StringComparison.OrdinalIgnoreCase))
                    continue;

                var parts = Regex.Split(trimmed, @"\s+");
                if (parts.Length < 5) continue;
                var local = parts[1];
                var pidStr = parts[parts.Length - 1];

                // local may be like [::]:80 or 0.0.0.0:8080 or 127.0.0.1:51779
                if (!local.Contains(":")) continue;
                var idx = local.LastIndexOf(':');
                var localPortStr = local.Substring(idx + 1);
                if (!int.TryParse(localPortStr, out int localPort)) continue;

                // optionally check IP match
                var localIp = local.Substring(0, idx);
                // windows may show 0.0.0.0 or [::], so if ip is 0.0.0.0 treat as wildcard
                if (localIp != "0.0.0.0" && localIp != "" && localIp != ip) continue;

                if (localPort == port)
                {
                    if (int.TryParse(pidStr, out int pidVal))
                        return pidVal;
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] GetPidByLocalEndpoint error: {ex.Message}");
        }
        return 0;
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
                try { proc.CloseMainWindow(); } catch { }
                if (!proc.WaitForExit(1500))
                {
                    try { proc.Kill(true); } catch { }
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] KillProcessTreeSafely error: {ex.Message}");
        }
    }

    public static void StopProxy()
    {
        Process? procSnapshot = null;
        lock (_procLock)
        {
            procSnapshot = _mitmProcess;
        }

        if (procSnapshot == null)
        {
            lock (_procLock) { _mitmProcess = null; _currentPid = 0; }
            return;
        }

        try
        {
            Console.WriteLine($"[ProxyRunner] Stopping mitmdump (PID={procSnapshot.Id}) safely...");
            KillProcessTreeSafely(procSnapshot.Id);
            try { procSnapshot.WaitForExit(3000); } catch { }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] StopProxy error: {ex.Message}");
        }
        finally
        {
            lock (_procLock)
            {
                if (ReferenceEquals(_mitmProcess, procSnapshot))
                {
                    _mitmProcess = null;
                    _currentPid = 0;
                }
            }
        }
    }

    private static void WatchLoop(CancellationToken token)
    {
        Console.WriteLine("[ProxyRunner] Started WMI-driven proxy watcher loop (transparent mode).");

        while (!token.IsCancellationRequested)
        {
            try
            {
                lock (_procLock)
                {
                    if (token.IsCancellationRequested) break;

                    if (_mitmProcess == null || _mitmProcess.HasExited)
                    {
                        Console.WriteLine("[ProxyRunner] transparent mitmdump not running → restarting.");
                        Thread.Sleep(1000);
                        EnsureTransparentMitmRunning();
                    }
                }
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"[ProxyRunner] Loop error: {ex.Message}");
            }

            Thread.Sleep(500);
        }

        Console.WriteLine("[ProxyRunner] Loop terminating...");
    }

    public static void StopAll()
    {
        Console.WriteLine("[ProxyRunner] Stop requested.");

        // 루프 종료 보장
        if (_watchThread != null && _watchThread.IsAlive)
        {
            Console.WriteLine("[ProxyRunner] Waiting for watcher loop to finish...");
            _watchThread.Join(2000);
        }

        StopProxy();
        Console.WriteLine("[ProxyRunner] All stopped.");
    }
}

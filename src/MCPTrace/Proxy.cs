using System;
using System.Diagnostics;
using System.IO;
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
    private static int _consecutiveFailures = 0;
    private const int MAX_CONSECUTIVE_FAILURES = 3;

    private const string TARGET_SUBSTR = "network.mojom.NetworkService";
    private const string MITM_EXE = "mitmdump";
    private const string MITM_ADDON = "Logger.py";
    private const int MITM_PORT = 8080;
    private const string COLLECTOR_HOST = "127.0.0.1";
    private const int COLLECTOR_PORT = 8888;

    public static void StartWatcherAsync(CancellationToken token)
    {
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
                catch
                {
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

    private static string FindLoggerPyPath()
    {
        string currentDir = AppDomain.CurrentDomain.BaseDirectory;
        string localPath = Path.Combine(currentDir, MITM_ADDON);
        if (File.Exists(localPath))
        {
            Console.WriteLine($"[ProxyRunner] Found Logger.py at: {localPath}");
            return localPath;
        }

        try
        {
            DirectoryInfo? currentDirInfo = new DirectoryInfo(currentDir);
            DirectoryInfo? binDir = null;

            if (currentDirInfo.Parent?.Parent?.Name.Equals("bin", StringComparison.OrdinalIgnoreCase) == true)
            {
                binDir = currentDirInfo.Parent.Parent;
            }
            else if (currentDirInfo.Parent?.Name.Equals("bin", StringComparison.OrdinalIgnoreCase) == true)
            {
                binDir = currentDirInfo.Parent;
            }

            if (binDir != null)
            {
                DirectoryInfo? projectDir = binDir.Parent;
                if (projectDir != null)
                {
                    string projectLoggerPath = Path.Combine(projectDir.FullName, MITM_ADDON);
                    if (File.Exists(projectLoggerPath))
                    {
                        Console.WriteLine($"[ProxyRunner] Found Logger.py at: {projectLoggerPath}");
                        return projectLoggerPath;
                    }
                }
            }

            DirectoryInfo? searchDir = currentDirInfo;
            for (int i = 0; i < 5 && searchDir != null; i++)
            {
                string searchPath = Path.Combine(searchDir.FullName, MITM_ADDON);
                if (File.Exists(searchPath))
                {
                    Console.WriteLine($"[ProxyRunner] Found Logger.py at: {searchPath}");
                    return searchPath;
                }

                string srcMcpTracePath = Path.Combine(searchDir.FullName, "src", "MCPTrace", MITM_ADDON);
                if (File.Exists(srcMcpTracePath))
                {
                    Console.WriteLine($"[ProxyRunner] Found Logger.py at: {srcMcpTracePath}");
                    return srcMcpTracePath;
                }

                searchDir = searchDir.Parent;
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Error searching for Logger.py: {ex.Message}");
        }

        Console.Error.WriteLine($"[ProxyRunner] Logger.py not found. Searched in and around: {currentDir}");
        return MITM_ADDON;
    }

    private static bool IsPortInUse(int port)
    {
        try
        {
            using (var client = new TcpClient())
            {
                client.Connect("127.0.0.1", port);
                return true;
            }
        }
        catch
        {
            return false;
        }
    }

    private static void StartMitmDump(int targetPid)
    {
        string loggerPath = FindLoggerPyPath();

        if (!File.Exists(loggerPath))
        {
            Console.Error.WriteLine($"[ProxyRunner] ERROR: Logger.py not found at: {loggerPath}");
            Console.Error.WriteLine($"[ProxyRunner] Cannot start mitmdump without Logger.py");
            _consecutiveFailures++;
            return;
        }

        // local:PID 모드에서는 포트 체크가 의미 없음 (투명 프록시)
        // 대신 기존 mitmdump 프로세스만 정리
        try
        {
            var processes = Process.GetProcessesByName("mitmdump");
            foreach (var proc in processes)
            {
                try
                {
                    // 이미 실행 중인 mitmdump이 있으면 정리
                    if (proc.Id != _mitmProcess?.Id)
                    {
                        Console.WriteLine($"[ProxyRunner] Killing old mitmdump process (PID={proc.Id})");
                        proc.Kill(true);
                        proc.WaitForExit(2000);
                    }
                }
                catch { }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to clean up old processes: {ex.Message}");
        }

        // local:PID 방식 사용
        var psi = new ProcessStartInfo
        {
            FileName = MITM_EXE,
            Arguments = $"--mode local:{targetPid} -p {MITM_PORT} -s \"{loggerPath}\" --set http2=true --set stream_large_bodies=1",
            UseShellExecute = false,
            CreateNoWindow = true, // 백그라운드 실행
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
                try
                {
                    using var mitmDoc = JsonDocument.Parse(e.Data);
                    var mitmRoot = mitmDoc.RootElement;

                    var collectorEvent = new Dictionary<string, object>();

                    // 안전한 ts 계산: Ticks 기반으로 나노초 생성 (overflow 없음)
                    if (mitmRoot.TryGetProperty("ts", out var tsElement))
                    {
                        // 원격에서 보내온 ts가 이미 있으면 그대로 사용
                        collectorEvent["ts"] = tsElement.GetInt64();
                    }
                    else
                    {
                        // Unix epoch 이후 ticks(100ns) 단위를 나노초로 변환
                        long ns = (DateTimeOffset.UtcNow.Ticks - DateTimeOffset.UnixEpoch.Ticks) * 100L;
                        collectorEvent["ts"] = ns;
                    }

                    collectorEvent["producer"] = "remote";
                    collectorEvent["pid"] = targetPid;
                    collectorEvent["pname"] = Program.TargetProcName;
                    collectorEvent["eventType"] = "MCP";

                    if (mitmRoot.TryGetProperty("data", out var dataElement))
                    {
                        collectorEvent["data"] = JsonSerializer.Deserialize<object>(dataElement.GetRawText());
                    }

                    string json = JsonSerializer.Serialize(collectorEvent);
                    SendToCollector(json);

                    _consecutiveFailures = 0;
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
            {
                Console.Error.WriteLine($"[mitmdump:ERR] {e.Data}");
                // Python traceback이나 중요한 에러 감지
                if (e.Data.Contains("Error") || e.Data.Contains("Traceback") || e.Data.Contains("Exception"))
                {
                    Console.Error.WriteLine($"[ProxyRunner] CRITICAL ERROR detected in mitmdump output");
                }
            }
        };

        _mitmProcess.Exited += (s, e) =>
        {
            Console.WriteLine($"[ProxyRunner] mitmdump exited (PID={_currentPid})");
            _mitmProcess = null;
            _currentPid = 0;
            _consecutiveFailures++;
        };

        Console.WriteLine($"[ProxyRunner] Launching mitmdump for PID {targetPid} (local mode)...");
        Console.WriteLine($"[ProxyRunner] Logger.py path: {loggerPath}");

        // 디버깅: mitmdump 명령줄 전체 출력
        string fullCommand = $"{MITM_EXE} --mode local:{targetPid} -p {MITM_PORT} -s \"{loggerPath}\" --set http2=true --set stream_large_bodies=1";
        Console.WriteLine($"[ProxyRunner] Full command: {fullCommand}");

        try
        {
            _mitmProcess.Start();
            _mitmProcess.BeginOutputReadLine();
            _mitmProcess.BeginErrorReadLine();

            // 프로세스가 즉시 종료되는지 확인 (500ms 대기)
            Thread.Sleep(500);

            if (_mitmProcess.HasExited)
            {
                int exitCode = _mitmProcess.ExitCode;
                Console.Error.WriteLine($"[ProxyRunner] mitmdump exited immediately with code {exitCode}");
                _mitmProcess = null;
                _currentPid = 0;
                _consecutiveFailures++;
                return;
            }

            Console.WriteLine($"[ProxyRunner] mitmdump process started successfully (PID={_mitmProcess.Id})");
            _consecutiveFailures = 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[ProxyRunner] Failed to start mitmdump: {ex.Message}");
            _mitmProcess = null;
            _currentPid = 0;
            _consecutiveFailures++;
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
        var processToStop = _mitmProcess;

        if (processToStop == null)
        {
            _currentPid = 0;
            return;
        }

        try
        {
            if (processToStop.HasExited)
            {
                Console.WriteLine($"[ProxyRunner] mitmdump already exited");
                return;
            }

            int pid = processToStop.Id;
            Console.WriteLine($"[ProxyRunner] Stopping mitmdump (PID={pid}) safely...");
            KillProcessTreeSafely(pid);

            if (!processToStop.WaitForExit(2000))
            {
                Console.Error.WriteLine($"[ProxyRunner] mitmdump did not exit gracefully, force killing...");
                processToStop.Kill(true);
            }
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

    private static bool WaitForMitmProxyReady(int maxWaitMs = 10000)
    {
        var sw = System.Diagnostics.Stopwatch.StartNew();
        Console.WriteLine($"[ProxyRunner] Waiting for mitmdump to be ready on port {MITM_PORT}...");

        while (sw.ElapsedMilliseconds < maxWaitMs)
        {
            try
            {
                using (var client = new TcpClient())
                {
                    client.Connect("127.0.0.1", MITM_PORT);
                    Console.WriteLine($"[ProxyRunner] mitmdump is ready on port {MITM_PORT} (took {sw.ElapsedMilliseconds}ms)");
                    return true;
                }
            }
            catch
            {
                // 포트가 아직 열리지 않음, 계속 대기
                Thread.Sleep(200);
            }
        }

        Console.Error.WriteLine($"[ProxyRunner] Timeout: mitmdump did not become ready within {maxWaitMs}ms");
        return false;
    }

    private static void WatchLoop(CancellationToken token)
    {
        Console.WriteLine("[ProxyRunner] Started WMI-driven proxy watcher loop.");

        while (!token.IsCancellationRequested)
        {
            try
            {
                if (_consecutiveFailures >= MAX_CONSECUTIVE_FAILURES)
                {
                    Console.Error.WriteLine($"[ProxyRunner] Too many consecutive failures ({_consecutiveFailures}). Waiting 10 seconds...");
                    Thread.Sleep(10000);
                    _consecutiveFailures = 0;
                }

                // 현재 추적 중인 PID가 있고 아직 살아있으면 계속 사용
                int pid = _currentPid;

                if (pid != 0)
                {
                    try
                    {
                        var existingProc = Process.GetProcessById(pid);
                        if (existingProc.HasExited)
                        {
                            Console.WriteLine($"[ProxyRunner] Tracked PID {pid} has exited");
                            pid = 0;
                            _currentPid = 0;  // 중요: _currentPid도 초기화
                        }
                    }
                    catch
                    {
                        Console.WriteLine($"[ProxyRunner] Tracked PID {pid} no longer exists");
                        pid = 0;
                        _currentPid = 0;  // 중요: _currentPid도 초기화
                    }
                }

                // PID가 없으면 새로 찾기
                if (pid == 0)
                {
                    var proc = FindTargetProcess();
                    pid = proc?.Id ?? 0;

                    if (pid == 0)
                    {
                        // mitmdump을 바로 종료하지 않고 5초 대기
                        // Claude Desktop이 재시작 중일 수 있음
                        if (_mitmProcess != null && !_mitmProcess.HasExited)
                        {
                            Console.WriteLine($"[ProxyRunner] No valid target, waiting before stopping mitmdump...");

                            // 5초 동안 1초마다 다시 체크
                            bool foundTarget = false;
                            for (int i = 0; i < 5; i++)
                            {
                                Thread.Sleep(1000);
                                var retryProc = FindTargetProcess();
                                if (retryProc != null)
                                {
                                    pid = retryProc.Id;
                                    foundTarget = true;
                                    Console.WriteLine($"[ProxyRunner] Found target PID {pid} during wait period");
                                    break;
                                }
                            }

                            if (!foundTarget)
                            {
                                Console.WriteLine($"[ProxyRunner] No target found after waiting → stopping mitmdump.");
                                StopProxy();
                            }
                        }

                        if (pid == 0)
                        {
                            Thread.Sleep(500);
                            continue;
                        }
                    }
                }

                // mitmdump이 없거나 종료되었으면 시작
                if (_mitmProcess == null || _mitmProcess.HasExited)
                {
                    Console.WriteLine($"[ProxyRunner] Target PID {pid} detected → starting mitmdump.");

                    // mitmdump 시작 시도 (실패하면 재시도)
                    bool startSuccess = false;
                    for (int attempt = 1; attempt <= 2; attempt++)
                    {
                        StartMitmDump(pid);

                        if (_mitmProcess != null && !_mitmProcess.HasExited)
                        {
                            // mitmdump이 제대로 시작되었는지 짧게 확인 (300ms만 대기)
                            Thread.Sleep(300);
                            if (_mitmProcess != null && !_mitmProcess.HasExited)
                            {
                                Console.WriteLine($"[ProxyRunner] mitmdump is running for PID {pid}");
                                _currentPid = pid;
                                startSuccess = true;
                                break;
                            }
                            else
                            {
                                Console.Error.WriteLine($"[ProxyRunner] mitmdump started but exited immediately (attempt {attempt}/2)");
                            }
                        }
                        else
                        {
                            Console.Error.WriteLine($"[ProxyRunner] mitmdump failed to start (attempt {attempt}/2)");
                        }

                        if (attempt < 2)
                        {
                            // 재시도 전에 실패한 프로세스 정리
                            if (_mitmProcess != null)
                            {
                                Console.WriteLine($"[ProxyRunner] Cleaning up failed mitmdump before retry...");
                                try
                                {
                                    if (!_mitmProcess.HasExited)
                                    {
                                        _mitmProcess.Kill(true);
                                        _mitmProcess.WaitForExit(1000);
                                    }
                                }
                                catch { }
                                _mitmProcess = null;
                            }
                            Console.WriteLine($"[ProxyRunner] Retrying after 500ms...");
                            Thread.Sleep(500);
                        }
                    }

                    if (!startSuccess)
                    {
                        Console.Error.WriteLine("[ProxyRunner] mitmdump failed to start after 2 attempts");
                        _consecutiveFailures++;
                        continue;
                    }
                }
                // mitmdump이 실행 중이면 그대로 유지 (PID 변경 없음)
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
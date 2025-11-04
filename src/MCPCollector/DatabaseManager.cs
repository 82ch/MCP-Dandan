using System;
using System.Data.SQLite;
using System.IO;
using System.Text.Json;
using System.Threading.Tasks;

namespace Collector
{
    /// <summary>
    /// SQLite 데이터베이스 관리자
    /// 이벤트 및 분석 결과 저장
    /// </summary>
    public class DatabaseManager : IDisposable
    {
        private readonly string dbPath;
        private readonly string schemaPath;
        private SQLiteConnection? connection;
        private bool isDisposed = false;

        public DatabaseManager(string? dbPath = null, string? schemaPath = null)
        {
            // 기본 경로 설정
            if (string.IsNullOrEmpty(dbPath))
            {
                // 환경 변수 또는 상대 경로로 82ch-engine 찾기
                string? enginePath = Environment.GetEnvironmentVariable("ENGINE_PATH");

                if (string.IsNullOrEmpty(enginePath))
                {
                    // 환경 변수가 없으면 상대 경로로 찾기
                    // 82ch-observer/src/MCPCollector/bin/Debug/net9.0 -> 82ch-engine
                    var currentDir = AppDomain.CurrentDomain.BaseDirectory;
                    Console.WriteLine($"[DB DEBUG] Current dir: {currentDir}");

                    // net9.0 -> Debug -> bin -> MCPCollector -> src -> 82ch-observer
                    var observerRoot = Directory.GetParent(currentDir)?.Parent?.Parent?.Parent?.Parent?.Parent?.FullName;
                    Console.WriteLine($"[DB DEBUG] Observer root: {observerRoot ?? "NULL"}");

                    if (observerRoot != null)
                    {
                        // 82ch-observer와 같은 레벨에서 82ch-engine 찾기
                        var parentDir = Directory.GetParent(observerRoot)?.FullName;
                        Console.WriteLine($"[DB DEBUG] Parent dir: {parentDir ?? "NULL"}");

                        if (parentDir != null)
                        {
                            enginePath = Path.Combine(parentDir, "82ch-engine");
                            Console.WriteLine($"[DB DEBUG] Engine path: {enginePath}");
                            Console.WriteLine($"[DB DEBUG] Directory exists: {Directory.Exists(enginePath)}");
                        }
                    }
                }

                if (!string.IsNullOrEmpty(enginePath) && Directory.Exists(enginePath))
                {
                    var dataDir = Path.Combine(enginePath, "data");
                    Directory.CreateDirectory(dataDir);
                    this.dbPath = Path.Combine(dataDir, "mcp_observer.db");
                }
                else
                {
                    // fallback: 현재 디렉토리에 생성
                    var dataDir = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "data");
                    Directory.CreateDirectory(dataDir);
                    this.dbPath = Path.Combine(dataDir, "mcp_observer.db");
                    Console.WriteLine($"[DB WARNING] 82ch-engine not found. Using local path: {this.dbPath}");
                }
            }
            else
            {
                this.dbPath = dbPath;
            }

            if (string.IsNullOrEmpty(schemaPath))
            {
                // 환경 변수 또는 상대 경로로 init_db.sql 찾기
                string? enginePath = Environment.GetEnvironmentVariable("ENGINE_PATH");

                if (string.IsNullOrEmpty(enginePath))
                {
                    var currentDir = AppDomain.CurrentDomain.BaseDirectory;
                    var observerRoot = Directory.GetParent(currentDir)?.Parent?.Parent?.Parent?.Parent?.Parent?.FullName;

                    if (observerRoot != null)
                    {
                        var parentDir = Directory.GetParent(observerRoot)?.FullName;
                        if (parentDir != null)
                        {
                            enginePath = Path.Combine(parentDir, "82ch-engine");
                        }
                    }
                }

                if (!string.IsNullOrEmpty(enginePath) && Directory.Exists(enginePath))
                {
                    this.schemaPath = Path.Combine(enginePath, "schema.sql");
                }
                else
                {
                    this.schemaPath = "";
                }
            }
            else
            {
                this.schemaPath = schemaPath;
            }
        }

        /// <summary>
        /// 데이터베이스 연결 및 초기화
        /// </summary>
        public async Task ConnectAsync()
        {
            if (connection != null)
                return;

            bool isNewDb = !File.Exists(dbPath);

            // SQLite 연결
            connection = new SQLiteConnection($"Data Source={dbPath};Version=3;");
            await connection.OpenAsync();

            // WAL 모드 활성화
            using (var cmd = connection.CreateCommand())
            {
                cmd.CommandText = "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;";
                await cmd.ExecuteNonQueryAsync();
            }

            // 새 데이터베이스면 스키마 초기화
            if (isNewDb)
            {
                await InitializeSchemaAsync();
            }

            Console.WriteLine($"[DB] Connected: {dbPath}");
        }

        /// <summary>
        /// 스키마 초기화
        /// </summary>
        private async Task InitializeSchemaAsync()
        {
            if (!File.Exists(schemaPath))
            {
                Console.WriteLine($"[DB WARNING] Schema file not found: {schemaPath}");
                return;
            }

            try
            {
                // 스키마 SQL 읽기
                string schemaSql = await File.ReadAllTextAsync(schemaPath);

                // 스키마 실행
                using (var cmd = connection!.CreateCommand())
                {
                    cmd.CommandText = schemaSql;
                    await cmd.ExecuteNonQueryAsync();
                }

                Console.WriteLine("[DB] Schema initialized successfully");
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Schema initialization failed: {ex.Message}");
                throw;
            }
        }

        /// <summary>
        /// 원시 이벤트 삽입
        /// </summary>
        public async Task<long?> InsertRawEventAsync(JsonDocument eventDoc)
        {
            if (connection == null)
                return null;

            try
            {
                var root = eventDoc.RootElement;

                long ts = root.TryGetProperty("ts", out var tsProp) ? tsProp.GetInt64() : 0;
                string producer = root.TryGetProperty("producer", out var prodProp) ? prodProp.GetString() ?? "unknown" : "unknown";
                int? pid = root.TryGetProperty("pid", out var pidProp) ? pidProp.GetInt32() : (int?)null;
                string? pname = root.TryGetProperty("pname", out var pnameProp) ? pnameProp.GetString() : null;
                string eventType = root.TryGetProperty("eventType", out var typeProp) ? typeProp.GetString() ?? "Unknown" : "Unknown";
                string data = root.TryGetProperty("data", out var dataProp) ? dataProp.GetRawText() : "{}";

                // mcpTag 추출
                string? mcpTag = null;
                if (root.TryGetProperty("mcpTag", out var mcpTagProp))
                {
                    mcpTag = mcpTagProp.GetString();
                }
                else if (root.TryGetProperty("data", out var dataObj) &&
                         dataObj.ValueKind == JsonValueKind.Object &&
                         dataObj.TryGetProperty("mcpTag", out var innerTagProp))
                {
                    mcpTag = innerTagProp.GetString();
                }

                using (var cmd = connection.CreateCommand())
                {
                    cmd.CommandText = @"
                INSERT INTO raw_events (ts, producer, pid, pname, event_type, mcpTag, data)
                VALUES (@ts, @producer, @pid, @pname, @event_type, @mcpTag, @data);
                SELECT last_insert_rowid();
            ";

                    cmd.Parameters.AddWithValue("@ts", ts);
                    cmd.Parameters.AddWithValue("@producer", producer);
                    cmd.Parameters.AddWithValue("@pid", pid ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@pname", pname ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@event_type", eventType);
                    cmd.Parameters.AddWithValue("@mcpTag", mcpTag ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@data", data);

                    var result = await cmd.ExecuteScalarAsync();
                    return result != null ? Convert.ToInt64(result) : (long?)null;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Failed to insert raw_event: {ex.Message}");
                return null;
            }
        }


        /// <summary>
        /// RPC 이벤트 삽입
        /// </summary>
        public async Task<long?> InsertRpcEventAsync(JsonDocument eventDoc, long? rawEventId = null)
        {
            if (connection == null)
                return null;

            try
            {
                var root = eventDoc.RootElement;
                long ts = root.TryGetProperty("ts", out var tsProp) ? tsProp.GetInt64() : 0;

                if (!root.TryGetProperty("data", out var data))
                    return null;

                // MCP 이벤트는 data.message 안에 JSON-RPC 데이터가 있음
                JsonElement message = data.TryGetProperty("message", out var msgProp) ? msgProp : data;

                // direction: SEND=Request, RECV=Response
                string task = data.TryGetProperty("task", out var taskProp) ? taskProp.GetString() ?? "" : "";
                string direction;
                if (task == "SEND")
                    direction = "Request";
                else if (task == "RECV")
                    direction = "Response";
                else
                    direction = data.TryGetProperty("direction", out var dirProp) ? dirProp.GetString() ?? "Unknown" : "Unknown";

                // message 안에서 데이터 추출
                string? method = message.TryGetProperty("method", out var methProp) ? methProp.GetString() : null;
                string? messageId = message.TryGetProperty("id", out var idProp) ? idProp.GetRawText() : null;
                string? parameters = message.TryGetProperty("params", out var paramsProp) ? paramsProp.GetRawText() : null;
                string? result = message.TryGetProperty("result", out var resultProp) ? resultProp.GetRawText() : null;
                string? error = message.TryGetProperty("error", out var errorProp) ? errorProp.GetRawText() : null;

                using (var cmd = connection.CreateCommand())
                {
                    cmd.CommandText = @"
                        INSERT INTO rpc_events
                        (raw_event_id, ts, direction, method, message_id, params, result, error)
                        VALUES (@raw_event_id, @ts, @direction, @method, @message_id, @params, @result, @error);
                        SELECT last_insert_rowid();
                    ";

                    cmd.Parameters.AddWithValue("@raw_event_id", rawEventId ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@ts", ts);
                    cmd.Parameters.AddWithValue("@direction", direction);
                    cmd.Parameters.AddWithValue("@method", method ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@message_id", messageId ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@params", parameters ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@result", result ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@error", error ?? (object)DBNull.Value);

                    var res = await cmd.ExecuteScalarAsync();
                    return res != null ? Convert.ToInt64(res) : (long?)null;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Failed to insert rpc_event: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// 파일 이벤트 삽입
        /// </summary>
        public async Task<long?> InsertFileEventAsync(JsonDocument eventDoc, long? rawEventId = null)
        {
            if (connection == null)
                return null;

            try
            {
                var root = eventDoc.RootElement;
                long ts = root.TryGetProperty("ts", out var tsProp) ? tsProp.GetInt64() : 0;
                int? pid = root.TryGetProperty("pid", out var pidProp) ? pidProp.GetInt32() : (int?)null;
                string? pname = root.TryGetProperty("pname", out var pnameProp) ? pnameProp.GetString() : null;

                if (!root.TryGetProperty("data", out var data))
                    return null;

                string operation = data.TryGetProperty("operation", out var opProp) ? opProp.GetString() ?? "Unknown" : "Unknown";
                string? filePath = data.TryGetProperty("filePath", out var pathProp) ? pathProp.GetString() :
                                   data.TryGetProperty("path", out var path2Prop) ? path2Prop.GetString() : null;
                string? oldPath = data.TryGetProperty("oldPath", out var oldProp) ? oldProp.GetString() : null;
                string? newPath = data.TryGetProperty("newPath", out var newProp) ? newProp.GetString() : null;
                int? size = data.TryGetProperty("size", out var sizeProp) ? sizeProp.GetInt32() : (int?)null;

                using (var cmd = connection.CreateCommand())
                {
                    cmd.CommandText = @"
                        INSERT INTO file_events
                        (raw_event_id, ts, pid, pname, operation, file_path, old_path, new_path, size)
                        VALUES (@raw_event_id, @ts, @pid, @pname, @operation, @file_path, @old_path, @new_path, @size);
                        SELECT last_insert_rowid();
                    ";

                    cmd.Parameters.AddWithValue("@raw_event_id", rawEventId ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@ts", ts);
                    cmd.Parameters.AddWithValue("@pid", pid ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@pname", pname ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@operation", operation);
                    cmd.Parameters.AddWithValue("@file_path", filePath ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@old_path", oldPath ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@new_path", newPath ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@size", size ?? (object)DBNull.Value);

                    var result = await cmd.ExecuteScalarAsync();
                    return result != null ? Convert.ToInt64(result) : (long?)null;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Failed to insert file_event: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// 프로세스 이벤트 삽입
        /// </summary>
        public async Task<long?> InsertProcessEventAsync(JsonDocument eventDoc, long? rawEventId = null)
        {
            if (connection == null)
                return null;

            try
            {
                var root = eventDoc.RootElement;
                long ts = root.TryGetProperty("ts", out var tsProp) ? tsProp.GetInt64() : 0;
                int? pid = root.TryGetProperty("pid", out var pidProp) ? pidProp.GetInt32() : (int?)null;
                string? pname = root.TryGetProperty("pname", out var pnameProp) ? pnameProp.GetString() : null;

                if (!root.TryGetProperty("data", out var data))
                    return null;

                // data 안에도 pid, pname이 있을 수 있음
                if (pid == null && data.TryGetProperty("pid", out var dataPidProp))
                    pid = dataPidProp.GetInt32();

                if (pname == null && data.TryGetProperty("processName", out var dataPnameProp))
                    pname = dataPnameProp.GetString();

                int? parentPid = data.TryGetProperty("parentPid", out var ppidProp) ? ppidProp.GetInt32() : (int?)null;
                string? commandLine = data.TryGetProperty("commandLine", out var cmdProp) ? cmdProp.GetString() : null;
                string operation = data.TryGetProperty("operation", out var opProp) ? opProp.GetString() ?? "Unknown" : "Unknown";
                int? exitCode = data.TryGetProperty("exitCode", out var exitProp) ? exitProp.GetInt32() : (int?)null;

                using (var cmd = connection.CreateCommand())
                {
                    cmd.CommandText = @"
                        INSERT INTO process_events
                        (raw_event_id, ts, pid, pname, parent_pid, command_line, operation, exit_code)
                        VALUES (@raw_event_id, @ts, @pid, @pname, @parent_pid, @command_line, @operation, @exit_code);
                        SELECT last_insert_rowid();
                    ";

                    cmd.Parameters.AddWithValue("@raw_event_id", rawEventId ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@ts", ts);
                    cmd.Parameters.AddWithValue("@pid", pid ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@pname", pname ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@parent_pid", parentPid ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@command_line", commandLine ?? (object)DBNull.Value);
                    cmd.Parameters.AddWithValue("@operation", operation);
                    cmd.Parameters.AddWithValue("@exit_code", exitCode ?? (object)DBNull.Value);

                    var result = await cmd.ExecuteScalarAsync();
                    return result != null ? Convert.ToInt64(result) : (long?)null;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Failed to insert process_event: {ex.Message}");
                return null;
            }
        }

        /// <summary>
        /// 이벤트 저장 (자동으로 타입별 테이블에 저장)
        /// </summary>
        public async Task<long?> SaveEventAsync(string jsonString)
        {
            try
            {
                using var doc = JsonDocument.Parse(jsonString);
                var root = doc.RootElement;

                // 1. raw_events 테이블에 저장
                long? rawEventId = await InsertRawEventAsync(doc);

                if (rawEventId == null)
                    return null;

                // 2. 이벤트 타입에 따라 전용 테이블에도 저장
                string eventType = root.TryGetProperty("eventType", out var typeProp) ? typeProp.GetString() ?? "" : "";

                switch (eventType.ToLower())
                {
                    case "rpc":
                    case "jsonrpc":
                    case "mcp":
                        await InsertRpcEventAsync(doc, rawEventId);
                        break;

                    case "file":
                    case "fileio":
                        await InsertFileEventAsync(doc, rawEventId);
                        break;

                    case "process":
                        await InsertProcessEventAsync(doc, rawEventId);
                        break;

                    // 필요시 network, registry 등 추가
                }

                return rawEventId;
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[DB ERROR] Failed to save event: {ex.Message}");
                return null;
            }
        }

        public void Dispose()
        {
            if (isDisposed)
                return;

            connection?.Close();
            connection?.Dispose();
            connection = null;

            isDisposed = true;
            Console.WriteLine("[DB] Connection closed");
        }
    }
}

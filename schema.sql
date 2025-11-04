-- 82ch MCP Observer Database - 간단한 초기화 스크립트

-- 1. 원시 이벤트 (mcpTag 추가)
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts BIGINT NOT NULL,
    producer TEXT NOT NULL,
    pid INTEGER,
    pname TEXT,
    event_type TEXT NOT NULL,
    mcpTag TEXT,                     
    data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_raw_ts ON raw_events(ts);
CREATE INDEX IF NOT EXISTS idx_raw_event_type ON raw_events(event_type);
CREATE INDEX IF NOT EXISTS idx_raw_mcpTag ON raw_events(mcpTag);


-- 2. RPC 이벤트
CREATE TABLE IF NOT EXISTS rpc_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id INTEGER,
    ts BIGINT NOT NULL,
    direction TEXT NOT NULL,
    method TEXT,
    message_id TEXT,
    params TEXT,
    result TEXT,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_event_id) REFERENCES raw_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_rpc_direction ON rpc_events(direction);
CREATE INDEX IF NOT EXISTS idx_rpc_method ON rpc_events(method);

-- 3. 파일 이벤트
CREATE TABLE IF NOT EXISTS file_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id INTEGER,
    ts BIGINT NOT NULL,
    pid INTEGER,
    pname TEXT,
    operation TEXT,
    file_path TEXT,
    old_path TEXT,
    new_path TEXT,
    size INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_event_id) REFERENCES raw_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_file_path ON file_events(file_path);

-- 4. 프로세스 이벤트
CREATE TABLE IF NOT EXISTS process_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id INTEGER,
    ts BIGINT NOT NULL,
    pid INTEGER NOT NULL,
    pname TEXT,
    parent_pid INTEGER,
    command_line TEXT,
    operation TEXT,
    exit_code INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_event_id) REFERENCES raw_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_proc_pid ON process_events(pid);

-- 5. 엔진 결과
CREATE TABLE IF NOT EXISTS engine_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id INTEGER,
    engine_name TEXT NOT NULL,
    detected BOOLEAN NOT NULL DEFAULT 0,
    severity TEXT,
    score INTEGER,
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_event_id) REFERENCES raw_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_engine_name ON engine_results(engine_name);
CREATE INDEX IF NOT EXISTS idx_detected ON engine_results(detected);

-- 6. Semantic Gap 결과
CREATE TABLE IF NOT EXISTS semantic_gap_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    engine_result_id INTEGER NOT NULL,
    domain_match INTEGER,
    operation_match INTEGER,
    argument_specificity INTEGER,
    consistency INTEGER,
    penalties TEXT,
    final_score INTEGER NOT NULL,
    tool_spec TEXT,
    event_description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (engine_result_id) REFERENCES engine_results(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_final_score ON semantic_gap_results(final_score);

-- 7. 시스템 메타데이터
CREATE TABLE IF NOT EXISTS system_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO system_metadata (key, value) VALUES ('db_version', '1.0');
INSERT OR IGNORE INTO system_metadata (key, value) VALUES ('created_at', datetime('now'));

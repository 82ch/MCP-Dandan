-- 82ch MCP Observer Database - 간단한 초기화 스크립트

-- raw Events (mcpTag, serverName 추가)
CREATE TABLE IF NOT EXISTS raw_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts DATETIME NOT NULL,
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


-- RPC Events
CREATE TABLE IF NOT EXISTS rpc_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mcptype TEXT NOT NULL,
    mcptag TEXT NOT NULL,
    raw_event_id INTEGER,
    ts DATETIME NOT NULL,
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

-- Engine Results
CREATE TABLE IF NOT EXISTS engine_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_event_id INTEGER,
    engine_name TEXT NOT NULL,
    serverName TEXT,
    producer TEXT,
    severity TEXT,
    score INTEGER,
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (raw_event_id) REFERENCES raw_events(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_engine_name ON engine_results(engine_name);
CREATE INDEX IF NOT EXISTS idx_serverName ON engine_results(serverName);

-- MCPL(tools/call list)
Create table if not exists mcpl (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mcpTag TEXT NOT NULL    ,  -- mcpTag
    producer TEXT NOT NULL  ,  -- producer
    tool TEXT NOT NULL      ,  -- name
    tool_title TEXT         ,  -- title
    tool_description TEXT   ,  -- description
    tool_parameter TEXT     ,  -- inputschema
    annotations TEXT        ,  -- annotations
    safety INTEGER DEFAULT 0,  -- 0: 검사 전, 1: 안전(score<40), 2: 조치권장(score 40-79), 3: 조치필요(score>=80)
    safety_checked_at DATETIME,  -- 검사 완료 시간
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(mcpTag, tool)    -- mcpTag와 tool 조합으로 유니크 제약
);

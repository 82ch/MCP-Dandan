import aiosqlite
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from utils import safe_print


class Database:

    def __init__(self, db_path: str = None, schema_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent / "data" / "mcp_observer.db"
        else:
            db_path = Path(db_path)

        if schema_path is None:
            schema_path = Path(__file__).parent / "schema.sql"
        else:
            schema_path = Path(schema_path)

        self.db_path = db_path
        self.schema_path = schema_path
        self.conn = None

        # 데이터베이스 디렉토리 생성
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def connect(self):
        if self.conn is not None:
            return

        self.conn = await aiosqlite.connect(str(self.db_path))

        # WAL 모드 활성화 (성능 향상)
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")

        # always schema initalize (CREATE TABLE IF NOT EXISTS)
        await self._initialize_schema()

        safe_print(f'Database connected: {self.db_path}')

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
            safe_print('Database connection closed')

    async def _initialize_schema(self):
        if not self.schema_path.exists():
            safe_print(f'Schema file not found: {self.schema_path}')
            return

        try:
            # Read schema SQL
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # Execute schema
            await self.conn.executescript(schema_sql)
            await self.conn.commit()

            safe_print(f'Database schema initialization complete')

        except Exception as e:
            safe_print(f'Schema initialization failed: {e}')
            raise

    async def insert_raw_event(self, event: Dict[str, Any]) -> Optional[int]:
        try:
            ts_millis = event.get('ts', 0)
            # 밀리초 타임스탬프를 DATETIME으로 변환
            ts = datetime.fromtimestamp(ts_millis / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if ts_millis else None

            producer = event.get('producer', 'unknown')
            pid = event.get('pid')
            pname = event.get('pname')
            event_type = event.get('eventType', 'Unknown')

            # Handle surrogate characters in data
            data_dict = event.get('data', {})
            # First, convert dict to JSON string (may contain surrogates)
            data_with_surrogates = json.dumps(data_dict, ensure_ascii=False)
            # Convert surrogates back to original bytes, then decode properly
            try:
                # Encode with surrogateescape to get original bytes
                original_bytes = data_with_surrogates.encode('utf-8', errors='surrogateescape')
                # Decode with proper encoding (try UTF-8 first, fallback to latin-1)
                data = original_bytes.decode('utf-8', errors='replace')
            except (UnicodeDecodeError, UnicodeEncodeError):
                # If conversion fails, use replace to ensure valid UTF-8
                data = data_with_surrogates.encode('utf-8', errors='replace').decode('utf-8')

            match producer:
                case 'local':
                    mcpTag = event.get('mcpTag', None)
                case 'remote':
                    mcpTag = event.get('data', {}).get('mcpTag', None)
                case _:
                    mcpTag = None


            cursor = await self.conn.execute(
                """
                INSERT INTO raw_events (ts, producer, pid, pname, event_type, mcpTag, data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, producer, pid, pname, event_type, mcpTag, data)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            safe_print(f'Failed to save raw_event: {e}')
            return None
        
    # RPC 이벤트 저장
    async def insert_rpc_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:

        try:
            data = event.get('data', {})
            ts_millis = event.get('ts', 0)
            # 밀리초 타임스탬프를 DATETIME으로 변환
            ts = datetime.fromtimestamp(ts_millis / 1000).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if ts_millis else None

            # mcpTag 위치가 producer에 따라 다름
            # - remote: data.mcpTag
            # - local: event.mcpTag
            mcptype = event.get('producer', 'unknown')
            
            match mcptype:
                case 'local':
                    mcpTag = event.get('mcpTag', None)
                case 'remote':
                    mcpTag = event.get('data', {}).get('mcpTag', None)
                case _:
                    mcpTag = None

            # MCP 이벤트는 data.message 안에 JSON-RPC 데이터가 있음
            message = data.get('message', {})

            # direction: SEND=Request, RECV=Response, task 필드 사용
            task = data.get('task', '')
            if task == 'SEND':
                direction = 'Request'
            elif task == 'RECV':
                direction = 'Response'
            else:
                direction = data.get('direction', 'Unknown')

            # message 안에서 데이터 추출
            method = message.get('method')
            message_id = message.get('id')
            params = json.dumps(message.get('params'), ensure_ascii=False) if message.get('params') else None
            result = json.dumps(message.get('result'), ensure_ascii=False) if message.get('result') else None
            error = json.dumps(message.get('error'), ensure_ascii=False) if message.get('error') else None

            # Response 메시지는 method 필드가 없으므로, 같은 message_id를 가진 Request에서 method를 찾아야 함
            if direction == 'Response' and method is None and message_id is not None:
                try:
                    cursor = await self.conn.execute(
                        """
                        SELECT method FROM rpc_events
                        WHERE mcptag = ? AND message_id = ? AND direction = 'Request'
                        ORDER BY ts DESC LIMIT 1
                        """,
                        (mcpTag, str(message_id))
                    )
                    row = await cursor.fetchone()
                    if row:
                        method = row[0]
                        safe_print(f'[DB] Found method from Request for Response message: {method} (id={message_id})')
                    else:
                        safe_print(f'[DB] Warning: Could not find Request for Response message (id={message_id}, mcpTag={mcpTag})')
                except Exception as e:
                    safe_print(f'[DB] Failed to query Response method: {e}')

            cursor = await self.conn.execute(
                """
                INSERT INTO rpc_events
                (raw_event_id, ts, mcptype, mcptag, direction, method, message_id, params, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, ts, mcptype, mcpTag, direction, method, message_id, params, result, error)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            safe_print(f'Failed to save rpc_event: {e}')
            return None

    # 엔진 결과 저장
    async def insert_engine_result(self, result: Dict[str, Any], raw_event_id: int = None, server_name: str = None, producer: str = None) -> Optional[int]:

        try:
            result_data = result.get('result', {})
            engine_name = result_data.get('detector', 'Unknown')
            severity = result_data.get('severity')

            # score 추출
            evaluation = result_data.get('evaluation')
            if isinstance(evaluation, dict):
                score = evaluation.get('Score')
            elif isinstance(evaluation, int):
                score = evaluation
            else:
                score = None

            # detail 처리
            detail_data = result_data.get('detail')
            if detail_data:
                # ToolsPoisoning 등에서 detail 필드로 보낸 경우
                detail = json.dumps(detail_data, ensure_ascii=False) if isinstance(detail_data, dict) else str(detail_data)
            else:
                # findings에서 reason만 추출 (다른 엔진용)
                findings = result_data.get('findings', [])
                reasons = [finding.get('reason', '') for finding in findings if isinstance(finding, dict)]
                detail = json.dumps(reasons, ensure_ascii=False) if reasons else None

            safe_print(f'[DB] insert_engine_result: engine={engine_name}, serverName={server_name}, severity={severity} score={score} detail={detail[:100] if detail else None}...')

            cursor = await self.conn.execute(
                """
                INSERT INTO engine_results
                (raw_event_id, engine_name, producer, serverName, severity, score, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, engine_name, producer, server_name, severity, score, detail)
            )

            await self.conn.commit()
            safe_print(f'[OK] engine_result saved successfully: id={cursor.lastrowid}')
            return cursor.lastrowid

        except Exception as e:
            safe_print(f'[ERROR] Failed to save engine_result: {e}')
            import traceback
            traceback.print_exc()
            return None

    # ========================================================================
    # 조회 메서드
    async def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:

        try:
            async with self.conn.execute(
                """
                SELECT * FROM raw_events
                ORDER BY ts DESC
                LIMIT ?
                """,
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            safe_print(f'[ERROR] Failed to query events: {e}')
            return []

    async def get_event_statistics(self) -> Dict[str, Any]:

        try:
            stats = {}

            # 전체 이벤트 수
            async with self.conn.execute("SELECT COUNT(*) FROM raw_events") as cursor:
                row = await cursor.fetchone()
                stats['total_events'] = row[0] if row else 0

            # 이벤트 타입별 통계
            async with self.conn.execute(
                """
                SELECT event_type, COUNT(*) as count
                FROM raw_events
                GROUP BY event_type
                """
            ) as cursor:
                rows = await cursor.fetchall()
                stats['by_type'] = {row[0]: row[1] for row in rows}

            # 탐지된 이벤트 수
            async with self.conn.execute(
                "SELECT COUNT(*) FROM engine_results WHERE detected = 1"
            ) as cursor:
                row = await cursor.fetchone()
                stats['detected_events'] = row[0] if row else 0

            return stats

        except Exception as e:
            safe_print(f'Failed to query statistics: {e}')
            return {}
    
    async def is_null_check(self, table_name: str) -> bool:
        """
        Table null check

        Args:
            table_name: Check table name

        Returns:
            True: table is null , False: table is not null
        """
        try:
            # SQL Injection 방지 (none accept 발생시 allowed table에 추가)
            allowed_tables = ['raw_events', 'rpc_events', 'engine_results', 'mcpl']
            if table_name not in allowed_tables:
                safe_print(f'none accept table name or type : {table_name}')
                return True

            query = f"SELECT NOT EXISTS (SELECT 1 FROM {table_name} LIMIT 1) as is_null"
            async with self.conn.execute(query) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else True

        except Exception as e:
            safe_print(f'table check failed: {e}')
            return True

    async def insert_mcpl(self) -> Optional[int]:
        """
         Tool information Extraction in 'rpc_events' Table
         (local + remote, ++tools duplication check)

        Returns:
            insert tools count
        """
        try:
            cursor = await self.conn.execute(
                """
                WITH tool_data AS (
                    SELECT
                        e.mcpTag,
                        e.mcptype,
                        json_each.value AS tool
                    FROM rpc_events e,
                         json_each(json_extract(e.result, '$.tools'))
                    WHERE 1=1
                      AND e.mcptype IN ('remote', 'local')
                      AND e.direction = 'Response'
                      AND e.method = 'tools/list'
                      AND e.mcpTag IS NOT NULL
                )
                INSERT OR IGNORE INTO mcpl (mcpTag, producer, tool, tool_title, tool_description, tool_parameter, annotations)
                SELECT
                    td.mcpTag,
                    td.mcptype,
                    json_extract(td.tool, '$.name'),
                    json_extract(td.tool, '$.title'),
                    json_extract(td.tool, '$.description'),
                    json_extract(td.tool, '$.inputSchema'),
                    json_extract(td.tool, '$.annotations')
                FROM tool_data td
                WHERE NOT EXISTS (
                    SELECT 1 FROM mcpl m
                    WHERE m.mcpTag = td.mcpTag
                      AND m.tool = json_extract(td.tool, '$.name')
                )
                """
            )

            await self.conn.commit()
            inserted_count = cursor.rowcount
            # safe_print(f'{inserted_count} tools inserted into mcpl table.')
            return inserted_count

        except Exception as e:
            safe_print(f'mcpl insert failed : {e}')
            return None

    async def get_recent_mcpl_tools(self, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get recently inserted tools from mcpl table

        Args:
            limit: Maximum number of tools to retrieve (None = all)

        Returns:
            List of dictionaries with tool and tool_description
        """
        try:
            query = "SELECT tool, tool_description, mcpTag, producer FROM mcpl ORDER BY id DESC"
            if limit:
                query += f" LIMIT {limit}"

            async with self.conn.execute(query) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            safe_print(f'Failed to query mcpl: {e}')
            return []

    async def get_tool_safety_status(self, mcp_tag: str, tool_name: str) -> int | None:
        """
        Get safety status for a specific tool from mcpl table.

        Args:
            mcp_tag: MCP server tag
            tool_name: Tool name

        Returns:
            0: unchecked, 1: safe (ALLOW), 2: danger (DENY), None: not found
        """
        try:
            cursor = await self.conn.execute(
                """
                SELECT safety
                FROM mcpl
                WHERE mcpTag = ? AND tool = ?
                """,
                (mcp_tag, tool_name)
            )
            row = await cursor.fetchone()
            if row:
                return row[0]
            return None

        except Exception as e:
            safe_print(f'[DB] Failed to get tool safety status: {e}')
            return None

    async def update_tool_safety(self, mcp_tag: str, tool_name: str, score: float) -> bool:
        """
        Update safety status for a specific tool in mcpl table based on score.

        Args:
            mcp_tag: MCP server tag
            tool_name: Tool name
            score: LLM analysis score (0-100)

        Safety values:
            0: 검사 전 (not checked)
            1: 안전 (safe) - score < 40
            2: 조치권장 (action recommended) - score 40-79
            3: 조치필요 (action required) - score >= 80

        Returns:
            True if update successful, False otherwise
        """
        try:
            # score 기반 safety 값 결정
            if score >= 80:
                safety_value = 3  # 조치필요
                safety_label = "ACTION_REQUIRED"
            elif score >= 40:
                safety_value = 2  # 조치권장
                safety_label = "ACTION_RECOMMENDED"
            else:
                safety_value = 1  # 안전
                safety_label = "SAFE"

            await self.conn.execute(
                """
                UPDATE mcpl
                SET safety = ?,
                    safety_checked_at = CURRENT_TIMESTAMP
                WHERE mcpTag = ? AND tool = ?
                """,
                (safety_value, mcp_tag, tool_name)
            )
            await self.conn.commit()
            safe_print(f'[DB] Updated safety for {mcp_tag}/{tool_name}: {safety_label} (score={score})')
            return True

        except Exception as e:
            safe_print(f'[DB] Failed to update tool safety: {e}')
            return False

    async def set_tool_safety_manual(self, mcp_tag: str, tool_name: str, safety_value: int) -> bool:
        """
        수동으로 safety 값을 직접 설정.

        Args:
            mcp_tag: MCP server tag
            tool_name: Tool name
            safety_value: Safety value (0-3)
                0: 검사 전 (not checked)
                1: 안전 (safe)
                2: 조치권장 (action recommended)
                3: 조치필요 (action required)

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Validate safety value
            if safety_value not in (0, 1, 2, 3):
                safe_print(f'[DB] Invalid safety value: {safety_value}')
                return False

            safety_labels = {
                0: "NOT_CHECKED",
                1: "SAFE",
                2: "ACTION_RECOMMENDED",
                3: "ACTION_REQUIRED"
            }

            await self.conn.execute(
                """
                UPDATE mcpl
                SET safety = ?,
                    safety_checked_at = CURRENT_TIMESTAMP
                WHERE mcpTag = ? AND tool = ?
                """,
                (safety_value, mcp_tag, tool_name)
            )
            await self.conn.commit()
            safe_print(f'[DB] Manually set safety for {mcp_tag}/{tool_name}: {safety_labels[safety_value]}')
            return True

        except Exception as e:
            safe_print(f'[DB] Failed to set tool safety manually: {e}')
            return False

    # ========================================================================
    # Custom Rules Methods
    async def insert_custom_rule(self, engine_name: str, rule_name: str, rule_content: str,
                                 category: str = None, description: str = None) -> Optional[int]:
        """
        Insert a new custom YARA rule.

        Args:
            engine_name: Engine name (e.g., 'pii_leak_engine')
            rule_name: YARA rule name
            rule_content: Full YARA rule content
            category: Optional category (PII, Financial, etc.)
            description: Optional user description

        Returns:
            Rule ID if successful, None otherwise

        Raises:
            Exception: If insertion fails (e.g., duplicate rule name)
        """
        try:
            cursor = await self.conn.execute(
                """
                INSERT INTO custom_rules (engine_name, rule_name, rule_content, category, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                (engine_name, rule_name, rule_content, category, description)
            )
            await self.conn.commit()
            safe_print(f'[DB] Custom rule inserted: {engine_name}/{rule_name}')
            return cursor.lastrowid

        except Exception as e:
            error_msg = str(e)
            if 'UNIQUE constraint' in error_msg:
                safe_print(f'[DB] Duplicate custom rule: {engine_name}/{rule_name}')
                raise Exception(f'Rule "{rule_name}" already exists for this engine')
            else:
                safe_print(f'[DB] Failed to insert custom rule: {e}')
                raise

    async def get_custom_rules(self, engine_name: str = None, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get custom rules, optionally filtered by engine name.

        Args:
            engine_name: Optional engine name to filter by
            enabled_only: If True, only return enabled rules

        Returns:
            List of custom rules
        """
        try:
            query = "SELECT * FROM custom_rules WHERE 1=1"
            params = []

            if engine_name:
                query += " AND engine_name = ?"
                params.append(engine_name)

            if enabled_only:
                query += " AND enabled = 1"

            query += " ORDER BY created_at DESC"

            async with self.conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            safe_print(f'[DB] Failed to get custom rules: {e}')
            return []

    async def get_custom_rules_content(self, engine_name: str) -> str:
        """
        Get combined YARA rule content for an engine (enabled rules only).

        Args:
            engine_name: Engine name

        Returns:
            Combined YARA rule content as a single string
        """
        try:
            rules = await self.get_custom_rules(engine_name, enabled_only=True)
            if not rules:
                return ""

            # Combine all rule contents with newlines
            combined = "\n\n".join(rule['rule_content'] for rule in rules)
            return combined

        except Exception as e:
            safe_print(f'[DB] Failed to get custom rules content: {e}')
            return ""

    async def delete_custom_rule(self, rule_id: int) -> bool:
        """
        Delete a custom rule by ID.

        Args:
            rule_id: Rule ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.conn.execute(
                "DELETE FROM custom_rules WHERE id = ?",
                (rule_id,)
            )
            await self.conn.commit()
            safe_print(f'[DB] Custom rule deleted: {rule_id}')
            return True

        except Exception as e:
            safe_print(f'[DB] Failed to delete custom rule: {e}')
            return False

    async def toggle_custom_rule(self, rule_id: int, enabled: bool) -> bool:
        """
        Enable or disable a custom rule.

        Args:
            rule_id: Rule ID
            enabled: True to enable, False to disable

        Returns:
            True if successful, False otherwise
        """
        try:
            await self.conn.execute(
                """
                UPDATE custom_rules
                SET enabled = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (1 if enabled else 0, rule_id)
            )
            await self.conn.commit()
            safe_print(f'[DB] Custom rule {"enabled" if enabled else "disabled"}: {rule_id}')
            return True

        except Exception as e:
            safe_print(f'[DB] Failed to toggle custom rule: {e}')
            return False

import aiosqlite
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


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

        # 데이터베이스 파일이 없으면 초기화 필요
        is_new_db = not self.db_path.exists()

        self.conn = await aiosqlite.connect(str(self.db_path))

        # WAL 모드 활성화 (성능 향상)
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA synchronous=NORMAL")

        # 새 데이터베이스면 스키마 초기화
        if is_new_db:
            await self._initialize_schema()

        print(f'Database 연결됨: {self.db_path}')

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None
            print('Database 연결 종료됨')

    async def _initialize_schema(self):
        if not self.schema_path.exists():
            print(f'스키마 파일이 없습니다: {self.schema_path}')
            return

        try:
            # 스키마 SQL 읽기
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # 스키마 실행
            await self.conn.executescript(schema_sql)
            await self.conn.commit()

            print(f'데이터베이스 스키마 초기화 완료')

        except Exception as e:
            print(f'스키마 초기화 실패: {e}')
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
            data = json.dumps(event.get('data', {}), ensure_ascii=False)

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
            print(f'raw_event 저장 실패: {e}')
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
                        print(f'[DB] Response 메시지의 method를 Request에서 찾음: {method} (id={message_id})')
                    else:
                        print(f'[DB] Warning: Response 메시지의 Request를 찾을 수 없음 (id={message_id}, mcpTag={mcpTag})')
                except Exception as e:
                    print(f'[DB] Response method 조회 실패: {e}')

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
            print(f'rpc_event 저장 실패: {e}')
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

            print(f'[DB] insert_engine_result: engine={engine_name}, serverName={server_name}, severity={severity} score={score} detail={detail[:100] if detail else None}...')

            cursor = await self.conn.execute(
                """
                INSERT INTO engine_results
                (raw_event_id, engine_name, producer, serverName, severity, score, detail)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, engine_name, producer, server_name, severity, score, detail)
            )

            await self.conn.commit()
            print(f'[OK] engine_result 저장 완료: id={cursor.lastrowid}')
            return cursor.lastrowid

        except Exception as e:
            print(f'[ERROR] engine_result 저장 실패: {e}')
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
            print(f'[ERROR] 이벤트 조회 실패: {e}')
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
            print(f'통계 조회 실패: {e}')
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
                print(f'none accept table name or type : {table_name}')
                return True

            query = f"SELECT NOT EXISTS (SELECT 1 FROM {table_name} LIMIT 1) as is_null"
            async with self.conn.execute(query) as cursor:
                row = await cursor.fetchone()
                return bool(row[0]) if row else True

        except Exception as e:
            print(f'table check failed: {e}')
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
            # print(f'{inserted_count} tools inserted into mcpl table.')
            return inserted_count

        except Exception as e:
            print(f'mcpl insert failed : {e}')
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
            print(f'mcpl 조회 실패: {e}')
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
            print(f'[DB] Failed to get tool safety status: {e}')
            return None

    async def update_tool_safety(self, mcp_tag: str, tool_name: str, is_safe: bool) -> bool:
        """
        Update safety status for a specific tool in mcpl table.

        Args:
            mcp_tag: MCP server tag
            tool_name: Tool name
            is_safe: True for ALLOW (safety=1), False for DENY (safety=2)

        Returns:
            True if update successful, False otherwise
        """
        try:
            safety_value = 1 if is_safe else 2
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
            print(f'[DB] Updated safety for {mcp_tag}/{tool_name}: {"ALLOW" if is_safe else "DENY"}')
            return True

        except Exception as e:
            print(f'[DB] Failed to update tool safety: {e}')
            return False

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
            ts = event.get('ts', 0)
            producer = event.get('producer', 'unknown')
            pid = event.get('pid')
            pname = event.get('pname')
            event_type = event.get('eventType', 'Unknown')
            data = json.dumps(event.get('data', {}), ensure_ascii=False)

            cursor = await self.conn.execute(
                """
                INSERT INTO raw_events (ts, producer, pid, pname, event_type, data)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, producer, pid, pname, event_type, data)
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
            ts = event.get('ts', 0)

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

            cursor = await self.conn.execute(
                """
                INSERT INTO rpc_events
                (raw_event_id, ts, direction, method, message_id, params, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, ts, direction, method, message_id, params, result, error)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f'rpc_event 저장 실패: {e}')
            return None

    # 파일 이벤트 저장
    async def insert_file_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:

        try:
            data = event.get('data', {})
            ts = event.get('ts', 0)
            pid = event.get('pid')
            pname = event.get('pname')
            operation = data.get('operation', 'Unknown')
            file_path = data.get('filePath') or data.get('path')
            old_path = data.get('oldPath')
            new_path = data.get('newPath')
            size = data.get('size')

            cursor = await self.conn.execute(
                """
                INSERT INTO file_events
                (raw_event_id, ts, pid, pname, operation, file_path, old_path, new_path, size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, ts, pid, pname, operation, file_path, old_path, new_path, size)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f'file_event 저장 실패: {e}')
            return None


    # 프로세스 이벤트 저장
    async def insert_process_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:

        try:
            data = event.get('data', {})
            ts = event.get('ts', 0)
            pid = event.get('pid') or data.get('pid')
            pname = event.get('pname') or data.get('processName')
            parent_pid = data.get('parentPid')
            command_line = data.get('commandLine')
            operation = data.get('operation', 'Unknown')
            exit_code = data.get('exitCode')

            cursor = await self.conn.execute(
                """
                INSERT INTO process_events
                (raw_event_id, ts, pid, pname, parent_pid, command_line, operation, exit_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, ts, pid, pname, parent_pid, command_line, operation, exit_code)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f'process_event 저장 실패: {e}')
            return None

    # 엔진 결과 저장
    async def insert_engine_result(self, result: Dict[str, Any], raw_event_id: int = None, server_name: str = None) -> Optional[int]:

        try:
            result_data = result.get('result', {})
            engine_name = result_data.get('detector', 'Unknown')
            severity = result_data.get('severity')
            score = result_data.get('evaluation') if isinstance(result_data.get('evaluation'), int) else None

            # findings에서 reason만 추출
            findings = result_data.get('findings', [])
            reasons = [finding.get('reason', '') for finding in findings if isinstance(finding, dict)]
            detail = json.dumps(reasons, ensure_ascii=False) if reasons else None

            print(f'[DB] insert_engine_result: engine={engine_name}, serverName={server_name}, severity={severity}')

            cursor = await self.conn.execute(
                """
                INSERT INTO engine_results
                (raw_event_id, engine_name, serverName, severity, score, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, engine_name, server_name, severity, score, detail)
            )

            await self.conn.commit()
            print(f'✓ engine_result 저장 완료: id={cursor.lastrowid}')
            return cursor.lastrowid

        except Exception as e:
            print(f'✗ engine_result 저장 실패: {e}')
            import traceback
            traceback.print_exc()
            return None

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
            print(f'✗ 이벤트 조회 실패: {e}')
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

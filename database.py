"""
SQLite Database Manager for 82ch-engine

비동기 SQLite 데이터베이스 관리 모듈
- 이벤트 저장
- 엔진 결과 저장
- 조회 및 통계
"""

import aiosqlite
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime


class Database:
    """
    비동기 SQLite 데이터베이스 관리자
    """

    def __init__(self, db_path: str = None, schema_path: str = None):
        """
        Args:
            db_path: 데이터베이스 파일 경로 (기본: ./data/mcp_observer.db)
            schema_path: 스키마 SQL 파일 경로 (기본: ./schema.sql)
        """
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
        """데이터베이스 연결"""
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

        print(f'✓ Database 연결됨: {self.db_path}')

    async def close(self):
        """데이터베이스 연결 종료"""
        if self.conn:
            await self.conn.close()
            self.conn = None
            print('✓ Database 연결 종료됨')

    async def _initialize_schema(self):
        """스키마 초기화"""
        if not self.schema_path.exists():
            print(f'⚠ 스키마 파일이 없습니다: {self.schema_path}')
            return

        try:
            # 스키마 SQL 읽기
            with open(self.schema_path, 'r', encoding='utf-8') as f:
                schema_sql = f.read()

            # 스키마 실행
            await self.conn.executescript(schema_sql)
            await self.conn.commit()

            print(f'✓ 데이터베이스 스키마 초기화 완료')

        except Exception as e:
            print(f'✗ 스키마 초기화 실패: {e}')
            raise

    # ========================================================================
    # 원시 이벤트 저장
    # ========================================================================

    async def insert_raw_event(self, event: Dict[str, Any]) -> Optional[int]:
        """
        원시 이벤트 삽입

        Args:
            event: 이벤트 데이터

        Returns:
            삽입된 이벤트의 ID
        """
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
            print(f'✗ raw_event 저장 실패: {e}')
            return None

    # ========================================================================
    # RPC 이벤트 저장
    # ========================================================================

    async def insert_rpc_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:
        """
        RPC 이벤트 삽입

        Args:
            event: RPC 이벤트 데이터
            raw_event_id: 연결된 raw_event ID

        Returns:
            삽입된 RPC 이벤트의 ID
        """
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
            print(f'✗ rpc_event 저장 실패: {e}')
            return None

    # ========================================================================
    # 파일 이벤트 저장
    # ========================================================================

    async def insert_file_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:
        """
        파일 이벤트 삽입

        Args:
            event: 파일 이벤트 데이터
            raw_event_id: 연결된 raw_event ID

        Returns:
            삽입된 파일 이벤트의 ID
        """
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
            print(f'✗ file_event 저장 실패: {e}')
            return None

    # ========================================================================
    # 프로세스 이벤트 저장
    # ========================================================================

    async def insert_process_event(self, event: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:
        """
        프로세스 이벤트 삽입

        Args:
            event: 프로세스 이벤트 데이터
            raw_event_id: 연결된 raw_event ID

        Returns:
            삽입된 프로세스 이벤트의 ID
        """
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
            print(f'✗ process_event 저장 실패: {e}')
            return None

    # ========================================================================
    # 엔진 결과 저장
    # ========================================================================

    async def insert_engine_result(self, result: Dict[str, Any], raw_event_id: int = None) -> Optional[int]:
        """
        엔진 분석 결과 삽입

        Args:
            result: 엔진 결과 데이터
            raw_event_id: 연결된 raw_event ID

        Returns:
            삽입된 엔진 결과의 ID
        """
        try:
            result_data = result.get('result', {})
            engine_name = result_data.get('detector', 'Unknown')
            detected = result.get('detected', False)
            severity = result_data.get('severity')
            score = result_data.get('evaluation') if isinstance(result_data.get('evaluation'), int) else None
            detail = json.dumps(result_data, ensure_ascii=False)

            cursor = await self.conn.execute(
                """
                INSERT INTO engine_results
                (raw_event_id, engine_name, detected, severity, score, detail)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (raw_event_id, engine_name, detected, severity, score, detail)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f'✗ engine_result 저장 실패: {e}')
            return None

    # ========================================================================
    # Semantic Gap 결과 저장
    # ========================================================================

    async def insert_semantic_gap_result(
        self,
        engine_result_id: int,
        evaluation: Any,
        original_event: Dict[str, Any]
    ) -> Optional[int]:
        """
        Semantic Gap 분석 결과 삽입

        Args:
            engine_result_id: 연결된 engine_result ID
            evaluation: 평가 결과 (int 또는 dict)
            original_event: 원본 이벤트

        Returns:
            삽입된 결과의 ID
        """
        try:
            # detail_mode인 경우 (dict)
            if isinstance(evaluation, dict):
                domain_match = evaluation.get('DomainMatch', 0)
                operation_match = evaluation.get('OperationMatch', 0)
                argument_specificity = evaluation.get('ArgumentSpecificity', 0)
                consistency = evaluation.get('Consistency', 0)
                penalties = json.dumps(evaluation.get('Penalties', []), ensure_ascii=False)
                final_score = evaluation.get('Score', 0)
            else:
                # 단순 점수 모드
                domain_match = None
                operation_match = None
                argument_specificity = None
                consistency = None
                penalties = None
                final_score = int(evaluation) if evaluation else 0

            tool_spec = json.dumps(original_event.get('data', {}).get('toolSpec'), ensure_ascii=False) if original_event.get('data', {}).get('toolSpec') else None
            event_description = str(original_event)

            cursor = await self.conn.execute(
                """
                INSERT INTO semantic_gap_results
                (engine_result_id, domain_match, operation_match, argument_specificity,
                 consistency, penalties, final_score, tool_spec, event_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (engine_result_id, domain_match, operation_match, argument_specificity,
                 consistency, penalties, final_score, tool_spec, event_description)
            )

            await self.conn.commit()
            return cursor.lastrowid

        except Exception as e:
            print(f'✗ semantic_gap_result 저장 실패: {e}')
            return None

    # ========================================================================
    # 조회 메서드
    # ========================================================================

    async def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        최근 이벤트 조회

        Args:
            limit: 조회할 이벤트 개수

        Returns:
            이벤트 목록
        """
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

    async def get_high_semantic_gap_results(self, threshold: int = 80, limit: int = 100) -> List[Dict[str, Any]]:
        """
        고득점 Semantic Gap 결과 조회

        Args:
            threshold: 점수 임계값
            limit: 조회할 결과 개수

        Returns:
            결과 목록
        """
        try:
            async with self.conn.execute(
                """
                SELECT * FROM v_high_semantic_gap
                WHERE final_score >= ?
                LIMIT ?
                """,
                (threshold, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            print(f'✗ Semantic Gap 결과 조회 실패: {e}')
            return []

    async def get_event_statistics(self) -> Dict[str, Any]:
        """
        이벤트 통계 조회

        Returns:
            통계 정보
        """
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
            print(f'✗ 통계 조회 실패: {e}')
            return {}

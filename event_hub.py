"""
EventHub - Central event processing hub for 82ch

Processes events from Observer and routes them to detection engines.
No ZeroMQ - direct in-process communication.
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime


class EventHub:
    """
    Central event processing hub.

    Receives events from Observer, stores them in database,
    and routes them to detection engines for analysis.
    """

    def __init__(self, engines: List, db):
        self.engines = engines
        self.db = db
        self.running = False
        self.event_id_map = {}  # {event_ts: raw_event_id} - 이벤트와 결과 연결용

    async def start(self):
        """Start the EventHub."""
        self.running = True
        print('[EventHub] Started')

    async def stop(self):
        """Stop the EventHub."""
        self.running = False
        print('[EventHub] Stopped')

    async def process_event(self, event: Dict[str, Any]) -> None:
        """
        Process a single event synchronously.

        1. Save event to database
        2. Route to all interested engines
        3. Save engine results to database

        Args:
            event: Event dictionary with eventType, producer, data, etc.
        """
        if not self.running:
            return

        try:
            # Save event to database and get raw_event_id
            raw_event_id = await self._save_event(event)

            # Add raw_event_id to event for engines to use
            if raw_event_id:
                event['raw_event_id'] = raw_event_id
            else:
                print(f"[EventHub] WARNING: Failed to save event to DB, raw_event_id is None for ts={event.get('ts')}")

            # Route to engines
            tasks = []
            for engine in self.engines:
                # Check if engine is interested in this event
                if engine.should_process(event):
                    task = self._process_with_engine(engine, event)
                    tasks.append(task)

            # Wait for all engines to process
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Save results
                for result in results:
                    if result and not isinstance(result, Exception):
                        await self._save_result(result)

        except Exception as e:
            print(f'[EventHub] Error processing event: {e}')

    async def _save_event(self, event: Dict[str, Any]) -> Optional[int]:
        """Save event to database and return raw_event_id."""
        try:
            event_type = event.get('eventType', 'Unknown')

            # Save to raw_events table
            raw_event_id = await self.db.insert_raw_event(event)

            if raw_event_id and 'ts' in event:
                self.event_id_map[event['ts']] = raw_event_id

                # Save to type-specific tables
                if event_type.lower() in ['rpc', 'jsonrpc', 'mcp']:
                    await self.db.insert_rpc_event(event, raw_event_id)

                    # Extract MCP tool information if present
                    data = event.get('data', {})
                    message = data.get('message', {})
                    task = data.get('task', '')

                    if task == 'RECV' and 'tools' in message.get('result', {}):
                        inserted_tools = await self.db.insert_mcpl()
                        if inserted_tools:  # list of tools or empty list
                            print(f'[EventHub] Extracted {len(inserted_tools)} tool(s) to mcpl table')
                            # MCPL에 tools가 저장되었으므로 ToolsPoisoningEngine에 전달
                            if len(inserted_tools) > 0:
                                await self._process_mcpl_tools(inserted_tools, event)

                elif event_type.lower() in ['file', 'fileio']:
                    await self.db.insert_file_event(event, raw_event_id)
                elif event_type.lower() == 'process':
                    await self.db.insert_process_event(event, raw_event_id)

            return raw_event_id

        except Exception as e:
            print(f'[EventHub] Error saving event: {e}')
            return None

    async def _save_result(self, result: Dict[str, Any]):
        """Save engine detection result to database."""
        try:
            # Get raw_event_id from result or original_event
            raw_event_id = None
            result_data = result.get('result', {})
            original_event = result_data.get('original_event', {})

            # 1. First try to get from original_event (engines may include it directly)
            if 'raw_event_id' in original_event:
                raw_event_id = original_event['raw_event_id']
            # 2. Fallback to event_id_map lookup by timestamp
            elif 'ts' in original_event:
                raw_event_id = self.event_id_map.get(original_event['ts'])
                if raw_event_id is None:
                    print(f"[EventHub] WARNING: raw_event_id not found for ts={original_event['ts']}")
                    print(f"[EventHub] Available timestamps in map: {list(self.event_id_map.keys())[:5]}")

            # Extract server name and producer
            server_name = original_event.get('mcpTag')
            producer = original_event.get('producer', 'unknown')

            # Save engine result
            engine_result_id = await self.db.insert_engine_result(
                result, raw_event_id, server_name, producer
            )

            if not engine_result_id:
                print(f'[EventHub] Failed to save engine result')
                return

            detector = result_data.get('detector')
            severity = result_data.get('severity')
            print(f'[EventHub] Saved detection result (id={engine_result_id}, detector={detector}, severity={severity}, server={server_name})')

        except Exception as e:
            print(f'[EventHub] Error saving result: {e}')

    async def _process_with_engine(self, engine, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process event with a specific engine."""
        try:
            result = await engine.handle_event(event)
            return result
        except Exception as e:
            print(f'[EventHub] [{engine.name}] Error: {e}')
            return None

    async def _process_mcpl_tools(self, inserted_tools: list, event: Dict[str, Any]) -> None:
        """
        MCPL 테이블에 tools가 INSERT된 직후 ToolsPoisoningEngine을 실행합니다.

        Args:
            inserted_tools: insert_mcpl()에서 반환된 tools 리스트
            event: 원본 이벤트 (메타데이터용)
        """
        try:
            # ToolsPoisoningEngine 찾기
            tools_poisoning_engine = None
            for engine in self.engines:
                if engine.name == 'ToolsPoisoningEngine':
                    tools_poisoning_engine = engine
                    break

            if not tools_poisoning_engine:
                print('[EventHub] ToolsPoisoningEngine not found, skipping MCPL processing')
                return

            print(f'[EventHub] Triggering ToolsPoisoningEngine for {len(inserted_tools)} newly inserted tools')

            # ToolsPoisoningEngine의 process_tools 메서드 직접 호출
            result = await tools_poisoning_engine.process_tools(inserted_tools, event)

            # 결과 저장
            if result:
                if isinstance(result, list):
                    # 여러 결과인 경우
                    for r in result:
                        await self._save_result(r)
                else:
                    # 단일 결과인 경우
                    await self._save_result(result)

        except Exception as e:
            print(f'[EventHub] Error processing MCPL tools: {e}')
            import traceback
            traceback.print_exc()
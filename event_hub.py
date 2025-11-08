import asyncio
from typing import List, Optional, Dict, Any


class EventHub:
    def __init__(self, source, engines: List, db):
        self.source = source
        self.engines = engines
        self.db = db
        self.running = False
        self.event_id_map = {}  # {event_ts: raw_event_id} - 이벤트와 결과 연결용
        
    async def start(self):
        self.running = True
        
        # 이벤트 소스 시작
        await self.source.start()
        
        print('EventHub 시작됨')
        
        # 메인 이벤트 루프
        await self._event_loop()
    
    async def stop(self):
        self.running = False
        await self.source.stop()
        print('EventHub 중지됨')
    
    async def _event_loop(self):
        """
        메인 이벤트 처리 루프

        1. 이벤트 수신
        2. 데이터베이스에 이벤트 저장
        3. 모든 엔진에 병렬 처리
        4. 데이터베이스에 결과 저장
        """
        while self.running:
            try:
                # 이벤트 수신 (0.1초 타임아웃)
                event = await self.source.get_event(timeout=0.1)

                if event is None:
                    # 타임아웃 또는 데이터 없음
                    await asyncio.sleep(0.01)
                    continue

                # 데이터베이스에 이벤트 저장 (백그라운드)
                asyncio.create_task(self._save_event(event))

                # 모든 엔진에 병렬 처리 요청
                tasks = []
                for engine in self.engines:
                    # 엔진이 관심있는 이벤트인지 확인
                    if engine.should_process(event):
                        task = self._process_with_engine(engine, event)
                        tasks.append(task)

                # 모든 엔진 처리 완료 대기 (에러는 무시)
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    # 결과 저장 (백그라운드)
                    for result in results:
                        if result and not isinstance(result, Exception):
                            asyncio.create_task(self._save_result(result))

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f'✗ EventHub 오류: {e}')
                await asyncio.sleep(0.1)
    
    async def _save_event(self, event: Dict[str, Any]):
        try:
            event_type = event.get('eventType', 'Unknown')

            # raw_events 테이블에 저장
            raw_event_id = await self.db.insert_raw_event(event)

            if raw_event_id and 'ts' in event:
                self.event_id_map[event['ts']] = raw_event_id

                # 이벤트 타입별 추가 저장
                if event_type.lower() in ['rpc', 'jsonrpc', 'mcp']:
                    await self.db.insert_rpc_event(event, raw_event_id)

                    # if(mcp event) -> mcpl tool information extraction
                    data = event.get('data', {})
                    message = data.get('message', {})
                    task = data.get('task', '')

                    if task == 'RECV' and 'tools' in message.get('result', {}):
                        count = await self.db.insert_mcpl()
                        if count and count > 0:
                            # print(f'mcpl {count}')
                            pass

                elif event_type.lower() in ['file', 'fileio']:
                    await self.db.insert_file_event(event, raw_event_id)
                elif event_type.lower() == 'process':
                    await self.db.insert_process_event(event, raw_event_id)

        except Exception as e:
            print(f'이벤트 저장 오류: {e}')

    async def _save_result(self, result: Dict[str, Any]):
        try:
            # 원본 이벤트의 ts를 찾아서 raw_event_id 매핑
            raw_event_id = None
            result_data = result.get('result', {})
            original_event = result_data.get('original_event', {})

            if 'ts' in original_event:
                raw_event_id = self.event_id_map.get(original_event['ts'])

            # mcpTag (serverName) 추출
            server_name = original_event.get('mcpTag')

            # 엔진 결과 저장
            engine_result_id = await self.db.insert_engine_result(result, raw_event_id)

            # Tools Poisoning 결과인 경우 추가 저장
            if engine_result_id and result_data.get('detector') == 'ToolsPoisoning':
                evaluation = result_data.get('evaluation')
                if evaluation is not None:
                    await self.db.insert_tools_poisoning_result(
                        engine_result_id,
                        evaluation,
                        original_event
                    )

            if not engine_result_id:
                print(f'✗ engine_result 저장 실패 - engine_result_id가 None')
                return

            detector = result_data.get('detector')
            print(f'✓ engine_result 저장 성공 (id={engine_result_id}, detector={detector}, serverName={server_name})')

        except Exception as e:
            print(f'결과 저장 오류: {e}')

    async def _process_with_engine(self, engine, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            result = await engine.handle_event(event)
            return result
        except Exception as e:
            print(f' [{engine.name}] 처리 오류: {e}')
            return None
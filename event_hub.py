"""
Event Hub - 이벤트 수신 및 분배

- ZeroMQ에서 이벤트 수신
- 모든 엔진에 병렬 처리 요청
- 결과를 로거에 전달
"""

import asyncio
from typing import List, Optional, Dict, Any


class EventHub:
    """
    이벤트 허브
    
    1. EventSource에서 이벤트 수신
    2. 모든 엔진에 병렬로 전달 (asyncio.gather)
    3. 로거에 이벤트 및 결과 기록
    """
    
    def __init__(self, source, engines: List, logger):
        """
        Args:
            source: 이벤트 소스 (ZeroMQSource 등)
            engines: 분석 엔진 리스트
            logger: 로거
        """
        self.source = source
        self.engines = engines
        self.logger = logger
        self.running = False
        
    async def start(self):
        """이벤트 허브 시작"""
        self.running = True
        
        # 이벤트 소스 시작
        await self.source.start()
        
        print('✓ EventHub 시작됨')
        
        # 메인 이벤트 루프
        await self._event_loop()
    
    async def stop(self):
        """이벤트 허브 중지"""
        self.running = False
        await self.source.stop()
        print('✓ EventHub 중지됨')
    
    async def _event_loop(self):
        """
        메인 이벤트 처리 루프
        
        1. 이벤트 수신
        2. 입력 이벤트 로깅
        3. 모든 엔진에 병렬 처리
        4. 결과 로깅
        """
        while self.running:
            try:
                # 이벤트 수신 (0.1초 타임아웃)
                event = await self.source.get_event(timeout=0.1)
                
                if event is None:
                    # 타임아웃 또는 데이터 없음
                    await asyncio.sleep(0.01)
                    continue
                
                # 이벤트 로깅 (백그라운드)
                asyncio.create_task(self.logger.log_event(event))
                
                # 모든 엔진에 병렬 처리 요청
                tasks = []
                for engine in self.engines:
                    # 엔진이 관심있는 이벤트인지 확인
                    if engine.should_process(event):
                        task = self._process_with_engine(engine, event)
                        tasks.append(task)
                
                # 모든 엔진 처리 완료 대기 (에러는 무시)
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f'✗ EventHub 오류: {e}')
                await asyncio.sleep(0.1)
    
    async def _process_with_engine(self, engine, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        엔진으로 이벤트 처리

        Args:
            engine: 분석 엔진
            event: 이벤트 데이터

        Returns:
            처리 결과 (없으면 None)
        """
        try:
            result = await engine.handle_event(event)
            return result
        except Exception as e:
            print(f'✗ [{engine.name}] 처리 오류: {e}')
            return None
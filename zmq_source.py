import zmq
import zmq.asyncio
import json
from typing import Optional, Dict, Any


class ZeroMQSource:
    def __init__(self, zmq_address: str = "tcp://localhost:5555"):
        self.zmq_address = zmq_address
        self.context = None
        self.socket = None
        self.running = False
    
    async def start(self):
        if self.running:
            return
        
        try:
            # 비동기 ZeroMQ 컨텍스트 생성
            self.context = zmq.asyncio.Context()
            self.socket = self.context.socket(zmq.SUB)
            
            # Publisher에 연결
            self.socket.connect(self.zmq_address)
            
            # 모든 토픽 구독
            self.socket.setsockopt_string(zmq.SUBSCRIBE, "")
            
            # 타임아웃 설정 없음 (비동기 방식)
            
            self.running = True
            print(f'ZeroMQ Subscriber 연결됨: {self.zmq_address}')
            
        except Exception as e:
            print(f'ZeroMQ 연결 실패: {e}')
            self.running = False
            raise
    
    async def stop(self):
        if not self.running:
            return
        
        self.running = False
        
        if self.socket:
            self.socket.close()
            self.socket = None
        
        if self.context:
            self.context.term()
            self.context = None
        
        print('ZeroMQ 연결 종료됨')
    
    async def get_event(self, timeout: float = 0.1) -> Optional[Dict[str, Any]]:
        if not self.running or not self.socket:
            return None
        
        try:
            # 비동기 수신 
            if await self.socket.poll(timeout=int(timeout * 1000)):  # ms로 변환
                # multipart 메시지 수신
                message = await self.socket.recv_multipart()
                if len(message) < 2:
                    return None
                # topic은 무시, data만 사용
                json_data = message[1].decode('utf-8')
                # JSON 파싱 및 검증
                data = json.loads(json_data)               
                # eventType 필드 확인
                if "eventType" in data:
                    return data
                else:
                    return None
            else:
                # 타임아웃
                return None
                
        except json.JSONDecodeError:
            # JSON 파싱 실패
            return None
        except zmq.ZMQError as e:
            if self.running:
                print(f'ZeroMQ 오류: {e}')
            return None
        except Exception as e:
            if self.running:
                print(f'이벤트 수신 오류: {e}')
            return None
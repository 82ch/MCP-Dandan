"""
82ch-Engine Server
ZeroMQ에서 이벤트를 직접 받아 엔진들에게 전달하고 결과를 로깅합니다.
"""

import asyncio
import signal
import sys
from typing import List
from config_loader import ConfigLoader
from event_hub import EventHub
from zmq_source import ZeroMQSource
from logger import Logger
from engines.sensitive_file_engine import SensitiveFileEngine
from engines.semantic_gap_engine import SemanticGapEngine
from engines.command_injection_engine import CommandInjectionEngine
from engines.file_system_exposure_engine import FileSystemExposureEngine


class EngineServer:
    """통합 분석 엔진 서버"""
    
    def __init__(self):
        self.config = ConfigLoader()
        self.logger = Logger(self.config)
        self.engines = []
        self.event_hub = None
        
    def _setup_engines(self):
        """엔진 초기화"""
        # Sensitive File Engine
        if self.config.get_sensitive_file_enabled():
            engine = SensitiveFileEngine(self.logger)
            self.engines.append(engine)

        # Semantic Gap Engine
        if self.config.get_semantic_gap_enabled():
            engine = SemanticGapEngine(
                self.logger,
                detail_mode=False
            )
            self.engines.append(engine)

        # Command Injection Engine
        if self.config.get_command_injection_enabled():
            engine = CommandInjectionEngine(self.logger)
            self.engines.append(engine)

        # File System Exposure Engine
        if self.config.get_file_system_exposure_enabled():
            engine = FileSystemExposureEngine(self.logger)
            self.engines.append(engine)

        print(f"\n실행 중인 엔진:")
        for i, engine in enumerate(self.engines, 1):
            print(f"  {i}. {engine.name}")
    
    def _setup_event_hub(self):
        """이벤트 허브 초기화"""
        zmq_address = self.config.get_zmq_address()
        source = ZeroMQSource(zmq_address)
        self.event_hub = EventHub(source, self.engines, self.logger)
    
    async def start(self):
        """서버 시작"""
        print("=" * 80)
        print("82ch-Engine Server 시작")
        print("=" * 80)
        
        # 설정 출력
        print(f"\n설정:")
        print(f"  - ZeroMQ 주소: {self.config.get_zmq_address()}")
        print(f"  - 로그 디렉토리: {self.config.get_log_dir()}")
        
        # 엔진 설정
        self._setup_engines()
        
        # 이벤트 허브 설정
        self._setup_event_hub()
        
        # Logger 시작
        await self.logger.start()
        
        print("\n" + "=" * 80)
        print("✓ 모든 컴포넌트가 실행 중입니다.")
        print("  MCPCollector가 실행 중이어야 이벤트를 수신할 수 있습니다.")
        print("  종료하려면 Ctrl+C를 누르세요.")
        print("=" * 80 + "\n")
        
        # EventHub 시작 (메인 루프)
        await self.event_hub.start()
    
    async def stop(self):
        """서버 중지"""
        print('\n프로그램을 종료합니다...')
        
        if self.event_hub:
            await self.event_hub.stop()
        
        if self.logger:
            await self.logger.stop()
        
        print('✓ 모든 컴포넌트가 중지되었습니다.')


async def main():
    """메인 함수"""
    server = EngineServer()
    
    # Ctrl+C 처리
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        print("\n\n[Signal] Ctrl+C 감지됨")
        asyncio.create_task(server.stop())
        loop.stop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)
    else:
        print("[!] Windows 환경: signal handler를 건너뜁니다 (KeyboardInterrupt로 종료 가능)")

    try:
        await server.start()
    except KeyboardInterrupt:
        await server.stop()
    except Exception as e:
        print(f"\n오류 발생: {e}")
        await server.stop()
        sys.exit(1)


if __name__ == '__main__':
    # Windows에서 asyncio 이벤트 루프 정책 설정
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
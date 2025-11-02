from abc import ABC, abstractmethod
from typing import Any


class BaseEngine(ABC):
    """
    모든 분석 엔진의 공통 기반 클래스 (Refactored - No Queue)
    """

    def __init__(self, logger, name: str, event_types: list[str] | None = None):
        """
        Args:
            logger: Logger 인스턴스
            name: 엔진 이름
            event_types: 처리할 이벤트 타입 리스트 (None이면 모든 이벤트 처리)
        """
        self.logger = logger
        self.name = name
        self.event_types = event_types or []

    def should_process(self, data: dict) -> bool:
        """
        엔진이 해당 이벤트를 처리해야 하는지 여부를 결정.
        EventHub에서 호출됨.
        """
        if not self.event_types:
            return True  # 모든 이벤트 처리
        return data.get("eventType") in self.event_types
    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        실제 이벤트 분석 로직 — 하위 클래스에서 반드시 구현해야 함.
        """
        pass

    async def handle_event(self, data: Any):
        """
        공통 이벤트 처리 진입점.
        event_types 필터링 후 process() 호출.
        """
        # 이벤트 타입 필터링
        if self.event_types and data.get('eventType') not in self.event_types:
            return None

        try:
            result = self.process(data)
            if result:
                await self.logger.write(result)
        except Exception as e:
            print(f"[{self.name}] ERROR: {e}")

from abc import ABC, abstractmethod
from typing import Any
from utils import safe_print


class BaseEngine(ABC):

    def __init__(self, db, name: str, event_types: list[str] | None = None, producers: list[str] | None = None):
        self.db = db
        self.name = name
        self.event_types = event_types or []
        self.producers = producers or []

    def should_process(self, data: dict) -> bool:
        # event_types 필터링
        if self.event_types and data.get("eventType") not in self.event_types:
            return False

        # producers 필터링
        if self.producers and data.get("producer") not in self.producers:
            return False

        return True

    @abstractmethod
    def process(self, data: Any) -> Any:
        raise NotImplementedError

    async def handle_event(self, data: Any):
        # 필터링 체크
        if not self.should_process(data):
            return None

        try:
            result = self.process(data)
            # process() Routine Chekc >> await
            if hasattr(result, '__await__'):
                result = await result
            return result
        except Exception as e:
            try:
                safe_print(f"[{self.name}] ERROR during processing: {e}")
            except Exception:
                pass
            return None

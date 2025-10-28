from threading import Thread, Event
from queue import Queue, Empty, Full
from typing import Dict, Optional
from config_loader import ConfigLoader
import copy


class EventDistributor:
    """
    이벤트 분배기

    메인 큐에서 이벤트를 가져와서:
    1. 등록된 모든 엔진 큐에 복사본 전송
    2. 이벤트 로그 큐에도 복사본 전송 (입력 이벤트 로깅)
    """

    def __init__(self, main_queue: Queue, engine_queues: Dict[str, Queue], event_log_queue: Optional[Queue] = None):
        """
        Args:
            main_queue: 메인 이벤트 큐 (EventProvider가 이벤트를 푸시)
            engine_queues: 엔진 이름 -> 엔진 입력 큐 매핑 딕셔너리
            event_log_queue: 이벤트 로그 큐 (입력 이벤트 로깅용, 선택사항)
        """
        config = ConfigLoader()

        self.main_queue = main_queue
        self.engine_queues = engine_queues
        self.event_log_queue = event_log_queue
        self.queue_timeout = config.get_queue_timeout()

        self._distribute_thread = None
        self._stop_event = Event()
        self._running = False

    def start(self):
        """분배 스레드 시작"""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        self._distribute_thread = Thread(target=self._distribute_loop, daemon=True)
        self._distribute_thread.start()

        print('✓ EventDistributor 시작됨')

    def stop(self):
        """분배 스레드 중지"""
        if not self._running:
            return

        self._stop_event.set()

        if self._distribute_thread and self._distribute_thread.is_alive():
            self._distribute_thread.join()

        self._running = False
        print('✓ EventDistributor 중지됨')

    def _distribute_loop(self):
        """
        메인 큐에서 이벤트를 가져와 모든 엔진 큐 + 이벤트 로그 큐에 복사 전송

        - 메인 큐에서 이벤트를 가져옴
        - 각 엔진 큐에 deepcopy하여 전송 (각 엔진이 독립적으로 처리 가능)
        - 이벤트 로그 큐에도 전송 (입력 이벤트 기록)
        - 큐가 가득 차면 스킵 (엔진이 처리 속도를 따라가지 못하는 경우)
        """
        while not self._stop_event.is_set():
            try:
                # 메인 큐에서 이벤트 가져오기
                event = self.main_queue.get(timeout=self.queue_timeout)

                # 이벤트 로그 큐에 전송 (입력 이벤트 로깅)
                if self.event_log_queue:
                    try:
                        event_copy = copy.deepcopy(event)
                        self.event_log_queue.put(event_copy, block=False)
                    except Full:
                        print(f'⚠️  [EventLog] 큐가 가득 참, 이벤트 드롭')

                # 모든 엔진 큐에 복사본 전송
                for engine_name, engine_queue in self.engine_queues.items():
                    try:
                        # deepcopy로 각 엔진이 독립적으로 데이터를 수정할 수 있도록 함
                        event_copy = copy.deepcopy(event)

                        # 큐가 가득 차면 스킵 (block=False)
                        engine_queue.put(event_copy, block=False)

                    except Full:
                        # 엔진 큐가 가득 참 - 이벤트 드롭
                        print(f'⚠️  [{engine_name}] 큐가 가득 차서 이벤트 드롭')
                        continue

            except Empty:
                # 메인 큐가 비어있음 - 계속 대기
                continue
            except Exception as e:
                # 예상치 못한 오류
                print(f'✗ EventDistributor 오류: {e}')
                continue

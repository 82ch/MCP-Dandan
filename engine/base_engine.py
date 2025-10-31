from abc import ABC, abstractmethod
from threading import Thread, Event
from queue import Queue, Empty, Full
from typing import Any, Optional, List
from datetime import datetime
from config_loader import ConfigLoader


class BaseEngine(ABC):
    """
    공통 분석 엔진 베이스 클래스

    - 입력: 입력 큐에서 데이터를 받음
    - 필터링: event_types로 지정된 이벤트만 처리
    - 처리: process() 메서드로 데이터 처리 (엔진이 자체 버퍼링 가능)
    - 출력: 처리 결과를 JSON 형식으로 로그 큐에 전송
    """

    def __init__(self, input_queue: Queue, log_queue: Queue, name: str, event_types: Optional[List[str]] = None):
        """
        Args:
            input_queue: 입력 큐 (EventDistributor가 이벤트를 푸시)
            log_queue: 로그 큐 (처리 결과를 푸시)
            name: 엔진 이름
            event_types: 처리할 이벤트 타입 리스트 (예: ['File'])
                        None = 모든 이벤트 처리
                        ['File'] = File 이벤트만 처리
                        ['File', 'MCP'] = File, MCP 이벤트만 처리
        """
        config = ConfigLoader()

        self.input_queue = input_queue
        self.log_queue = log_queue
        self.name = name
        self.event_types = event_types

        # 성능 튜닝 파라미터 로드
        self._queue_timeout = config.get_queue_timeout()

        self._process_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False

    def start(self):
        """엔진 시작 (처리 스레드 시작)"""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        # 처리 스레드 시작
        self._process_thread = Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

        print(f'✓ [{self.name}] 엔진 시작됨')

    def stop(self):
        """엔진 중지"""
        if not self._running:
            return

        self._stop_event.set()

        # 처리 스레드 종료 대기
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join()

        self._running = False
        print(f'✓ [{self.name}] 엔진 중지됨')

    def _process_loop(self):
        """
        처리 루프: 입력 큐에서 데이터를 가져와 process() 실행 후 로그 큐로 전송

        - event_types가 지정된 경우 매칭되는 이벤트만 처리
        - 매칭되지 않는 이벤트는 스킵
        """
        while not self._stop_event.is_set():
            try:
                # 입력 큐에서 데이터 가져오기
                data = self.input_queue.get(timeout=self._queue_timeout)

                # event_type 필터링
                if self.event_types is not None:
                    event_type = data.get('eventType')
                    if event_type not in self.event_types:
                        # 관심 없는 이벤트 타입은 스킵
                        continue

                try:
                    # 처리 로직 실행
                    result = self.process(data)

                    # 결과가 있으면 로그 큐로 전송
                    if result is not None:
                        self._send_output(result)

                except Exception as e:
                    # 처리 중 오류 발생
                    print(f'✗ [{self.name}] 처리 오류: {e}')

            except Empty:
                # 입력 큐가 비어있음 - 계속 대기
                continue

    def _send_output(self, result: Any):
        """출력 메서드: 결과를 JSON 형식으로 만들어 로그 큐에 전송"""
        try:
            # JSON 형식으로 변환
            output_data = self._format_output(result)

            # 로그 큐에 전송 (큐가 가득 차면 스킵)
            self.log_queue.put(output_data, block=False)

        except Full:
            print(f'⚠️  [{self.name}] 로그 큐가 가득 차서 결과 드롭')
        except Exception as e:
            print(f'✗ [{self.name}] 출력 오류: {e}')

    def _format_output(self, result: Any) -> dict:
        """
        결과를 JSON 형식으로 변환

        Args:
            result: 처리 결과 (dict 형태)

        Returns:
            JSON 형식의 출력 데이터
        """
        # result에서 detected, reference, result 추출
        if isinstance(result, dict):
            detected = result.get('detected', True)
            reference = result.get('reference', [])
            detail_result = result.get('result', result)
        else:
            detected = True
            reference = []
            detail_result = result

        # reference를 리스트로 정규화
        if reference is None:
            reference = []
        elif isinstance(reference, str):
            # 단일 reference는 리스트로 변환
            reference = [reference]
        elif not isinstance(reference, list):
            # 기타 타입은 빈 리스트로
            reference = []

        output = {
            "timestamp": datetime.now().isoformat(),
            "engine": self.name,
            "detected": detected,
            "reference": reference,  # 필수 필드, 리스트 형식
            "result": detail_result
        }

        return output

    @abstractmethod
    def process(self, data: Any) -> Any:
        """
        데이터 처리 로직 (반드시 구현 필요)

        Args:
            data: 입력 데이터 (event_types로 필터링된 이벤트)

        Returns:
            처리된 결과 (None이면 출력하지 않음)
        """
        pass

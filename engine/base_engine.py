from abc import ABC, abstractmethod
from threading import Thread, Event
from queue import Queue, Empty
from typing import Any, Optional, List
from kafka import KafkaConsumer, KafkaProducer
import json
from datetime import datetime
from config_loader import ConfigLoader


class BaseEngine(ABC):
    """
    공통 분석 엔진 베이스 클래스

    - 입력: Kafka에서 데이터를 받아 큐에 저장
    - 처리: 큐에서 데이터를 가져와 process() 메서드로 처리
    - 출력: 처리 결과를 JSON 형식으로 Kafka에 전송
    """

    def __init__(self,
                 input_topics: List[str],
                 output_topic: str,
                 consumer_group: str):
        """
        Args:
            input_topics: 입력 토픽 리스트 (여러 개 구독 가능)
            output_topic: 출력 토픽
            consumer_group: Consumer 그룹 ID (필수, 각 엔진은 고유한 그룹을 가져야 함)
        """
        # 설정 파일에서 모든 설정 로드
        config = ConfigLoader()
        self.kafka_brokers = config.get_kafka_brokers()
        self.input_topics = input_topics
        self.output_topic = output_topic
        self.consumer_group = consumer_group

        # 성능 튜닝 파라미터 로드
        self._queue_maxsize = config.get_queue_maxsize()
        self._poll_timeout_ms = config.get_poll_timeout_ms()
        self._queue_timeout = config.get_queue_timeout()

        self._queue = Queue(maxsize=self._queue_maxsize)
        self._input_thread: Optional[Thread] = None
        self._process_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._running = False

        self.consumer: Optional[KafkaConsumer] = None
        self.producer: Optional[KafkaProducer] = None

    def start(self):
        """엔진 시작 (입력, 처리, 출력 쓰레드 모두 시작)"""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        # Kafka Consumer/Producer 초기화
        self._init_kafka()

        # 입력 쓰레드 시작
        self._input_thread = Thread(target=self._input_loop, daemon=True)
        self._input_thread.start()

        # 처리 쓰레드 시작
        self._process_thread = Thread(target=self._process_loop, daemon=True)
        self._process_thread.start()

    def stop(self):
        """엔진 중지"""
        if not self._running:
            return

        self._stop_event.set()

        # 모든 쓰레드 종료 대기
        if self._input_thread and self._input_thread.is_alive():
            self._input_thread.join()
        if self._process_thread and self._process_thread.is_alive():
            self._process_thread.join()

        # Kafka 연결 종료
        if self.consumer:
            self.consumer.close()
        if self.producer:
            self.producer.close()

        self._running = False

    def _init_kafka(self):
        """Kafka Consumer/Producer 초기화"""
        # Consumer 초기화 (여러 토픽 구독)
        self.consumer = KafkaConsumer(
            *self.input_topics,
            bootstrap_servers=self.kafka_brokers,
            group_id=self.consumer_group,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest'
        )

        # Producer 초기화
        self.producer = KafkaProducer(
            bootstrap_servers=self.kafka_brokers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8')
        )

    def _input_loop(self):
        """입력 메서드: Kafka에서 데이터를 받아 큐에 저장"""
        while not self._stop_event.is_set():
            try:
                # Kafka에서 메시지 읽기 (설정된 타임아웃 사용)
                messages = self.consumer.poll(timeout_ms=self._poll_timeout_ms)

                for records in messages.values():
                    for record in records:
                        # 큐에 데이터 저장 (큐가 가득 차면 빌 때까지 무한 대기)
                        self._queue.put(record.value, block=True)

            except Exception:
                pass

    def _process_loop(self):
        """처리 루프: 큐에서 데이터를 가져와 process() 실행 후 출력"""
        while not self._stop_event.is_set():
            try:
                # 큐에서 데이터 가져오기 (설정된 타임아웃 사용)
                data = self._queue.get(timeout=self._queue_timeout)

                try:
                    # 처리 로직 실행
                    result = self.process(data)

                    # 결과가 있으면 Kafka로 전송
                    if result is not None:
                        self._send_output(result)

                except Exception:
                    pass

            except Empty:
                continue

    def _send_output(self, result: Any):
        """출력 메서드: 결과를 JSON 형식으로 만들어 Kafka에 전송"""
        try:
            # JSON 형식으로 변환
            output_data = self._format_output(result)

            # Kafka에 전송
            self.producer.send(self.output_topic, value=output_data)

        except Exception:
            pass

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
            "engine": self.__class__.__name__,
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
            data: 입력 데이터

        Returns:
            처리된 결과 (None이면 출력하지 않음)
        """
        pass

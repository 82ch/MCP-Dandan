import configparser
import os
from typing import List


class ConfigLoader:
    """
    설정 파일 로더

    config.conf 파일을 읽어서 설정값을 제공합니다.
    """

    def __init__(self, config_path: str = 'config.conf'):
        """
        Args:
            config_path: 설정 파일 경로 (기본값: config.conf)
        """
        self.config_path = config_path
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_path):
            raise FileNotFoundError(f'설정 파일을 찾을 수 없습니다: {config_path}')

        self.config.read(config_path, encoding='utf-8')

    # Kafka 설정
    def get_kafka_brokers(self) -> List[str]:
        """Kafka 브로커 주소 리스트"""
        brokers_str = self.config.get('kafka', 'brokers', fallback='localhost:9092')
        return [broker.strip() for broker in brokers_str.split(',')]

    # Kafka Producer 설정 (삭제 예정)
    def get_client_id(self) -> str:
        """클라이언트 ID"""
        return self.config.get('kafka_producer', 'client_id', fallback='my-kafka-app')

    def get_process_path(self) -> str:
        """외부 프로세스 실행 경로"""
        return self.config.get('kafka_producer', 'process_path', fallback='')

    # Engine 설정
    def get_queue_maxsize(self) -> int:
        """큐 최대 크기"""
        return self.config.getint('engine', 'queue_maxsize', fallback=1000)

    def get_poll_timeout_ms(self) -> int:
        """Kafka poll 타임아웃 (밀리초)"""
        return self.config.getint('engine', 'poll_timeout_ms', fallback=1000)

    def get_queue_timeout(self) -> float:
        """큐 get 타임아웃 (초)"""
        return self.config.getfloat('engine', 'queue_timeout', fallback=0.1)

    # Sensitive File Engine 설정
    def get_sensitive_file_consumer_group(self) -> str:
        """민감 파일 엔진 Consumer 그룹 ID"""
        return self.config.get('sensitive_file_engine', 'consumer_group', fallback='sensitive-file-engine')

    def get_sensitive_file_input_topics(self) -> List[str]:
        """민감 파일 엔진 입력 토픽 리스트"""
        topics_str = self.config.get('sensitive_file_engine', 'input_topics', fallback='File')
        return [topic.strip() for topic in topics_str.split(',')]

    def get_sensitive_file_output_topic(self) -> str:
        """민감 파일 엔진 출력 토픽"""
        return self.config.get('sensitive_file_engine', 'output_topic', fallback='results')
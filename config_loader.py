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
        # 스크립트 파일의 디렉토리를 기준으로 설정 파일 경로를 찾음
        if not os.path.isabs(config_path):
            # 상대 경로인 경우, 이 파일이 있는 디렉토리를 기준으로 변환
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, config_path)

        self.config_path = config_path
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_path):
            raise FileNotFoundError(f'설정 파일을 찾을 수 없습니다: {config_path}')

        self.config.read(config_path, encoding='utf-8')

    # System 설정
    def get_main_queue_maxsize(self) -> int:
        """메인 이벤트 큐 최대 크기"""
        return self.config.getint('system', 'main_queue_maxsize', fallback=10000)

    def get_engine_queue_maxsize(self) -> int:
        """각 엔진별 입력 큐 최대 크기"""
        return self.config.getint('system', 'engine_queue_maxsize', fallback=1000)

    def get_event_log_queue_maxsize(self) -> int:
        """이벤트 로그 큐 최대 크기"""
        return self.config.getint('system', 'event_log_queue_maxsize', fallback=5000)

    def get_result_log_queue_maxsize(self) -> int:
        """결과 로그 큐 최대 크기"""
        return self.config.getint('system', 'result_log_queue_maxsize', fallback=5000)

    def get_queue_timeout(self) -> float:
        """큐 get 타임아웃 (초)"""
        return self.config.getfloat('system', 'queue_timeout', fallback=0.1)

    # Event Provider 설정
    def get_process_path(self) -> str:
        """외부 프로세스 실행 경로"""
        return self.config.get('event_provider', 'process_path', fallback='')

    # Log Writer 설정
    def get_log_directory(self) -> str:
        """로그 파일 저장 경로"""
        return self.config.get('log_writer', 'log_directory', fallback='./logs')

    def get_log_filename_prefix(self) -> str:
        """로그 파일명 접두사"""
        return self.config.get('log_writer', 'log_filename_prefix', fallback='engine_results')

    def get_max_log_file_size(self) -> int:
        """로그 파일 최대 크기 (MB)"""
        return self.config.getint('log_writer', 'max_log_file_size', fallback=100)

    def get_max_log_files(self) -> int:
        """로그 파일 최대 개수"""
        return self.config.getint('log_writer', 'max_log_files', fallback=10)

    # Sensitive File Engine 설정
    def get_sensitive_file_enabled(self) -> bool:
        """민감 파일 엔진 활성화 여부"""
        return self.config.getboolean('sensitive_file_engine', 'enabled', fallback=True)
import configparser
import os


class ConfigLoader:
    """
    설정 파일 로더

    config.conf 파일을 읽어서 설정 값들을 제공합니다.
    """

    def __init__(self, config_file: str = 'config.conf'):
        """
        Args:
            config_file: 설정 파일 경로 (기본값: config.conf)
        """
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_file):
            print(f'⚠️  경고: 설정 파일을 찾을 수 없습니다 - {config_file}')
            print(f'⚠️  config.conf.example을 참고하여 config.conf를 생성하세요.')
            return

        self.config.read(config_file, encoding='utf-8')

    # ========== EventProvider 설정 ==========
    
    def get_zmq_address(self) -> str:
        """
        ZeroMQ Subscriber 주소 가져오기

        Returns:
            str: ZeroMQ 주소 (기본값: tcp://localhost:5555)
        """
        return self.config.get('EventProvider', 'zmq_address', fallback='tcp://localhost:5555')

    def get_process_path(self) -> str:
        """
        외부 프로세스 경로 가져오기 (레거시 지원)

        Returns:
            str: 프로세스 경로 (없으면 빈 문자열)
        """
        return self.config.get('EventProvider', 'process_path', fallback='')

    # ========== Queue 설정 ==========

    def get_main_queue_size(self) -> int:
        """
        메인 큐 크기 가져오기

        Returns:
            int: 큐 크기 (기본값: 10000)
        """
        return self.config.getint('Queue', 'main_queue_size', fallback=10000)

    def get_main_queue_maxsize(self) -> int:
        """
        메인 큐 최대 크기 가져오기 (호환성)

        Returns:
            int: 큐 크기 (기본값: 10000)
        """
        return self.get_main_queue_size()

    def get_engine_queue_size(self) -> int:
        """
        엔진 큐 크기 가져오기

        Returns:
            int: 큐 크기 (기본값: 1000)
        """
        return self.config.getint('Queue', 'engine_queue_size', fallback=1000)

    def get_engine_queue_maxsize(self) -> int:
        """
        엔진 큐 최대 크기 가져오기 (호환성)

        Returns:
            int: 큐 크기 (기본값: 1000)
        """
        return self.get_engine_queue_size()

    def get_log_queue_size(self) -> int:
        """
        로그 큐 크기 가져오기

        Returns:
            int: 큐 크기 (기본값: 5000)
        """
        return self.config.getint('Queue', 'log_queue_size', fallback=5000)

    def get_event_log_queue_maxsize(self) -> int:
        """
        이벤트 로그 큐 최대 크기 가져오기

        Returns:
            int: 큐 크기 (기본값: 5000)
        """
        return self.config.getint('Queue', 'event_log_queue_size', fallback=5000)

    def get_result_log_queue_maxsize(self) -> int:
        """
        결과 로그 큐 최대 크기 가져오기

        Returns:
            int: 큐 크기 (기본값: 5000)
        """
        return self.config.getint('Queue', 'result_log_queue_size', fallback=5000)

    def get_queue_timeout(self) -> float:
        """
        큐 타임아웃 가져오기 (초)

        Returns:
            float: 큐 타임아웃 (기본값: 0.5초)
        """
        return self.config.getfloat('Queue', 'queue_timeout', fallback=0.5)

    # ========== Engine 설정 ==========

    def get_engine_list(self) -> list[str]:
        """
        활성화할 엔진 목록 가져오기

        Returns:
            list[str]: 엔진 이름 리스트
        """
        engine_str = self.config.get('Engine', 'active_engines', fallback='')
        if not engine_str:
            return []

        # 쉼표로 구분된 엔진 목록 파싱
        engines = [e.strip() for e in engine_str.split(',') if e.strip()]
        return engines

    def get_sensitive_file_enabled(self) -> bool:
        """
        Sensitive File Engine 활성화 여부

        Returns:
            bool: 활성화 여부 (기본값: True)
        """
        return self.config.getboolean('Engine', 'sensitive_file_enabled', fallback=True)

    def get_semantic_gap_enabled(self) -> bool:
        """
        Semantic Gap Engine 활성화 여부

        Returns:
            bool: 활성화 여부 (기본값: True)
        """
        return self.config.getboolean('Engine', 'semantic_gap_enabled', fallback=True)

    def get_command_injection_enabled(self) -> bool:
        """
        Command Injection Engine 활성화 여부

        Returns:
            bool: 활성화 여부 (기본값: True)
        """
        return self.config.getboolean('Engine', 'command_injection_enabled', fallback=True)

    def get_file_system_exposure_enabled(self) -> bool:
        """
        File System Exposure Engine 활성화 여부

        Returns:
            bool: 활성화 여부 (기본값: True)
        """
        return self.config.getboolean('Engine', 'file_system_exposure_enabled', fallback=True)

    # ========== Log 설정 ==========

    def get_log_dir(self) -> str:
        """
        로그 디렉토리 경로 가져오기

        Returns:
            str: 로그 디렉토리 경로 (기본값: ./logs)
        """
        return self.config.get('Log', 'log_dir', fallback='./logs')

    def get_log_rotation_size(self) -> int:
        """
        로그 파일 로테이션 크기 가져오기 (MB)

        Returns:
            int: 로테이션 크기 (기본값: 100MB)
        """
        return self.config.getint('Log', 'rotation_size_mb', fallback=100)
    
    def get_max_log_files(self) -> int:
        """
        최대 로그 파일 개수 가져오기

        Returns:
            int: 최대 로그 파일 개수 (기본값: 5)
        """
        return self.config.getint('Log', 'max_log_files', fallback=5)
    def get_max_log_file_size(self) -> int:
        """
        최대 로그 파일 크기 가져오기 (MB)
        Returns:
            int: 최대 로그 파일 크기 (기본값: 100MB)
        """
        return self.config.getint('Log', 'max_log_file_size_mb', fallback=100)
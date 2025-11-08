import configparser
import os


class ConfigLoader:
    def __init__(self, config_file: str = 'config.conf'):
        self.config = configparser.ConfigParser()

        if not os.path.exists(config_file):
            print(f'설정 파일을 찾을 수 없습니다 - {config_file}')
            print(f'config.conf.example을 참고하여 config.conf를 생성하세요.')
            return

        self.config.read(config_file, encoding='utf-8')

    # ========== EventProvider 설정 ==========
    
    def get_zmq_address(self) -> str:
        return self.config.get('EventProvider', 'zmq_address', fallback='tcp://localhost:5555')

    def get_process_path(self) -> str:
        return self.config.get('EventProvider', 'process_path', fallback='')

    # ========== Queue 설정 ==========

    def get_main_queue_size(self) -> int:
        return self.config.getint('Queue', 'main_queue_size', fallback=10000)

    def get_main_queue_maxsize(self) -> int:
        return self.get_main_queue_size()

    def get_engine_queue_size(self) -> int:
        return self.config.getint('Queue', 'engine_queue_size', fallback=1000)

    def get_engine_queue_maxsize(self) -> int:
        return self.get_engine_queue_size()

    def get_log_queue_size(self) -> int:
        return self.config.getint('Queue', 'log_queue_size', fallback=5000)

    def get_event_log_queue_maxsize(self) -> int:
        return self.config.getint('Queue', 'event_log_queue_size', fallback=5000)

    def get_result_log_queue_maxsize(self) -> int:
        return self.config.getint('Queue', 'result_log_queue_size', fallback=5000)

    def get_queue_timeout(self) -> float:
        return self.config.getfloat('Queue', 'queue_timeout', fallback=0.5)

    # ========== Engine 설정 ==========

    def get_engine_list(self) -> list[str]:
        engine_str = self.config.get('Engine', 'active_engines', fallback='')
        if not engine_str:
            return []
        engines = [e.strip() for e in engine_str.split(',') if e.strip()]
        return engines

    def get_sensitive_file_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'sensitive_file_enabled', fallback=True)

    def get_tools_poisoning_enabled(self) -> bool:
        """
        Tools Poisoning Engine 활성화 여부

        Returns:
            bool: 활성화 여부 (기본값: True)
        """
        return self.config.getboolean('Engine', 'tools_poisoning_enabled', fallback=True)

    def get_command_injection_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'command_injection_enabled', fallback=True)

    def get_file_system_exposure_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'file_system_exposure_enabled', fallback=True)

    # ========== Log 설정 ==========

    def get_log_dir(self) -> str:
        return self.config.get('Log', 'log_dir', fallback='./logs')

    def get_log_rotation_size(self) -> int:
        return self.config.getint('Log', 'rotation_size_mb', fallback=100)
    
    def get_max_log_files(self) -> int:
        return self.config.getint('Log', 'max_log_files', fallback=5)
    
    def get_max_log_file_size(self) -> int:
        return self.config.getint('Log', 'max_log_file_size_mb', fallback=100)
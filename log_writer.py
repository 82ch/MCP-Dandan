from threading import Thread, Event
from queue import Queue, Empty
from config_loader import ConfigLoader
from datetime import datetime
import os
import json
import glob
from typing import Dict


class LogWriter:
    """
    로그 작성기

    2개의 큐를 처리하여 파일로 저장합니다:
    1. event_queue -> 이벤트 타입별 파일 (File, Registry, Network 등)
       - raw_events_File_*.jsonl
       - raw_events_Registry_*.jsonl
       - raw_events_Network_*.jsonl
       등
    2. result_queue -> engine_results_*.jsonl (엔진 결과)

    - JSON Lines 형식 (.jsonl)
    - 로그 로테이션 지원 (크기 기반, 개수 제한)
    """

    def __init__(self, event_queue: Queue, result_queue: Queue):
        """
        Args:
            event_queue: 이벤트 로그 큐 (입력 이벤트)
            result_queue: 결과 로그 큐 (엔진 결과)
        """
        config = ConfigLoader()

        self.event_queue = event_queue
        self.result_queue = result_queue
        self.queue_timeout = config.get_queue_timeout()

        # 로그 설정
        self.log_directory = config.get_log_directory()
        self.max_log_file_size = config.get_max_log_file_size() * 1024 * 1024  # MB to bytes
        self.max_log_files = config.get_max_log_files()

        # 이벤트 타입별 로그 파일 핸들러 (동적 생성)
        # {eventType: (file_handle, file_path)}
        self._event_files: Dict[str, tuple] = {}

        # 결과 로그 파일 핸들러
        self._result_write_thread = None
        self._result_current_file = None
        self._result_current_file_path = None

        # 이벤트 로그 작성 스레드
        self._event_write_thread = None

        self._stop_event = Event()
        self._running = False

        # 로그 디렉토리 생성
        os.makedirs(self.log_directory, exist_ok=True)

    def start(self):
        """로그 작성 스레드 시작 (2개)"""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True

        # 초기 결과 로그 파일 생성
        self._rotate_result_log_file()

        # 이벤트 로그 작성 스레드 시작
        self._event_write_thread = Thread(target=self._event_write_loop, daemon=True)
        self._event_write_thread.start()

        # 결과 로그 작성 스레드 시작
        self._result_write_thread = Thread(target=self._result_write_loop, daemon=True)
        self._result_write_thread.start()

        print(f'✓ LogWriter 시작됨 (로그 경로: {self.log_directory})')
        print(f'  - 입력 이벤트: raw_events_<EventType>_*.jsonl (타입별 분리)')
        print(f'  - 엔진 결과: engine_results_*.jsonl')

    def stop(self):
        """로그 작성 스레드 중지"""
        if not self._running:
            return

        self._stop_event.set()

        # 스레드 종료 대기
        if self._event_write_thread and self._event_write_thread.is_alive():
            self._event_write_thread.join()
        if self._result_write_thread and self._result_write_thread.is_alive():
            self._result_write_thread.join()

        # 모든 이벤트 파일 닫기
        for event_type, (file_handle, _) in self._event_files.items():
            if file_handle:
                file_handle.close()

        # 결과 파일 닫기
        if self._result_current_file:
            self._result_current_file.close()

        self._running = False
        print('✓ LogWriter 중지됨')

    def _event_write_loop(self):
        """
        이벤트 로그 작성 루프

        event_queue에서 입력 이벤트를 가져와 이벤트 타입별로 파일에 저장
        - raw_events_File_*.jsonl
        - raw_events_Registry_*.jsonl
        - raw_events_Network_*.jsonl
        등
        """
        while not self._stop_event.is_set():
            try:
                # 이벤트 큐에서 데이터 가져오기
                log_entry = self.event_queue.get(timeout=self.queue_timeout)

                # eventType 추출
                event_type = log_entry.get('eventType', 'Unknown')

                # 해당 eventType 파일 핸들러 가져오기 (없으면 생성)
                if event_type not in self._event_files:
                    self._create_event_file(event_type)

                file_handle, file_path = self._event_files[event_type]

                # JSON 형식으로 변환
                log_line = json.dumps(log_entry, ensure_ascii=False) + '\n'

                # 파일에 쓰기
                file_handle.write(log_line)
                file_handle.flush()

                # 파일 크기 확인 및 로테이션
                if os.path.getsize(file_path) >= self.max_log_file_size:
                    print(f'✓ 이벤트 로그 파일 로테이션 [{event_type}] (크기 제한 초과)')
                    self._rotate_event_file(event_type)

            except Empty:
                continue
            except Exception as e:
                print(f'✗ EventLogWriter 오류: {e}')
                continue

    def _result_write_loop(self):
        """
        결과 로그 작성 루프

        result_queue에서 엔진 결과를 가져와 engine_results_*.jsonl에 저장
        """
        while not self._stop_event.is_set():
            try:
                # 결과 큐에서 데이터 가져오기
                log_entry = self.result_queue.get(timeout=self.queue_timeout)

                # JSON 형식으로 변환
                log_line = json.dumps(log_entry, ensure_ascii=False) + '\n'

                # 파일에 쓰기
                self._result_current_file.write(log_line)
                self._result_current_file.flush()

                # 파일 크기 확인 및 로테이션
                if os.path.getsize(self._result_current_file_path) >= self.max_log_file_size:
                    print(f'✓ 결과 로그 파일 로테이션 (크기 제한 초과)')
                    self._rotate_result_log_file()

            except Empty:
                continue
            except Exception as e:
                print(f'✗ ResultLogWriter 오류: {e}')
                continue

    def _create_event_file(self, event_type: str):
        """
        특정 이벤트 타입의 새 파일 생성

        Args:
            event_type: 이벤트 타입 (예: File, Registry, Network)
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'raw_events_{event_type}_{timestamp}.jsonl'
        file_path = os.path.join(self.log_directory, filename)

        # 파일 열기
        file_handle = open(file_path, 'a', encoding='utf-8')

        # 딕셔너리에 저장
        self._event_files[event_type] = (file_handle, file_path)

        print(f'✓ 새 이벤트 로그 파일 생성 [{event_type}]: {filename}')

        # 오래된 파일 삭제
        self._cleanup_old_logs(f'raw_events_{event_type}')

    def _rotate_event_file(self, event_type: str):
        """
        특정 이벤트 타입의 파일 로테이션

        Args:
            event_type: 이벤트 타입 (예: File, Registry, Network)
        """
        # 기존 파일 닫기
        if event_type in self._event_files:
            file_handle, _ = self._event_files[event_type]
            if file_handle:
                file_handle.close()

        # 새 파일 생성
        self._create_event_file(event_type)

    def _rotate_result_log_file(self):
        """결과 로그 파일 로테이션"""
        # 현재 파일 닫기
        if self._result_current_file:
            self._result_current_file.close()

        # 새 파일명 생성
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'engine_results_{timestamp}.jsonl'
        self._result_current_file_path = os.path.join(self.log_directory, filename)

        # 새 파일 열기
        self._result_current_file = open(self._result_current_file_path, 'a', encoding='utf-8')

        print(f'✓ 새 결과 로그 파일 생성: {filename}')

        # 오래된 파일 삭제
        self._cleanup_old_logs('engine_results')

    def _cleanup_old_logs(self, prefix: str):
        """
        오래된 로그 파일 삭제

        Args:
            prefix: 파일명 접두사
                   - 'raw_events_File'
                   - 'raw_events_Registry'
                   - 'engine_results'
                   등
        """
        # 로그 파일 목록 가져오기
        pattern = os.path.join(self.log_directory, f'{prefix}_*.jsonl')
        log_files = glob.glob(pattern)

        # 파일 개수가 제한을 초과하면 삭제
        if len(log_files) > self.max_log_files:
            # 생성 시간 기준으로 정렬 (오래된 것부터)
            log_files.sort(key=os.path.getctime)

            # 초과하는 파일 삭제
            files_to_delete = log_files[:len(log_files) - self.max_log_files]
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    print(f'✓ 오래된 로그 파일 삭제: {os.path.basename(file_path)}')
                except Exception as e:
                    print(f'✗ 로그 파일 삭제 실패 ({os.path.basename(file_path)}): {e}')

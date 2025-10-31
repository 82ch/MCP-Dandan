from config_loader import ConfigLoader
from queue import Queue, Full
import subprocess
import json
from threading import Thread, Event


class EventProvider:
    """
    이벤트 제공자

    외부 프로세스(ETW.exe)를 실행하고 stdout을 읽어 메인 큐에 이벤트를 푸시합니다.
    """

    def __init__(self, main_queue: Queue):
        """
        Args:
            main_queue: 메인 이벤트 큐 (이벤트를 푸시할 대상)
        """
        config = ConfigLoader()

        self.main_queue = main_queue
        self.process_path = config.get_process_path()

        self._process = None
        self._read_thread = None
        self._stop_event = Event()
        self._running = False

    def start(self):
        """외부 프로세스 시작 및 읽기 스레드 시작"""
        if self._running:
            return

        if not self.process_path:
            print('✗ 오류: config.conf에 process_path가 설정되지 않았습니다.')
            return

        self._stop_event.clear()
        self._running = True

        # 외부 프로세스 시작
        try:
            self._process = subprocess.Popen(
                self.process_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            print(f'✓ 외부 프로세스 시작됨: {self.process_path}')

        except FileNotFoundError:
            print(f'✗ 오류: 프로세스를 찾을 수 없습니다 - {self.process_path}')
            self._running = False
            return
        except Exception as e:
            print(f'✗ 프로세스 실행 오류: {e}')
            self._running = False
            return

        # 읽기 스레드 시작
        self._read_thread = Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()

    def stop(self):
        """외부 프로세스 및 읽기 스레드 중지"""
        if not self._running:
            return

        self._stop_event.set()

        # 프로세스 종료
        if self._process:
            self._process.terminate()
            self._process.wait(timeout=5)

        # 읽기 스레드 종료 대기
        if self._read_thread and self._read_thread.is_alive():
            self._read_thread.join()

        self._running = False
        print('✓ EventProvider 중지됨')

    def _read_loop(self):
        """
        프로세스의 stdout을 읽어 메인 큐에 푸시

        - JSON 형식 검증
        - eventType 필드 확인
        - 메인 큐가 가득 차면 이벤트 드롭
        """
        for line in self._process.stdout:
            if self._stop_event.is_set():
                break

            line = line.rstrip('\n')

            # 출력 형식 검증
            is_valid, data = self._validate_output(line)

            if is_valid:
                try:
                    # 메인 큐에 푸시 (큐가 가득 차면 스킵)
                    self.main_queue.put(data, block=False)

                except Full:
                    print(f'⚠️  메인 큐가 가득 참, 이벤트 드롭')
                    continue

        # stderr 출력 확인
        if self._process.stderr:
            stderr_output = self._process.stderr.read()
            if stderr_output:
                print(f'stderr: {stderr_output}')

    def _validate_output(self, output_line: str):
        """
        프로세스 출력을 검증하는 함수

        Args:
            output_line: 검사할 출력 라인

        Returns:
            tuple: (유효 여부, 파싱된 데이터) - 유효하면 (True, data), 아니면 (False, None)

        검증 로직:
        1. JSON 형식인지 확인
        2. "eventType" 항목이 존재하는지 확인
        """
        try:
            # 1. JSON 형식인지 확인
            data = json.loads(output_line)

            # 2. "eventType" 항목이 존재하는지 확인
            if "eventType" in data:
                return True, data
            else:
                return False, None

        except json.JSONDecodeError:
            # JSON 파싱 실패
            return False, None
        except Exception:
            # 기타 오류
            return False, None

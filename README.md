## 설치

외부 의존성이 없습니다. Python 3.7 이상이면 바로 실행 가능합니다.

```bash
# 의존성 없음 - Python 표준 라이브러리만 사용
python engine_server.py
```

## 사용 방법

### 1. 설정 파일 수정

`config.conf` 파일에서 외부 프로세스 경로를 설정하세요:

```ini
[event_provider]
process_path = C:\path\to\your\ETW.exe
```

### 2. 엔진 서버 실행

```bash
python engine_server.py
```

서버가 시작되면:
1. 외부 프로세스(ETW.exe)가 실행됩니다
2. 모든 이벤트가 메인 큐에 저장됩니다
3. 각 엔진이 이벤트 복사본을 받아 분석합니다
4. 분석 결과는 `./logs/` 디렉토리에 JSON Lines 형식으로 저장됩니다

### 3. 로그 확인

```bash
# 최신 로그 파일 확인
type logs\engine_results_*.jsonl

# 또는
cat logs/engine_results_*.jsonl
```

## 아키텍처

### 전체 데이터 흐름

```
ETW.exe (외부 프로세스)
    ↓ (stdout, JSON 형식)
EventProvider (프로세스 출력 읽기)
    ↓
Main Event Queue (모든 이벤트 저장)
    ↓
EventDistributor (이벤트 복사 및 분배)
    ↓
Engine Queues (각 엔진별 전용 큐)
    ↓
Engines (병렬 분석)
    ↓
Log Queue (결과 수집)
    ↓
LogWriter (파일 저장)
    ↓
./logs/engine_results_*.jsonl
```

### BaseEngine 구조

`BaseEngine`은 큐 기반 분석 엔진을 쉽게 만들 수 있는 추상 클래스입니다.

**주요 특징:**
- 입력 큐에서 이벤트를 자동으로 가져옴
- 멀티스레드 처리
- `process()` 메서드만 구현하면 됨
- 결과를 자동으로 JSON 형식으로 로그 큐에 전송

**데이터 흐름:**
```
Input Queue → process() → Log Queue → 파일
```

### 커스텀 엔진 만들기

`BaseEngine`을 상속받아 `process()` 메서드만 구현하면 됩니다.

**예제:**
```python
from engine.base_engine import BaseEngine
from queue import Queue
from typing import Any

class MyCustomEngine(BaseEngine):
    def __init__(self, input_queue: Queue, log_queue: Queue):
        super().__init__(
            input_queue=input_queue,
            log_queue=log_queue,
            name='MyCustomEngine'
        )

    def process(self, data: Any) -> Any:
        """
        이벤트 분석 로직

        Returns:
            탐지 결과 (None이면 로그에 저장하지 않음)
        """
        # 관심있는 이벤트만 필터링
        if data.get('eventType') != 'MyEventType':
            return None

        # 분석 로직
        is_suspicious = self.analyze(data)

        if is_suspicious:
            return {
                'detected': True,
                'reference': [f"id-{data.get('ts')}"],
                'result': {
                    'detector': 'MyCustomEngine',
                    'severity': 'high',
                    'details': '...'
                }
            }

        return None
```

**엔진 등록:**
`engine_server.py`에서 엔진을 추가:

```python
# 새 엔진 큐 생성
my_engine_queue = Queue(maxsize=config.get_engine_queue_maxsize())

# 엔진 인스턴스 생성
my_engine = MyCustomEngine(my_engine_queue, log_queue)

# 엔진 등록
engines.append(my_engine)
engine_queues['MyCustomEngine'] = my_engine_queue
```

## 프로젝트 구조

```
.
├── engine/
│   ├── __init__.py
│   ├── base_engine.py           # BaseEngine 추상 클래스
│   └── sensitive_file_engine.py # 민감 파일 탐지 엔진
├── event_provider.py             # 외부 프로세스 실행 및 이벤트 수집
├── event_distributor.py          # 이벤트 분배기 (메인 큐 → 엔진 큐)
├── log_writer.py                 # 로그 파일 작성기
├── engine_server.py              # 엔진 서버 (메인 실행 파일)
├── config_loader.py              # 설정 파일 로더
├── config.conf                   # 설정 파일
├── requirements.txt              # Python 의존성 (없음)
└── README.md                     # 문서
```

## 설정 파일 (config.conf)

### [system] - 시스템 전역 설정

```ini
[system]
# 메인 이벤트 큐 최대 크기
main_queue_maxsize = 10000

# 각 엔진별 입력 큐 최대 크기
engine_queue_maxsize = 1000

# 로그 큐 최대 크기
log_queue_maxsize = 5000

# 큐 get 타임아웃 (초)
queue_timeout = 0.1
```

### [event_provider] - 외부 프로세스 설정

```ini
[event_provider]
# 외부 프로세스 실행 경로
process_path = C:\path\to\your\ETW.exe
```

### [log_writer] - 로그 파일 설정

```ini
[log_writer]
# 로그 파일 저장 경로
log_directory = ./logs

# 로그 파일명 접두사
log_filename_prefix = engine_results

# 로그 파일 최대 크기 (MB)
max_log_file_size = 100

# 로그 파일 최대 개수 (로테이션)
max_log_files = 10
```

### [sensitive_file_engine] - 민감 파일 엔진 설정

```ini
[sensitive_file_engine]
# 엔진 활성화 여부
enabled = true
```

## 출력 형식

### BaseEngine 출력 형식

모든 엔진의 출력은 다음 형식으로 표준화됩니다:

```json
{
  "timestamp": "2025-10-28T12:34:56.789",
  "engine": "SensitiveFileEngine",
  "detected": true,
  "reference": ["id-1761033313696000000"],
  "result": {
    "detector": "SensitiveFile",
    { ... }
  }
}
```

**필드 설명**:
- `timestamp`: ISO 8601 형식의 처리 시각 (필수)
- `engine`: 엔진 이름 (필수)
- `detected`: 탐지 여부 (필수, boolean)
- `reference`: 원본 이벤트 참조 ID 리스트 (필수, 배열)
- `result`: 엔진별 상세 처리 결과 (필수)

## 주요 컴포넌트

### EventProvider
- 외부 프로세스(ETW.exe) 실행
- stdout에서 JSON 이벤트 읽기
- 유효한 이벤트만 메인 큐에 푸시

### EventDistributor
- 메인 큐에서 이벤트 가져오기
- 각 엔진 큐에 deepcopy하여 분배
- 엔진이 독립적으로 데이터를 수정할 수 있도록 함

### BaseEngine
- 추상 클래스 (상속 필요)
- 입력 큐에서 이벤트 자동 가져오기
- `process()` 메서드 호출
- 결과를 JSON 형식으로 로그 큐에 전송

### LogWriter
- 로그 큐에서 결과 가져오기
- JSON Lines 형식으로 파일에 저장
- 로그 로테이션 (크기 제한, 개수 제한)

## 성능 튜닝

큐 크기와 타임아웃을 조절하여 성능을 최적화할 수 있습니다:

- `main_queue_maxsize`: 큰 값 = 버스트 트래픽 대응, 작은 값 = 메모리 절약
- `engine_queue_maxsize`: 각 엔진의 처리 속도에 맞춰 조절
- `log_queue_maxsize`: 로그 작성 속도에 맞춰 조절
- `queue_timeout`: 작은 값 = 빠른 응답, 큰 값 = CPU 사용량 감소

## 특징

1. **Kafka 불필요**: Python 표준 라이브러리만 사용
2. **멀티스레드 아키텍처**: 각 컴포넌트가 독립적으로 동작
3. **유연한 확장**: 새로운 엔진을 쉽게 추가 가능
4. **표준화된 출력**: 모든 엔진이 동일한 JSON 형식으로 출력
5. **자동 로그 로테이션**: 파일 크기와 개수 자동 관리
6. **설정 파일 기반**: config.conf로 모든 설정 중앙 관리

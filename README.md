## 설치

```bash
pip install -r requirements.txt
```

## 사용 방법

### 1. Kafka 서버 실행

로컬에서 Kafka를 실행해야 합니다.

1. Kafka를 `C:\kafka` 경로에 설치

2. 3개의 CMD 창을 열어서 각각 실행:

**CMD 1 - Zookeeper 실행:**
```cmd
cd c:\kafka
.\bin\windows\zookeeper-server-start.bat .\config\zookeeper.properties
```

**CMD 2 - Kafka 서버 실행:**
```cmd
cd c:\kafka
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

**CMD 3 - Consumer로 메시지 확인 (선택사항):**
```cmd
cd c:\kafka
.\bin\windows\kafka-console-consumer.bat --bootstrap-server localhost:9092 --topic results
```

### 2. 엔진 서버 실행

```bash
# 테스트용 메시지 전송 (선택사항)
python kafka_provider.py

# 분석 엔진 서버 실행
python engine_server.py
```

## 아키텍처

### BaseEngine 구조

`BaseEngine`은 Kafka 기반 분석 엔진을 쉽게 만들 수 있는 추상 클래스입니다.

**주요 특징:**
- 멀티스레드 입력/처리 분리
- Kafka Consumer/Producer 자동 관리
- 여러 토픽 동시 구독 가능
- `process()` 메서드만 구현하면 됨

**데이터 흐름:**
```
Kafka Topic → Consumer → Queue → process() → Producer → Output Topic
```

### 커스텀 엔진 만들기

`BaseEngine`을 상속받아 `process()` 메서드만 구현하면 됩니다.

## 프로젝트 구조

```
.
├── engine/
│   ├── __init__.py
│   ├── base_engine.py           # BaseEngine 추상 클래스
│   └── sensitive_file_engine.py # 민감 파일 탐지 엔진
├── engine_server.py              # 엔진 서버 (메인 실행 파일)
├── kafka_producer.py             # SimpleKafkaProducer 클래스
├── main.py                       # 외부 프로세스 → Kafka 파이프라인
├── requirements.txt              # Python 의존성
├── .gitignore                    # Git 제외 파일
└── README.md                     # 문서
```

## 출력 형식

엔진을 추가할 경우 아래 출력 형식을 추가해주세요.

### BaseEngine 출력 형식

모든 엔진의 출력은 다음 형식으로 표준화됩니다:

```json
{
  "timestamp": "2025-10-21T12:34:56.789",
  "engine": "SensitiveFileEngine",
  "detected": true,
  "reference": ["id-1761033313696000000"],
  "result": {
    // 엔진별 처리 상세 결과
  }
}
```

**필드 설명**:
- `timestamp`: ISO 8601 형식의 처리 시각 (필수)
- `engine`: 엔진 클래스 이름 (필수)
- `detected`: 탐지 여부 (필수, boolean)
- `reference`: 원본 이벤트 참조 ID 리스트 (필수, 배열)
- `result`: 엔진별 상세 처리 결과 (필수)
## 82ch-Engine

**Option 1**
```
.\setup.ps1
```

**Option 2**
```bash
pip install -r requirements.txt
python engine_server.py
```

### Data Flow
```
ETW.exe (or 82ch-observer)
    ↓ (stdout, JSON)
EventProvider (stdout read)
    ↓
Main Event Queue 
    ↓
EventDistributor 
    ↓
Engine Queues 
    ↓
Engines
    ↓
Log Queue 
    ↓
LogWriter
    ↓
./logs/engine_results_*.jsonl
```

### Project Struct
```
.
├── engine/
│   ├── __init__.py
│   ├── base_engine.py           # BaseEngine 추상 클래스
│   ├── sensitive_file_engine.py # 민감 파일 탐지 엔진
│   └── semantic_gap_engine.py   
│
├── event_provider.py             # 외부 프로세스 실행 및 이벤트 수집
├── event_distributor.py          # 이벤트 분배기 (메인 큐 → 엔진 큐)
├── log_writer.py                 # 로그 파일 작성기
├── engine_server.py              # 엔진 서버 (메인 실행 파일)
├── config_loader.py              # 설정 파일 로더
├── config.conf                   # 설정 파일
├── requirements.txt              # Python 의존성 (없음)
└── README.md                     # 문서
```

# 82ch - MCP Security Framework

<p align="center">
  <img src="https://github.com/user-attachments/assets/64407558-fe51-4960-862c-05024ab1a912" width="124" height="124" />
</p>
<p align="center">MCP (Model Context Protocol) 보안 프록시 및 위협 탐지 통합 시스템</p>

## Overview

82ch는 MCP(Model Context Protocol) 통신을 모니터링하고 보안 위협을 실시간으로 탐지하는 통합 프레임워크입니다.

**통합 모드**: Observer(프록시) + Engine(탐지 엔진)이 단일 프로세스에서 실행됩니다.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (macOS only) Install SSL certificates
# Required if using python.org installer
python3 install_certificates.py

# 3. Configure (optional)
cp config.conf.example config.conf
# Edit config.conf to enable/disable engines

# 4. Run the integrated server
python server.py
```

### SSL Certificate Setup

**macOS users**: If you installed Python from python.org, you may need to install SSL certificates:

```bash
# Option 1: Use our installer script
python3 install_certificates.py

# Option 2: Run Python's installer
open "/Applications/Python 3.XX/Install Certificates.command"
```

**Linux/Windows users**: SSL certificates should work out of the box. If you encounter SSL errors, the proxy will automatically fall back to using certifi's certificate bundle.

Server will start on `http://127.0.0.1:8282`

## Architecture

```
MCP Client
    ↓
Observer (HTTP+SSE / STDIO Proxy)
    ↓ (in-process)
EventHub (Event Router)
    ↓
Detection Engines (parallel processing)
    ↓
Database (SQLite)
```

### Data Flow

```
MCP Request → Observer → Verification
                ↓
            EventHub.process_event()
                ↓
    ├─→ Database (raw_events, rpc_events)
    │
    └─→ Detection Engines (parallel)
        ├─ SensitiveFileEngine
        ├─ CommandInjectionEngine
        ├─ FileSystemExposureEngine
        └─ ToolsPoisoningEngine (LLM)
            ↓
        Database (engine_results)
```

## Components

### Observer (MCP Proxy)
- Intercepts MCP communications (HTTP+SSE, STDIO)
- Injects `user_intent` parameter into tool calls
- Performs real-time verification
- Publishes events to EventHub

**Supported Transports:**
- HTTP+SSE (Server-Sent Events)
- HTTP-only (polling)
- STDIO (standard input/output via cli_proxy.py)

### EventHub
- Central event processing hub
- Routes events to interested engines
- Manages database persistence
- No external dependencies (in-process)

### Detection Engines
All engines run in parallel for each event:

1. **SensitiveFileEngine** (Signature-based)
   - Detects access to sensitive files (.env, credentials, etc.)

2. **CommandInjectionEngine** (Signature-based)
   - Identifies command injection patterns

3. **FileSystemExposureEngine** (Signature-based)
   - Monitors filesystem exposure risks

4. **ToolsPoisoningEngine** (LLM-based)
   - Uses Mistral AI for semantic analysis
   - Compares tool specs vs actual usage
   - Scores alignment (0-100) with detailed breakdown
   - Auto-categorizes severity: none/low/medium/high

## Project Structure

```
82ch/
├── server.py                    # Main entry point (Observer + Engine)
├── cli_proxy.py                 # STDIO proxy wrapper
│
├── transports/                  # Observer transport handlers
│   ├── sse_transport.py
│   ├── http_only_handler.py
│   ├── stdio_handlers.py
│   └── message_handler.py
│
├── engines/                     # Detection engines
│   ├── base_engine.py
│   ├── sensitive_file_engine.py
│   ├── command_injection_engine.py
│   ├── file_system_exposure_engine.py
│   └── tools_poisoning_engine.py
│
├── verification.py              # Security verification + EventHub integration
├── event_hub.py                 # Event routing hub
├── database.py                  # SQLite database manager
├── config.py                    # Unified configuration
├── state.py                     # Global state management
│
├── schema.sql                   # Database schema
├── query_db.py                  # Database query utilities
│
├── config.conf.example          # Example configuration
├── requirements.txt             # Python dependencies
├── setup.ps1                    # PowerShell setup script
├── Dockerfile
├── docker-compose.yml
│
└── data/                        # Database files (auto-created)
    └── mcp_observer.db
```

## Configuration

### Environment Variables (Observer)
```bash
export MCP_PROXY_PORT=8282
export MCP_PROXY_HOST=127.0.0.1
export MCP_SCAN_MODE=REQUEST_RESPONSE
export MCP_DEBUG=false
```

### config.conf (Engine)
```ini
[Engine]
sensitive_file_enabled = True
command_injection_enabled = True
file_system_exposure_enabled = True
tools_poisoning_enabled = True
```

### Mistral API Key (for ToolsPoisoningEngine)
Create `.env` file:
```
MISTRAL_API_KEY=your_api_key_here
```

## Database Schema

### raw_events
모든 수신 이벤트 (타임스탬프, producer, eventType)

### rpc_events
JSON-RPC MCP 메시지 (request/response)

### mcpl (MCP Tool List)
`tools/list`에서 추출한 도구 명세

### engine_results
탐지 결과:
- `severity`: none/low/medium/high
- `score`: 수치 점수 (0-100)
- `detail`: 상세 분석 JSON
- `serverName`: MCP 서버명
- `producer`: 이벤트 소스 (local/remote)

## ToolsPoisoningEngine

LLM 기반 semantic gap 탐지:

### Scoring Dimensions
- **DomainMatch** (0-40): 도메인 일치도
- **OperationMatch** (0-35): 동작 일치도
- **ArgumentSpecificity** (0-15): 인수 일치도
- **Consistency** (0-10): 논리 일관성

### Severity Classification
- **80-100** → `none` (정상)
- **60-79** → `low` (의심)
- **40-59** → `medium` (위험)
- **0-39** → `high` (치명적)

## Usage Examples

### Running the Server
```bash
# Single command starts everything
python server.py
```

Output:
```
================================================================================
82ch - MCP Security Framework
================================================================================
Observer + Engine integrated mode
================================================================================
Initializing Engine System
================================================================================

Active Detection Engines (4):
  1. Sensitive File Detector
  2. Tools Poisoning Detector
  3. Command Injection Detector
  4. File System Exposure Detector

[EventHub] Started
Engine system initialized successfully
================================================================================

[Observer] Starting HTTP server...
[Observer] Listening on http://127.0.0.1:8282
[Observer] Scan mode: REQUEST_RESPONSE

================================================================================
All components ready. Waiting for connections...
Press Ctrl+C to stop
================================================================================
```

### Using STDIO Proxy
```bash
# Wrap an MCP server with security monitoring
python cli_proxy.py npx -y @modelcontextprotocol/server-filesystem /path/to/allowed
```

### Querying Results
```bash
# View detection results
python query_db.py
```

## Requirements

- Python 3.10+
- SQLite3
- aiohttp
- aiosqlite
- Mistral API key (for ToolsPoisoningEngine)

## Development

The codebase is organized as a single integrated application:

- **No ZeroMQ**: Direct in-process communication
- **Single Database**: Shared SQLite instance
- **Unified Config**: Combined Observer + Engine settings
- **Async Throughout**: Full asyncio support

## License

See LICENSE file for details.
## DanDan
<p align="center">
  <img src="https://github.com/user-attachments/assets/64407558-fe51-4960-862c-05024ab1a912" width="124" height="124" />
</p>
<p align="center">MCP (Model Context Protocol) 기반 보안 위협 탐지 엔진 시스템</p>

**Option 1: PowerShell Setup Script**
```powershell
.\setup.ps1
```

**Option 2: Manual Setup**
```bash
pip install -r requirements.txt
python engine_server.py
```

### Data Flow

```
ZMQ Source (82ch-observer)
    ↓ (ZMQ Socket, JSON Events)
EventHub (ZMQ Subscriber)
    ↓ (Event Processing & Routing)
    ├─→ Database (SQLite)
    │   ├─ raw_events
    │   ├─ mcpl (MCP Tool Specs)
    │   └─ engine_results
    │
    └─→ Detection Engines
        ├─ SensitiveFileEngine      (Signature-based)
        ├─ CommandInjectionEngine   (Signature-based)
        ├─ FileSystemExposureEngine (Signature-based)
        └─ ToolsPoisoningEngine     (LLM-based)
```

### Architecture Components

#### 1. Event Collection
- **zmq_source.py**: ZMQ subscriber that receives events from 82ch-observer
- **event_hub.py**: Central event processing hub
  - Routes events to appropriate engines
  - Stores raw events and results in database
  - Manages MCP tool specifications

#### 2. Database Layer
- **database.py**: SQLite database manager
  - `raw_events`: All incoming events
  - `mcpl`: MCP tool specifications (tools/list)
  - `engine_results`: Detection results with severity, score, and details
  - `file_events`, `process_events`: Event type-specific tables

#### 3. Detection Engines
All engines inherit from `BaseEngine` and process specific event types:

- **SensitiveFileEngine**: Detects access to sensitive files
- **CommandInjectionEngine**: Identifies command injection attempts
- **FileSystemExposureEngine**: Monitors filesystem exposure risks
- **ToolsPoisoningEngine**: LLM-based semantic analysis
  - Compares MCP tool specifications with actual usage
  - Uses Mistral API for semantic gap detection
  - Scores alignment (0-100) with detailed breakdown
  - Auto-categorizes severity based on score

#### 4. Configuration
- **config_loader.py**: Configuration file parser
- **config.conf**: Engine settings and feature flags

### Project Structure

```
.
├── engines/
│   ├── __init__.py
│   ├── base_engine.py                    # BaseEngine abstract class
│   ├── sensitive_file_engine.py          # Sensitive file access detector
│   ├── command_injection_engine.py       # Command injection detector
│   ├── file_system_exposure_engine.py    # Filesystem exposure detector
│   └── tools_poisoning_engine.py         # LLM-based Tools Poisoing Attack detector
│
├── engine_server.py                      # Main engine server (entry point)
├── event_hub.py                          # Event processing & routing hub
├── zmq_source.py                         # ZMQ event source subscriber
├── database.py                           # SQLite database manager
├── config_loader.py                      # Configuration file loader
├── query_db.py                           # Database query utilities
├── schema.sql                            # Database schema definition
│
├── config.conf                           # Configuration file
├── config.conf.example                   # Example configuration
├── requirements.txt                      # Python dependencies
├── setup.ps1                             # PowerShell setup script
├── Dockerfile                            # Docker container definition
├── docker-compose.yml                    # Docker Compose configuration
│
└── data/
    └── events.db                         # SQLite database (auto-created)
```

### Database Schema

#### raw_events
Stores all incoming events with timestamp and metadata.

#### mcpl (MCP Tool Specifications)
Stores MCP tool definitions from `tools/list` responses:
- Tool name, description, parameters
- Used by ToolsPoisoningEngine for semantic comparison

#### engine_results
Detection results from all engines:
- `severity`: none/low/medium/high
- `score`: Numeric score (0-100)
- `detail`: JSON with detailed analysis
- `serverName`: MCP server that triggered detection
- `producer`: Event source identifier

### ToolsPoisoningEngine Details

The ToolsPoisoningEngine uses LLM to detect semantic gaps between MCP tool specifications and actual usage:

#### Scoring Dimensions
- **DomainMatch** (0-40): High-level domain alignment
- **OperationMatch** (0-35): Verb/noun alignment
- **ArgumentSpecificity** (0-15): Argument matching
- **Consistency** (0-10): Logical consistency

#### Severity Classification
- **Score 80-100** → `none` (normal, not stored)
- **Score 60-79** → `low` (suspicious)
- **Score 40-59** → `medium` (risky)
- **Score 0-39** → `high` (critical)

#### Output Format
```json
{
  "DomainMatch": 40,
  "OperationMatch": 35,
  "ArgumentSpecificity": 14,
  "Consistency": 9,
  "Penalties": [
    "Reason for penalty..."
  ],
  "Score": 93
}
```

### Configuration

Edit `config.conf` to enable/disable engines:

```ini
[SensitiveFile]
enabled = true

[CommandInjection]
enabled = true

[FileSystemExposure]
enabled = true

[ToolsPoisoning]
enabled = true
```

### Requirements

- Python 3.8+
- SQLite3
- ZMQ (pyzmq)
- Mistral API key (for ToolsPoisoningEngine)

Create `.env` file in `engines/` directory:
```
MISTRAL_API_KEY=your_api_key_here
```

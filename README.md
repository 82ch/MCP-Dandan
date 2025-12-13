# MCP-Dandan - MCP Security Framework
<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/electron-35+-green.svg" alt="Electron">
</p>
<p align="center">
  <img width="124" height="124" alt="image" src="https://github.com/user-attachments/assets/679e148e-b328-4ebe-b301-d8c17f7e4e93" />

</p>
<p align="center">MCP-Dandan</p>



## Overview

MCP-Dandan is an integrated monitoring service that observes MCP (Model Context Protocol) communications and detects security threats in real time. It features a modern desktop UI built with Electron for easy monitoring and management.


https://github.com/user-attachments/assets/928686ab-a5aa-4486-8d8e-d4a9592adc3e


## Features

- **Real-time MCP Traffic Monitoring**: Intercepts and analyzes MCP communications
- **Multi-Engine Threat Detection**:
  - Command Injection Detection
  - File System Exposure Detection
  - PII Leak Detection(custom rules supported)
  - Data Exfiltration Detection
  - Tools Poisoning Detection (LLM-based)
- **Desktop UI**: Electron-based application with interactive dashboard
- **Interactive Tutorial**: Built-in tutorial system for new users
- **Blocking Capabilities**: Real-time threat blocking with user control
- **Cross-Platform**: Supports Windows, macOS, and Linux

## Quick Start

### Desktop Application (Recommended)

**One-Line Installation (Linux)**:
```bash
curl -fsSL https://raw.githubusercontent.com/your-org/82ch/main/install.sh | sudo bash
```

**Build and Install Locally**:
```bash
./build-linux.sh    # Build for Linux
./quick-install.sh  # Install
82ch-desktop        # Run
```

See [BUILD.md](BUILD.md) for detailed desktop build instructions.

### Command Line Server

```bash
# Clone the repository
git clone https://github.com/82ch/MCP-Dandan.git
cd MCP-Dandan

# 1. Install dependencies
pip install -r requirements.txt

# 2. (macOS only) Install SSL certificates
# Required if using python.org installer
python3 mcp_python_install_certificates.py

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
python3 mcp_python_install_certificates.py

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
<img width="4726" height="4052" alt="image" src="https://github.com/user-attachments/assets/b37e688a-71a2-499b-b6be-45b3bd6ac6d4" />




## Detection Engines

### 1. Command Injection Engine
Identifies potential command injection patterns in tool calls.

### 2. File System Exposure Engine
Monitors unauthorized file system access attempts.

### 3. PII Leak Engine (custom rules supported)
Detects potential PII leakage with built-in rules and optional user-defined customization.

### 4. Data Exfiltration Engine
Identifies suspicious data transfer patterns.

### 5. Tools Poisoning Engine (LLM-based)
Uses semantic analysis to detect misuse of MCP tools:
- Compares tool specifications vs actual usage
- Scores alignment (0-100) with detailed breakdown
- Auto-categorizes severity: none/low/medium/high

### Engine Setting
<p align="center">
</p>

https://github.com/user-attachments/assets/3d6f2304-0a6b-492e-9f2d-bba76df98b4c


<p align="center">
Input your <b>MISTRAL_API_KEY</b> to enable the Tools Poisoning Engine, and configure detection settings as needed.
</p>


- **No ZeroMQ**: Direct in-process communication
- **Single Database**: Shared SQLite instance
- **Unified Config**: Combined Observer + Engine settings
- **Async Throughout**: Full asyncio support

## License

https://github.com/user-attachments/assets/19bcbdfb-c893-468d-a8a6-1c7b70a1c7b7

> ## Full Documentation  
> For detailed explanations and technical documentation, please refer to the  
> **[MCP-Dandan Wiki](https://github.com/82ch/MCP-Dandan/wiki)**.
>
> **Have questions or suggestions?**  
> Please visit the **[Discussions](https://github.com/82ch/MCP-Dandan/discussions)** tab.




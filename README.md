# MCP-Dandan - MCP Security Framework

<p align="center">
  <img src="https://github.com/user-attachments/assets/64407558-fe51-4960-862c-05024ab1a912" width="124" height="124" />
</p>
<p align="center">MCP-DANDAN</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/electron-33+-green.svg" alt="Electron">
</p>

## Overview

MCP-Dandan is an integrated monitoring service that observes MCP (Model Context Protocol) communications and detects security threats in real time. It features a modern desktop UI built with Electron for easy monitoring and management.


https://github.com/user-attachments/assets/02eaa237-f95d-4711-8d6b-ee31ab05468f


## Features

- **Real-time MCP Traffic Monitoring**: Intercepts and analyzes MCP communications
- **Multi-Engine Threat Detection**:
  - Command Injection Detection
  - File System Exposure Detection
  - PII Leak Detection
  - Data Exfiltration Detection
  - Tools Poisoning Detection (LLM-based)
- **Desktop UI**: Electron-based application with interactive dashboard
- **Interactive Tutorial**: Built-in tutorial system for new users
- **Blocking Capabilities**: Real-time threat blocking with user control
- **Cross-Platform**: Supports Windows, macOS, and Linux

## Quick Start
### Installation

```bash
# Install all dependencies (Python + Node.js)
npm run install-all
```

### Running the Application

```bash
# Start both server and desktop UI
npm run dev
```

The server will start on `http://127.0.0.1:8282` and the Electron desktop app will launch automatically.

## Project Structure

```
82ch/
├── server.py                    # Main server entry point
├── cli_proxy.py                 # STDIO proxy wrapper
├── cli_remote_proxy.py          # Remote proxy handler
│
├── transports/                  # MCP transport handlers
│   ├── stdio_handlers.py        # STDIO protocol handling
│   └── config_finder.py         # Claude config management
│
├── engines/                     # Threat detection engines
│   ├── base_engine.py           # Base engine interface
│   ├── command_injection_engine.py
│   ├── data_exfiltration_engine.py
│   ├── file_system_exposure_engine.py
│   ├── pii_leak_engine.py
│   └── tools_poisoning_engine.py
│
├── front/                       # Electron desktop application
│   ├── electron/                # Electron main process
│   │   ├── main.ts              # Main process entry
│   │   └── preload.ts           # Preload script
│   ├── src/                     # React frontend
│   │   ├── components/          # UI components
│   │   │   ├── BlockingModal.tsx
│   │   │   ├── BlockingPage.tsx
│   │   │   ├── MiddleBottomPanel.tsx
│   │   │   ├── MiddleTopPanel.tsx
│   │   │   ├── RightChatPanel.tsx
│   │   │   ├── SettingsModal.tsx
│   │   │   └── Tutorial/        # Tutorial system
│   │   ├── main.tsx             # React entry point
│   │   └── types.ts             # TypeScript types
│   └── package.json
│
├── verification.py              # Security verification
├── event_hub.py                 # Event routing
├── database.py                  # Database manager
├── config.py                    # Configuration
├── state.py                     # Global state
│
├── package.json                 # Root package config
├── requirements.txt             # Python dependencies
└── README.md
```

## Detection Engines

### 1. Sensitive File Engine
Detects access to sensitive files like `.env`, credentials, private keys, etc.

### 2. Command Injection Engine
Identifies potential command injection patterns in tool calls.

### 3. File System Exposure Engine
Monitors unauthorized file system access attempts.

### 4. PII Leak Engine
Detects potential leakage of personally identifiable information.

### 5. Data Exfiltration Engine
Identifies suspicious data transfer patterns.

### 6. Tools Poisoning Engine (LLM-based)
Uses semantic analysis to detect misuse of MCP tools:
- Compares tool specifications vs actual usage
- Scores alignment (0-100) with detailed breakdown
- Auto-categorizes severity: none/low/medium/high

### Mistral API Key
<p align="center">

https://github.com/user-attachments/assets/07ffcf8a-f4d7-4013-8cce-9a18fb3cf261

</p>
<p align="center">Input your MISTRAL_API_KEY for Tool Poisoning Engine</p>

## Desktop UI Features

- **Real-time Dashboard**: Monitor MCP traffic and threats in real time
- **Interactive Tutorial**: Learn how to use the system with step-by-step guides
- **Blocking Interface**: Review and control threat blocking actions
- **Settings Panel**: Configure detection engines and system behavior
- **Chat Panel**: Interact with the system and view logs


https://github.com/user-attachments/assets/0d19c049-07a9-439a-9e99-634aeb029067



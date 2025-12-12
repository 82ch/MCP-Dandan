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


## Desktop UI Features

- **Real-time Dashboard**: Monitor MCP traffic and threats in real time
- **Interactive Tutorial**: Learn how to use the system with step-by-step guides
- **Blocking Interface**: Review and control threat blocking actions
- **Settings Panel**: Configure detection engines and system behavior
- **Chat Panel**: Interact with the system and view logs

https://github.com/user-attachments/assets/19bcbdfb-c893-468d-a8a6-1c7b70a1c7b7

> ## Full Documentation  
> For detailed explanations and technical documentation, please refer to the  
> **[MCP-Dandan Wiki](https://github.com/82ch/MCP-Dandan/wiki)**.
>
> **Have questions or suggestions?**  
> Please visit the **[Discussions](https://github.com/82ch/MCP-Dandan/discussions)** tab.




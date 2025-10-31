## 📦 mitmproxy 설치

### Windows
1. **공식 바이너리 다운로드**
  - [mitmproxy 다운로드 페이지](https://mitmproxy.org/)에서 Windows용 설치 파일을 다운로드합니다.

2. **pip로 설치 (모든 플랫폼 공통)**
  ```bash
  pip install mitmproxy
  ```

3. **install-file로 설치**
  ```powershell
  powershell -ExecutionPolicy Bypass -File mitm-setting.ps1
  ```

### **설치 확인**
  ```powershell
  mitmproxy --version
  ```

### 인증서 설치 (3번으로 설치시 불필요)
  ```powershell
  powershell -ExecutionPolicy Bypass -File install-mitm-ca.ps1
  ```

# 🧩 MCP Proxy 사용법

## ⚙️ config.json 설정
(etc. claude_desktop_config.json)
빌드된 `MCPProxy.exe`의 경로를 `command`에 입력합니다.
```json
{
  "mcpServers": {
    "filesystem": {
      "command": "C:\\Users\\ey896\\OneDrive\\Desktop\\82ch-observer\\src\\MCPProxy\\bin\\Debug\\net9.0\\MCPProxy.exe",
      "args": [
        "C:\\Program Files\\nodejs\\npx.cmd",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\"
      ]
    },
    "weather": {
      "command": "C:\\Users\\ey896\\OneDrive\\Desktop\\82ch-observer\\src\\MCPProxy\\bin\\Debug\\net9.0\\MCPProxy.exe",
      "args": [
        "C:\\Users\\ey896\\.local\\bin\\uv.exe",
        "--directory",
        "C:\\Users\\ey896\\Downloads\\quickstart-resources\\weather-server-python",
        "run",
        "weather.py"
      ]
    }
  }
}
```

## ⚡ MCPTrace 실행
1. `MCPTrace.exe`를 **관리자 권한으로 실행**합니다.
2. 모니터링할 프로세스를 선택하면 **ETW 기반 시스템 이벤트**가 수집됩니다.
3. Proxy(`MCPProxy.exe`)와 연결되면 **실시간 JSON-RPC 및 시스템 이벤트 로그**가 콘솔에 표시됩니다.

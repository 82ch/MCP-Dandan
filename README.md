# 🧩 MCP Proxy 사용법

## ⚙️ config.json 설정
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

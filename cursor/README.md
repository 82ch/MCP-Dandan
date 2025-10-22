# 🔍 Cursor MCP Observer

Windows **ETW (Event Tracing for Windows)** 기반으로  
`Cursor.exe` 내 **MCP(Model Context Protocol) 행위**를 추적하는 도구입니다.

---

## 📌 Features
- MCP 관련 **프로세스 트리 추적** (`[START]`, `[EXIT]`)
- MCP 로그 파일 감지 및 **실시간 로그 출력**
- MCP 세션과 연관된 **네트워크 이벤트 추적**
- 컬러 콘솔 출력 & 로그 파일 저장 (`etw_events_log.txt`)

---

## ⚡ Requirements
- Windows 11
- 관리자 권한 실행 필요
- .NET Framework 4.8.1 이상

---

## 🚀 Usage

```powershell
ETW.exe
Enter target process name (e.g., Cursor.exe):
Cursor.exe

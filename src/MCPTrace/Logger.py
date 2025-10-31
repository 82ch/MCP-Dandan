# ws_logger_inline.py
from mitmproxy import ctx
import json
import time

def load(loader):
    ctx.log.info("[ws_logger] Loaded (inline mode: terminal only)")

def done():
    ctx.log.info("[ws_logger] Done")

def contains_jsonrpc(text: str) -> bool:
    if not text:
        return False
    l = text.lower()
    return ("jsonrpc" in l) or ("method" in l)

def pretty_json(text: str) -> object:
    """
    Try to parse JSON text and return a Python object for safe dumping.
    If not JSON, return original text (string).
    """
    try:
        return json.loads(text)
    except Exception:
        return text

def websocket_message(flow):
    """WebSocket 메시지를 가로채 콘솔에 바로 출력 (항상 유효한 JSON 한 줄로 출력)"""
    try:
        msg = flow.websocket.messages[-1]
    except Exception:
        return

    # 텍스트/바이너리 처리
    if getattr(msg, "is_text", False):
        text = getattr(msg, "text", "") or ""
    else:
        raw = getattr(msg, "content", b"") or b""
        try:
            text = raw.decode("utf-8")
        except Exception:
            # 디코딩 실패시 replacement로 안전하게 표시
            text = raw.decode("utf-8", errors="replace")

    if not contains_jsonrpc(text):
        return

    # 메타데이터 추출 (안전하게)
    server_ip = None
    server_port = None
    try:
        saddr = getattr(flow.server_conn, "address", None)
        if isinstance(saddr, tuple) and len(saddr) >= 2:
            server_ip = saddr[0]
            server_port = saddr[1]
        elif saddr:
            server_ip = str(saddr)
    except Exception:
        pass

    host = getattr(flow.server_conn, "sni", None) or getattr(flow, "server", None) or getattr(flow.request, "pretty_host", None) or "unknown"

    client_ip = None
    client_port = None
    try:
        caddr = getattr(flow.client_conn, "address", None)
        if isinstance(caddr, tuple) and len(caddr) >= 2:
            client_ip = caddr[0]
            client_port = caddr[1]
        elif caddr:
            client_ip = str(caddr)
    except Exception:
        pass

    client_addr_display = f"{client_ip or 'unknown'}:{client_port or 'no-port'}"
    server_addr_display = f"{server_ip or 'no-ip'}:{server_port or 'no-port'}"

    task = "SEND" if getattr(msg, "from_client", False) else "RECV"
    ts = time.time_ns()

    # message는 JSON이면 파싱된 오브젝트로, 아니면 원본 문자열로 둔다.
    message_obj = pretty_json(text)

    # byte length (있으면)
    byte_len = None
    try:
        content = getattr(msg, "content", None)
        if isinstance(content, (bytes, bytearray)):
            byte_len = len(content)
    except Exception:
        pass

    entry = {
        "ts": ts,
        "producer": "proxy",
        "pid": "NonePID",
        "pname": "NonePName",
        "eventType": "MCP",
        "data": {
            "task": task,
            "transPort": "http",
            "src": client_addr_display if task == "SEND" else server_addr_display,
            "dst": server_addr_display if task == "SEND" else client_addr_display,
            "message": message_obj
        }
    }

    # 항상 한 줄 JSON으로 출력 (한글 포함), 바로 flush
    print(json.dumps(entry, ensure_ascii=False, separators=(",", ":")), flush=True)

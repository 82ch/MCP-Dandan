"""
Global state management for 82ch MCP proxy.

Tracks active SSE connections, pending tool calls, and server configurations.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from utils import safe_print


@dataclass
class SSEConnection:
    """Represents an active SSE connection."""
    server_name: str
    app_name: str
    target_url: str
    client_response: Any  # aiohttp StreamResponse
    connection_id: str
    target_headers: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    target_session: Any = None  # aiohttp ClientSession for SSE-only servers
    message_queue: Any = None  # asyncio.Queue for sending messages to target


@dataclass
class PendingToolCall:
    """Represents a pending tool call awaiting response."""
    tool_name: str
    request_id: Any
    server_name: str
    app_name: str
    args: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ServerToolsInfo:
    """Information about discovered tools from a server."""
    tools: list
    server_info: Dict[str, Any]
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class AnalysisStatus:
    """Tracks the status of ongoing tool poisoning analysis."""
    server_name: str
    total_tools: int
    analyzed_tools: int = 0
    malicious_found: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    status: str = "analyzing"  # "analyzing", "completed", "error"


@dataclass
class BlockingRequest:
    """Represents a blocking request awaiting user decision."""
    request_id: str
    event_data: Dict[str, Any]
    detection_results: list  # List of detection findings
    engine_name: str
    severity: str
    server_name: str
    tool_name: str
    created_at: datetime = field(default_factory=datetime.now)
    future: Any = None  # asyncio.Future for waiting on user decision


class GlobalState:
    """Global state for the proxy server."""

    def __init__(self):
        # Active SSE connections: connection_id -> SSEConnection
        self.sse_connections: Dict[str, SSEConnection] = {}

        # Pending tool calls: "{app}:{server}:{request_id}" -> PendingToolCall
        self.pending_tool_calls: Dict[str, PendingToolCall] = {}

        # Discovered tools: "{app}:{server}" -> ServerToolsInfo
        self.server_tools: Dict[str, ServerToolsInfo] = {}

        # Protected server configurations: app_name -> List[server_configs]
        self.protected_servers: Dict[str, list] = {}

        # Analysis status tracking: "server_name" -> AnalysisStatus
        self.analysis_status: Dict[str, AnalysisStatus] = {}

        # Blocking requests: request_id -> BlockingRequest
        self.blocking_requests: Dict[str, 'BlockingRequest'] = {}

        # Settings
        self.scan_mode: str = "REQUEST_RESPONSE"
        self.running: bool = False

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

        # EventHub instance (initialized on startup)
        self.event_hub: Optional[Any] = None

    async def add_blocking_request(self, blocking_request: 'BlockingRequest'):
        """Add a blocking request awaiting user decision."""
        async with self._lock:
            self.blocking_requests[blocking_request.request_id] = blocking_request
            safe_print(f"[State] Added blocking request: {blocking_request.request_id}")

    async def get_blocking_request(self, request_id: str) -> Optional['BlockingRequest']:
        """Get a blocking request by ID."""
        async with self._lock:
            return self.blocking_requests.get(request_id)

    async def remove_blocking_request(self, request_id: str):
        """Remove a blocking request after decision."""
        async with self._lock:
            self.blocking_requests.pop(request_id, None)
            safe_print(f"[State] Removed blocking request: {request_id}")

    def get_call_key(self, request_id: Any, server_name: str, app_name: str) -> str:
        """Generate unique key for tracking tool calls."""
        return f"{app_name}:{server_name}:{request_id}"

    async def track_tool_call(
        self,
        tool_name: str,
        request_id: Any,
        server_name: str,
        app_name: str,
        args: Dict[str, Any]
    ) -> str:
        """Track a pending tool call."""
        async with self._lock:
            call_key = self.get_call_key(request_id, server_name, app_name)

            self.pending_tool_calls[call_key] = PendingToolCall(
                tool_name=tool_name,
                request_id=request_id,
                server_name=server_name,
                app_name=app_name,
                args=args
            )

            return call_key

    async def get_pending_call(self, call_key: str) -> Optional[PendingToolCall]:
        """Retrieve a pending tool call."""
        async with self._lock:
            return self.pending_tool_calls.get(call_key)

    async def remove_pending_call(self, call_key: str):
        """Remove a pending tool call after completion."""
        async with self._lock:
            self.pending_tool_calls.pop(call_key, None)

    async def cleanup_stale_calls(self, max_age_seconds: int = 600):
        """Remove pending calls older than max_age_seconds."""
        async with self._lock:
            now = datetime.now()
            stale_keys = [
                key for key, call in self.pending_tool_calls.items()
                if (now - call.timestamp).total_seconds() > max_age_seconds
            ]

            for key in stale_keys:
                del self.pending_tool_calls[key]

            if stale_keys:
                safe_print(f"Cleaned up {len(stale_keys)} stale tool calls")

    async def register_tools(
        self,
        app_name: str,
        server_name: str,
        tools: list,
        server_info: Dict[str, Any]
    ):
        """Register discovered tools for a server."""
        async with self._lock:
            key = f"{app_name}:{server_name}"
            self.server_tools[key] = ServerToolsInfo(
                tools=tools,
                server_info=server_info
            )
            safe_print(f"Registered {len(tools)} tools for {key}")

    async def add_sse_connection(self, connection: SSEConnection):
        """Add an active SSE connection."""
        async with self._lock:
            self.sse_connections[connection.connection_id] = connection

    async def remove_sse_connection(self, connection_id: str):
        """Remove an SSE connection."""
        async with self._lock:
            self.sse_connections.pop(connection_id, None)

    async def find_sse_connection(
        self,
        server_name: str,
        app_name: Optional[str] = None
    ) -> Optional[SSEConnection]:
        """Find an active SSE connection by server and app name. Returns the most recent one."""
        async with self._lock:
            matching_connections = []
            for conn in self.sse_connections.values():
                if conn.server_name == server_name:
                    if app_name is None or conn.app_name == app_name:
                        matching_connections.append(conn)

            if not matching_connections:
                return None

            # Return the most recent connection (sorted by created_at descending)
            matching_connections.sort(key=lambda c: c.created_at, reverse=True)
            return matching_connections[0]


# Global state instance
state = GlobalState()

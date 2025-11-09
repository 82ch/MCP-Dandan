"""
Event Publisher for Electron Integration

Publishes MCP events to stdout in a structured format that Electron can parse.
"""

import sys
import json
import time
import os
from typing import Dict, Any, Optional


class StdoutEventPublisher:
    """
    Publishes events to stdout in a format that Electron Main Process can parse.

    Event format:
    __EVENT__<json>__END__
    """

    def __init__(self):
        self.enabled = os.getenv('MCP_EVENT_PUBLISH', 'true').lower() == 'true'
        self.debug = os.getenv('MCP_DEBUG', 'false').lower() == 'true'

    def publish(self, event: Dict[str, Any]):
        """
        Publish an event to stdout.

        Args:
            event: Event data to publish
        """
        if not self.enabled:
            return

        try:
            # Add timestamp if not present
            if 'ts' not in event:
                event['ts'] = int(time.time() * 1000)  # milliseconds

            # Serialize to JSON
            json_str = json.dumps(event, ensure_ascii=False)

            # Output with delimiters for easy parsing
            print(f"__EVENT__{json_str}__END__", flush=True)

            if self.debug:
                print(f"[EventPublisher] Published event: {event.get('eventType', 'unknown')}",
                      file=sys.stderr, flush=True)

        except Exception as e:
            print(f"[EventPublisher] Error publishing event: {e}",
                  file=sys.stderr, flush=True)

    def publish_mcp_event(
        self,
        direction: str,
        message: Dict[str, Any],
        app_name: str,
        server_name: str,
        tool_name: Optional[str] = None
    ):
        """
        Publish an MCP protocol event.

        Args:
            direction: 'request' or 'response'
            message: JSON-RPC message
            app_name: Application name (e.g., 'Cursor', 'ClaudeDesktop')
            server_name: MCP server name (e.g., 'filesystem', 'github')
            tool_name: Tool name if this is a tool call
        """
        event = {
            'eventType': 'MCP',
            'ts': int(time.time() * 1000),
            'producer': app_name,
            'mcpTag': server_name,
            'data': {
                'task': 'SEND' if direction == 'request' else 'RECV',
                'src': 'client' if direction == 'request' else 'server',
                'message': message
            }
        }

        # Add tool name if available
        if tool_name:
            event['toolName'] = tool_name

        # Add process info
        try:
            import os
            event['pid'] = os.getpid()
            event['pname'] = 'cli_proxy'
        except:
            pass

        self.publish(event)

    def publish_log(self, level: str, message: str, data: Optional[Dict] = None):
        """
        Publish a log event.

        Args:
            level: Log level ('INFO', 'WARN', 'ERROR', 'DEBUG')
            message: Log message
            data: Additional data
        """
        event = {
            'eventType': 'LOG',
            'level': level,
            'message': message
        }

        if data:
            event['data'] = data

        self.publish(event)

    def publish_verification_result(
        self,
        tool_name: str,
        blocked: bool,
        reason: Optional[str] = None,
        server_info: Optional[Dict] = None
    ):
        """
        Publish a verification result event.

        Args:
            tool_name: Name of the tool that was verified
            blocked: Whether the tool call was blocked
            reason: Reason for blocking (if blocked)
            server_info: Server information
        """
        event = {
            'eventType': 'VERIFICATION',
            'toolName': tool_name,
            'blocked': blocked,
            'reason': reason,
            'serverInfo': server_info or {}
        }

        self.publish(event)


# Global publisher instance
_publisher: Optional[StdoutEventPublisher] = None


def get_publisher() -> StdoutEventPublisher:
    """Get or create the global publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = StdoutEventPublisher()
    return _publisher
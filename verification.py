"""
Verification module for security scanning of tool calls and responses.

Integrates with EventHub to send events to detection engines.
"""

from typing import Dict, Any, Optional
import json
import time
from state import state


class VerificationResult:
    """Result of a verification check."""

    def __init__(self, allowed: bool = True, reason: Optional[str] = None):
        self.allowed = allowed
        self.reason = reason


async def verify_tool_call(
    tool_name: str,
    tool_args: Dict[str, Any],
    server_info: Dict[str, Any],
    user_intent: str = "",
    skip_logging: bool = False
) -> VerificationResult:
    """
    Verify a tool call against security policies.

    Args:
        tool_name: Name of the tool being called
        tool_args: Arguments passed to the tool
        server_info: Information about the MCP server
        user_intent: User's explanation for the tool call
        skip_logging: If True, skip EventHub logging (used when already logged)

    Returns:
        VerificationResult indicating if the call is allowed
    """
    app_name = server_info.get('appName', 'unknown')
    server_name = server_info.get('name', 'unknown')

    print(f"[Verification] Checking tool call: {tool_name}")
    print(f"[Verification] Server: {app_name}/{server_name}")

    if user_intent:
        print(f"[Verification] User intent: {user_intent}")

    # Send event to EventHub for engine analysis (unless already logged)
    if not skip_logging and state.event_hub:
        event = {
            'ts': int(time.time() * 1000),
            'producer': 'local',  # STDIO
            'pid': None,
            'pname': app_name,
            'eventType': 'MCP',
            'mcpTag': server_name,
            'data': {
                'task': 'SEND',
                'message': {
                    'jsonrpc': '2.0',
                    'method': 'tools/call',
                    'params': {
                        'name': tool_name,
                        'arguments': {**tool_args, 'user_intent': user_intent} if user_intent else tool_args
                    }
                },
                'mcpTag': server_name
            }
        }

        # Process event asynchronously (don't wait)
        try:
            await state.event_hub.process_event(event)
        except Exception as e:
            print(f"[Verification] Error sending event to EventHub: {e}")

    # Basic blocking checks
    dangerous_patterns = ["rm -rf", "/etc/", "format", "del /f"]
    args_str = json.dumps(tool_args).lower()

    for pattern in dangerous_patterns:
        if pattern in args_str:
            return VerificationResult(
                allowed=False,
                reason=f"Potentially dangerous operation detected: {pattern}"
            )

    return VerificationResult(allowed=True)


async def verify_tool_response(
    tool_name: str,
    response_data: Dict[str, Any],
    server_info: Dict[str, Any],
    skip_logging: bool = False
) -> VerificationResult:
    """
    Verify a tool response against security policies.

    Args:
        tool_name: Name of the tool that was called
        response_data: Response data from the tool
        server_info: Information about the MCP server
        skip_logging: If True, skip EventHub logging (used when already logged)

    Returns:
        VerificationResult indicating if the response is allowed
    """
    app_name = server_info.get('appName', 'unknown')
    server_name = server_info.get('name', 'unknown')

    print(f"[Verification] Checking tool response: {tool_name}")

    # Send event to EventHub for engine analysis (unless already logged)
    if not skip_logging and state.event_hub:
        event = {
            'ts': int(time.time() * 1000),
            'producer': 'local',  # STDIO
            'pid': None,
            'pname': app_name,
            'eventType': 'MCP',
            'mcpTag': server_name,
            'data': {
                'task': 'RECV',
                'message': response_data,
                'mcpTag': server_name
            }
        }

        # Process event asynchronously
        try:
            await state.event_hub.process_event(event)
        except Exception as e:
            print(f"[Verification] Error sending event to EventHub: {e}")

    # Basic warning checks
    response_str = json.dumps(response_data).lower()
    sensitive_patterns = ["password", "api_key", "secret", "token", "credential"]

    for pattern in sensitive_patterns:
        if pattern in response_str:
            print(f"[Verification] Warning: Response may contain sensitive data: {pattern}")

    return VerificationResult(allowed=True)

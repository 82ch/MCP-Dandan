"""
Verification module for security scanning of tool calls and responses.

Integrates with EventHub to send events to detection engines.
"""

from typing import Dict, Any, Optional
import json
import time
import asyncio
import uuid
from state import state, BlockingRequest
from utils import safe_print
from websocket_handler import ws_handler


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
    skip_logging: bool = False,
    producer: str = "local"
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

    safe_print(f"[Verification] Checking tool call: {tool_name}")
    safe_print(f"[Verification] Server: {app_name}/{server_name}")

    if user_intent:
        safe_print(f"[Verification] User intent: {user_intent}")

    # Send event to EventHub for engine analysis (unless already logged)
    if not skip_logging and state.event_hub:
        event = {
            'ts': int(time.time() * 1000),
            'producer': producer,
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
            safe_print(f"[Verification] Error sending event to EventHub: {e}")

    # Run real-time engine analysis for blocking decision
    if state.event_hub:
        try:
            # Create event for analysis
            analysis_event = {
                'ts': int(time.time() * 1000),
                'producer': producer,
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

            # Run engines synchronously and check for high severity
            detection_results = await _run_realtime_analysis(analysis_event)

            if detection_results:
                # Found high severity detection - ask user
                high_severity_results = [r for r in detection_results if r.get('severity') == 'high']

                if high_severity_results:
                    # Create blocking request and wait for user decision
                    request_id = str(uuid.uuid4())
                    future = asyncio.get_event_loop().create_future()

                    blocking_request = BlockingRequest(
                        request_id=request_id,
                        event_data=analysis_event,
                        detection_results=high_severity_results,
                        engine_name=high_severity_results[0].get('detector', 'Unknown'),
                        severity='high',
                        server_name=server_name,
                        tool_name=tool_name,
                        future=future
                    )

                    await state.add_blocking_request(blocking_request)

                    # Broadcast to frontend
                    await ws_handler.broadcast_blocking_request(
                        request_id=request_id,
                        event_data=analysis_event,
                        detection_results=high_severity_results,
                        engine_name=blocking_request.engine_name,
                        severity='high',
                        server_name=server_name,
                        tool_name=tool_name
                    )

                    # Wait for user decision (with timeout)
                    try:
                        allowed = await asyncio.wait_for(future, timeout=60.0)
                        if not allowed:
                            return VerificationResult(
                                allowed=False,
                                reason=f"Blocked by user: {blocking_request.engine_name} detected high severity threat"
                            )
                    except asyncio.TimeoutError:
                        await state.remove_blocking_request(request_id)
                        return VerificationResult(
                            allowed=False,
                            reason="Blocked: User decision timeout (60s)"
                        )

        except Exception as e:
            safe_print(f"[Verification] Error in real-time analysis: {e}")

    return VerificationResult(allowed=True)


async def _run_realtime_analysis(event: Dict[str, Any]) -> list:
    """
    Run real-time engine analysis for blocking decision.

    Args:
        event: Event to analyze

    Returns:
        List of detection results with high severity
    """
    if not state.event_hub:
        return []

    results = []

    # Run CommandInjection and FileSystemExposure engines (not ToolsPoisoning)
    for engine in state.event_hub.engines:
        if engine.name == 'ToolsPoisoningEngine':
            continue  # Skip - this is for tool descriptions only

        if not engine.should_process(event):
            continue

        try:
            result = await engine.handle_event(event)
            if result:
                result_data = result.get('result', {})
                severity = result_data.get('severity', 'none')

                if severity in ['high', 'medium']:
                    results.append(result_data)

        except Exception as e:
            safe_print(f"[Verification] Engine {engine.name} error: {e}")

    return results


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

    safe_print(f"[Verification] Checking tool response: {tool_name}")

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
            safe_print(f"[Verification] Error sending event to EventHub: {e}")

    # Basic warning checks
    response_str = json.dumps(response_data).lower()
    sensitive_patterns = ["password", "api_key", "secret", "token", "credential"]

    for pattern in sensitive_patterns:
        if pattern in response_str:
            safe_print(f"[Verification] Warning: Response may contain sensitive data: {pattern}")

    return VerificationResult(allowed=True)

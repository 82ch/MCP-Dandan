"""
Remote SSE proxy for Claude Desktop STDIO connections.

This module adapts the existing transports/sse_bidirectional.py logic
to work with STDIO for Claude Desktop, which doesn't support HTTP+SSE natively.
"""

import sys
import os
import asyncio
import json
import aiohttp
import time
from typing import Optional, Dict, Any

# Import state management
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Override safe_print to use stderr before importing verification
# This prevents verification logs from polluting stdout (which is used for JSON-RPC)
import utils
_original_safe_print = utils.safe_print
def _stderr_safe_print(*args, **kwargs):
    """Redirect safe_print to stderr for remote proxy"""
    kwargs['file'] = sys.stderr
    return _original_safe_print(*args, **kwargs)
utils.safe_print = _stderr_safe_print

from state import state, SSEConnection


def log(level: str, message: str):
    """Log a message to stderr."""
    import sys
    print(f"[{level}] {message}", file=sys.stderr, flush=True)


async def verify_request_via_http(session: aiohttp.ClientSession, message: Dict[str, Any],
                                    tool_name: str, server_info: Dict[str, Any],
                                    observer_host: str, observer_port: int) -> Dict[str, Any]:
    """Send verification request to Observer HTTP endpoint."""
    try:
        # Timeout must be longer than user decision timeout (60s) + processing time
        async with session.post(
            f'http://{observer_host}:{observer_port}/verify/request',
            json={
                'message': message,
                'toolName': tool_name,
                'serverInfo': server_info
            },
            timeout=aiohttp.ClientTimeout(total=70)  # 60s user timeout + 10s buffer
        ) as resp:
            result = await resp.json()
            log('INFO', f"Verification result: blocked={result.get('blocked')}, reason={result.get('reason')}")
            return result
    except asyncio.TimeoutError:
        log('ERROR', f"Verification timeout (70s) - blocking by default")
        return {'blocked': True, 'reason': 'Verification timeout', 'modified': False}
    except Exception as e:
        log('ERROR', f"Failed to verify request via HTTP: {e}")
        return {'blocked': False, 'reason': None, 'modified': False}


async def verify_response_via_http(session: aiohttp.ClientSession, message: Dict[str, Any],
                                     tool_name: str, server_info: Dict[str, Any],
                                     observer_host: str, observer_port: int) -> Dict[str, Any]:
    """Send verification response to Observer HTTP endpoint."""
    try:
        async with session.post(
            f'http://{observer_host}:{observer_port}/verify/response',
            json={
                'message': message,
                'toolName': tool_name,
                'serverInfo': server_info
            },
            timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            return await resp.json()
    except Exception as e:
        log('ERROR', f"Failed to verify response via HTTP: {e}")
        return {'blocked': False, 'reason': None, 'modified': False}


async def get_dangerous_tools_async(session: aiohttp.ClientSession,
                                     server_name: str,
                                     observer_host: str,
                                     observer_port: int) -> tuple[set, bool]:
    """
    Get list of dangerous tools (safety=3) from the server.

    Returns:
        Tuple of (set of dangerous tool names, filter_enabled flag)
    """
    try:
        async with session.post(
            f'http://{observer_host}:{observer_port}/tools/safety',
            json={'mcp_tag': server_name},
            timeout=aiohttp.ClientTimeout(total=5)
        ) as resp:
            result = await resp.json()
            dangerous_tools = set(result.get('dangerous_tools', []))
            filter_enabled = result.get('filter_enabled', True)
            return dangerous_tools, filter_enabled
    except Exception as e:
        log('ERROR', f"Failed to get dangerous tools: {e}")
        return set(), True


async def handle_sse_connection():
    """
    Main entry point for remote SSE connections via STDIO.

    Uses the same logic as transports/sse_bidirectional.py but adapted for STDIO.
    """
    # Get configuration from environment
    target_url = os.getenv('MCP_TARGET_URL')
    app_name = os.getenv('MCP_OBSERVER_APP_NAME', 'claude_desktop')
    server_name = os.getenv('MCP_OBSERVER_SERVER_NAME', 'remote')
    api_token = os.getenv('API_ACCESS_TOKEN', '')
    debug = os.getenv('MCP_DEBUG', 'false').lower() == 'true'
    observer_host = os.getenv('MCP_PROXY_HOST', '127.0.0.1')
    observer_port = int(os.getenv('MCP_PROXY_PORT', '8282'))

    if not target_url:
        log('ERROR', "MCP_TARGET_URL is required for remote mode")
        sys.exit(1)

    log('INFO', f"Starting remote SSE proxy for {app_name}/{server_name}")
    log('INFO', f"Target URL: {target_url}")
    log('INFO', f"Observer: http://{observer_host}:{observer_port}")

    # Create headers for SSE connection
    target_headers = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }

    # Check for custom headers from MCP_TARGET_HEADERS (JSON format)
    custom_headers_str = os.getenv('MCP_TARGET_HEADERS', '')
    if custom_headers_str:
        try:
            custom_headers = json.loads(custom_headers_str)
            target_headers.update(custom_headers)
            log('INFO', f"Added custom headers from MCP_TARGET_HEADERS: {list(custom_headers.keys())}")
        except json.JSONDecodeError as e:
            log('ERROR', f"Failed to parse MCP_TARGET_HEADERS as JSON: {e}")
            sys.exit(1)
    elif api_token:
        target_headers['Authorization'] = f'Bearer {api_token}'
        log('INFO', "Using API token for authentication")

    # Track pending tool calls for verification (maps message ID -> tool name)
    pending_tool_calls = {}

    # Track the target's message endpoint (received via endpoint event)
    target_message_endpoint = None

    # Message queue for client -> target messages
    message_queue = asyncio.Queue()

    # Tasks for reading stdin and processing SSE
    tasks = []

    try:
        async with aiohttp.ClientSession() as session:
            # Try GET first to detect server type
            log('INFO', f"Probing server type at {target_url}...")

            # Try GET first
            probe_response = await session.get(
                target_url,
                headers=target_headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ).__aenter__()

            # Check if this is a POST-based SSE server (like Composio)
            uses_post_sse = False
            if probe_response.status == 405:
                log('INFO', "GET returned 405 - server requires POST to establish SSE")
                uses_post_sse = True
            elif probe_response.status != 200:
                error_msg = await probe_response.text()
                log('ERROR', f"Probe returned {probe_response.status}: {error_msg}")
                await probe_response.__aexit__(None, None, None)
                sys.exit(1)

            await probe_response.__aexit__(None, None, None)

            # For POST-based SSE: wait for first client message (initialize) then connect
            # For GET-based SSE: connect now
            target_response = None

            if uses_post_sse:
                log('INFO', "POST-SSE mode: Waiting for client initialize message...")
            else:
                # Standard GET-based SSE - connect now
                log('INFO', f"Connecting via GET to {target_url}...")
                target_response = await session.get(
                    target_url,
                    headers=target_headers,
                    timeout=aiohttp.ClientTimeout(total=None, connect=30)
                ).__aenter__()

                if target_response.status == 200:
                    log('INFO', f"Connected to target: HTTP {target_response.status}")
                else:
                    error_msg = await target_response.text()
                    log('ERROR', f"Target returned {target_response.status}: {error_msg}")
                    await target_response.__aexit__(None, None, None)
                    sys.exit(1)

            try:
                # Task 1: Forward events from target to client (STDOUT)
                async def forward_target_to_client():
                    nonlocal target_message_endpoint, target_response
                    try:
                        # For POST-SSE mode, wait for connection to be established
                        if uses_post_sse:
                            retry_count = 0
                            while target_response is None and retry_count < 100:
                                await asyncio.sleep(0.1)
                                retry_count += 1

                            if target_response is None:
                                log('ERROR', "POST-SSE connection was never established")
                                return

                        current_event = None
                        current_data_lines = []

                        # Read content in chunks and process line by line
                        buffer = b""
                        async for chunk in target_response.content.iter_any():
                            buffer += chunk
                            # Process all complete lines in buffer
                            while b'\n' in buffer:
                                line_bytes, buffer = buffer.split(b'\n', 1)
                                line_str = line_bytes.decode('utf-8')

                                # Debug: log all SSE lines
                                if debug and line_str.strip():
                                    log('DEBUG', f"SSE line: {line_str[:100]}")

                                # SSE events are separated by blank lines
                                if line_str.strip() == '':
                                    # End of event - process it
                                    if current_event == 'endpoint' and current_data_lines:
                                        # Capture target's message endpoint
                                        target_message_endpoint = ''.join(current_data_lines)
                                        log('INFO', f"Captured target message endpoint: {target_message_endpoint}")

                                        # Don't forward endpoint event to client - we handle it internally

                                    elif current_event or current_data_lines:
                                        # Parse and modify data lines before forwarding
                                        for idx, data_line in enumerate(current_data_lines):
                                            if idx == 0:
                                                try:
                                                    parsed = json.loads(data_line)

                                                    # Log what we received for debugging
                                                    method = parsed.get('method', 'response')
                                                    msg_id = parsed.get('id', 'no-id')
                                                    log('INFO', f"Received from target: {method} (id={msg_id})")

                                                    # Verify the response with Observer
                                                    verification = await verify_response_via_http(
                                                        session=session,
                                                        message=parsed,
                                                        tool_name='unknown',  # Will be determined by Observer
                                                        server_info={
                                                            'appName': app_name,
                                                            'name': server_name,
                                                            'version': 'unknown'
                                                        },
                                                        observer_host=observer_host,
                                                        observer_port=observer_port
                                                    )

                                                    # Check if response is blocked
                                                    if verification.get('blocked'):
                                                        reason = verification.get('reason') or 'Security policy violation'
                                                        log('WARNING', f"Response blocked by Observer: {reason}")
                                                        # Replace response with blocked message
                                                        parsed = {
                                                            "jsonrpc": "2.0",
                                                            "id": parsed.get('id'),
                                                            "error": {
                                                                "code": -32000,
                                                                "message": f"Response blocked: {reason}"
                                                            }
                                                        }
                                                        data_line = json.dumps(parsed)
                                                        current_data_lines[0] = data_line
                                                    else:
                                                        # Handle tools/list response - add user_intent parameter
                                                        result = parsed.get('result', {})
                                                        if result.get('tools'):
                                                            log('INFO', f"Modifying {len(result.get('tools', []))} tools to add user_intent")

                                                            # Get dangerous tools for filtering
                                                            dangerous_tools, filter_enabled = await get_dangerous_tools_async(
                                                                session, server_name, observer_host, observer_port
                                                            )
                                                            if dangerous_tools and filter_enabled:
                                                                log('INFO', f"Found {len(dangerous_tools)} dangerous tools to filter: {dangerous_tools}")

                                                            # Modify tools to add user_intent parameter
                                                            modified_tools = []
                                                            filtered_count = 0
                                                            for tool in result.get('tools', []):
                                                                tool_name_check = tool.get('name', '')

                                                                # Filter out dangerous tools (safety=3)
                                                                if filter_enabled and tool_name_check in dangerous_tools:
                                                                    log('INFO', f"Filtering out dangerous tool: {tool_name_check}")
                                                                    filtered_count += 1
                                                                    continue

                                                                modified_tool = tool.copy()

                                                                # Ensure inputSchema exists
                                                                if 'inputSchema' not in modified_tool:
                                                                    modified_tool['inputSchema'] = {
                                                                        'type': 'object',
                                                                        'properties': {},
                                                                        'required': []
                                                                    }

                                                                # Add user_intent to properties
                                                                if 'properties' not in modified_tool['inputSchema']:
                                                                    modified_tool['inputSchema']['properties'] = {}

                                                                modified_tool['inputSchema']['properties']['user_intent'] = {
                                                                    'type': 'string',
                                                                    'description': 'Explain the reasoning and context for why you are calling this tool.'
                                                                }

                                                                # Add to required fields
                                                                required = modified_tool['inputSchema'].get('required', [])
                                                                if 'user_intent' not in required:
                                                                    modified_tool['inputSchema']['required'] = required + ['user_intent']

                                                                modified_tools.append(modified_tool)

                                                            if filtered_count > 0:
                                                                log('INFO', f"Filtered {filtered_count} dangerous tools from response")

                                                            # Update parsed data with modified tools
                                                            parsed['result']['tools'] = modified_tools

                                                            # Update data_line with modified JSON
                                                            data_line = json.dumps(parsed)
                                                            current_data_lines[0] = data_line
                                                            log('INFO', f"Tools modified and ready to send")

                                                except json.JSONDecodeError:
                                                    log('WARNING', f"Failed to parse JSON from SSE: {data_line[:100]}")

                                        # Build the JSON-RPC message to send to stdout
                                        # For STDIO, we send JSON-RPC messages directly, not SSE events
                                        if current_data_lines:
                                            output = current_data_lines[0]
                                            print(output, flush=True)
                                            if debug:
                                                log('DEBUG', f"→ Client: {output[:200]}...")
                                            log('INFO', f"Forwarded response to client")

                                    # Reset for next event
                                    current_event = None
                                    current_data_lines = []
                                elif line_str.startswith('event:'):
                                    current_event = line_str[6:].strip()
                                    if debug:
                                        log('DEBUG', f"SSE event type: {current_event}")
                                elif line_str.startswith('data:'):
                                    data_content = line_str[5:].strip()
                                    current_data_lines.append(data_content)

                    except Exception as e:
                        log('ERROR', f"Error forwarding target->client: {e}")

                # Task 2: Read messages from STDIN and forward to target
                async def forward_client_to_target():
                    nonlocal target_message_endpoint, target_response
                    try:
                        loop = asyncio.get_event_loop()

                        while True:
                            # Read from stdin (non-blocking)
                            try:
                                line = await loop.run_in_executor(None, sys.stdin.readline)
                            except Exception as e:
                                log('ERROR', f"Error reading from stdin: {e}")
                                break

                            if not line:
                                log('INFO', "STDIN closed, exiting")
                                break

                            line = line.strip()
                            if not line:
                                # Empty line - skip but don't exit
                                if debug:
                                    log('DEBUG', "Received empty line, continuing...")
                                continue

                            try:
                                message = json.loads(line)
                            except json.JSONDecodeError as e:
                                log('ERROR', f"Invalid JSON from client: {e}")
                                continue

                            if debug:
                                log('DEBUG', f"← Client: {line[:200]}...")

                            # Log all requests to Observer
                            method = message.get('method', 'unknown')
                            server_info = {
                                'appName': app_name,
                                'name': server_name,
                                'version': 'unknown'
                            }

                            # For tools/call, get the actual tool name
                            tool_name = method
                            if method == 'tools/call':
                                params = message.get('params', {})
                                tool_name = params.get('name', 'unknown')
                                log('INFO', f"Verifying tool call: {tool_name}")

                            # Send to Observer for logging and verification
                            verification = await verify_request_via_http(
                                session=session,
                                message=message,
                                tool_name=tool_name,
                                server_info=server_info,
                                observer_host=observer_host,
                                observer_port=observer_port
                            )

                            # Check if blocked
                            if verification['blocked']:
                                reason = verification.get('reason') or 'Security policy violation'
                                log('WARNING', f"Request blocked: {reason}")
                                error_response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get('id'),
                                    "error": {
                                        "code": -32000,
                                        "message": f"Request blocked: {reason}"
                                    }
                                }
                                print(json.dumps(error_response), flush=True)
                                continue

                            # For POST-SSE mode: establish connection with first message
                            if uses_post_sse and target_response is None:
                                log('INFO', f"Establishing POST-SSE connection with initialize message")
                                # Use target_headers for POST-SSE connection
                                post_headers = target_headers.copy()
                                post_headers['Accept'] = 'application/json, text/event-stream'

                                target_response = await session.post(
                                    target_url,
                                    headers=post_headers,
                                    json=message,  # Send the initialize message
                                    timeout=aiohttp.ClientTimeout(total=None, connect=30)
                                ).__aenter__()

                                if target_response.status == 200:
                                    log('INFO', f"POST-SSE connection established: HTTP {target_response.status}")
                                    # Start reading SSE responses in the other task
                                    continue  # Skip sending this message again via POST
                                else:
                                    error_msg = await target_response.text()
                                    log('ERROR', f"POST-SSE failed: {target_response.status}: {error_msg}")
                                    await target_response.__aexit__(None, None, None)
                                    sys.exit(1)

                            # For tools/call, strip user_intent before forwarding
                            if method == 'tools/call':
                                params = message.get('params', {})
                                tool_args = params.get('arguments', {})

                                if 'user_intent' in tool_args:
                                    log('INFO', "Stripping user_intent before forwarding")
                                    tool_args_clean = {k: v for k, v in tool_args.items() if k != 'user_intent'}
                                    message = {
                                        **message,
                                        'params': {
                                            **params,
                                            'arguments': tool_args_clean
                                        }
                                    }

                                # Track this tool call for response verification
                                msg_id = message.get('id')
                                if msg_id is not None:
                                    pending_tool_calls[msg_id] = tool_name

                            # For notifications, skip waiting for message endpoint since they don't expect responses
                            is_notification = method and method.startswith('notifications/')
                            if is_notification:
                                log('INFO', f"Skipping notification message (no response expected): {method}")
                                # Send notification but don't wait for response
                                # Wait briefly for endpoint to be set
                                retry_count = 0
                                while target_message_endpoint is None and retry_count < 10:
                                    await asyncio.sleep(0.05)
                                    retry_count += 1

                                if target_message_endpoint is None:
                                    target_message_endpoint = target_url

                                if target_message_endpoint.startswith('/'):
                                    from urllib.parse import urlparse
                                    parsed = urlparse(target_url)
                                    message_url = f"{parsed.scheme}://{parsed.netloc}{target_message_endpoint}"
                                else:
                                    message_url = target_message_endpoint

                                try:
                                    # Use target_headers for notification
                                    notif_headers = target_headers.copy()
                                    notif_headers['Accept'] = 'application/json, text/event-stream'

                                    # Fire and forget - don't wait for response
                                    asyncio.create_task(session.post(
                                        message_url,
                                        json=message,
                                        headers=notif_headers,
                                        timeout=aiohttp.ClientTimeout(total=10)
                                    ))
                                    log('INFO', f"Notification sent (fire-and-forget): {method}")
                                except Exception as e:
                                    log('WARNING', f"Failed to send notification: {e}")
                                continue  # Skip to next message

                            # Wait for target_message_endpoint to be set (from endpoint event)
                            # Some servers don't send endpoint events, so try with a fallback
                            retry_count = 0
                            while target_message_endpoint is None and retry_count < 50:
                                await asyncio.sleep(0.1)
                                retry_count += 1

                            if target_message_endpoint is None:
                                # Fallback: construct message endpoint from target_url
                                if target_url.endswith('/sse'):
                                    # Standard MCP servers: /sse -> /message
                                    target_message_endpoint = target_url.replace('/sse', '/message')
                                elif '/sse' in target_url:
                                    # Has /sse in the middle somewhere
                                    target_message_endpoint = target_url.replace('/sse', '/message')
                                else:
                                    # No /sse in URL - server might use the same endpoint for everything
                                    # Try the original URL first (Context7 style)
                                    target_message_endpoint = target_url

                                log('WARNING', f"No endpoint event received, using fallback: {target_message_endpoint}")

                            # Construct full URL for target message endpoint
                            if target_message_endpoint.startswith('/'):
                                # Extract base URL from target_url
                                from urllib.parse import urlparse
                                parsed = urlparse(target_url)
                                message_url = f"{parsed.scheme}://{parsed.netloc}{target_message_endpoint}"
                            else:
                                message_url = target_message_endpoint

                            log('INFO', f"Sending {message.get('method', 'message')} to: {message_url}")

                            # Use target_headers for message POST
                            msg_headers = target_headers.copy()
                            msg_headers['Accept'] = 'application/json, text/event-stream'

                            try:
                                async with session.post(
                                    message_url,
                                    json=message,
                                    headers=msg_headers,
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as msg_response:
                                    if msg_response.status == 200:
                                        # Check content type - some servers return SSE stream with 200
                                        content_type = msg_response.headers.get('Content-Type', '')
                                        if 'text/event-stream' in content_type:
                                            # This is a one-time SSE response - read it directly
                                            log('INFO', "Message returned SSE stream (200), reading response from stream")

                                            # Read the SSE stream for this specific response
                                            buffer = b""
                                            current_event = None
                                            current_data_lines = []

                                            async for chunk in msg_response.content.iter_any():
                                                buffer += chunk
                                                while b'\n' in buffer:
                                                    line_bytes, buffer = buffer.split(b'\n', 1)
                                                    line_str = line_bytes.decode('utf-8')

                                                    if debug and line_str.strip():
                                                        log('DEBUG', f"SSE response: {line_str[:100]}")

                                                    if line_str.strip() == '':
                                                        # End of event - process it
                                                        if current_data_lines:
                                                            try:
                                                                response_data = json.loads(current_data_lines[0])

                                                                # Verify response
                                                                verification = await verify_response_via_http(
                                                                    session=session,
                                                                    message=response_data,
                                                                    tool_name='unknown',
                                                                    server_info=server_info,
                                                                    observer_host=observer_host,
                                                                    observer_port=observer_port
                                                                )

                                                                if verification.get('blocked'):
                                                                    reason = verification.get('reason') or 'Security policy violation'
                                                                    log('WARNING', f"Response blocked by Observer: {reason}")
                                                                    response_data = {
                                                                        "jsonrpc": "2.0",
                                                                        "id": response_data.get('id'),
                                                                        "error": {
                                                                            "code": -32000,
                                                                            "message": f"Response blocked: {reason}"
                                                                        }
                                                                    }
                                                                else:
                                                                    # Handle tools/list response
                                                                    result = response_data.get('result', {})
                                                                    if result.get('tools'):
                                                                        log('INFO', f"Modifying {len(result.get('tools', []))} tools to add user_intent")

                                                                        # Get dangerous tools for filtering
                                                                        dangerous_tools, filter_enabled = await get_dangerous_tools_async(
                                                                            session, server_name, observer_host, observer_port
                                                                        )
                                                                        if dangerous_tools and filter_enabled:
                                                                            log('INFO', f"Found {len(dangerous_tools)} dangerous tools to filter: {dangerous_tools}")

                                                                        modified_tools = []
                                                                        filtered_count = 0
                                                                        for tool in result.get('tools', []):
                                                                            tool_name_check = tool.get('name', '')

                                                                            # Filter out dangerous tools (safety=3)
                                                                            if filter_enabled and tool_name_check in dangerous_tools:
                                                                                log('INFO', f"Filtering out dangerous tool: {tool_name_check}")
                                                                                filtered_count += 1
                                                                                continue

                                                                            modified_tool = tool.copy()
                                                                            if 'inputSchema' not in modified_tool:
                                                                                modified_tool['inputSchema'] = {'type': 'object', 'properties': {}, 'required': []}
                                                                            if 'properties' not in modified_tool['inputSchema']:
                                                                                modified_tool['inputSchema']['properties'] = {}
                                                                            modified_tool['inputSchema']['properties']['user_intent'] = {
                                                                                'type': 'string',
                                                                                'description': 'Explain the reasoning and context for why you are calling this tool.'
                                                                            }
                                                                            required = modified_tool['inputSchema'].get('required', [])
                                                                            if 'user_intent' not in required:
                                                                                modified_tool['inputSchema']['required'] = required + ['user_intent']
                                                                            modified_tools.append(modified_tool)

                                                                        if filtered_count > 0:
                                                                            log('INFO', f"Filtered {filtered_count} dangerous tools from response")

                                                                        response_data['result']['tools'] = modified_tools

                                                                # Send response to client
                                                                print(json.dumps(response_data), flush=True)
                                                                log('INFO', f"Sent response from SSE stream to client")
                                                                break  # Exit after first message
                                                            except json.JSONDecodeError as e:
                                                                log('ERROR', f"Failed to parse SSE response: {e}")

                                                        current_event = None
                                                        current_data_lines = []
                                                    elif line_str.startswith('event:'):
                                                        current_event = line_str[6:].strip()
                                                    elif line_str.startswith('data:'):
                                                        data_content = line_str[5:].strip()
                                                        current_data_lines.append(data_content)
                                        else:
                                            # Regular JSON response
                                            response_data = await msg_response.json()
                                            log('INFO', f"Got response from target via POST (200)")

                                            # Verify response with Observer
                                            verification = await verify_response_via_http(
                                                session=session,
                                                message=response_data,
                                                tool_name='unknown',
                                                server_info=server_info,
                                                observer_host=observer_host,
                                                observer_port=observer_port
                                            )

                                            # Check if response is blocked
                                            if verification.get('blocked'):
                                                reason = verification.get('reason') or 'Security policy violation'
                                                log('WARNING', f"Response blocked by Observer: {reason}")
                                                # Replace response with blocked message
                                                response_data = {
                                                    "jsonrpc": "2.0",
                                                    "id": response_data.get('id'),
                                                    "error": {
                                                        "code": -32000,
                                                        "message": f"Response blocked: {reason}"
                                                    }
                                                }
                                            else:
                                                # Handle tools/list response - add user_intent parameter
                                                result = response_data.get('result', {})
                                                if result.get('tools'):
                                                    log('INFO', f"Modifying {len(result.get('tools', []))} tools to add user_intent")

                                                    # Get dangerous tools for filtering
                                                    dangerous_tools, filter_enabled = await get_dangerous_tools_async(
                                                        session, server_name, observer_host, observer_port
                                                    )
                                                    if dangerous_tools and filter_enabled:
                                                        log('INFO', f"Found {len(dangerous_tools)} dangerous tools to filter: {dangerous_tools}")

                                                    modified_tools = []
                                                    filtered_count = 0
                                                    for tool in result.get('tools', []):
                                                        tool_name_check = tool.get('name', '')

                                                        # Filter out dangerous tools (safety=3)
                                                        if filter_enabled and tool_name_check in dangerous_tools:
                                                            log('INFO', f"Filtering out dangerous tool: {tool_name_check}")
                                                            filtered_count += 1
                                                            continue

                                                        modified_tool = tool.copy()

                                                        # Ensure inputSchema exists
                                                        if 'inputSchema' not in modified_tool:
                                                            modified_tool['inputSchema'] = {
                                                                'type': 'object',
                                                                'properties': {},
                                                                'required': []
                                                            }

                                                        # Add user_intent to properties
                                                        if 'properties' not in modified_tool['inputSchema']:
                                                            modified_tool['inputSchema']['properties'] = {}

                                                        modified_tool['inputSchema']['properties']['user_intent'] = {
                                                            'type': 'string',
                                                            'description': 'Explain the reasoning and context for why you are calling this tool.'
                                                        }

                                                        # Add to required fields
                                                        required = modified_tool['inputSchema'].get('required', [])
                                                        if 'user_intent' not in required:
                                                            modified_tool['inputSchema']['required'] = required + ['user_intent']

                                                        modified_tools.append(modified_tool)

                                                    if filtered_count > 0:
                                                        log('INFO', f"Filtered {filtered_count} dangerous tools from response")

                                                    # Update response data with modified tools
                                                    response_data['result']['tools'] = modified_tools

                                            # Send response back to client via STDOUT
                                            print(json.dumps(response_data), flush=True)
                                    elif msg_response.status == 202:
                                        # 202 Accepted - response will come via SSE stream
                                        log('INFO', "Message accepted (202), waiting for response via SSE")
                                        # Don't send anything - response will come via SSE
                                    else:
                                        error_text = await msg_response.text()
                                        log('ERROR', f"Target POST failed: {msg_response.status}")
                                        log('ERROR', f"Error: {error_text}")

                                        # Return error to client
                                        error_response = {
                                            "jsonrpc": "2.0",
                                            "id": message.get('id'),
                                            "error": {
                                                "code": -32000,
                                                "message": f"Target server error: {msg_response.status}"
                                            }
                                        }
                                        print(json.dumps(error_response), flush=True)

                            except Exception as e:
                                log('ERROR', f"Error sending to target: {e}")
                                # Return error to client
                                error_response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get('id'),
                                    "error": {
                                        "code": -32000,
                                        "message": f"Failed to communicate with target: {str(e)}"
                                    }
                                }
                                print(json.dumps(error_response), flush=True)

                    except Exception as e:
                        log('ERROR', f"Error forwarding client->target: {e}")

                # Run both tasks concurrently
                await asyncio.gather(
                    forward_target_to_client(),
                    forward_client_to_target(),
                    return_exceptions=True
                )
            finally:
                # Clean up target_response (if it was established)
                if target_response is not None:
                    await target_response.__aexit__(None, None, None)

    except Exception as e:
        log('ERROR', f"Error in SSE connection: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(handle_sse_connection())

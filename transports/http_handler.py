"""
HTTP-only endpoint handler for MCP servers that don't use SSE.

Handles POST requests directly without SSE connection (like Context7).
"""

import aiohttp
import json
import time
from verification import verify_tool_call, verify_tool_response
from state import state
from utils import safe_print


async def handle_http_only_message(request):
    """
    Handle POST requests for HTTP-only MCP servers (without SSE).

    This handles the full message flow without delegating.
    """
    # Extract app and server names from URL path variables
    # aiohttp already validated the path format via route pattern
    app_name = request.match_info.get('app')
    server_name = request.match_info.get('server')

    if not app_name or not server_name:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "Invalid path format"}),
            content_type='application/json'
        )

    safe_print(f"[HTTP-Only] Request for {app_name}/{server_name}")

    # Parse request body
    try:
        message = await request.json()
    except Exception as e:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "Invalid JSON"}),
            content_type='application/json'
        )

    # Check if this is a notification (no id field)
    is_notification = 'id' not in message
    msg_type = "Notification" if is_notification else "Request"

    safe_print(f"[HTTP-Only] {msg_type}: method={message.get('method')}, id={message.get('id', 'N/A')}")
    safe_print(f"[HTTP-Only] Payload: {json.dumps(message, indent=2)}")

    # Log all requests to EventHub
    if state.event_hub:
        event = {
            'ts': int(time.time() * 1000),
            'producer': 'remote',
            'pid': None,
            'pname': app_name,
            'eventType': 'MCP',
            'mcpTag': server_name,
            'data': {
                'task': 'SEND',
                'message': message,
                'mcpTag': server_name
            }
        }
        await state.event_hub.process_event(event)

    # Check for tool calls and verify
    if message.get('method') == 'tools/call':
        params = message.get('params', {})
        tool_name = params.get('name', 'unknown')
        tool_args = params.get('arguments', {})

        # Extract user_intent
        user_intent = tool_args.get('user_intent', '')
        tool_args_clean = {k: v for k, v in tool_args.items() if k != 'user_intent'}

        server_info = {
            'appName': app_name,
            'name': server_name,
            'version': 'unknown'
        }

        safe_print(f"[Verify] Tool call: {tool_name} from {app_name}/{server_name}")
        if user_intent:
            safe_print(f"[Verify] User intent: {user_intent}")

        # Verify the tool call (skip logging since we already logged above)
        verification = await verify_tool_call(
            tool_name=tool_name,
            tool_args=tool_args_clean,
            server_info=server_info,
            user_intent=user_intent,
            skip_logging=True,
            producer='remote'
        )

        if not verification.allowed:
            reason = verification.reason or 'Security policy violation'
            safe_print(f"[Verify] Tool call blocked: {reason}")
            return aiohttp.web.Response(
                status=200,
                text=json.dumps({
                    "jsonrpc": "2.0",
                    "id": message.get('id'),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"Tool call blocked: {reason}"
                        }]
                    }
                }),
                content_type='application/json'
            )

        # Strip user_intent before forwarding to target
        if 'user_intent' in tool_args:
            safe_print(f"[HTTP-Only] Stripping user_intent before forwarding")
            message = {
                **message,
                'params': {
                    **params,
                    'arguments': tool_args_clean
                }
            }

    # Get target URL and headers from query/headers
    import os
    target_url = None
    target_headers = {}

    # 1. Check query parameter
    if 'target' in request.url.query:
        target_url = request.url.query.get('target')
        safe_print(f"[HTTP-Only] Using target URL from query: {target_url}")

    # 2. Check header
    if not target_url:
        target_url = request.headers.get('X-MCP-Target-URL')
        if target_url:
            safe_print(f"[HTTP-Only] Using target URL from header: {target_url}")

    # 3. Check environment variable
    if not target_url:
        target_url = os.getenv('MCP_TARGET_URL')
        if target_url:
            safe_print(f"[HTTP-Only] Using target URL from env: {target_url}")

    if not target_url:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "No target URL specified"}),
            content_type='application/json'
        )

    # Forward all headers from client to target (except proxy-specific ones)
    skip_headers = {'host', 'content-length', 'connection', 'transfer-encoding'}
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in skip_headers:
            target_headers[header_name] = header_value

    if target_headers:
        safe_print(f"[HTTP-Only] Forwarding headers: {list(target_headers.keys())}")

    # Forward request to target server
    safe_print(f"[HTTP-Only] Forwarding to target: {target_url}")

    try:
        async with aiohttp.ClientSession() as session:
            # Merge default headers with client headers
            headers_to_send = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }
            headers_to_send.update(target_headers)

            async with session.post(
                target_url,
                json=message,
                headers=headers_to_send
            ) as response:
                # Handle 202 Accepted (no body) - typically for notifications
                if response.status == 202:
                    safe_print(f"[HTTP-Only] Target accepted request (202)")
                    return aiohttp.web.Response(
                        status=202,
                        text="",
                        content_type='application/json'
                    )

                # Handle other non-200 status codes
                if response.status != 200:
                    error_text = await response.text()
                    safe_print(f"[HTTP-Only] Target returned HTTP {response.status}")
                    safe_print(f"[HTTP-Only] Error response: {error_text}")
                    safe_print(f"[HTTP-Only] Response headers: {dict(response.headers)}")
                    return aiohttp.web.Response(
                        status=response.status,
                        text=error_text,
                        content_type='application/json'
                    )

                # Handle notifications (no response body expected)
                if is_notification:
                    safe_print(f"[HTTP-Only] Notification forwarded successfully")
                    return aiohttp.web.Response(
                        status=202,
                        text="",
                        content_type='application/json'
                    )

                # Get response data
                # Check if response is SSE stream (Streamable HTTP)
                content_type = response.headers.get('Content-Type', '')
                if 'text/event-stream' in content_type:
                    safe_print(f"[HTTP-Only] Response is SSE stream, reading events...")
                    # Read SSE stream and extract JSON from data events
                    response_data = None
                    async for line in response.content:
                        line_str = line.decode('utf-8').strip()
                        if line_str.startswith('data: '):
                            data_str = line_str[6:]  # Remove 'data: ' prefix
                            try:
                                response_data = json.loads(data_str)
                                safe_print(f"[HTTP-Only] Parsed JSON from SSE: {data_str[:100]}...")
                                break  # Use first data event
                            except json.JSONDecodeError:
                                continue

                    if not response_data:
                        return aiohttp.web.Response(
                            status=502,
                            text=json.dumps({"error": "No valid JSON in SSE stream"}),
                            content_type='application/json'
                        )
                else:
                    response_data = await response.json()

                # Log all responses to EventHub
                if state.event_hub:
                    event = {
                        'ts': int(time.time() * 1000),
                        'producer': 'remote',
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
                    await state.event_hub.process_event(event)

                # Verify tool response if this was a tool call
                if message.get('method') == 'tools/call' and response_data.get('result'):
                    params = message.get('params', {})
                    tool_name = params.get('name', 'unknown')

                    server_info = {
                        'appName': app_name,
                        'name': server_name,
                        'version': 'unknown'
                    }

                    safe_print(f"[Verify] Tool response: {tool_name} from {app_name}/{server_name}")

                    # Log response to EventHub
                    if state.event_hub:
                        event = {
                            'ts': int(time.time() * 1000),
                            'producer': 'remote',
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
                        await state.event_hub.process_event(event)

                    # Verify the tool response (skip logging since we already logged above)
                    verification = await verify_tool_response(
                        tool_name=tool_name,
                        response_data=response_data,
                        server_info=server_info,
                        skip_logging=True
                    )

                    if not verification.allowed:
                        reason = verification.reason or 'Security policy violation'
                        safe_print(f"[Verify] Response blocked: {reason}")
                        response_data = {
                            "jsonrpc": "2.0",
                            "id": response_data.get('id'),
                            "result": {
                                "content": [{
                                    "type": "text",
                                    "text": f"Response blocked: {reason}"
                                }]
                            }
                        }

                # Determine response type
                result = response_data.get('result', {})
                method = message.get('method', '')

                # Determine response type and print formatted output
                if result.get('tools'):
                    response_type = "tools/list"
                    tools = result.get('tools', [])
                    safe_print(f"[HTTP-Only] Discovered {len(tools)} tools")

                    # Modify tools to add user_intent parameter (like STDIO)
                    modified_tools = []
                    for i, tool in enumerate(tools):
                        tool_name = tool.get('name', 'unknown')
                        description = tool.get('description', '(no description)')
                        safe_print(f"  {i+1}. {tool_name} - {description}")

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

                        # Add security prefix to description
                        if modified_tool.get('description'):
                            modified_tool['description'] = f"🔒{modified_tool['description']}"

                        modified_tools.append(modified_tool)

                    # Replace tools in response
                    response_data['result']['tools'] = modified_tools
                    safe_print()  # Empty line after tool list
                elif result.get('content'):
                    response_type = "tools/call"
                    # Print response info
                    response_json = json.dumps(response_data)
                    safe_print(f"\n[HTTP-Only] {response_type} ({len(response_json)} chars)")
                    safe_print(json.dumps(response_data, indent=2, ensure_ascii=False))
                    safe_print()
                elif result.get('prompts'):
                    response_type = "prompts/list"
                    # Print prompts list
                    prompts = result.get('prompts', [])
                    safe_print(f"[HTTP-Only] Discovered {len(prompts)} prompts")
                    for i, prompt in enumerate(prompts):
                        prompt_name = prompt.get('name', 'unknown')
                        description = prompt.get('description', '(no description)')
                        safe_print(f"  {i+1}. {prompt_name} - {description}")
                    safe_print()
                elif result.get('messages'):
                    response_type = "prompts/get"
                    response_json = json.dumps(response_data)
                    safe_print(f"\n[HTTP-Only] {response_type} ({len(response_json)} chars)")
                    safe_print(json.dumps(response_data, indent=2, ensure_ascii=False))
                    safe_print()
                elif result.get('resources'):
                    response_type = "resources/list"
                    # Print resources list
                    resources = result.get('resources', [])
                    safe_print(f"[HTTP-Only] Discovered {len(resources)} resources")
                    for i, resource in enumerate(resources):
                        resource_uri = resource.get('uri', 'unknown')
                        name = resource.get('name', '')
                        description = resource.get('description', '(no description)')
                        display = f"{name} ({resource_uri})" if name else resource_uri
                        safe_print(f"  {i+1}. {display} - {description}")
                    safe_print()
                elif 'initialize' in method or result.get('protocolVersion'):
                    response_type = "initialize"
                    response_json = json.dumps(response_data)
                    safe_print(f"\n[HTTP-Only] {response_type} ({len(response_json)} chars)")
                    safe_print(json.dumps(response_data, indent=2, ensure_ascii=False))
                    safe_print()
                elif response_data.get('error'):
                    response_type = "error"
                    response_json = json.dumps(response_data)
                    safe_print(f"\n[HTTP-Only] {response_type} ({len(response_json)} chars)")
                    safe_print(json.dumps(response_data, indent=2, ensure_ascii=False))
                    safe_print()
                else:
                    response_type = "Response"
                    response_json = json.dumps(response_data)
                    safe_print(f"\n[HTTP-Only] {response_type} ({len(response_json)} chars)")
                    safe_print(json.dumps(response_data, indent=2, ensure_ascii=False))
                    safe_print()

                # Return response to client
                return aiohttp.web.Response(
                    status=200,
                    text=json.dumps(response_data),
                    content_type='application/json'
                )

    except Exception as e:
        safe_print(f"[HTTP-Only] Error forwarding to target: {e}")
        import traceback
        traceback.print_exc()
        return aiohttp.web.Response(
            status=502,
            text=json.dumps({
                "jsonrpc": "2.0",
                "id": message.get('id'),
                "error": {
                    "code": -32000,
                    "message": f"Error communicating with target: {str(e)}"
                }
            }),
            content_type='application/json'
        )

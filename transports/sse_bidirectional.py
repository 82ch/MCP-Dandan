"""
Bidirectional SSE transport for SSE-only MCP servers.

Some MCP servers (like CoinGecko) only support SSE for both directions,
not HTTP POST /message endpoint.
"""

import aiohttp
import asyncio
import json
import time
from verification import verify_tool_call, verify_tool_response
from state import state


async def write_chunked(response, data: str, chunk_size: int = 4000):
    """
    Write data to response in chunks to avoid "Chunk too big" error.

    aiohttp has a default chunk size limit of 8192 bytes when using chunked encoding.
    We use 4000 bytes chunks to ensure compatibility.
    """
    data_bytes = data.encode('utf-8') if isinstance(data, str) else data

    for i in range(0, len(data_bytes), chunk_size):
        chunk = data_bytes[i:i+chunk_size]
        try:
            await response.write(chunk)
            await response.drain()
        except Exception as e:
            print(f"[write_chunked] Error at offset {i}/{len(data_bytes)}: {e}")
            raise


async def handle_sse_bidirectional(
    target_url: str,
    target_headers: dict,
    client_response,
    message_endpoint: str,
    connection
):
    """
    Handle bidirectional communication over SSE.

    This is for servers that only use SSE (no /message endpoint).
    Messages from client are sent via SSE POST with chunked encoding.

    Args:
        target_url: Target SSE endpoint
        target_headers: Headers to forward to target
        client_response: StreamResponse to client
        message_endpoint: Proxy message endpoint for client
        connection: SSEConnection object from state
    """
    print(f"[SSE-Bidir] Starting bidirectional SSE mode for {target_url}")

    # Create message queue for client -> target messages
    message_queue = asyncio.Queue()
    connection.message_queue = message_queue

    # Track the target's message endpoint (received via endpoint event)
    target_message_endpoint = None

    # Track pending tool calls for verification (maps message ID -> tool name)
    pending_tool_calls = {}

    # Headers for SSE connection
    headers_to_send = {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
    }
    headers_to_send.update(target_headers)

    try:
        async with aiohttp.ClientSession() as session:
            # Connect to target SSE endpoint
            async with session.get(
                target_url,
                headers=headers_to_send,
                timeout=aiohttp.ClientTimeout(total=None, connect=30)  # No total timeout for SSE
            ) as target_response:
                print(f"[SSE-Bidir] Connected to target: HTTP {target_response.status}")

                if target_response.status != 200:
                    error_event = f"event: error\ndata: {json.dumps({'error': f'Target returned {target_response.status}'})}\n\n"
                    await write_chunked(client_response, error_event)
                    return

                # Task 1: Forward events from target to client
                async def forward_target_to_client():
                    nonlocal target_message_endpoint
                    try:
                        current_event = None
                        current_data_lines = []

                        # Read content in chunks and process line by line
                        # Use iter_any() to read without chunk size limits
                        buffer = b""
                        async for chunk in target_response.content.iter_any():
                            buffer += chunk
                            # Process all complete lines in buffer
                            while b'\n' in buffer:
                                line_bytes, buffer = buffer.split(b'\n', 1)
                                line_str = line_bytes.decode('utf-8')

                                # SSE events are separated by blank lines
                                if line_str.strip() == '':
                                    # End of event - process it
                                    # Log all received events to EventHub
                                    if current_event and current_data_lines:
                                        try:
                                            # Try to parse JSON data for logging
                                            parsed_data = None
                                            if current_data_lines and current_event != 'endpoint':
                                                try:
                                                    parsed_data = json.loads(current_data_lines[0])
                                                except:
                                                    pass

                                            if state.event_hub:
                                                event = {
                                                    'ts': int(time.time() * 1000),
                                                    'producer': 'remote',
                                                    'pid': None,
                                                    'pname': connection.app_name,
                                                    'eventType': 'MCP',
                                                    'mcpTag': connection.server_name,
                                                    'data': {
                                                        'task': 'RECV',
                                                        'message': parsed_data if parsed_data else {'raw': current_data_lines},
                                                        'mcpTag': connection.server_name
                                                    }
                                                }
                                                await state.event_hub.process_event(event)
                                        except Exception as log_err:
                                            print(f"[SSE-Bidir] Error logging event to EventHub: {log_err}")

                                    if current_event == 'endpoint' and current_data_lines:
                                        # Capture target's message endpoint
                                        target_message_endpoint = ''.join(current_data_lines)
                                        print(f"[SSE-Bidir] Captured target message endpoint: {target_message_endpoint}")

                                        # Rewrite to proxy endpoint
                                        print(f"[SSE-Bidir] Rewriting endpoint event")
                                        try:
                                            rewritten = f"event: endpoint\ndata: {message_endpoint}\n\n"
                                            await write_chunked(client_response, rewritten)
                                        except Exception as e:
                                            print(f"[SSE-Bidir] Cannot write endpoint (connection may be closing): {e}")
                                            return  # Exit if client disconnected
                                    elif current_event or current_data_lines:
                                        # Forward other events as-is
                                        try:
                                            # Parse and modify data lines BEFORE building event
                                            for idx, data_line in enumerate(current_data_lines):
                                                # Parse and display JSON responses (first line only)
                                                if idx == 0:
                                                    try:
                                                        import json as json_lib
                                                        parsed = json_lib.loads(data_line)

                                                        # Determine response type
                                                        result = parsed.get('result', {})
                                                        method = parsed.get('method', '')

                                                        # Determine response type and print formatted output
                                                        if result.get('tools'):
                                                            response_type = "tools/list"
                                                            tools = result.get('tools', [])
                                                            print(f"[SSE-Bidir] Discovered {len(tools)} tools")

                                                            # Modify tools to add user_intent parameter (like STDIO)
                                                            modified_tools = []
                                                            for i, tool in enumerate(tools):
                                                                tool_name = tool.get('name', 'unknown')
                                                                description = tool.get('description', '(no description)')
                                                                print(f"  {i+1}. {tool_name} - {description}")

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

                                                            # Update parsed data with modified tools
                                                            parsed['result']['tools'] = modified_tools

                                                            # Update data_line with modified JSON
                                                            data_line = json_lib.dumps(parsed)
                                                            current_data_lines[0] = data_line
                                                            print()
                                                        elif result.get('content'):
                                                            response_type = "tools/call"

                                                            # Check if this is a tool response we need to verify
                                                            msg_id = parsed.get('id')
                                                            if msg_id in pending_tool_calls:
                                                                tool_name = pending_tool_calls[msg_id]

                                                                server_info = {
                                                                    'appName': connection.app_name,
                                                                    'name': connection.server_name,
                                                                    'version': 'unknown'
                                                                }

                                                                print(f"[Verify] Tool response: {tool_name} from {connection.app_name}/{connection.server_name}")

                                                                # Log response to EventHub
                                                                if state.event_hub:
                                                                    event = {
                                                                        'ts': int(time.time() * 1000),
                                                                        'producer': 'remote',
                                                                        'pid': None,
                                                                        'pname': connection.app_name,
                                                                        'eventType': 'MCP',
                                                                        'mcpTag': connection.server_name,
                                                                        'data': {
                                                                            'task': 'RECV',
                                                                            'message': parsed,
                                                                            'mcpTag': connection.server_name
                                                                        }
                                                                    }
                                                                    await state.event_hub.process_event(event)

                                                                # Verify the tool response (skip logging since we already logged above)
                                                                verification = await verify_tool_response(
                                                                    tool_name=tool_name,
                                                                    response_data=parsed,
                                                                    server_info=server_info,
                                                                    skip_logging=True
                                                                )

                                                                if not verification.allowed:
                                                                    reason = verification.reason or 'Security policy violation'
                                                                    print(f"[Verify] Response blocked: {reason}")
                                                                    parsed = {
                                                                        "jsonrpc": "2.0",
                                                                        "id": parsed.get('id'),
                                                                        "result": {
                                                                            "content": [{
                                                                                "type": "text",
                                                                                "text": f"Response blocked: {reason}"
                                                                            }]
                                                                        }
                                                                    }
                                                                    data_line = json_lib.dumps(parsed)
                                                                    current_data_lines[0] = data_line

                                                                # Remove from pending
                                                                del pending_tool_calls[msg_id]

                                                            print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                            print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                            print()
                                                        elif result.get('prompts'):
                                                            response_type = "prompts/list"
                                                            # Print prompts list
                                                            prompts = result.get('prompts', [])
                                                            print(f"[SSE-Bidir] Discovered {len(prompts)} prompts")
                                                            for i, prompt in enumerate(prompts):
                                                                prompt_name = prompt.get('name', 'unknown')
                                                                description = prompt.get('description', '(no description)')
                                                                print(f"  {i+1}. {prompt_name} - {description}")
                                                            print()
                                                        elif result.get('messages'):
                                                            response_type = "prompts/get"
                                                            print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                            print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                            print()
                                                        elif result.get('resources'):
                                                            response_type = "resources/list"
                                                            # Print resources list
                                                            resources = result.get('resources', [])
                                                            print(f"[SSE-Bidir] Discovered {len(resources)} resources")
                                                            for i, resource in enumerate(resources):
                                                                resource_uri = resource.get('uri', 'unknown')
                                                                name = resource.get('name', '')
                                                                description = resource.get('description', '(no description)')
                                                                display = f"{name} ({resource_uri})" if name else resource_uri
                                                                print(f"  {i+1}. {display} - {description}")
                                                            print()
                                                        elif 'initialize' in method or result.get('protocolVersion'):
                                                            response_type = "initialize"
                                                            print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                            print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                            print()
                                                        elif parsed.get('error'):
                                                            response_type = "error"
                                                            print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                            print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                            print()
                                                        else:
                                                            response_type = "Response"
                                                            print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                            print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                            print()
                                                    except:
                                                        pass

                                            # Now build the SSE event with (possibly modified) data
                                            event_parts = []
                                            if current_event:
                                                event_parts.append(f"event: {current_event}\n")

                                            # Write data lines (using modified data from current_data_lines)
                                            for data_line in current_data_lines:
                                                event_parts.append(f"data: {data_line}\n")

                                            event_parts.append("\n")
                                            full_event = ''.join(event_parts)
                                            await write_chunked(client_response, full_event)
                                        except ConnectionResetError:
                                            print(f"[SSE-Bidir] Client disconnected")
                                            return  # Exit gracefully
                                        except Exception as e:
                                            print(f"[SSE-Bidir] Error writing event to client: {e}")
                                            # Check if it's a connection error
                                            if "closing" in str(e).lower() or "closed" in str(e).lower():
                                                return  # Exit gracefully

                                    # Reset for next event
                                    current_event = None
                                    current_data_lines = []
                                elif line_str.startswith('event:'):
                                    current_event = line_str[6:].strip()
                                    print(f"[SSE-Bidir] Event type: {current_event}")
                                elif line_str.startswith('id:'):
                                    event_id = line_str[3:].strip()
                                    print(f"[SSE-Bidir] Event ID: {event_id}")
                                elif line_str.startswith('data:'):
                                    data_content = line_str[5:].strip()
                                    current_data_lines.append(data_content)
                                else:
                                    # Other SSE fields (id, retry, etc.) - forward as-is
                                    await write_chunked(client_response, line_bytes + b"\n")
                    except Exception as e:
                        print(f"[SSE-Bidir] Error forwarding target->client: {e}")

                # Task 2: Send queued messages from client to target via POST
                async def forward_client_to_target():
                    nonlocal target_message_endpoint
                    try:
                        while True:
                            # Wait for message from client (via /message endpoint)
                            message = await message_queue.get()

                            if message is None:  # Shutdown signal
                                break

                            print(f"[SSE-Bidir] Client -> Target: {message.get('method', 'response')}")

                            # Log all requests to EventHub
                            if state.event_hub:
                                event = {
                                    'ts': int(time.time() * 1000),
                                    'producer': 'remote',
                                    'pid': None,
                                    'pname': connection.app_name,
                                    'eventType': 'MCP',
                                    'mcpTag': connection.server_name,
                                    'data': {
                                        'task': 'SEND',
                                        'message': message,
                                        'mcpTag': connection.server_name
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
                                    'appName': connection.app_name,
                                    'name': connection.server_name,
                                    'version': 'unknown'
                                }

                                print(f"[Verify] Tool call: {tool_name} from {connection.app_name}/{connection.server_name}")
                                if user_intent:
                                    print(f"[Verify] User intent: {user_intent}")

                                # Verify the tool call (skip logging since we already logged above)
                                verification = await verify_tool_call(
                                    tool_name=tool_name,
                                    tool_args=tool_args_clean,
                                    server_info=server_info,
                                    user_intent=user_intent,
                                    skip_logging=True
                                )

                                if not verification.allowed:
                                    reason = verification.reason or 'Security policy violation'
                                    print(f"[Verify] Tool call blocked: {reason}")
                                    error_response = {
                                        "jsonrpc": "2.0",
                                        "id": message.get('id'),
                                        "result": {
                                            "content": [{
                                                "type": "text",
                                                "text": f"Tool call blocked: {reason}"
                                            }]
                                        }
                                    }
                                    event = f"event: message\ndata: {json.dumps(error_response)}\n\n"
                                    await write_chunked(client_response, event)
                                    continue

                                # Strip user_intent before forwarding to target
                                if 'user_intent' in tool_args:
                                    print(f"[SSE-Bidir] Stripping user_intent before forwarding")
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
                                    print(f"[SSE-Bidir] Tracking tool call {tool_name} with ID {msg_id}")

                            # Wait for target_message_endpoint to be set (from endpoint event)
                            retry_count = 0
                            while target_message_endpoint is None and retry_count < 50:
                                await asyncio.sleep(0.1)
                                retry_count += 1

                            if target_message_endpoint is None:
                                print(f"[SSE-Bidir] Error: Target message endpoint not received")
                                error_response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get('id'),
                                    "error": {
                                        "code": -32000,
                                        "message": "Target message endpoint not available"
                                    }
                                }
                                event = f"event: message\ndata: {json.dumps(error_response)}\n\n"
                                await write_chunked(client_response, event)
                                continue

                            # Construct full URL for target message endpoint
                            # If it's a relative path, use the target URL's base
                            if target_message_endpoint.startswith('/'):
                                # Extract base URL from target_url
                                from urllib.parse import urlparse
                                parsed = urlparse(target_url)
                                message_url = f"{parsed.scheme}://{parsed.netloc}{target_message_endpoint}"
                            else:
                                message_url = target_message_endpoint

                            print(f"[SSE-Bidir] Sending to: {message_url}")

                            try:
                                async with session.post(
                                    message_url,
                                    json=message,
                                    headers={
                                        'Content-Type': 'application/json',
                                        'Accept': 'application/json'
                                    },
                                    timeout=aiohttp.ClientTimeout(total=30)
                                ) as msg_response:
                                    if msg_response.status == 200:
                                        # Some servers return 200 with response body
                                        response_data = await msg_response.json()
                                        print(f"[SSE-Bidir] Got response from target via POST (200)")

                                        # Verify tool response if this was a tool call
                                        if message.get('method') == 'tools/call' and response_data.get('result'):
                                            params = message.get('params', {})
                                            tool_name = params.get('name', 'unknown')

                                            server_info = {
                                                'appName': connection.app_name,
                                                'name': connection.server_name,
                                                'version': 'unknown'
                                            }

                                            print(f"[Verify] Tool response: {tool_name} from {connection.app_name}/{connection.server_name}")

                                            # Log response to EventHub
                                            if state.event_hub:
                                                event = {
                                                    'ts': int(time.time() * 1000),
                                                    'producer': 'remote',
                                                    'pid': None,
                                                    'pname': connection.app_name,
                                                    'eventType': 'MCP',
                                                    'mcpTag': connection.server_name,
                                                    'data': {
                                                        'task': 'RECV',
                                                        'message': response_data,
                                                        'mcpTag': connection.server_name
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
                                                print(f"[Verify] Response blocked: {reason}")
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

                                        # Send response back to client via SSE
                                        event = f"event: message\ndata: {json.dumps(response_data)}\n\n"
                                        await write_chunked(client_response, event)
                                    elif msg_response.status == 202:
                                        # 202 Accepted - response will come via SSE stream
                                        print(f"[SSE-Bidir] Message accepted (202), waiting for response via SSE")
                                        # Don't send anything - response will come via SSE
                                    else:
                                        error_text = await msg_response.text()
                                        print(f"[SSE-Bidir] Target POST failed: {msg_response.status}")
                                        print(f"[SSE-Bidir] Error: {error_text}")

                                        # Return error to client
                                        error_response = {
                                            "jsonrpc": "2.0",
                                            "id": message.get('id'),
                                            "error": {
                                                "code": -32000,
                                                "message": f"Target server error: {msg_response.status}"
                                            }
                                        }
                                        event = f"event: message\ndata: {json.dumps(error_response)}\n\n"
                                        await write_chunked(client_response, event)
                            except Exception as e:
                                print(f"[SSE-Bidir] Error sending to target: {e}")
                                # Return error to client
                                error_response = {
                                    "jsonrpc": "2.0",
                                    "id": message.get('id'),
                                    "error": {
                                        "code": -32000,
                                        "message": f"Failed to communicate with target: {str(e)}"
                                    }
                                }
                                event = f"event: message\ndata: {json.dumps(error_response)}\n\n"
                                await write_chunked(client_response, event)
                    except Exception as e:
                        print(f"[SSE-Bidir] Error forwarding client->target: {e}")

                # Run both tasks concurrently
                await asyncio.gather(
                    forward_target_to_client(),
                    forward_client_to_target(),
                    return_exceptions=True
                )

    except Exception as e:
        print(f"[SSE-Bidir] Error in bidirectional SSE: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        try:
            await write_chunked(client_response, error_event)
        except:
            pass

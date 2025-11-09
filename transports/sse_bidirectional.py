"""
Bidirectional SSE transport for SSE-only MCP servers.

Some MCP servers (like CoinGecko) only support SSE for both directions,
not HTTP POST /message endpoint.
"""

import aiohttp
import asyncio
import json
from typing import Optional


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
                                            # Build complete SSE event
                                            event_parts = []
                                            if current_event:
                                                event_parts.append(f"event: {current_event}\n")

                                            # Write data lines
                                            for idx, data_line in enumerate(current_data_lines):
                                                event_parts.append(f"data: {data_line}\n")
                                                # Parse and display JSON responses (first line only)
                                                if idx == 0:
                                                    try:
                                                        import json as json_lib
                                                        parsed = json_lib.loads(data_line)

                                                        # Determine response type
                                                        result = parsed.get('result', {})
                                                        method = parsed.get('method', '')

                                                        if result.get('tools'):
                                                            response_type = "tools/list"
                                                        elif result.get('content'):
                                                            response_type = "tools/call"
                                                        elif result.get('prompts'):
                                                            response_type = "prompts/list"
                                                        elif result.get('messages'):
                                                            response_type = "prompts/get"
                                                        elif result.get('resources'):
                                                            response_type = "resources/list"
                                                        elif 'initialize' in method or result.get('protocolVersion'):
                                                            response_type = "initialize"
                                                        elif parsed.get('error'):
                                                            response_type = "error"
                                                        else:
                                                            response_type = "Response"

                                                        # Display response
                                                        print(f"\n[SSE-Bidir] {response_type} ({len(data_line)} chars)")
                                                        print(json_lib.dumps(parsed, indent=2, ensure_ascii=False))
                                                        print()
                                                    except:
                                                        pass

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

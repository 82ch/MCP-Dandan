"""
Message endpoint handler for MCP HTTP+SSE protocol.

Handles POST requests to the message endpoint for tool calls.
"""

import aiohttp
import json
import time

from state import state
from verification import verify_tool_call, verify_tool_response


async def handle_message_endpoint(request):
    """
    Handle POST requests to message endpoint (/{app}/{server}/message).

    This function:
    1. Receives JSON-RPC tool call from client
    2. Verifies the tool call
    3. Forwards to target server if allowed
    4. Receives response from target
    5. Verifies the response
    6. Returns to client if allowed

    Args:
        request: aiohttp Request object

    Returns:
        JSON response
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

    print(f"[Message] Handling message for {app_name}/{server_name}")

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

    print(f"[Message] {msg_type}: method={message.get('method')}, id={message.get('id', 'N/A')}")
    print(f"[Message] Payload: {json.dumps(message, indent=2)}")

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

    # Find matching SSE connection
    connection = await state.find_sse_connection(server_name, app_name)

    if not connection:
        print(f"[Message] No active SSE connection found for {server_name}")
        return aiohttp.web.Response(
            status=404,
            text=json.dumps({"error": "SSE connection not found"}),
            content_type='application/json'
        )

    target_url = connection.target_url
    target_headers = getattr(connection, 'target_headers', {})

    # Check if this is an SSE-only server with message queue
    if hasattr(connection, 'message_queue') and connection.message_queue is not None:
        print(f"[Message] Using SSE bidirectional mode (message queue)")
        # Put message in queue for SSE handler to send
        await connection.message_queue.put(message)
        # For SSE-only servers, the response comes back via SSE, not HTTP
        # Return 202 Accepted
        return aiohttp.web.Response(
            status=202,
            text="",
            content_type='application/json'
        )

    print(f"[Message] Target headers to forward: {list(target_headers.keys())}")

    # Verify tool calls
    if message.get('method') == 'tools/call' and message.get('params'):
        try:
            tool_name = message['params'].get('name')
            tool_args = message['params'].get('arguments', {})

            # Track the tool call
            call_key = await state.track_tool_call(
                tool_name=tool_name,
                request_id=message.get('id'),
                server_name=server_name,
                app_name=app_name,
                args=tool_args
            )

            print(f"[Message] Tracking tool call: {tool_name} as {call_key}")

            # Verify the tool call
            server_info = {
                "serverName": server_name,
                "appName": app_name,
                "serverVersion": "unknown"
            }

            verification = await verify_tool_call(
                tool_name=tool_name,
                tool_args=tool_args,
                server_info=server_info,
                user_intent="",  # HTTP+SSE doesn't have user_intent
                skip_logging=True  # Skip logging since we already logged above
            )

            if not verification.allowed:
                print(f"[Message] Tool call blocked: {verification.reason}")
                await state.remove_pending_call(call_key)

                return aiohttp.web.Response(
                    status=200,
                    text=json.dumps({
                        "jsonrpc": "2.0",
                        "id": message.get('id'),
                        "error": {
                            "code": -32000,
                            "message": f"Tool call blocked: {verification.reason}"
                        }
                    }),
                    content_type='application/json'
                )

            # Cleanup stale calls periodically
            await state.cleanup_stale_calls()

        except Exception as e:
            print(f"[Message] Error during verification: {e}")

    # Forward request to target server
    # Convert SSE URL to message endpoint
    # Some servers use /sse, others don't have it
    if target_url.endswith('/sse'):
        message_endpoint = target_url.replace('/sse', '/message')
    elif '/sse?' in target_url:
        # Handle query parameters after /sse
        message_endpoint = target_url.replace('/sse?', '/message?')
    else:
        # URL doesn't have /sse, try to find the right endpoint
        # For servers like composio/coingecko that don't use /sse suffix
        message_endpoint = target_url

    print(f"[Message] Forwarding to target: {message_endpoint}")

    try:
        async with aiohttp.ClientSession() as session:
            # Merge default headers with custom headers
            headers_to_send = {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'
            }

            # Forward MCP-Protocol-Version header if present
            if 'MCP-Protocol-Version' in request.headers:
                headers_to_send['MCP-Protocol-Version'] = request.headers['MCP-Protocol-Version']
                print(f"[Message] Forwarding MCP-Protocol-Version: {request.headers['MCP-Protocol-Version']}")

            headers_to_send.update(target_headers)

            async with session.post(
                message_endpoint,
                json=message,
                headers=headers_to_send
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[Message] Target returned HTTP {response.status}")
                    print(f"[Message] Error response: {error_text}")
                    print(f"[Message] Response headers: {dict(response.headers)}")
                    return aiohttp.web.Response(
                        status=response.status,
                        text=error_text,
                        content_type='application/json'
                    )

                # Handle 202 Accepted (no body)
                if response.status == 202:
                    return aiohttp.web.Response(
                        status=202,
                        text="",
                        content_type='application/json'
                    )

                # Handle 202 or notifications (no response body expected)
                if is_notification:
                    print(f"[Message] Notification forwarded successfully")
                    return aiohttp.web.Response(
                        status=202,
                        text="",
                        content_type='application/json'
                    )

                # Get response data
                response_data = await response.json()
                print(f"[Message] Received response from target")
                print(f"[Message] Response payload: {json.dumps(response_data, indent=2)}")

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
                call_key = state.get_call_key(message.get('id'), server_name, app_name)
                pending_call = await state.get_pending_call(call_key)

                if pending_call and response_data.get('result'):
                    try:
                        tool_name = pending_call.tool_name
                        server_info = {
                            "serverName": server_name,
                            "appName": app_name,
                            "serverVersion": "unknown"
                        }

                        verification = await verify_tool_response(
                            tool_name=tool_name,
                            response_data=response_data.get('result'),
                            server_info=server_info,
                            skip_logging=True  # Skip logging since we already logged above
                        )

                        if not verification.allowed:
                            print(f"[Message] Response blocked: {verification.reason}")
                            await state.remove_pending_call(call_key)

                            return aiohttp.web.Response(
                                status=200,
                                text=json.dumps({
                                    "jsonrpc": "2.0",
                                    "id": message.get('id'),
                                    "error": {
                                        "code": -32000,
                                        "message": f"Response blocked: {verification.reason}"
                                    }
                                }),
                                content_type='application/json'
                            )

                        # Remove from pending calls
                        await state.remove_pending_call(call_key)

                    except Exception as e:
                        print(f"[Message] Error verifying response: {e}")

                # Return response to client
                return aiohttp.web.Response(
                    status=200,
                    text=json.dumps(response_data),
                    content_type='application/json'
                )

    except Exception as e:
        print(f"[Message] Error forwarding to target: {e}")
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

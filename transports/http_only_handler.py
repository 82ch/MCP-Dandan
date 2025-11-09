"""
HTTP-only endpoint handler for MCP servers that don't use SSE.

Handles POST requests directly without SSE connection (like Context7).
"""

import aiohttp
import json

from state import state, SSEConnection
from datetime import datetime


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

    print(f"[HTTP-Only] Request for {app_name}/{server_name}")

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

    print(f"[HTTP-Only] {msg_type}: method={message.get('method')}, id={message.get('id', 'N/A')}")
    print(f"[HTTP-Only] Payload: {json.dumps(message, indent=2)}")

    # Get target URL and headers from query/headers
    import os
    target_url = None
    target_headers = {}

    # 1. Check query parameter
    if 'target' in request.url.query:
        target_url = request.url.query.get('target')
        print(f"[HTTP-Only] Using target URL from query: {target_url}")

    # 2. Check header
    if not target_url:
        target_url = request.headers.get('X-MCP-Target-URL')
        if target_url:
            print(f"[HTTP-Only] Using target URL from header: {target_url}")

    # 3. Check environment variable
    if not target_url:
        target_url = os.getenv('MCP_TARGET_URL')
        if target_url:
            print(f"[HTTP-Only] Using target URL from env: {target_url}")

    if not target_url:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "No target URL specified"}),
            content_type='application/json'
        )

    # Collect custom headers (X-MCP-Header-* pattern)
    for header_name, header_value in request.headers.items():
        if header_name.startswith('X-MCP-Header-'):
            actual_header = header_name[len('X-MCP-Header-'):]
            target_headers[actual_header] = header_value
            print(f"[HTTP-Only] Forwarding custom header: {actual_header}")

    # Create or get existing dummy SSE connection
    connection = await state.find_sse_connection(server_name, app_name)

    if not connection:
        # Create a dummy SSE connection for HTTP-only mode
        connection_id = f"{server_name}-http-only-{int(datetime.now().timestamp() * 1000)}"
        connection = SSEConnection(
            server_name=server_name,
            app_name=app_name,
            target_url=target_url,
            client_response=None,  # No actual SSE response
            connection_id=connection_id,
            target_headers=target_headers
        )
        await state.add_sse_connection(connection)
        print(f"[HTTP-Only] Created dummy SSE connection: {connection_id}")

    # Forward request to target server
    print(f"[HTTP-Only] Forwarding to target: {target_url}")

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
                print(f"[HTTP-Only] Forwarding MCP-Protocol-Version: {request.headers['MCP-Protocol-Version']}")

            headers_to_send.update(target_headers)

            async with session.post(
                target_url,
                json=message,
                headers=headers_to_send
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[HTTP-Only] Target returned HTTP {response.status}")
                    print(f"[HTTP-Only] Error response: {error_text}")
                    print(f"[HTTP-Only] Response headers: {dict(response.headers)}")
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

                # Handle notifications (no response body expected)
                if is_notification:
                    print(f"[HTTP-Only] Notification forwarded successfully")
                    return aiohttp.web.Response(
                        status=202,
                        text="",
                        content_type='application/json'
                    )

                # Get response data
                response_data = await response.json()
                print(f"[HTTP-Only] Received response from target")
                print(f"[HTTP-Only] Response payload: {json.dumps(response_data, indent=2)}")

                # Return response to client
                return aiohttp.web.Response(
                    status=200,
                    text=json.dumps(response_data),
                    content_type='application/json'
                )

    except Exception as e:
        print(f"[HTTP-Only] Error forwarding to target: {e}")
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

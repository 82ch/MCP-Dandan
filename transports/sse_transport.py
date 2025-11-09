"""
SSE (Server-Sent Events) transport handler for MCP HTTP+SSE protocol.

Implements the SSE connection endpoint from MCP specification 2024-11-05.
"""

import aiohttp
import asyncio
import json
from typing import Optional
from datetime import datetime

from state import state, SSEConnection
from verification import verify_tool_response
from transports.sse_bidirectional import handle_sse_bidirectional


async def query_server_tools(target_url: str, server_name: str, app_name: str):
    """
    Query tools from the target MCP server using tools/list.

    Args:
        target_url: Target server's SSE URL
        server_name: Name of the MCP server
        app_name: Name of the application
    """
    try:
        print(f"[Tools] Querying tools from {server_name} at {target_url}")

        # Convert SSE URL to message endpoint
        message_endpoint = target_url.replace('/sse', '/message')

        # Create tools/list JSON-RPC request
        request_id = f"mcp-proxy-tools-list-{int(datetime.now().timestamp() * 1000)}"
        list_request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
            "params": {}
        }

        # Send request with timeout
        async with aiohttp.ClientSession() as session:
            async with session.post(
                message_endpoint,
                json=list_request,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"[Message] Target returned HTTP {response.status}")
                    print(f"[Message] Error response: {error_text}")
                    print(f"[Message] Response headers: {dict(response.headers)}")
                    return aiohttp.web.Response(
                        status=response.status,
                        text=error_text,
                        content_type='application/json',
                    )

                data = await response.json()

                if data.get('result') and data['result'].get('tools'):
                    tools = data['result']['tools']
                    print(f"[Tools] Discovered {len(tools)} tools from {server_name}")

                    # Register tools in state
                    await state.register_tools(
                        app_name=app_name,
                        server_name=server_name,
                        tools=tools,
                        server_info={"name": server_name, "version": "unknown"}
                    )
                else:
                    print(f"[Tools] Invalid tools/list response from {server_name}")

    except asyncio.TimeoutError:
        print(f"[Tools] Tool query to {server_name} timed out")
    except Exception as e:
        print(f"[Tools] Error querying tools from {server_name}: {e}")


async def handle_sse_connection(request):
    """
    Handle SSE connection endpoint (GET /{app}/{server}/sse).

    This function:
    1. Accepts GET request from client with Accept: text/event-stream
    2. Establishes connection to target MCP server
    3. Rewrites 'endpoint' event to point to proxy
    4. Forwards events between target and client
    5. Verifies tool responses if needed

    Args:
        request: aiohttp Request object

    Returns:
        StreamResponse with SSE events
    """
    # Extract app and server names from URL
    path_parts = request.path.strip('/').split('/')
    if len(path_parts) < 2:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "Invalid path format"})
        )

    app_name = path_parts[0]
    server_name = path_parts[1]

    print(f"[SSE] New connection for {app_name}/{server_name}")

    # Validate Accept header
    accept_header = request.headers.get('Accept', '')
    if 'text/event-stream' not in accept_header:
        return aiohttp.web.Response(
            status=406,
            text=json.dumps({"error": "Client must accept text/event-stream"})
        )

    # Get target URL from multiple sources (priority order):
    # 1. Query parameter: ?target=https://...
    # 2. Header: X-MCP-Target-URL
    # 3. Environment variable: MCP_TARGET_URL
    # 4. State configuration: state.protected_servers
    import os

    target_url = None
    target_headers = {}

    # Debug: print full request URL
    print(f"[SSE] Full request URL: {request.url}")
    print(f"[SSE] Query string: {request.url.query_string}")

    # 1. Check query parameter
    if request.url.query_string:
        # aiohttp provides query as multidict
        if 'target' in request.url.query:
            target_url = request.url.query.get('target')
            print(f"[SSE] Using target URL from query parameter: {target_url}")

    # 2. Check header
    if not target_url:
        target_url = request.headers.get('X-MCP-Target-URL')
        if target_url:
            print(f"[SSE] Using target URL from header: {target_url}")

    # 3. Check environment variable
    if not target_url:
        target_url = os.getenv('MCP_TARGET_URL')
        if target_url:
            print(f"[SSE] Using target URL from environment variable: {target_url}")

    # 4. Check state configuration
    if not target_url:
        # TODO: Look up from state.protected_servers[app_name]
        # For now, use default
        target_url = 'http://localhost:3001/sse'
        print(f"[SSE] Using default target URL")

    print(f"[SSE] Final target URL: {target_url}")

    # Collect custom headers from client (X-MCP-Header-* pattern)
    for header_name, header_value in request.headers.items():
        if header_name.startswith('X-MCP-Header-'):
            # Extract actual header name (e.g., X-MCP-Header-CONTEXT7_API_KEY -> CONTEXT7_API_KEY)
            actual_header = header_name[len('X-MCP-Header-'):]
            target_headers[actual_header] = header_value
            print(f"[SSE] Forwarding custom header: {actual_header}")

    # Create SSE response to client with compression disabled
    response = aiohttp.web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
        }
    )
    # Enable chunked encoding
    response.enable_chunked_encoding()
    # Increase the chunk size limit
    response._length_check = False  # Disable length check

    await response.prepare(request)

    # Send endpoint event with proxy's message URL
    message_endpoint = f"/{app_name}/{server_name}/message"
    endpoint_event = f"event: endpoint\ndata: {message_endpoint}\n\n"
    await response.write(endpoint_event.encode('utf-8'))
    print(f"[SSE] Sent endpoint event: {message_endpoint}")

    # Create connection tracking
    connection_id = f"{server_name}-{int(datetime.now().timestamp() * 1000)}"
    connection = SSEConnection(
        server_name=server_name,
        app_name=app_name,
        target_url=target_url,
        client_response=response,
        connection_id=connection_id,
        target_headers=target_headers
    )

    await state.add_sse_connection(connection)

    try:
        # Check if target URL looks like it needs SSE or just HTTP POST
        # If target doesn't end with /sse, it's likely HTTP-only (like Context7)
        is_http_only = not target_url.endswith('/sse')

        if is_http_only:
            print(f"[SSE] Target appears to be HTTP-only, keeping SSE connection open without target SSE")
            # Keep the connection alive but don't connect to target SSE
            # The client (Cursor) will send POST requests to /message endpoint
            # Just wait indefinitely (client will close when done)
            try:
                while True:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                print(f"[SSE] Client closed SSE connection")
        else:
            # Traditional SSE mode - connect to target SSE
            # Use bidirectional SSE mode (supports both SSE streaming and message queue)
            await handle_sse_bidirectional(
                target_url=target_url,
                target_headers=target_headers,
                client_response=response,
                message_endpoint=message_endpoint,
                connection=connection
            )

    except Exception as e:
        print(f"[SSE] Error in SSE connection: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        try:
            await response.write(error_event.encode('utf-8'))
        except:
            pass

    finally:
        # Cleanup connection
        await state.remove_sse_connection(connection_id)
        print(f"[SSE] Connection closed: {connection_id}")

    return response

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
from transports.sse_bidirectional import handle_sse_bidirectional, write_chunked
from utils import safe_print


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
    # Extract app and server names from URL path variables
    # aiohttp already validated the path format via route pattern
    app_name = request.match_info.get('app')
    server_name = request.match_info.get('server')

    if not app_name or not server_name:
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({"error": "Invalid path format"})
        )

    safe_print(f"[SSE] New connection for {app_name}/{server_name}")

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
    safe_print(f"[SSE] Full request URL: {request.url}")
    safe_print(f"[SSE] Query string: {request.url.query_string}")

    # 1. Check query parameter
    if request.url.query_string:
        # aiohttp provides query as multidict
        if 'target' in request.url.query:
            target_url = request.url.query.get('target')
            safe_print(f"[SSE] Using target URL from query parameter: {target_url}")

    # 2. Check header
    if not target_url:
        target_url = request.headers.get('X-MCP-Target-URL')
        if target_url:
            safe_print(f"[SSE] Using target URL from header: {target_url}")

    # 3. Check environment variable
    if not target_url:
        target_url = os.getenv('MCP_TARGET_URL')
        if target_url:
            safe_print(f"[SSE] Using target URL from environment variable: {target_url}")

    # 4. Require target URL
    if not target_url:
        safe_print(f"[SSE] Error: No target URL specified for {app_name}/{server_name}")
        return aiohttp.web.Response(
            status=400,
            text=json.dumps({
                "error": "No target URL specified",
                "message": "Please provide target URL via query parameter (?target=), header (X-MCP-Target-URL), or environment variable (MCP_TARGET_URL)"
            }),
            content_type='application/json'
        )

    safe_print(f"[SSE] Final target URL: {target_url}")

    # Forward all headers from client to target (except proxy-specific ones)
    skip_headers = {'host', 'content-length', 'connection', 'transfer-encoding', 'accept'}
    for header_name, header_value in request.headers.items():
        if header_name.lower() not in skip_headers:
            target_headers[header_name] = header_value

    if target_headers:
        safe_print(f"[SSE] Forwarding headers: {list(target_headers.keys())}")

    # Create SSE response to client with compression disabled
    response = aiohttp.web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache, no-transform',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Transfer-Encoding': 'chunked',  # Explicit chunked encoding
        }
    )
    # Enable chunked encoding
    response.enable_chunked_encoding()
    # Disable compression to avoid issues with large chunks
    response.enable_compression(aiohttp.web.ContentCoding.identity)

    await response.prepare(request)

    # Try to configure payload writer for large chunks
    if hasattr(response, '_payload_writer') and response._payload_writer:
        writer = response._payload_writer
        # In aiohttp 3.x, check for different attributes
        if hasattr(writer, 'buffer_size'):
            writer.buffer_size = 1024 * 1024  # 1MB
        if hasattr(writer, '_chunk_size'):
            writer._chunk_size = 1024 * 1024  # 1MB
        safe_print(f"[SSE] Payload writer configured: {type(writer).__name__}")

    # Send endpoint event with proxy's message URL
    message_endpoint = f"/{app_name}/{server_name}/message"
    endpoint_event = f"event: endpoint\ndata: {message_endpoint}\n\n"
    await write_chunked(response, endpoint_event)
    safe_print(f"[SSE] Sent endpoint event: {message_endpoint}")

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
            safe_print(f"[SSE] Target appears to be HTTP-only, keeping SSE connection open without target SSE")
            # Keep the connection alive but don't connect to target SSE
            # The client (Cursor) will send POST requests to /message endpoint
            # Just wait indefinitely (client will close when done)
            try:
                while True:
                    await asyncio.sleep(60)
            except asyncio.CancelledError:
                safe_print(f"[SSE] Client closed SSE connection")
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
        safe_print(f"[SSE] Error in SSE connection: {e}")
        error_event = f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        try:
            await write_chunked(response, error_event)
        except:
            pass

    finally:
        # Cleanup connection
        await state.remove_sse_connection(connection_id)
        safe_print(f"[SSE] Connection closed: {connection_id}")

    return response

"""
Auto-detecting transport handler.

Automatically detects if target is SSE or HTTP-only based on initial connection.
"""

import aiohttp
import asyncio
from transports.sse_transport import handle_sse_connection
from transports.http_handler import handle_http_only_message
from utils import safe_print


async def handle_auto_detect(request):
    """
    Auto-detect handler that determines if target is SSE or HTTP-only.

    Strategy:
    1. Check if request is GET with Accept: text/event-stream -> SSE mode
    2. Check if request is POST -> Try to detect from target URL response
    """

    # GET request with text/event-stream = SSE connection
    if request.method == 'GET':
        accept_header = request.headers.get('Accept', '')
        if 'text/event-stream' in accept_header:
            safe_print(f"[Auto] Detected SSE connection (GET + text/event-stream)")
            return await handle_sse_connection(request)

    # POST request = Could be HTTP-only or message endpoint
    # Delegate to HTTP-only handler (which handles both cases now)
    if request.method == 'POST':
        safe_print(f"[Auto] Detected POST request, using HTTP-only handler")
        return await handle_http_only_message(request)

    # Unsupported method
    return aiohttp.web.Response(
        status=405,
        text='Method not allowed',
        content_type='text/plain'
    )

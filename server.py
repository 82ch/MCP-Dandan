"""
82ch - MCP Security Proxy Server

Main HTTP server that routes requests to appropriate handlers.
Supports both HTTP+SSE and STDIO transports.
"""

import os
from aiohttp import web

from transports.sse_transport import handle_sse_connection
from transports.message_handler import handle_message_endpoint
from transports.stdio_handlers import (
    handle_verify_request,
    handle_verify_response,
    handle_register_tools
)
from state import state


# Server configuration
SERVER_CONFIG = {
    'port': int(os.getenv('MCP_PROXY_PORT', '28173')),
    'host': os.getenv('MCP_PROXY_HOST', '127.0.0.1')
}


async def handle_health(request):
    """Health check endpoint."""
    return web.Response(
        text='{"status": "ok"}',
        content_type='application/json'
    )


def setup_routes(app):
    """Setup application routes."""

    # Health check
    app.router.add_get('/health', handle_health)

    # STDIO verification API endpoints
    app.router.add_post('/verify/request', handle_verify_request)
    app.router.add_post('/verify/response', handle_verify_response)
    app.router.add_post('/register-tools', handle_register_tools)

    # HTTP+SSE transport endpoints
    # Format: /{appName}/{serverName}/sse (GET)
    app.router.add_get('/{app}/{server}/sse', handle_sse_connection)

    # Format: /{appName}/{serverName}/message (POST)
    app.router.add_post('/{app}/{server}/message', handle_message_endpoint)

    print(f"[Server] Routes configured:")
    print(f"  GET  /health - Health check")
    print(f"  POST /verify/request - STDIO verification API")
    print(f"  POST /verify/response - STDIO verification API")
    print(f"  POST /register-tools - Tool registration")
    print(f"  GET  /{{app}}/{{server}}/sse - SSE connection endpoint")
    print(f"  POST /{{app}}/{{server}}/message - Message endpoint")


async def on_startup(app):
    """Called when the application starts."""
    state.running = True
    print(f"[Server] 82ch MCP proxy starting...")
    print(f"[Server] Listening on http://{SERVER_CONFIG['host']}:{SERVER_CONFIG['port']}")


async def on_shutdown(app):
    """Called when the application shuts down."""
    state.running = False
    print(f"[Server] 82ch MCP proxy shutting down...")


def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Setup routes
    setup_routes(app)

    # Setup lifecycle callbacks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


def main():
    """Main entry point."""
    print("=" * 60)
    print("82ch - MCP Security Proxy")
    print("=" * 60)

    app = create_app()

    # Run the server
    web.run_app(
        app,
        host=SERVER_CONFIG['host'],
        port=SERVER_CONFIG['port'],
        print=None  # Disable aiohttp's startup message
    )


if __name__ == '__main__':
    main()

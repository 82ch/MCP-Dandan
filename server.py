"""
82ch - Unified MCP Security Framework

Single entry point for Observer (MCP Proxy) + Engine (Threat Detection).
Runs both components in a single process.
"""

import os
import sys
import asyncio
from aiohttp import web

from transports.auto_handler import handle_auto_detect
from transports.message_handler import handle_message_endpoint
from transports.stdio_handlers import (
    handle_verify_request,
    handle_verify_response,
    handle_register_tools
)
from state import state
from config import config

# Engine components
from database import Database
from event_hub import EventHub
from engines.sensitive_file_engine import SensitiveFileEngine
from engines.tools_poisoning_engine import ToolsPoisoningEngine
from engines.command_injection_engine import CommandInjectionEngine
from engines.file_system_exposure_engine import FileSystemExposureEngine


def setup_engines(db: Database) -> list:
    """Initialize and configure detection engines based on config."""
    engines = []

    # Sensitive File Engine
    if config.get_sensitive_file_enabled():
        try:
            engine = SensitiveFileEngine(db)
            engines.append(engine)
        except Exception as e:
            print(f"[Engine] Failed to initialize SensitiveFileEngine: {e}")

    # Tools Poisoning Engine (LLM-based)
    if config.get_tools_poisoning_enabled():
        try:
            engine = ToolsPoisoningEngine(db, detail_mode=True)
            engines.append(engine)
        except Exception as e:
            print(f"[Engine] Failed to initialize ToolsPoisoningEngine: {e}")

    # Command Injection Engine
    if config.get_command_injection_enabled():
        try:
            engine = CommandInjectionEngine(db)
            engines.append(engine)
        except Exception as e:
            print(f"[Engine] Failed to initialize CommandInjectionEngine: {e}")

    # File System Exposure Engine
    if config.get_file_system_exposure_enabled():
        try:
            engine = FileSystemExposureEngine(db)
            engines.append(engine)
        except Exception as e:
            print(f"[Engine] Failed to initialize FileSystemExposureEngine: {e}")

    return engines


async def initialize_engine_system():
    """Initialize the engine detection system."""
    print("=" * 80)
    print("Initializing Engine System")
    print("=" * 80)

    # Initialize database
    db = Database()
    await db.connect()

    # Setup engines
    engines = setup_engines(db)

    if engines:
        print(f"\nActive Detection Engines ({len(engines)}):")
        for i, engine in enumerate(engines, 1):
            print(f"  {i}. {engine.name}")
    else:
        print("\nWarning: No detection engines enabled!")

    # Initialize EventHub
    event_hub = EventHub(engines, db)
    await event_hub.start()

    # Store in global state
    state.event_hub = event_hub

    print("\nEngine system initialized successfully")
    print("=" * 80)

    return db, event_hub


async def handle_health(request):
    """Health check endpoint."""
    return web.Response(
        text='{"status": "ok", "components": ["observer", "engine"]}',
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

    # Unified auto-detect endpoint
    # Format: /{appName}/{serverName} (GET or POST)
    # Automatically detects SSE vs HTTP-only based on request
    app.router.add_route('*', '/{app}/{server}', handle_auto_detect)

    # Message endpoint for SSE mode
    # Format: /{appName}/{serverName}/message (POST)
    # Used when SSE connection sends 'endpoint' event
    app.router.add_post('/{app}/{server}/message', handle_message_endpoint)

    print(f"[Server] Routes configured:")
    print(f"  GET  /health - Health check")
    print(f"  POST /verify/request - STDIO verification API")
    print(f"  POST /verify/response - STDIO verification API")
    print(f"  POST /register-tools - Tool registration")
    print(f"  *    /{{app}}/{{server}} - Unified MCP endpoint (auto-detect)")
    print(f"  POST /{{app}}/{{server}}/message - SSE message endpoint")


async def on_startup(app):
    """Called when the application starts."""
    state.running = True

    print("\n" + "=" * 80)
    print("82ch - MCP Security Framework")
    print("=" * 80)
    print("Observer + Engine integrated mode")
    print("=" * 80)

    # Initialize engine system
    try:
        db, event_hub = await initialize_engine_system()
        # Store references for cleanup
        app['db'] = db
        app['event_hub'] = event_hub
    except Exception as e:
        print(f"[Server] Warning: Failed to initialize engines: {e}")
        print("[Server] Continuing in Observer-only mode...")
        # Create minimal database without engines
        db = Database()
        await db.connect()
        app['db'] = db

    print(f"\n[Observer] Starting HTTP server...")
    print(f"[Observer] Listening on http://{config.server_host}:{config.server_port}")
    print(f"[Observer] Scan mode: {config.scan_mode}")
    print("\n" + "=" * 80)
    print("All components ready. Waiting for connections...")
    print("Press Ctrl+C to stop")
    print("=" * 80 + "\n")


async def on_shutdown(app):
    """Called when the application shuts down."""
    state.running = False

    print(f"[Server] Cleanup starting...")

    # Stop EventHub
    if state.event_hub:
        try:
            await asyncio.wait_for(state.event_hub.stop(), timeout=0.5)
        except asyncio.TimeoutError:
            print("[Server] EventHub timeout")
        except Exception as e:
            print(f"[Server] EventHub error: {e}")

    # Close database
    if 'db' in app:
        try:
            await asyncio.wait_for(app['db'].close(), timeout=0.5)
        except asyncio.TimeoutError:
            print("[Server] Database timeout")
        except Exception as e:
            print(f"[Server] Database error: {e}")

    print(f"[Server] Cleanup done")


def create_app():
    """Create and configure the aiohttp application."""
    app = web.Application()

    # Setup routes
    setup_routes(app)

    # Setup lifecycle callbacks
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app


async def start_server():
    """Main entry point."""
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, config.server_host, config.server_port)
    await site.start()

    print(f"[Observer] Listening on http://{config.server_host}:{config.server_port}")

    # Run the server
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Server] Interrupted")
    finally:
        await runner.cleanup()
        await app.shutdown()
        await app.cleanup()
        print("[Server] Server stopped")

if __name__ == '__main__':
    asyncio.run(start_server())

"""
82ch - Unified MCP Security Framework

Single entry point for Observer (MCP Proxy) + Engine (Threat Detection).
Runs both components in a single process.
"""

import os
import sys
import asyncio
from aiohttp import web
from utils import safe_print
from pathlib import Path

# 현재 서버를 실행 중인 파이썬 인터프리터 경로 (cross-platform)
PYTHON_CMD = sys.executable

# config_finder.py의 절대 경로
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FINDER_PATH = BASE_DIR / "transports" / "config_finder.py"


# Force UTF-8 encoding for stdin/stdout to handle Unicode properly
# This prevents encoding issues on Windows (cp949) and other systems
if sys.stdin.encoding != 'utf-8':
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Force unbuffered output for real-time logging
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from transports.auto_handler import handle_auto_detect
from transports.message_handler import handle_message_endpoint
from transports.stdio_handlers import (
    handle_verify_request,
    handle_verify_response,
    handle_register_tools
)
from transports.config_finder import ClaudeConfigFinder
from state import state
from config import config

# Global flag to track if config has been restored
_config_restored = False

def restore_original_config():
    """Restore original config files from backup"""
    global _config_restored
    if _config_restored:
        return
    _config_restored = True

    safe_print("\n[Config] Restoring original configuration...")
    try:
        import subprocess
        result = subprocess.run(
            [PYTHON_CMD, str(CONFIG_FINDER_PATH), '--restore'],
            text=True,
            timeout=10,
            capture_output=True
        )
        if result.returncode == 0:
            safe_print("[Config] Configuration restored successfully")
        else:
            safe_print(f"[Config] Restore warning: {result.stderr}")
    except Exception as e:
        safe_print(f"[Config] Failed to restore configuration: {e}")

# Register signal handlers for graceful shutdown with config restoration
import signal

def signal_handler(signum, frame):
    """Handle termination signals"""
    sig_name = signal.Signals(signum).name
    safe_print(f"\n[Server] Received {sig_name} signal")
    restore_original_config()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Process termination

# Windows-specific: handle console close events (X button, shutdown, logoff)
if sys.platform == 'win32':
    signal.signal(signal.SIGBREAK, signal_handler)

    # Also use atexit as fallback
    import atexit
    atexit.register(restore_original_config)

    # Use win32api for console control handler (handles X button better)
    try:
        import win32api
        import win32con

        def console_ctrl_handler(ctrl_type):
            """Handle Windows console control events"""
            if ctrl_type in (win32con.CTRL_CLOSE_EVENT,
                           win32con.CTRL_SHUTDOWN_EVENT,
                           win32con.CTRL_LOGOFF_EVENT):
                safe_print(f"\n[Server] Console control event: {ctrl_type}")
                restore_original_config()
                return True  # Handled
            return False  # Not handled

        win32api.SetConsoleCtrlHandler(console_ctrl_handler, True)
        safe_print("[Server] Windows console control handler registered")
    except ImportError:
        safe_print("[Server] win32api not available, using signal handlers only")

# Engine components
from database import Database
from event_hub import EventHub
from engines.tools_poisoning_engine import ToolsPoisoningEngine
from engines.command_injection_engine import CommandInjectionEngine
from engines.file_system_exposure_engine import FileSystemExposureEngine
from engines.pii_filter_engine import PIIFilterEngine
from engines.data_exfiltration_engine import DataExfiltrationEngine

# WebSocket handler
from websocket_handler import ws_handler


def setup_engines(db: Database) -> list:
    """Initialize and configure detection engines based on config."""
    engines = []

    # Tools Poisoning Engine (LLM-based)
    if config.get_tools_poisoning_enabled():
        try:
            engine = ToolsPoisoningEngine(db)
            engines.append(engine)
        except Exception as e:
            safe_print(f"[Engine] Failed to initialize ToolsPoisoningEngine: {e}")

    # Command Injection Engine
    if config.get_command_injection_enabled():
        try:
            engine = CommandInjectionEngine(db)
            engines.append(engine)
        except Exception as e:
            safe_print(f"[Engine] Failed to initialize CommandInjectionEngine: {e}")

    # File System Exposure Engine
    if config.get_file_system_exposure_enabled():
        try:
            engine = FileSystemExposureEngine(db)
            engines.append(engine)
        except Exception as e:
            safe_print(f"[Engine] Failed to initialize FileSystemExposureEngine: {e}")

    # PII Filter Engine
    if config.get_pii_filter_enabled():
        try:
            engine = PIIFilterEngine(db)
            engines.append(engine)
        except Exception as e:
            safe_print(f"[Engine] Failed to initialize PIIFilterEngine: {e}")
    # Data Exfiltration Engine
    if config.get_data_exfiltration_enabled():
        try:
            engine = DataExfiltrationEngine(db)
            engines.append(engine)
        except Exception as e:
            safe_print(f"[Engine] Failed to initialize DataExfiltrationEngine: {e}")

    return engines


async def initialize_engine_system():
    """Initialize the engine detection system."""
    safe_print("=" * 80)
    safe_print("Initializing Engine System")
    safe_print("=" * 80)

    # Initialize database
    db = Database()
    await db.connect()

    # Setup engines
    engines = setup_engines(db)

    if engines:
        safe_print(f"\nActive Detection Engines ({len(engines)}):")
        for i, engine in enumerate(engines, 1):
            safe_print(f"  {i}. {engine.name}")
    else:
        safe_print("\nWarning: No detection engines enabled!")

    # Initialize WebSocket handler
    await ws_handler.start()

    # Initialize EventHub with WebSocket handler
    event_hub = EventHub(engines, db, ws_handler)
    await event_hub.start()

    # Store in global state
    state.event_hub = event_hub

    safe_print("\nEngine system initialized successfully")
    safe_print("=" * 80)

    return db, event_hub


async def handle_health(request):
    """Health check endpoint."""
    return web.Response(
        text='{"status": "ok", "components": ["observer", "engine"]}',
        content_type='application/json'
    )


async def handle_analysis_status(request):
    """Get analysis status for all servers."""
    import json
    from state import state

    statuses = {}
    for server_name, status in state.analysis_status.items():
        statuses[server_name] = {
            'total_tools': status.total_tools,
            'analyzed_tools': status.analyzed_tools,
            'malicious_found': status.malicious_found,
            'status': status.status,
            'started_at': status.started_at.isoformat(),
            'completed_at': status.completed_at.isoformat() if status.completed_at else None,
            'progress_percent': int((status.analyzed_tools / status.total_tools * 100) if status.total_tools > 0 else 0)
        }

    return web.Response(
        text=json.dumps(statuses),
        content_type='application/json'
    )


def setup_routes(app):
    """Setup application routes."""

    # Health check
    app.router.add_get('/health', handle_health)

    # Analysis status
    app.router.add_get('/analysis/status', handle_analysis_status)

    # WebSocket endpoint
    app.router.add_get('/ws', ws_handler.handle_websocket)

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

    safe_print(f"[Server] Routes configured:")
    safe_print(f"  GET  /health - Health check")
    safe_print(f"  GET  /ws - WebSocket endpoint (real-time updates)")
    safe_print(f"  POST /verify/request - STDIO verification API")
    safe_print(f"  POST /verify/response - STDIO verification API")
    safe_print(f"  POST /register-tools - Tool registration")
    safe_print(f"  *    /{{app}}/{{server}} - Unified MCP endpoint (auto-detect)")
    safe_print(f"  POST /{{app}}/{{server}}/message - SSE message endpoint")


async def on_startup(app):
    """Called when the application starts."""
    state.running = True

    safe_print("\n" + "=" * 80)
    safe_print("82ch - MCP Security Framework")
    safe_print("=" * 80)
    safe_print("Observer + Engine integrated mode")
    safe_print("=" * 80)

    # Configure Claude Desktop config on startup
    import subprocess
    try:
        result = subprocess.run(
            [PYTHON_CMD, str(CONFIG_FINDER_PATH)],
            text=True,
            timeout=30,
            capture_output=True   # stderr 보려고 이거 넣는 것도 추천
        )
        if result.returncode == 0:
            safe_print("\n[Config] Claude Desktop configured successfully")
        else:
            safe_print(f"\n[Config] Warning: Configuration failed - {result.stderr}")
    except Exception as e:
        safe_print(f"\n[Config] Warning: Failed to configure Claude Desktop - {e}")

    # Initialize engine system
    try:
        db, event_hub = await initialize_engine_system()
        # Store references for cleanup
        app['db'] = db
        app['event_hub'] = event_hub
    except Exception as e:
        safe_print(f"[Server] Warning: Failed to initialize engines: {e}")
        safe_print("[Server] Continuing in Observer-only mode...")
        # Create minimal database without engines
        db = Database()
        await db.connect()
        app['db'] = db

    safe_print(f"\n[Observer] Starting HTTP server...")
    safe_print(f"[Observer] Listening on http://{config.server_host}:{config.server_port}")
    safe_print(f"[Observer] Scan mode: {config.scan_mode}")
    safe_print("\n" + "=" * 80)
    safe_print("All components ready. Waiting for connections...")
    safe_print("Press Ctrl+C to stop")
    safe_print("=" * 80 + "\n")


async def on_shutdown(app):
    """Called when the application shuts down."""
    state.running = False

    safe_print(f"[Server] Cleanup starting...")

    # Restore original config files
    restore_original_config()

    # Close all SSE connections gracefully
    if state.sse_connections:
        safe_print(f"[Server] Closing {len(state.sse_connections)} SSE connections...")
        connections_to_close = list(state.sse_connections.values())
        for conn in connections_to_close:
            try:
                # Send a close event to client if possible
                if conn.client_response and not conn.client_response._eof_sent:
                    try:
                        await conn.client_response.write_eof()
                    except:
                        pass

                # Close target session if exists
                if conn.target_session and not conn.target_session.closed:
                    await conn.target_session.close()
            except Exception as e:
                safe_print(f"[Server] Error closing SSE connection {conn.connection_id}: {e}")

        # Clear all connections
        state.sse_connections.clear()
        safe_print(f"[Server] All SSE connections closed")

    # Stop WebSocket handler
    try:
        await asyncio.wait_for(ws_handler.stop(), timeout=0.5)
    except asyncio.TimeoutError:
        safe_print("[Server] WebSocket handler timeout")
    except Exception as e:
        safe_print(f"[Server] WebSocket handler error: {e}")

    # Stop EventHub
    if state.event_hub:
        try:
            await asyncio.wait_for(state.event_hub.stop(), timeout=0.5)
        except asyncio.TimeoutError:
            safe_print("[Server] EventHub timeout")
        except Exception as e:
            safe_print(f"[Server] EventHub error: {e}")

    # Close database
    if 'db' in app:
        try:
            await asyncio.wait_for(app['db'].close(), timeout=0.5)
        except asyncio.TimeoutError:
            safe_print("[Server] Database timeout")
        except Exception as e:
            safe_print(f"[Server] Database error: {e}")

    safe_print(f"[Server] Cleanup done")


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

    safe_print(f"[Observer] Listening on http://{config.server_host}:{config.server_port}")

    # Run the server
    try:
        while True:
            await asyncio.sleep(1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        safe_print("\n[Server] Interrupted")
    finally:
        # Stop the site FIRST to prevent new connections and close the socket
        try:
            await site.stop()
            safe_print("[Server] Site stopped")
        except Exception as e:
            safe_print(f"[Server] Site stop error: {e}")

        # Then trigger shutdown callbacks to clean up SSE connections, etc.
        try:
            await asyncio.wait_for(app.shutdown(), timeout=2.0)
        except asyncio.TimeoutError:
            safe_print("[Server] App shutdown timeout")
        except Exception as e:
            safe_print(f"[Server] App shutdown error: {e}")

        # Cancel all remaining tasks
        try:
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            if tasks:
                safe_print(f"[Server] Cancelling {len(tasks)} remaining tasks...")
                for task in tasks:
                    task.cancel()

                # Wait for tasks to complete cancellation with suppressed exceptions
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            safe_print(f"[Server] Task cancellation error: {e}")

        # Final cleanup
        try:
            await asyncio.wait_for(runner.cleanup(), timeout=1.0)
        except asyncio.TimeoutError:
            safe_print("[Server] Runner cleanup timeout")
        except Exception as e:
            safe_print(f"[Server] Runner cleanup error: {e}")

        try:
            await asyncio.wait_for(app.cleanup(), timeout=1.0)
        except asyncio.TimeoutError:
            safe_print("[Server] App cleanup timeout")
        except Exception as e:
            safe_print(f"[Server] App cleanup error: {e}")

        safe_print("[Server] Server stopped")

if __name__ == '__main__':
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        # Clean exit, already handled in start_server()
        pass

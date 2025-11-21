"""
WebSocket handler for real-time updates to frontend.

Broadcasts events to all connected clients when:
- New MCP servers are registered
- New messages/events arrive
- Detection engine results are available
"""

import asyncio
import json
from typing import Set
from aiohttp import web, WSMsgType
from utils import safe_print


class WebSocketHandler:
    """
    Manages WebSocket connections and broadcasts real-time updates.
    """

    def __init__(self):
        self.connections: Set[web.WebSocketResponse] = set()
        self.running = False

    async def start(self):
        """Start the WebSocket handler."""
        self.running = True
        safe_print('[WebSocket] Handler started')

    async def stop(self):
        """Stop the WebSocket handler and close all connections."""
        self.running = False

        # Close all active connections
        if self.connections:
            safe_print(f'[WebSocket] Closing {len(self.connections)} connections...')
            close_tasks = []
            for ws in list(self.connections):
                close_tasks.append(ws.close())

            await asyncio.gather(*close_tasks, return_exceptions=True)
            self.connections.clear()

        safe_print('[WebSocket] Handler stopped')

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        Handle incoming WebSocket connection.

        Args:
            request: aiohttp request object

        Returns:
            WebSocketResponse
        """
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        # Add to active connections
        self.connections.add(ws)
        client_id = id(ws)
        safe_print(f'[WebSocket] Client {client_id} connected. Total: {len(self.connections)}')

        # Send initial connection success message
        await self.send_to_client(ws, {
            'type': 'connection',
            'status': 'connected',
            'message': 'WebSocket connection established'
        })

        try:
            # Listen for messages from client
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    msg_type = data.get('type')

                    if msg_type == 'ping':
                        await self.send_to_client(ws, {
                            'type': 'pong',
                            'timestamp': data.get('timestamp')
                        })
                    elif msg_type == 'blocking_decision':
                        # Handle user's blocking decision
                        await self._handle_blocking_decision(data)
                elif msg.type == WSMsgType.ERROR:
                    safe_print(f'[WebSocket] Client {client_id} error: {ws.exception()}')
                elif msg.type == WSMsgType.CLOSE:
                    safe_print(f'[WebSocket] Client {client_id} closed connection')
                    break
        except Exception as e:
            safe_print(f'[WebSocket] Client {client_id} exception: {e}')
        finally:
            # Remove from active connections
            self.connections.discard(ws)
            safe_print(f'[WebSocket] Client {client_id} disconnected. Total: {len(self.connections)}')

        return ws

    async def send_to_client(self, ws: web.WebSocketResponse, data: dict):
        """
        Send data to a specific client.

        Args:
            ws: WebSocket connection
            data: Dictionary to send as JSON
        """
        try:
            if not ws.closed:
                await ws.send_json(data)
        except Exception as e:
            safe_print(f'[WebSocket] Error sending to client: {e}')

    async def broadcast(self, event_type: str, data: dict):
        """
        Broadcast event to all connected clients.

        Args:
            event_type: Type of event ('server_update', 'message_update', etc.)
            data: Event data to broadcast
        """
        if not self.running or not self.connections:
            return

        message = {
            'type': event_type,
            'data': data
        }

        # Broadcast to all clients
        dead_connections = set()
        for ws in self.connections:
            try:
                if ws.closed:
                    dead_connections.add(ws)
                else:
                    await ws.send_json(message)
            except Exception as e:
                safe_print(f'[WebSocket] Error broadcasting to client: {e}')
                dead_connections.add(ws)

        # Clean up dead connections
        if dead_connections:
            self.connections -= dead_connections
            safe_print(f'[WebSocket] Removed {len(dead_connections)} dead connections')

    async def broadcast_server_update(self):
        """Notify clients that server list has changed."""
        await self.broadcast('server_update', {
            'message': 'Server list updated',
            'action': 'refresh_servers'
        })
        safe_print('[WebSocket] Broadcasted server_update')

    async def broadcast_message_update(self, server_id: int, server_name: str):
        """
        Notify clients that new messages are available for a server.

        Args:
            server_id: Server database ID
            server_name: Server name/tag
        """
        await self.broadcast('message_update', {
            'server_id': server_id,
            'server_name': server_name,
            'action': 'refresh_messages'
        })
        safe_print(f'[WebSocket] Broadcasted message_update for {server_name}')

    async def broadcast_detection_result(self, event_id: int, engine_name: str, severity: str):
        """
        Notify clients that a detection result is available.

        Args:
            event_id: Raw event ID
            engine_name: Name of detection engine
            severity: Severity level (none/low/medium/high)
        """
        await self.broadcast('detection_result', {
            'event_id': event_id,
            'engine_name': engine_name,
            'severity': severity,
            'action': 'refresh_detections'
        })
        safe_print(f'[WebSocket] Broadcasted detection_result: {engine_name} ({severity})')

    async def broadcast_reload_all(self):
        """Notify clients to reload all data (nuclear option)."""
        await self.broadcast('reload_all', {
            'message': 'Full reload requested',
            'action': 'reload_all'
        })
        safe_print('[WebSocket] Broadcasted reload_all')

    async def broadcast_blocking_request(self, request_id: str, event_data: dict,
                                         detection_results: list, engine_name: str,
                                         severity: str, server_name: str, tool_name: str):
        """
        Notify clients that a blocking decision is needed.

        Args:
            request_id: Unique ID for this blocking request
            event_data: Original event data
            detection_results: List of detection findings
            engine_name: Name of detection engine
            severity: Severity level
            server_name: Server name
            tool_name: Tool name being called
        """
        await self.broadcast('blocking_request', {
            'request_id': request_id,
            'event_data': event_data,
            'detection_results': detection_results,
            'engine_name': engine_name,
            'severity': severity,
            'server_name': server_name,
            'tool_name': tool_name,
            'action': 'show_blocking_modal'
        })
        safe_print(f'[WebSocket] Broadcasted blocking_request: {request_id} ({engine_name}: {severity})')

    async def _handle_blocking_decision(self, data: dict):
        """
        Handle user's blocking decision from frontend.

        Args:
            data: Decision data with request_id and decision (allow/block)
        """
        from state import state

        request_id = data.get('request_id')
        decision = data.get('decision')  # 'allow' or 'block'

        if not request_id or not decision:
            safe_print(f'[WebSocket] Invalid blocking decision: {data}')
            return

        blocking_request = await state.get_blocking_request(request_id)
        if not blocking_request:
            safe_print(f'[WebSocket] Blocking request not found: {request_id}')
            return

        # Resolve the future with user's decision
        if blocking_request.future and not blocking_request.future.done():
            blocking_request.future.set_result(decision == 'allow')
            safe_print(f'[WebSocket] Blocking decision received: {request_id} -> {decision}')

        # Clean up
        await state.remove_blocking_request(request_id)


# Global singleton instance
ws_handler = WebSocketHandler()

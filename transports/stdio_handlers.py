"""
STDIO transport verification API handlers.

These endpoints are used by the CLI proxy for verifying tool calls and responses.
"""

import json
import time
from aiohttp import web

from state import state
from verification import verify_tool_call, verify_tool_response
from utils import safe_print


async def handle_verify_request(request):
    """
    Handle verification and logging for all requests from STDIO proxy.

    POST /verify/request

    Body:
    {
        "message": {...},  // JSON-RPC message
        "toolName": "...",  // Tool name or method name
        "serverInfo": {...}
    }

    Returns:
    {
        "blocked": bool,
        "reason": str,
        "modified": bool
    }
    """
    try:
        data = await request.json()
    except Exception as e:
        return web.Response(
            status=400,
            text=json.dumps({"error": "Invalid JSON"}),
            content_type='application/json'
        )

    message = data.get('message')
    tool_name = data.get('toolName')
    server_info = data.get('serverInfo', {})
    stage = data.get('stage', None)  # 구분자 읽기

    if not message:
        return web.Response(
            status=400,
            text=json.dumps({"error": "Missing message"}),
            content_type='application/json'
        )

    try:
        app_name = server_info.get('appName', 'unknown')
        server_name = server_info.get('name', 'unknown')
        method = message.get('method', tool_name)

        # Determine event type: Proxy only for pre_init stage, MCP otherwise
        event_type = 'Proxy' if stage == 'pre_init' else 'MCP'

        # Create event for EventHub (logs all requests)
        event = {
            'ts': int(time.time() * 1000),
            'producer': 'local',
            'pid': None,
            'pname': app_name,
            'eventType': event_type,
            'mcpTag': server_name,
            'data': {
                'task': 'SEND',
                'message': message,
                'mcpTag': server_name
            }
        }

        # Send to EventHub for DB logging
        if state.event_hub:
            await state.event_hub.process_event(event)

        # Only verify tools/call for security
        if message.get('method') == 'tools/call':
            tool_args = message.get('params', {}).get('arguments', {})
            user_intent = tool_args.get('user_intent', '')
            tool_args_clean = {k: v for k, v in tool_args.items() if k != 'user_intent'}

            safe_print(f"[Verify] Tool call: {tool_name} from {app_name}/{server_name}")
            if user_intent:
                safe_print(f"[Verify] User intent: {user_intent}")

            # Verify the tool call (skip logging since we already logged above)
            verification = await verify_tool_call(
                tool_name=tool_name,
                tool_args=tool_args_clean,
                server_info=server_info,
                user_intent=user_intent,
                skip_logging=True
            )

            return web.Response(
                status=200,
                text=json.dumps({
                    "blocked": not verification.allowed,
                    "reason": verification.reason if not verification.allowed else None,
                    "modified": False
                }),
                content_type='application/json'
            )
        else:
            # Other methods: just log, don't block
            # pre_init 단계면 로그에 표시
            if stage == 'pre_init':
                safe_print(f"[Log] [Pre-Init] Request: {method} from {app_name}/{server_name}")
            else:
                safe_print(f"[Log] Request: {method} from {app_name}/{server_name}")
            return web.Response(
                status=200,
                text=json.dumps({
                    "blocked": False,
                    "reason": None,
                    "modified": False
                }),
                content_type='application/json'
            )

    except Exception as e:
        safe_print(f"[Verify] Error processing request: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(
            status=500,
            text=json.dumps({"error": "Processing error", "blocked": False}),
            content_type='application/json'
        )


async def handle_verify_response(request):
    """
    Handle verification and logging for all responses from STDIO proxy.

    POST /verify/response

    Body:
    {
        "message": {...},  // JSON-RPC response message
        "toolName": "...",  // Tool name or method name
        "serverInfo": {...}
    }

    Returns:
    {
        "blocked": bool,
        "reason": str,
        "modified": bool
    }
    """
    try:
        data = await request.json()
    except Exception as e:
        return web.Response(
            status=400,
            text=json.dumps({"error": "Invalid JSON"}),
            content_type='application/json'
        )

    message = data.get('message')
    server_info = data.get('serverInfo', {})
    tool_name = data.get('toolName', 'unknown')
    stage = data.get('stage', None)  # 구분자 읽기
    skip_analysis = data.get('skip_analysis', False)  # 엔진 분석 스킵 플래그

    if not message:
        return web.Response(
            status=400,
            text=json.dumps({"error": "Missing message"}),
            content_type='application/json'
        )

    try:
        app_name = server_info.get('appName', 'unknown')
        server_name = server_info.get('name', 'unknown')

        # Determine event type: Proxy only for pre_init stage, MCP otherwise
        event_type = 'Proxy' if stage == 'pre_init' else 'MCP'

        # Create event for EventHub (logs all responses)
        event = {
            'ts': int(time.time() * 1000),
            'producer': 'local',
            'pid': None,
            'pname': app_name,
            'eventType': event_type,
            'mcpTag': server_name,
            'data': {
                'task': 'RECV',
                'message': message,
                'mcpTag': server_name
            }
        }

        # Check if this is a tools/list response - needs synchronous processing
        is_tools_list = False
        if message.get('result') and message['result'].get('tools'):
            is_tools_list = True

        # Send to EventHub for DB logging and analysis
        if state.event_hub:
            if is_tools_list and not skip_analysis:
                # tools/list: 동기적으로 처리 (엔진 검사 완료까지 대기)
                stage_label = '[Pre-Init]' if stage == 'pre_init' else ''
                safe_print(f"[Log] {stage_label} tools/list Response from {app_name}/{server_name} - waiting for engine analysis")
                await state.event_hub.process_event_sync(event)
                safe_print(f"[Log] {stage_label} tools/list engine analysis completed for {app_name}/{server_name}")
            elif is_tools_list and skip_analysis:
                # tools/list이지만 분석 스킵 (캐시된 응답)
                safe_print(f"[Log] [Cached] tools/list Response from {app_name}/{server_name} - skipping analysis (already done)")
                await state.event_hub.process_event(event)
            else:
                # 다른 응답: 백그라운드 처리
                await state.event_hub.process_event(event)

        # Only verify tools/call responses for security
        if tool_name != 'unknown' and tool_name not in ['initialize', 'tools/list', 'notifications/initialized']:
            safe_print(f"[Verify] Tool response: {tool_name} from {app_name}/{server_name}")

            # Verify the tool response (skip logging since we already logged above)
            verification = await verify_tool_response(
                tool_name=tool_name,
                response_data=message,
                server_info=server_info,
                skip_logging=True
            )

            return web.Response(
                status=200,
                text=json.dumps({
                    "blocked": not verification.allowed,
                    "reason": verification.reason if not verification.allowed else None,
                    "modified": False
                }),
                content_type='application/json'
            )
        else:
            # Other responses: just log, don't block
            if not is_tools_list:
                # pre_init 단계면 로그에 표시
                if stage == 'pre_init':
                    safe_print(f"[Log] [Pre-Init] Response from {app_name}/{server_name}")
                else:
                    safe_print(f"[Log] Response from {app_name}/{server_name}")
            return web.Response(
                status=200,
                text=json.dumps({
                    "blocked": False,
                    "reason": None,
                    "modified": False
                }),
                content_type='application/json'
            )

    except Exception as e:
        safe_print(f"[Verify] Error processing response: {e}")
        import traceback
        traceback.print_exc()
        return web.Response(
            status=500,
            text=json.dumps({"error": "Processing error", "blocked": False}),
            content_type='application/json'
        )


async def handle_register_tools(request):
    """
    Handle tool registration from CLI proxy.

    POST /register-tools

    Body:
    {
        "tools": [...],
        "serverInfo": {...},
        "appName": "...",
        "serverName": "..."
    }

    Returns:
    {
        "success": bool,
        "message": str,
        "stats": {...}
    }
    """
    try:
        data = await request.json()
    except Exception as e:
        return web.Response(
            status=400,
            text=json.dumps({"error": "Invalid JSON"}),
            content_type='application/json'
        )

    tools = data.get('tools')
    app_name = data.get('appName')
    server_name = data.get('serverName')
    server_info = data.get('serverInfo', {})

    if not tools or not isinstance(tools, list):
        return web.Response(
            status=400,
            text=json.dumps({"error": "Invalid tools data"}),
            content_type='application/json'
        )

    try:
        safe_print(f"[Register] Registering {len(tools)} tools for {app_name}/{server_name}")

        # Log tool information
        for i, tool in enumerate(tools):
            description = tool.get('description', '(no description)')
            safe_print(f"  {i+1}. {tool.get('name')} - {description}")

        # Register tools in state
        await state.register_tools(
            app_name=app_name,
            server_name=server_name,
            tools=tools,
            server_info=server_info
        )

        # Count tools with/without descriptions
        with_desc = sum(1 for t in tools if t.get('description'))
        without_desc = len(tools) - with_desc

        safe_print(f"[Register] Successfully registered {len(tools)} tools for {app_name}:{server_name}")
        safe_print(f"  {with_desc} with descriptions, {without_desc} without")

        return web.Response(
            status=200,
            text=json.dumps({
                "success": True,
                "message": f"Registered {len(tools)} tools for {app_name}:{server_name}",
                "stats": {
                    "total": len(tools),
                    "withDescriptions": with_desc,
                    "withoutDescriptions": without_desc
                }
            }),
            content_type='application/json'
        )

    except Exception as e:
        safe_print(f"[Register] Error registering tools: {e}")
        return web.Response(
            status=500,
            text=json.dumps({"error": "Tool registration error"}),
            content_type='application/json'
        )

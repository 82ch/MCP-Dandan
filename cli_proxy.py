#!/usr/bin/env python3
"""
82ch STDIO Proxy - CLI Helper

Intercepts MCP STDIO communications between client and server for security verification.
"""

import sys
import os
import json
import subprocess
import asyncio
import requests
from typing import Optional, Dict, Any
from event_publisher import get_publisher


# Configuration
CONFIG = {
    'debug': os.getenv('MCP_DEBUG', 'false').lower() == 'true',
    'proxy_port': int(os.getenv('MCP_PROXY_PORT', '28173')),
    'proxy_host': os.getenv('MCP_PROXY_HOST', '127.0.0.1'),
    'app_name': os.getenv('MCP_OBSERVER_APP_NAME', 'unknown'),
    'server_name': os.getenv('MCP_OBSERVER_SERVER_NAME', 'unknown'),
    'discovery_mode': os.getenv('MCP_OBSERVER_DISCOVERY_MODE', 'false').lower() == 'true'
}


def log(level: str, message: str):
    """Log a message to stderr."""
    if CONFIG['debug'] or level == 'ERROR':
        print(f"[{level}] {message}", file=sys.stderr)


def make_api_request(endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make HTTP request to the proxy server."""
    url = f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}{endpoint}"

    try:
        log('DEBUG', f"API request to {endpoint}")
        response = requests.post(
            url,
            json=data,
            headers={'Content-Type': 'application/json'},
            timeout=35
        )

        if response.status_code >= 200 and response.status_code < 300:
            return response.json() if response.text else {}
        else:
            log('ERROR', f"API request failed: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        log('ERROR', f"Request to {endpoint} timed out")
        return None
    except requests.exceptions.ConnectionError:
        log('ERROR', "Proxy server not running or not accessible")
        return None
    except Exception as e:
        log('ERROR', f"API request error: {e}")
        return None


class MCPState:
    """State tracking for MCP protocol."""

    def __init__(self):
        self.protocol_version = "2024-11-05"
        self.current_tool_name: Optional[str] = None
        self.current_tool_id: Optional[Any] = None
        self.pending_tools_list_id: Optional[Any] = None
        self.server_version = "unknown"


state = MCPState()
publisher = get_publisher()


def process_request(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a JSON-RPC message from stdin before forwarding to target server.

    Returns:
        - Modified message to forward to target
        - Blocked response to send directly to stdout (if blocked)
        - None if message should be dropped
    """
    try:
        # Track tools/list request
        if message.get('method') == 'tools/list':
            log('DEBUG', f"Detected tools/list request: {message.get('id')}")
            state.pending_tools_list_id = message.get('id')

        # Check for tool calls
        if message.get('method') == 'tools/call':
            params = message.get('params', {})
            state.current_tool_name = params.get('name', 'unknown')
            state.current_tool_id = message.get('id')

            log('INFO', f"Verifying tool call: {state.current_tool_name}")

            # Publish MCP event to stdout for Electron
            publisher.publish_mcp_event(
                direction='request',
                message=message,
                app_name=CONFIG['app_name'],
                server_name=CONFIG['server_name'],
                tool_name=state.current_tool_name
            )

            # Send for verification
            verification_data = {
                'message': message,
                'toolName': state.current_tool_name,
                'serverInfo': {
                    'appName': CONFIG['app_name'],
                    'name': CONFIG['server_name'],
                    'version': state.server_version
                }
            }

            verification = make_api_request('/verify/request', verification_data)

            if verification is None:
                # Verification failed - block for security
                log('ERROR', f"Blocking {state.current_tool_name} - verification service unavailable")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get('id'),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"Tool call blocked - verification service unavailable"
                        }]
                    }
                }

            if verification.get('blocked'):
                reason = verification.get('reason', 'Security policy violation')
                log('INFO', f"Tool call blocked: {reason}")
                return {
                    "jsonrpc": "2.0",
                    "id": message.get('id'),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"Tool call blocked: {reason}"
                        }]
                    }
                }

            # Strip user_intent before forwarding to target
            if params.get('arguments') and 'user_intent' in params['arguments']:
                log('DEBUG', "Stripping user_intent before forwarding")
                clean_args = {k: v for k, v in params['arguments'].items() if k != 'user_intent'}
                message = {
                    **message,
                    'params': {
                        **params,
                        'arguments': clean_args
                    }
                }

        return message

    except Exception as e:
        log('ERROR', f"Error processing request: {e}")
        return message


def process_response(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a JSON-RPC message from target server before forwarding to stdout.

    Returns:
        - Modified message to forward to stdout
    """
    try:
        # Check for tools/list response
        if state.pending_tools_list_id is not None and message.get('id') == state.pending_tools_list_id:
            if message.get('result') and message['result'].get('tools'):
                tools = message['result']['tools']
                log('INFO', f"Discovered {len(tools)} tools")

                # Modify tools to add user_intent parameter
                modified_tools = []
                for tool in tools:
                    modified_tool = tool.copy()

                    # Ensure inputSchema exists
                    if 'inputSchema' not in modified_tool:
                        modified_tool['inputSchema'] = {
                            'type': 'object',
                            'properties': {},
                            'required': []
                        }

                    # Add user_intent to properties
                    if 'properties' not in modified_tool['inputSchema']:
                        modified_tool['inputSchema']['properties'] = {}

                    modified_tool['inputSchema']['properties']['user_intent'] = {
                        'type': 'string',
                        'description': 'Explain the reasoning and context for why you are calling this tool.'
                    }

                    # Add to required fields
                    required = modified_tool['inputSchema'].get('required', [])
                    if 'user_intent' not in required:
                        modified_tool['inputSchema']['required'] = required + ['user_intent']

                    # Add security prefix to description
                    if modified_tool.get('description'):
                        modified_tool['description'] = f"🔒{modified_tool['description']}"

                    modified_tools.append(modified_tool)

                message['result']['tools'] = modified_tools

                # Register tools with proxy (async, don't wait)
                registration_data = {
                    'tools': tools,
                    'serverInfo': {
                        'appName': CONFIG['app_name'],
                        'name': CONFIG['server_name'],
                        'version': state.server_version
                    },
                    'appName': CONFIG['app_name'],
                    'serverName': CONFIG['server_name']
                }

                # Make request in background
                try:
                    make_api_request('/register-tools', registration_data)
                    log('DEBUG', "Successfully registered tools")
                except:
                    pass

                state.pending_tools_list_id = None

        # Check for tool response
        if (state.current_tool_name and
            message.get('id') == state.current_tool_id and
            message.get('result')):

            log('DEBUG', f"Verifying response for {state.current_tool_name}")

            # Publish MCP event to stdout for Electron
            publisher.publish_mcp_event(
                direction='response',
                message=message,
                app_name=CONFIG['app_name'],
                server_name=CONFIG['server_name'],
                tool_name=state.current_tool_name
            )

            verification_data = {
                'message': message,
                'toolName': state.current_tool_name,
                'serverInfo': {
                    'appName': CONFIG['app_name'],
                    'name': CONFIG['server_name'],
                    'version': state.server_version
                }
            }

            verification = make_api_request('/verify/response', verification_data)

            if verification and verification.get('blocked'):
                reason = verification.get('reason', 'Security policy violation')
                log('INFO', f"Response blocked: {reason}")
                message = {
                    "jsonrpc": "2.0",
                    "id": message.get('id'),
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": f"Response blocked: {reason}"
                        }]
                    }
                }

            state.current_tool_name = None
            state.current_tool_id = None

        return message

    except Exception as e:
        log('ERROR', f"Error processing response: {e}")
        return message


def read_jsonrpc_message(stream) -> Optional[Dict[str, Any]]:
    """Read a single JSON-RPC message from stream."""
    try:
        line = stream.readline()
        if not line:
            return None

        # Parse JSON-RPC message
        message = json.loads(line)
        return message

    except json.JSONDecodeError:
        return None
    except Exception as e:
        log('ERROR', f"Error reading message: {e}")
        return None


def write_jsonrpc_message(stream, message: Dict[str, Any]):
    """Write a JSON-RPC message to stream."""
    try:
        line = json.dumps(message) + '\n'
        stream.write(line)
        stream.flush()
    except Exception as e:
        log('ERROR', f"Error writing message: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python cli_proxy.py <command> [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    log('INFO', f"Starting STDIO proxy for: {command} {' '.join(args)}")
    log('INFO', f"App: {CONFIG['app_name']}, Server: {CONFIG['server_name']}")

    # Start target server process
    try:
        process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1
        )
    except Exception as e:
        log('ERROR', f"Failed to start target server: {e}")
        sys.exit(1)

    log('INFO', f"Target server started (PID: {process.pid})")

    # Process stdin -> target
    def stdin_to_target():
        while True:
            message = read_jsonrpc_message(sys.stdin)
            if message is None:
                break

            log('DEBUG', f"stdin -> proxy: {message.get('method', 'response')}")

            processed = process_request(message)

            if processed is None:
                continue

            # If it's a block response, send directly to stdout
            if processed != message and processed.get('result'):
                log('DEBUG', "Sending blocked response to stdout")
                write_jsonrpc_message(sys.stdout, processed)
            else:
                # Forward to target
                write_jsonrpc_message(process.stdin, processed)

        process.stdin.close()

    # Process target -> stdout
    def target_to_stdout():
        while True:
            message = read_jsonrpc_message(process.stdout)
            if message is None:
                break

            log('DEBUG', f"target -> proxy: {message.get('method', 'response')}")

            processed = process_response(message)
            write_jsonrpc_message(sys.stdout, processed)

    import threading

    # Start threads for bidirectional communication
    stdin_thread = threading.Thread(target=stdin_to_target, daemon=True)
    stdout_thread = threading.Thread(target=target_to_stdout, daemon=True)

    stdin_thread.start()
    stdout_thread.start()

    # Wait for process to exit
    process.wait()
    sys.exit(process.returncode)


if __name__ == '__main__':
    main()

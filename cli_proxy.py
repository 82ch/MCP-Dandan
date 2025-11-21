#!/usr/bin/env python3
"""
82ch STDIO Proxy - CLI Helper

Intercepts MCP STDIO communications between client and server for security verification.
"""

import sys
import os
import json
import subprocess
import requests
from typing import Optional, Dict, Any
from utils import safe_print

# Force UTF-8 encoding for stdin/stdout to handle Unicode properly
# This prevents encoding issues on Windows (cp949) and other systems
if sys.stdin.encoding != 'utf-8':
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


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
        safe_print(f"[{level}] {message}", file=sys.stderr)


def make_api_request(endpoint: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make HTTP request to the proxy server."""
    url = f"http://{CONFIG['proxy_host']}:{CONFIG['proxy_port']}{endpoint}"

    try:
        log('DEBUG', f"API request to {endpoint}")
        response = requests.post(
            url,
            json=data,
            headers={'Content-Type': 'application/json'}
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
        self.server_initialized = False
        self.server_tools_fetched = False
        self.pending_client_initialize_id: Optional[Any] = None
        self.server_initialize_result: Optional[Dict[str, Any]] = None
        self.server_tools: Optional[list] = None


state = MCPState()
server_process = None  # Will be set in main()


def process_request(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Process a JSON-RPC message from stdin before forwarding to target server.

    Returns:
        - Modified message to forward to target
        - Blocked response to send directly to stdout (if blocked)
        - None if message should be dropped
    """
    try:
        # Send all requests to verification endpoint for logging and security check
        method = message.get('method')
        if method:
            log('DEBUG', f"Processing request: {method}")

            # Track tools/list request
            if method == 'tools/list':
                log('DEBUG', f"Detected tools/list request: {message.get('id')}")
                state.pending_tools_list_id = message.get('id')

                # If we already have tools from pre-initialization, return them immediately
                if state.server_tools_fetched and state.server_tools is not None:
                    log('INFO', "Returning cached tools from pre-initialization")

                    # Verify request for logging
                    verification_data = {
                        'message': message,
                        'toolName': 'tools/list',
                        'serverInfo': {
                            'appName': CONFIG['app_name'],
                            'name': CONFIG['server_name'],
                            'version': state.server_version
                        }
                    }
                    try:
                        make_api_request('/verify/request', verification_data)
                    except Exception as e:
                        log('ERROR', f"Exception verifying tools/list request: {e}")

                    # Modify tools to add user_intent parameter (same as process_response)
                    modified_tools = []
                    for tool in state.server_tools:
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

                    # Create response message
                    response_msg = {
                        "jsonrpc": "2.0",
                        "id": message.get('id'),
                        "result": {
                            "tools": modified_tools
                        }
                    }

                    # Verify response for logging (skip engine analysis - already done in pre-init)
                    verification_data = {
                        'message': response_msg,
                        'toolName': 'tools/list',
                        'serverInfo': {
                            'appName': CONFIG['app_name'],
                            'name': CONFIG['server_name'],
                            'version': state.server_version
                        },
                        'skip_analysis': True  # 이미 pre-init에서 분석 완료
                    }
                    try:
                        make_api_request('/verify/response', verification_data)
                    except Exception as e:
                        log('ERROR', f"Exception verifying cached tools/list response: {e}")

                    # Return cached tools response
                    return response_msg

            # Prepare verification data for all methods
            verification_data = {
                'message': message,
                'toolName': message.get('params', {}).get('name', method),
                'serverInfo': {
                    'appName': CONFIG['app_name'],
                    'name': CONFIG['server_name'],
                    'version': state.server_version
                }
            }

            # Send to verification endpoint (logs all methods, only blocks dangerous ones)
            try:
                result = make_api_request('/verify/request', verification_data)
                if result:
                    log('DEBUG', f"Verified and logged request: {method}")
                    # Check if blocked
                    if result.get('blocked'):
                        reason = result.get('reason', 'Security policy violation')
                        log('INFO', f"Request blocked: {reason}")
                        return {
                            "jsonrpc": "2.0",
                            "id": message.get('id'),
                            "result": {
                                "content": [{
                                    "type": "text",
                                    "text": f"Request blocked: {reason}"
                                }]
                            }
                        }
                else:
                    log('ERROR', f"Failed to verify request: {method}")
            except Exception as e:
                log('ERROR', f"Exception verifying request {method}: {e}")

        # Handle tool calls specifically (for user_intent stripping and state tracking)
        if message.get('method') == 'tools/call':
            params = message.get('params', {})
            state.current_tool_name = params.get('name', 'unknown')
            state.current_tool_id = message.get('id')

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
        # Send all responses to verification endpoint for logging
        if message.get('id') or message.get('result') or message.get('error'):
            log('DEBUG', f"Processing response")

            verification_data = {
                'message': message,
                'toolName': state.current_tool_name or 'unknown',
                'serverInfo': {
                    'appName': CONFIG['app_name'],
                    'name': CONFIG['server_name'],
                    'version': state.server_version
                }
            }

            try:
                result = make_api_request('/verify/response', verification_data)
                if result:
                    log('DEBUG', f"Verified and logged response")
                    # Check if blocked
                    if result.get('blocked'):
                        reason = result.get('reason', 'Security policy violation')
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
                else:
                    log('ERROR', f"Failed to verify response")
            except Exception as e:
                log('ERROR', f"Exception verifying response: {e}")

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

                # Cache tools for future requests
                state.server_tools = tools
                state.server_tools_fetched = True
                log('INFO', f"Cached {len(tools)} tools for future requests")

                state.pending_tools_list_id = None

        # Clear tool call state after processing response
        if state.current_tool_name and message.get('id') == state.current_tool_id:
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
    global server_process

    if len(sys.argv) < 2:
        safe_print("Usage: python cli_proxy.py <command> [args...]", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    log('INFO', f"Starting STDIO proxy for: {command} {' '.join(args)}")
    log('INFO', f"App: {CONFIG['app_name']}, Server: {CONFIG['server_name']}")

    # Start target server process
    try:
        # Windows requires shell=True for .cmd files like npx
        import platform
        use_shell = platform.system() == 'Windows'

        process = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid UTF-8 bytes with � instead of surrogates
            bufsize=1,
            shell=use_shell
        )
        server_process = process  # Set global for pre-initialization
    except Exception as e:
        log('ERROR', f"Failed to start target server: {e}")
        sys.exit(1)

    log('INFO', f"Target server started (PID: {process.pid})")

    # Wait for first message (should be initialize)
    first_message = read_jsonrpc_message(sys.stdin)
    if first_message and first_message.get('method') == 'initialize':
        log('INFO', "Received client initialize, performing pre-initialization with server")

        # Step 1: Send initialize to server
        server_init_msg = {
            "jsonrpc": "2.0",
            "id": first_message.get('id'),
            "method": "initialize",
            "params": first_message.get('params', {})
        }

        # Log client initialize request (일반 MCP 통신, pre-init 아님)
        verification_data = {
            'message': first_message,
            'toolName': 'initialize',
            'serverInfo': {
                'appName': CONFIG['app_name'],
                'name': CONFIG['server_name'],
                'version': state.server_version
            }
            # stage 없음 - 일반 MCP 이벤트로 기록
        }
        try:
            make_api_request('/verify/request', verification_data)
        except Exception as e:
            log('ERROR', f"Failed to log client initialize request: {e}")

        # Log proxy->server initialize request (pre-init 단계, Proxy 이벤트)
        verification_data = {
            'message': server_init_msg,
            'toolName': 'initialize',
            'serverInfo': {
                'appName': CONFIG['app_name'],
                'name': CONFIG['server_name'],
                'version': state.server_version
            },
            'stage': 'pre_init'  # pre-init 단계 - Proxy 이벤트로 기록
        }
        try:
            make_api_request('/verify/request', verification_data)
        except Exception as e:
            log('ERROR', f"Failed to log proxy->server initialize request: {e}")

        # Send to server and wait
        write_jsonrpc_message(process.stdin, server_init_msg)
        server_init_response = read_jsonrpc_message(process.stdout)

        if not server_init_response:
            log('ERROR', "Failed to get initialize response from server")
            sys.exit(1)

        log('INFO', "Received initialize response from server")

        # Log server initialize response (pre-init 단계, Proxy 이벤트)
        verification_data = {
            'message': server_init_response,
            'toolName': 'initialize',
            'serverInfo': {
                'appName': CONFIG['app_name'],
                'name': CONFIG['server_name'],
                'version': state.server_version
            },
            'stage': 'pre_init'  # pre-init 단계 - Proxy 이벤트로 기록
        }
        try:
            make_api_request('/verify/response', verification_data)
        except Exception as e:
            log('ERROR', f"Failed to log server initialize response: {e}")

        # Save server version
        if server_init_response.get('result', {}).get('serverInfo', {}).get('version'):
            state.server_version = server_init_response['result']['serverInfo']['version']

        # Step 1.5: Send initialized notification to complete initialization
        log('INFO', "Sending initialized notification to server")
        initialized_msg = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        write_jsonrpc_message(process.stdin, initialized_msg)

        # Step 2: Send tools/list to server
        log('INFO', "Requesting tools/list from server")
        tools_list_msg = {
            "jsonrpc": "2.0",
            "id": "pre_tools_1",
            "method": "tools/list",
            "params": {}
        }

        # Log tools/list request
        verification_data = {
            'message': tools_list_msg,
            'toolName': 'tools/list',
            'serverInfo': {
                'appName': CONFIG['app_name'],
                'name': CONFIG['server_name'],
                'version': state.server_version
            },
            'stage': 'pre_init'  # 구분자 추가
        }
        try:
            make_api_request('/verify/request', verification_data)
        except Exception as e:
            log('ERROR', f"Failed to log tools/list request: {e}")

        # Send to server and wait
        write_jsonrpc_message(process.stdin, tools_list_msg)
        tools_list_response = read_jsonrpc_message(process.stdout)

        if not tools_list_response:
            log('ERROR', "Failed to get tools/list response from server")
            sys.exit(1)

        log('INFO', "Received tools/list response from server")

        # Log and WAIT for tools/list response verification (includes engine analysis)
        if tools_list_response.get('result', {}).get('tools'):
            verification_data = {
                'message': tools_list_response,
                'toolName': 'tools/list',
                'serverInfo': {
                    'appName': CONFIG['app_name'],
                    'name': CONFIG['server_name'],
                    'version': state.server_version
                },
                'stage': 'pre_init'  # 구분자 추가
            }
            try:
                log('INFO', "Waiting for tools/list engine analysis to complete...")
                make_api_request('/verify/response', verification_data)
                log('INFO', "Engine analysis completed")
            except Exception as e:
                log('ERROR', f"Failed to verify tools/list response: {e}")

            # Cache tools
            state.server_tools = tools_list_response['result']['tools']
            state.server_tools_fetched = True

        state.server_initialized = True

        # Now send initialize response to client
        log('INFO', "Sending initialize response to client")

        # Log client initialize response (일반 MCP 통신, pre-init 아님)
        verification_data = {
            'message': server_init_response,
            'toolName': 'initialize',
            'serverInfo': {
                'appName': CONFIG['app_name'],
                'name': CONFIG['server_name'],
                'version': state.server_version
            }
            # stage 없음 - 일반 MCP 이벤트로 기록
        }
        try:
            make_api_request('/verify/response', verification_data)
        except Exception as e:
            log('ERROR', f"Failed to log client initialize response: {e}")

        write_jsonrpc_message(sys.stdout, server_init_response)

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

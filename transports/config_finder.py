""" config_finder """

"""
Claude Desktop & Cursor MCP Config Finder and Modifier

This module finds the Claude Desktop and Cursor configuration files and modifies
Local MCP server settings to use a proxy.

Usage:
    from config_finder import ClaudeConfigFinder

    finder = ClaudeConfigFinder()
    finder.configure_claude_proxy()
    finder.configure_cursor_proxy()

    # or configure all
    finder.configure_all_proxies()
"""

import json
import os
import sys
import platform
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Windows-only import
if platform.system() == 'Windows':
    import winreg
else:
    winreg = None

# Force UTF-8 encoding for stdin/stdout to handle Unicode properly
# This prevents encoding issues on Windows (cp949) and other systems
if sys.stdin.encoding != 'utf-8':
    sys.stdin.reconfigure(encoding='utf-8', errors='replace')
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add parent directory to path to import utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    # format='[%(levelname)s] %(message)s'
    format = '%(message)s'
)
logger = logging.getLogger(__name__)

class ClaudeConfigFinder:

    def __init__(self, proxy_path: Optional[str] = None):
        self.proxy_path = proxy_path or self._build_proxy_path()
        # Use python3 on macOS/Linux, python on Windows
        self.python_cmd = 'python' if platform.system() == 'Windows' else 'python3'

    def configure_all_proxies(self) -> bool:
        """Configure both Claude and Cursor proxies"""
        claude_success = self.configure_claude_proxy()
        cursor_success = self.configure_cursor_proxy()
        return claude_success or cursor_success

    def configure_claude_proxy(self) -> bool:
        """Configure Claude Desktop MCP proxy"""
        config_path = self.find_claude_config()

        if not config_path:
            logger.error("[Failed] Claude Config.json Not Found")
            return False

        logger.info(f"[Found] Claude Config at: {config_path}")

        # Read and display current config
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"Current config:\n{content}")
        except Exception as e:
            logger.error(f"Failed to read Claude config: {e}")
            return False

        # Modify config
        return self.modify_mcp_servers_config(config_path, app_name='Claude')

    def configure_cursor_proxy(self) -> bool:
        """Configure Cursor MCP proxy"""
        config_path = self.find_cursor_config()

        if not config_path:
            logger.warning("[Info] Cursor mcp.json Not Found (Skip)")
            return False

        logger.info(f"[Found] Cursor Config at: {config_path}")

        # Read and display current config
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"Current config:\n{content}")
        except Exception as e:
            logger.error(f"Failed to read Cursor config: {e}")
            return False

        # Modify config
        return self.modify_cursor_mcp_config(config_path)

    def find_claude_config(self) -> Optional[str]:
        """Find Claude Desktop config file"""
        # [1] Default path search (platform-specific)
        system = platform.system()
        base_paths = []

        if system == 'Windows':
            base_paths = [
                os.path.join(os.environ.get('APPDATA', ''), 'Claude', 'claude_desktop_config.json'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude', 'claude_desktop_config.json'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Claude', 'claude_desktop_config.json'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Claude', 'claude_desktop_config.json'),
            ]
        elif system == 'Darwin':  # macOS
            base_paths = [
                os.path.expanduser('~/Library/Application Support/Claude/claude_desktop_config.json'),
            ]
        else:  # Linux
            base_paths = [
                os.path.expanduser('~/.config/Claude/claude_desktop_config.json'),
                os.path.expanduser('~/.claude/claude_desktop_config.json'),
            ]

        for path in base_paths:
            if path and os.path.isfile(path):
                logger.info(f"[Found] Config in default path: {path}")
                return path

        # [2] Registry search (Windows only)
        if system == 'Windows':
            reg_path = self._find_from_registry()
            if reg_path:
                config_candidate = os.path.join(reg_path, 'claude_desktop_config.json')
                if os.path.isfile(config_candidate):
                    logger.info(f"[Found] Config via registry: {config_candidate}")
                    return config_candidate

        # [3] User directory recursive search
        user_dir = os.path.expanduser('~')
        try:
            # Platform-specific directories to skip
            skip_dirs = {'node_modules', '.git', 'Downloads'}
            if system == 'Windows':
                skip_dirs.update({'AppData\\Local\\Temp', 'AppData\\Local\\Microsoft'})
            elif system == 'Darwin':
                skip_dirs.update({'Library/Caches', 'Library/Logs'})
            else:
                skip_dirs.update({'.cache', '.local/share/Trash'})

            for root, dirs, files in os.walk(user_dir):
                # Skip some common large directories to speed up search
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                if 'claude_desktop_config.json' in files:
                    found_path = os.path.join(root, 'claude_desktop_config.json')
                    logger.info(f"[Found] Config via recursive search: {found_path}")
                    return found_path
        except (PermissionError, OSError) as e:
            logger.debug(f"Search error (expected): {e}")

        return None

    def find_cursor_config(self) -> Optional[str]:
        """Find Cursor MCP config file"""
        system = platform.system()

        # [1] Current working directory
        cwd_path = os.path.join(os.getcwd(), '.cursor', 'mcp.json')
        if os.path.isfile(cwd_path):
            logger.info(f"[Found] Cursor config in CWD: {cwd_path}")
            return cwd_path

        # [2] User home directory
        home_cursor_path = os.path.join(os.path.expanduser('~'), '.cursor', 'mcp.json')
        if os.path.isfile(home_cursor_path):
            logger.info(f"[Found] Cursor config in home: {home_cursor_path}")
            return home_cursor_path

        # [3] Common Cursor locations (platform-specific)
        base_paths = []
        if system == 'Windows':
            base_paths = [
                os.path.join(os.environ.get('APPDATA', ''), 'Cursor', '.cursor', 'mcp.json'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Cursor', '.cursor', 'mcp.json'),
            ]
        elif system == 'Darwin':  # macOS
            base_paths = [
                os.path.expanduser('~/Library/Application Support/Cursor/mcp.json'),
            ]
        else:  # Linux
            base_paths = [
                os.path.expanduser('~/.config/Cursor/mcp.json'),
            ]

        for path in base_paths:
            if path and os.path.isfile(path):
                logger.info(f"[Found] Cursor config in default path: {path}")
                return path

        # [4] Recursive search from home directory
        user_dir = os.path.expanduser('~')
        try:
            # Platform-specific directories to skip
            skip_dirs = {'node_modules', '.git', 'Downloads'}
            if system == 'Windows':
                skip_dirs.update({'AppData\\Local\\Temp', 'AppData\\Local\\Microsoft'})
            elif system == 'Darwin':
                skip_dirs.update({'Library/Caches', 'Library/Logs'})
            else:
                skip_dirs.update({'.cache', '.local/share/Trash'})

            for root, dirs, files in os.walk(user_dir):
                # Skip large directories
                dirs[:] = [d for d in dirs if d not in skip_dirs]

                if '.cursor' in dirs:
                    config_candidate = os.path.join(root, '.cursor', 'mcp.json')
                    if os.path.isfile(config_candidate):
                        logger.info(f"[Found] Cursor config via recursive search: {config_candidate}")
                        return config_candidate
        except (PermissionError, OSError) as e:
            logger.debug(f"Search error (expected): {e}")

        return None

    def _find_from_registry(self) -> Optional[str]:
        """Find Claude installation path from Windows registry (Windows only)"""
        if winreg is None:
            return None

        registry_roots = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hkey, subkey_path in registry_roots:
            try:
                with winreg.OpenKey(hkey, subkey_path) as base_key:
                    # Enumerate all subkeys
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(base_key, i)
                            i += 1

                            with winreg.OpenKey(base_key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if "claude" in display_name.lower():
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                        logger.info(f"[Registry] Found Claude installation: {install_location}")
                                        return install_location
                                except (WindowsError, FileNotFoundError):
                                    continue
                        except OSError:
                            break
            except (WindowsError, FileNotFoundError) as e:
                logger.debug(f"Registry access error (expected): {e}")
                continue

        return None

    def _build_proxy_path(self) -> str:
        # Get current script directory
        current_dir = Path(__file__).resolve().parent

        # Navigate to project root (cd ..)
        project_root = current_dir.parent

        # Build proxy path to cli_proxy.py
        proxy_path = project_root / "cli_proxy.py"

        if not proxy_path.exists():
            logger.warning(f"[Warning] cli_proxy.py not found at {proxy_path}")
        else:
            logger.info(f"[INFO] cli_proxy.py Path Detected: {proxy_path}")

        return str(proxy_path)

    def _modified_env(self, server_name: str, existing_env: Optional[Dict[str, str]] = None, app_name: str = 'Claude') -> Dict[str, str]:
        """
        Create or modify environment variables for MCP server.

        Args:
            server_name: Name of the MCP server
            existing_env: Existing environment variables (if any)
            app_name: Application name (Claude or Cursor)

        Returns:
            Modified environment variables dictionary
        """
        # Start with existing env or empty dict
        env = existing_env.copy() if existing_env else {}

        # Add/update MCP Observer variables
        env['MCP_OBSERVER_APP_NAME'] = app_name
        env['MCP_OBSERVER_SERVER_NAME'] = server_name
        env['MCP_DEBUG'] = 'true'

        return env

    def _save_remote_servers(self, config_path: str, remote_servers: Dict[str, Any]) -> Optional[str]:
        """Save remote servers to a separate file for Claude Desktop."""
        if not remote_servers:
            return None

        # Create remote config file path
        config_dir = os.path.dirname(config_path)
        remote_path = os.path.join(config_dir, 'claude_desktop_remote.json')

        try:
            remote_config = {'mcpServers': remote_servers}
            with open(remote_path, 'w', encoding='utf-8') as f:
                json.dump(remote_config, f, indent=2, ensure_ascii=False)
            logger.info(f"[Remote] Saved {len(remote_servers)} remote server(s) to: {remote_path}")
            return remote_path
        except Exception as e:
            logger.error(f"[Error] Failed to save remote servers: {e}")
            return None

    def _delete_remote_servers_file(self, config_path: str) -> bool:
        """Delete the remote servers file."""
        config_dir = os.path.dirname(config_path)
        remote_path = os.path.join(config_dir, 'claude_desktop_remote.json')

        if os.path.exists(remote_path):
            try:
                os.remove(remote_path)
                logger.info(f"[Remote] Deleted remote servers file: {remote_path}")
                return True
            except Exception as e:
                logger.error(f"[Error] Failed to delete remote servers file: {e}")
                return False
        return True

    def _load_remote_servers_from_backup(self, config_path: str) -> Dict[str, Any]:
        """Load remote servers from claude_desktop_remote.json backup."""
        config_dir = os.path.dirname(config_path)
        remote_path = os.path.join(config_dir, 'claude_desktop_remote.json')

        if not os.path.exists(remote_path):
            return {}

        try:
            with open(remote_path, 'r', encoding='utf-8') as f:
                remote_config = json.load(f)
            servers = remote_config.get('mcpServers', {})
            if servers:
                logger.info(f"[Remote] Loaded {len(servers)} remote server(s) from backup: {remote_path}")
            return servers
        except Exception as e:
            logger.error(f"[Error] Failed to load remote servers from backup: {e}")
            return {}

    def modify_mcp_servers_config(self, config_path: str, app_name: str = 'Claude') -> bool:
        """Modify Claude Desktop MCP servers config"""
        # First, restore from .backup to get clean state (for re-runs)
        backup_path = f"{config_path}.backup"
        if os.path.exists(backup_path):
            logger.info(f"[Restore] Restoring from backup before applying proxy...")
            self._restore_config(backup_path, config_path)
        else:
            # First run - create backup
            self._backup_config(config_path)

        try:
            # Read config (now restored to original state)
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'mcpServers' not in config:
                logger.warning("[Warning] No 'mcpServers' section found in config")
                return False

            mcp_servers = config['mcpServers']
            if not isinstance(mcp_servers, dict):
                logger.warning("[Warning] 'mcpServers' is not an object")
                return False

            modified_count = 0

            # For Claude: Extract and save remote servers separately
            remote_servers = {}

            # Load existing remote servers from claude_desktop_remote.json (for re-runs after disable)
            backup_remote_servers = self._load_remote_servers_from_backup(config_path)

            # Add remote servers from backup that are not in current config
            for server_name, server_config in backup_remote_servers.items():
                if server_name not in mcp_servers:
                    mcp_servers[server_name] = server_config.copy()
                    logger.info(f"[Remote] Restored '{server_name}' from remote backup")

            # Process each MCP server
            for server_name, server_config in list(mcp_servers.items()):
                if not isinstance(server_config, dict):
                    continue

                # Handle remote servers (with url) - similar to Cursor handling
                if 'url' in server_config:
                    current_url = server_config['url']

                    # Skip localhost/127.0.0.1 URLs (these were old Observer endpoints)
                    if 'localhost' in current_url.lower() or '127.0.0.1' in current_url:
                        logger.info(f"[Skip] '{server_name}' - localhost URL detected (old Observer endpoint), removing...")
                        # Remove this server entirely as it's deprecated
                        del mcp_servers[server_name]
                        continue

                    # Skip if already using cli_proxy.py for remote
                    if 'command' in server_config and server_config['command'] == self.python_cmd:
                        if 'args' in server_config and isinstance(server_config['args'], list):
                            if len(server_config['args']) > 0 and 'cli_proxy.py' in str(server_config['args'][0]):
                                logger.info(f"[Skip] '{server_name}' already uses cli_proxy.py for remote connection")
                                continue

                    # Save original remote server config to separate file
                    remote_servers[server_name] = server_config.copy()

                    # Convert url-based remote server to cli_remote_proxy.py with MCP_TARGET_URL
                    del server_config['url']

                    # Build new config for cli_remote_proxy.py
                    server_config['command'] = self.python_cmd
                    # Use cli_remote_proxy.py for remote servers
                    remote_proxy_path = os.path.join(os.path.dirname(self.proxy_path), 'cli_remote_proxy.py')
                    server_config['args'] = [remote_proxy_path]

                    # Add environment variables for remote connection
                    existing_env = server_config.get('env', {})
                    new_env = self._modified_env(server_name, existing_env, app_name)
                    new_env['MCP_TARGET_URL'] = current_url

                    # Transfer all headers to environment variables
                    headers = remote_servers[server_name].get('headers', {})
                    if headers:
                        # Store headers as JSON string for cli_remote_proxy.py to parse
                        new_env['MCP_TARGET_HEADERS'] = json.dumps(headers)

                    server_config['env'] = new_env

                    # Remove headers field if exists
                    if 'headers' in server_config:
                        del server_config['headers']

                    logger.info(f"[Modified] '{server_name}' - Converted remote URL to cli_remote_proxy.py with MCP_TARGET_URL={current_url}")
                    modified_count += 1
                    continue

                if 'command' not in server_config:
                    continue

                current_command = server_config['command']
                if not current_command:
                    continue

                # Skip if already using cli_proxy
                if 'args' in server_config and isinstance(server_config['args'], list):
                    if len(server_config['args']) > 0 and 'cli_proxy.py' in str(server_config['args'][0]):
                        logger.info(f"[Skip] '{server_name}' already uses cli_proxy.py")
                        continue

                # Get existing args or create new array
                if 'args' in server_config and isinstance(server_config['args'], list):
                    existing_args = server_config['args'].copy()
                else:
                    existing_args = []

                # Build new args: [cli_proxy.py, original_command, ...original_args]
                new_args = [self.proxy_path, current_command] + existing_args
                server_config['args'] = new_args

                # Set command to python/python3 based on OS
                server_config['command'] = self.python_cmd

                # Add/update environment variables
                existing_env = server_config.get('env', {})
                server_config['env'] = self._modified_env(server_name, existing_env, app_name)

                logger.info(f"[Modified] '{server_name}' - command: {self.python_cmd}, args: [cli_proxy.py, {current_command}, ...], env: MCP_OBSERVER_*")
                modified_count += 1

            # Save remote servers to separate file (Claude only)
            if remote_servers:
                self._save_remote_servers(config_path, remote_servers)

            # Save modified config
            if modified_count > 0:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                logger.info(f"\n[Success] Modified {modified_count} MCP server(s) in config")
                logger.info(f"[Success] Config saved to: {config_path}")
                return True
            else:
                logger.info("[INFO] No MCP servers needed modification")
                return True

        except json.JSONDecodeError as e:
            logger.error(f"[Error] Failed to parse JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"[Error] Failed to modify config: {e}")
            return False

    def modify_cursor_mcp_config(self, config_path: str) -> bool:
        """Modify Cursor MCP config"""
        # backup original config
        self._backup_config(config_path)

        try:
            # Read config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'mcpServers' not in config:
                logger.warning("[Warning] No 'mcpServers' section found in Cursor config")
                return False

            mcp_servers = config['mcpServers']
            if not isinstance(mcp_servers, dict):
                logger.warning("[Warning] 'mcpServers' is not an object")
                return False

            modified_count = 0

            # Process each MCP server
            for server_name, server_config in mcp_servers.items():
                if not isinstance(server_config, dict):
                    continue

                # Cursor config structure: command, args, env (similar to Claude)
                # But also supports: url, headers (for remote MCP servers)

                # Handle remote servers (with url)
                if 'url' in server_config:
                    current_url = server_config['url']

                    # Skip localhost/127.0.0.1 URLs (these were old Observer endpoints)
                    if 'localhost' in current_url.lower() or '127.0.0.1' in current_url:
                        logger.info(f"[Skip] '{server_name}' - localhost URL detected (old Observer endpoint), removing...")
                        # Remove this server entirely as it's deprecated
                        continue

                    # Skip if already using cli_proxy.py for remote
                    if 'command' in server_config and server_config['command'] == self.python_cmd:
                        if 'args' in server_config and isinstance(server_config['args'], list):
                            if len(server_config['args']) > 0 and 'cli_proxy.py' in str(server_config['args'][0]):
                                logger.info(f"[Skip] '{server_name}' already uses cli_proxy.py for remote connection")
                                continue

                    # Convert url-based remote server to cli_proxy.py with MCP_TARGET_URL
                    # Remove url field and create command/args/env structure
                    del server_config['url']

                    # Build new config for cli_proxy.py
                    server_config['command'] = self.python_cmd
                    server_config['args'] = [self.proxy_path]

                    # Add environment variables for remote connection
                    existing_env = server_config.get('env', {})
                    existing_headers = server_config.get('headers', {})

                    # Build env with MCP_TARGET_URL and other required variables
                    new_env = self._modified_env(server_name, existing_env, 'Cursor')
                    new_env['MCP_TARGET_URL'] = current_url

                    # If there were custom headers, add them to env
                    if existing_headers:
                        new_env['MCP_TARGET_HEADERS'] = json.dumps(existing_headers)
                        logger.debug(f"[Info] Original headers for '{server_name}': {existing_headers}")

                    server_config['env'] = new_env

                    # Remove headers field since we're now using cli_proxy.py
                    if 'headers' in server_config:
                        del server_config['headers']

                    logger.info(f"[Modified] '{server_name}' - Converted remote URL to cli_proxy.py with MCP_TARGET_URL={current_url}")
                    modified_count += 1
                    continue

                if 'command' not in server_config:
                    continue

                current_command = server_config['command']
                if not current_command:
                    continue

                # Skip if already using cli_proxy
                if 'args' in server_config and isinstance(server_config['args'], list):
                    if len(server_config['args']) > 0 and 'cli_proxy.py' in str(server_config['args'][0]):
                        logger.info(f"[Skip] '{server_name}' already uses cli_proxy.py")
                        continue

                # Get existing args or create new array
                if 'args' in server_config and isinstance(server_config['args'], list):
                    existing_args = server_config['args'].copy()
                else:
                    existing_args = []

                # Build new args: [cli_proxy.py, original_command, ...original_args]
                new_args = [self.proxy_path, current_command] + existing_args
                server_config['args'] = new_args

                # Set command to python/python3 based on OS
                server_config['command'] = self.python_cmd

                # Add/update environment variables
                existing_env = server_config.get('env', {})
                server_config['env'] = self._modified_env(server_name, existing_env, 'Cursor')

                logger.info(f"[Modified] '{server_name}' - command: {self.python_cmd}, args: [cli_proxy.py, {current_command}, ...], env: MCP_OBSERVER_*")
                modified_count += 1

            # Save modified config
            if modified_count > 0:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                logger.info(f"\n[Success] Modified {modified_count} Cursor MCP server(s)")
                logger.info(f"[Success] Config saved to: {config_path}")
                return True
            else:
                logger.info("[INFO] No Cursor MCP servers needed modification")
                return True

        except json.JSONDecodeError as e:
            logger.error(f"[Error] Failed to parse Cursor JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"[Error] Failed to modify Cursor config: {e}")
            return False

    def _backup_config(self, config_path: str) -> Optional[str]:
        try:
            backup_path = f"{config_path}.backup"
            # Only create backup if it doesn't already exist (preserve original)
            if os.path.exists(backup_path):
                logger.info(f"[Backup] Backup already exists, skipping: {backup_path}")
                return backup_path
            with open(config_path, 'r', encoding='utf-8') as original_file:
                content = original_file.read()
            with open(backup_path, 'w', encoding='utf-8') as backup_file:
                backup_file.write(content)
            logger.info(f"[Backup] Config backed up to: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"[Error] Failed to backup config: {e}")
            return None
    
    def _restore_config(self, backup_path: str, config_path: str) -> bool:
        try: # none delete backup config
            with open(backup_path, 'r', encoding='utf-8') as backup_file:
                content = backup_file.read()
            with open(config_path, 'w', encoding='utf-8') as original_file:
                original_file.write(content)
            logger.info(f"[Restore] Config restored from backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"[Error] Failed to restore config: {e}")
            return False

    def disable_proxy(self, config_path: str, app_name: str = 'Claude') -> bool:
        """
        Disable 82ch proxy:
        - For Claude: Remove cli_proxy.py from local servers, delete remote servers
        - For Cursor: Restore from backup file
        """
        # For Cursor, simply restore from backup
        if app_name == 'Cursor':
            backup_path = f"{config_path}.backup"
            if os.path.exists(backup_path):
                return self._restore_config(backup_path, config_path)
            else:
                logger.warning(f"[Warning] Cursor backup file not found: {backup_path}")
                return False

        # For Claude, process config to remove proxy
        # Note: Keep claude_desktop_remote.json for next startup
        try:
            # Read config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            if 'mcpServers' not in config:
                logger.warning("[Warning] No 'mcpServers' section found in config")
                return False

            mcp_servers = config['mcpServers']
            if not isinstance(mcp_servers, dict):
                logger.warning("[Warning] 'mcpServers' is not an object")
                return False

            modified_count = 0
            removed_servers = []

            # Process each MCP server
            for server_name in list(mcp_servers.keys()):  # Use list() to allow deletion during iteration
                server_config = mcp_servers[server_name]

                if not isinstance(server_config, dict):
                    continue

                # Check if this is a remote server (has MCP_TARGET_URL in env)
                env = server_config.get('env', {})
                is_remote = 'MCP_TARGET_URL' in env

                if is_remote:
                    # Delete remote servers for Claude (Claude Desktop doesn't support URL-based servers natively)
                    del mcp_servers[server_name]
                    logger.info(f"[Removed] '{server_name}' - Remote server deleted (Claude Desktop doesn't support URL-based servers)")
                    removed_servers.append(server_name)
                    modified_count += 1
                    continue

                # Check if this is using cli_proxy.py
                if 'args' not in server_config or not isinstance(server_config['args'], list):
                    continue

                args = server_config['args']
                if len(args) == 0 or 'cli_proxy.py' not in str(args[0]):
                    continue

                # This is a local server using cli_proxy.py - restore it
                # args format: [cli_proxy.py, original_command, ...original_args]
                if len(args) < 2:
                    logger.warning(f"[Warning] '{server_name}' has invalid args format, skipping")
                    continue

                # Extract original command and args
                original_command = args[1]  # Second arg is original command
                original_args = args[2:]     # Rest are original args

                # Restore original configuration
                server_config['command'] = original_command
                if original_args:
                    server_config['args'] = original_args
                else:
                    # Remove args if there were none originally
                    if 'args' in server_config:
                        del server_config['args']

                # Remove MCP Observer environment variables
                if 'env' in server_config:
                    env = server_config['env']
                    # Remove only MCP_OBSERVER_* and MCP_DEBUG variables
                    keys_to_remove = [k for k in env.keys() if k.startswith('MCP_OBSERVER_') or k == 'MCP_DEBUG' or k == 'MCP_PROXY_PORT' or k == 'MCP_PROXY_HOST']
                    for key in keys_to_remove:
                        del env[key]

                    # If env is now empty, remove it entirely
                    if not env:
                        del server_config['env']

                logger.info(f"[Restored] '{server_name}' - Removed cli_proxy.py, restored to: {original_command}")
                modified_count += 1

            # Save modified config
            if modified_count > 0:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)

                logger.info(f"\n[Success] Disabled proxy for {modified_count} server(s)")
                if removed_servers:
                    logger.info(f"[Success] Removed {len(removed_servers)} remote server(s): {', '.join(removed_servers)}")
                logger.info(f"[Success] Config saved to: {config_path}")
                return True
            else:
                logger.info("[INFO] No servers needed proxy disabling")
                return True

        except json.JSONDecodeError as e:
            logger.error(f"[Error] Failed to parse JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"[Error] Failed to disable proxy: {e}")
            return False
    
def main():
    """Only Ganzi"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Claude Desktop & Cursor MCP Config Finder and Modifier'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore config from backup file'
    )
    parser.add_argument(
        '--disable',
        action='store_true',
        help='Disable 82ch proxy (remove cli_proxy.py from local servers, delete remote servers)'
    )
    parser.add_argument(
        '--app',
        choices=['claude', 'cursor', 'all'],
        default='all',
        help='Target application (default: all)'
    )
    args = parser.parse_args()

    safe_print("=" * 70)
    safe_print(r"      ____             __ _         _____ _           _           ")
    safe_print(r"     / ___|___  _ __  / _(_) __ _  |  ___(_)_ __   __| | ___ _ __ ")
    safe_print(r"    | |   / _ \| '_ \| |_| |/ _` | | |_  | | '_ \ / _` |/ _ \ '__|")
    safe_print(r"    | |__| (_) | | | |  _| | (_| | |  _| | | | | | (_| |  __/ |   ")
    safe_print(r"     \____\___/|_| |_|_| |_|\__, | |_|   |_|_| |_|\__,_|\___|_|   ")
    safe_print(r"                            |___/                                 ")
    safe_print("\n    [*] Calude Config Finder")
    safe_print("=" * 70)
    safe_print()

    finder = ClaudeConfigFinder()

    if args.restore:
        # Restore mode
        success = True

        if args.app in ['claude', 'all']:
            config_path = finder.find_claude_config()
            if config_path:
                backup_path = f"{config_path}.backup"
                if os.path.exists(backup_path):
                    logger.info(f"[Restore] Found Claude config at: {config_path}")
                    logger.info(f"[Restore] Found backup at: {backup_path}")
                    if not finder._restore_config(backup_path, config_path):
                        success = False
                else:
                    logger.warning(f"[Warning] Claude backup file not found: {backup_path}")
            else:
                logger.warning("[Warning] Claude config not found")

        if args.app in ['cursor', 'all']:
            cursor_path = finder.find_cursor_config()
            if cursor_path:
                backup_path = f"{cursor_path}.backup"
                if os.path.exists(backup_path):
                    logger.info(f"[Restore] Found Cursor config at: {cursor_path}")
                    logger.info(f"[Restore] Found backup at: {backup_path}")
                    if not finder._restore_config(backup_path, cursor_path):
                        success = False
                else:
                    logger.warning(f"[Warning] Cursor backup file not found: {backup_path}")
            else:
                logger.warning("[Warning] Cursor config not found")

        if success:
            safe_print("\n[Done] Configuration restored successfully!")
        else:
            safe_print("\n[Failed] Restore failed.")
    elif args.disable:
        # Disable mode
        success = True

        if args.app in ['claude', 'all']:
            config_path = finder.find_claude_config()
            if config_path:
                logger.info(f"[Disable] Found Claude config at: {config_path}")
                if not finder.disable_proxy(config_path, app_name='Claude'):
                    success = False
            else:
                logger.warning("[Warning] Claude config not found")

        if args.app in ['cursor', 'all']:
            cursor_path = finder.find_cursor_config()
            if cursor_path:
                logger.info(f"[Disable] Found Cursor config at: {cursor_path}")
                if not finder.disable_proxy(cursor_path, app_name='Cursor'):
                    success = False
            else:
                logger.warning("[Warning] Cursor config not found")

        if success:
            safe_print("\n[Done] Proxy disabled successfully!")
            safe_print("[Info] Local servers restored to original state")
            safe_print("[Info] Remote servers removed (not supported without 82ch)")
        else:
            safe_print("\n[Failed] Disable failed.")
    else:
        # Normal configuration mode (enable proxy)
        success = False

        if args.app in ['claude', 'all']:
            if finder.configure_claude_proxy():
                success = True

        if args.app in ['cursor', 'all']:
            if finder.configure_cursor_proxy():
                success = True

        if success:
            safe_print("\n[Done] Configuration completed successfully!")
        else:
            safe_print("\n[Failed] Configuration failed.")

    return 0 if success else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

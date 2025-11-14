"""
Claude Desktop Config Finder and Modifier

This module finds the Claude Desktop configuration file and modifies
Local MCP server settings to use a proxy.

Usage:
    from config_finder import ClaudeConfigFinder
from utils import safe_print

    finder = ClaudeConfigFinder()
    finder.configure_claude_proxy()
    
    # or Just Insert that 
     ClaudeConfigFinder.ConfigureClaudeProxy()
"""

import json
import os
import winreg
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
import logging

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

    def configure_claude_proxy(self) -> bool:
        config_path = self.find_claude_config()

        if not config_path:
            logger.error("[Failed] Config.json Not Found")
            return False

        logger.info(f"[Found] Config at: {config_path}")

        # Read and display current config
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"Current config:\n{content}")
        except Exception as e:
            logger.error(f"Failed to read config: {e}")
            return False

        # Modify config
        return self.modify_mcp_servers_config(config_path)

    def find_claude_config(self) -> Optional[str]:

        # [1] Default path search (Claude Targeting)
        base_paths = [
            os.path.join(os.environ.get('APPDATA', ''), 'Claude', 'claude_desktop_config.json'),
            os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Claude', 'claude_desktop_config.json'),
            os.path.join(os.environ.get('PROGRAMFILES', ''), 'Claude', 'claude_desktop_config.json'),
            os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Claude', 'claude_desktop_config.json'),
        ]

        for path in base_paths:
            if path and os.path.isfile(path):
                logger.info(f"[Found] Config in default path: {path}")
                return path

        # [2] Registry search
        reg_path = self._find_from_registry()
        if reg_path:
            config_candidate = os.path.join(reg_path, 'claude_desktop_config.json')
            if os.path.isfile(config_candidate):
                logger.info(f"[Found] Config via registry: {config_candidate}")
                return config_candidate

        # [3] User directory recursive search
        user_dir = os.path.expanduser('~')
        try:
            for root, dirs, files in os.walk(user_dir):
                # Skip some common large directories to speed up search
                dirs[:] = [d for d in dirs if d not in {
                    'node_modules', '.git', 'AppData\\Local\\Temp',
                    'AppData\\Local\\Microsoft', 'Downloads'
                }]

                if 'claude_desktop_config.json' in files:
                    found_path = os.path.join(root, 'claude_desktop_config.json')
                    logger.info(f"[Found] Config via recursive search: {found_path}")
                    return found_path
        except (PermissionError, OSError) as e:
            logger.debug(f"Search error (expected): {e}")

        return None

    def _find_from_registry(self) -> Optional[str]:

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

    def _modified_env(self, server_name: str, existing_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Create or modify environment variables for MCP server.

        Args:
            server_name: Name of the MCP server
            existing_env: Existing environment variables (if any)

        Returns:
            Modified environment variables dictionary
        """
        # Start with existing env or empty dict
        env = existing_env.copy() if existing_env else {}

        # Add/update MCP Observer variables
        env['MCP_OBSERVER_APP_NAME'] = 'Claude'
        env['MCP_OBSERVER_SERVER_NAME'] = server_name
        env['MCP_DEBUG'] = 'true'

        return env

    def modify_mcp_servers_config(self, config_path: str) -> bool:
        # backup orginal config
        self._backup_config(config_path)
        
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

            # Process each MCP server
            for server_name, server_config in mcp_servers.items():
                if not isinstance(server_config, dict):
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

                # Set command to "python"
                server_config['command'] = 'python'

                # Add/update environment variables
                existing_env = server_config.get('env', {})
                server_config['env'] = self._modified_env(server_name, existing_env)

                logger.info(f"[Modified] '{server_name}' - command: python, args: [cli_proxy.py, {current_command}, ...], env: MCP_OBSERVER_*")
                modified_count += 1

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

    def _backup_config(self, config_path: str) -> Optional[str]:
        try:
            backup_path = f"{config_path}.backup"
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
    
def main():
    """Only Ganzi"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Claude Desktop Config Finder and Modifier'
    )
    parser.add_argument(
        '--restore',
        action='store_true',
        help='Restore config from backup file'
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
        config_path = finder.find_claude_config()
        if not config_path:
            logger.error("[Failed] Config.json Not Found")
            return 1

        backup_path = f"{config_path}.backup"
        if not os.path.exists(backup_path):
            logger.error(f"[Failed] Backup file not found: {backup_path}")
            return 1

        logger.info(f"[Restore] Found config at: {config_path}")
        logger.info(f"[Restore] Found backup at: {backup_path}")

        success = finder._restore_config(backup_path, config_path)

        if success:
            safe_print("\n[Done] Configuration restored successfully!")
        else:
            safe_print("\n[Failed] Restore failed.")
    else:
        # Normal configuration mode
        success = finder.configure_claude_proxy()

        if success:
            safe_print("\n[Done] Configuration completed successfully!")
        else:
            safe_print("\n[Failed] Configuration failed.")

    return 0 if success else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

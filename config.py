"""
Unified configuration management for 82ch.

Combines Observer and Engine configurations.
"""

import os
import configparser
from typing import Optional
from utils import safe_print


class Config:
    """Unified configuration for Observer + Engine."""

    def __init__(self, config_file: str = 'config.conf'):
        # Observer settings (from environment variables)
        self.server_port = int(os.getenv('MCP_PROXY_PORT', '28173'))
        self.server_host = os.getenv('MCP_PROXY_HOST', '127.0.0.1')
        self.debug = os.getenv('MCP_DEBUG', 'false').lower() == 'true'
        self.scan_mode = os.getenv('MCP_SCAN_MODE', 'REQUEST_RESPONSE')

        # Timeout settings
        self.sse_timeout = 300  # 5 minutes
        self.tool_call_timeout = 600  # 10 minutes
        self.verification_timeout = 35  # 35 seconds

        # Engine settings (from config file)
        self.config = configparser.ConfigParser()
        if os.path.exists(config_file):
            self.config.read(config_file, encoding='utf-8')
        else:
            safe_print(f'[Config] Warning: {config_file} not found, using defaults')

    # ========== Engine Settings ==========

    def get_sensitive_file_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'sensitive_file_enabled', fallback=True)

    def get_tools_poisoning_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'tools_poisoning_enabled', fallback=True)

    def get_command_injection_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'command_injection_enabled', fallback=True)

    def get_file_system_exposure_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'file_system_exposure_enabled', fallback=True)

    def get_data_exfiltration_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'data_exfiltration_enabled', fallback=True)

    # ========== Observer Settings ==========

    def get_target_url(self, app_name: str, server_name: str) -> Optional[str]:
        """
        Get target URL for a specific app/server combination.

        Try app-specific environment variable first, then fallback.
        """
        env_var = f"MCP_TARGET_{app_name.upper()}_{server_name.upper()}"
        url = os.getenv(env_var)

        if url:
            return url

        return os.getenv('MCP_TARGET_URL')


# Global config instance
config = Config()
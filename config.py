"""
Configuration management for 82ch MCP proxy.
"""

import os
from typing import Optional


class Config:
    """Configuration settings for the proxy."""

    def __init__(self):
        # Server settings
        self.server_port = int(os.getenv('MCP_PROXY_PORT', '28173'))
        self.server_host = os.getenv('MCP_PROXY_HOST', '127.0.0.1')

        # Debug mode
        self.debug = os.getenv('MCP_DEBUG', 'false').lower() == 'true'

        # Verification settings
        self.scan_mode = os.getenv('MCP_SCAN_MODE', 'REQUEST_RESPONSE')

        # Timeout settings
        self.sse_timeout = 300  # 5 minutes
        self.tool_call_timeout = 600  # 10 minutes
        self.verification_timeout = 35  # 35 seconds

    def get_target_url(self, app_name: str, server_name: str) -> Optional[str]:
        """
        Get target URL for a specific app/server combination.

        In production, this would look up from a configuration database.
        For demo, we use environment variables.
        """
        # Try app-specific environment variable first
        env_var = f"MCP_TARGET_{app_name.upper()}_{server_name.upper()}"
        url = os.getenv(env_var)

        if url:
            return url

        # Fallback to generic target URL
        return os.getenv('MCP_TARGET_URL')


# Global config instance
config = Config()

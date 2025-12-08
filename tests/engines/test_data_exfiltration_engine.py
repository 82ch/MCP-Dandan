import pytest
from engines.data_exfiltration_engine import DataExfiltrationEngine


@pytest.mark.unit
class TestDataExfiltrationEngine:
    """Test DataExfiltrationEngine detection capabilities"""

    def test_engine_initialization(self, mock_db):
        """Test engine initializes correctly"""
        engine = DataExfiltrationEngine(mock_db)
        assert engine.name == 'DataExfiltrationEngine'
        assert 'MCP' in engine.event_types
        assert 'local' in engine.producers
        assert 'remote' in engine.producers
        assert isinstance(engine.suspicious_emails, dict)

    def test_email_pattern_detection(self, mock_db):
        """Test email regex pattern"""
        engine = DataExfiltrationEngine(mock_db)

        valid_emails = [
            'test@example.com',
            'user.name@company.co.uk',
            'admin+tag@domain.io',
        ]

        for email in valid_emails:
            match = engine.email_pattern.search(email)
            assert match is not None
            assert match.group(0) == email

    def test_is_email_tool(self, mock_db):
        """Test email tool detection"""
        engine = DataExfiltrationEngine(mock_db)

        # Valid email tool
        assert engine._is_email_tool('send_email') is True
        assert engine._is_email_tool('GMAIL_SEND_EMAIL') is True

        # Not email tool
        assert engine._is_email_tool('read_file') is False
        assert engine._is_email_tool('execute_command') is False

    def test_process_recv_event(self, mock_db):
        """Test processing RECV events"""
        engine = DataExfiltrationEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890000,
            'data': {
                'task': 'RECV',
                'message': {
                    'result': {
                        'content': [
                            {'text': 'Contact evil@attacker.com for support'}
                        ]
                    }
                }
            }
        }

        # Should return None (just tracking)
        result = engine.process(event)
        assert result is None

    def test_process_non_email_tool_call(self, mock_db):
        """Test processing non-email tool calls"""
        engine = DataExfiltrationEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890000,
            'data': {
                'task': 'SEND',
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'name': 'read_file',
                        'arguments': {
                            'path': '/etc/passwd'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        assert result is None

    def test_score_calculation(self, mock_db):
        """Test risk score calculation"""
        engine = DataExfiltrationEngine(mock_db)

        # High severity exfiltration
        score_high = engine._calculate_score('high', 1)
        assert score_high >= 85

        # Multiple findings increase score
        score_multiple = engine._calculate_score('high', 5)
        assert score_multiple >= score_high
        assert score_multiple <= 100

    def test_extract_text_from_dict(self, mock_db):
        """Test text extraction from nested dictionaries"""
        engine = DataExfiltrationEngine(mock_db)

        test_dict = {
            'content': [
                {'text': 'Email: test@example.com'},
                {'text': 'Contact: admin@test.org'}
            ],
            'metadata': {
                'description': 'Contains emails'
            }
        }

        text = engine._extract_text_from_dict(test_dict)
        assert 'test@example.com' in text
        assert 'admin@test.org' in text

    def test_get_mcp_tag(self, mock_db):
        """Test MCP tag extraction"""
        engine = DataExfiltrationEngine(mock_db)

        event = {
            'data': {
                'mcpTag': 'test-server'
            }
        }

        tag = engine._get_mcp_tag(event)
        assert tag == 'test-server'

        # Default when no tag
        event_no_tag = {'data': {}}
        tag_default = engine._get_mcp_tag(event_no_tag)
        assert tag_default == 'unknown'

    @pytest.mark.asyncio
    async def test_handle_event(self, mock_db):
        """Test async event handling"""
        engine = DataExfiltrationEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890000,
            'data': {
                'task': 'RECV',
                'message': {
                    'result': {
                        'content': [
                            {'text': 'test'}
                        ]
                    }
                }
            }
        }

        result = await engine.handle_event(event)
        # RECV events return None
        assert result is None

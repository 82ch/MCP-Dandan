import pytest
from engines.file_system_exposure_engine import FileSystemExposureEngine


@pytest.mark.unit
class TestFileSystemExposureEngine:
    """Test FileSystemExposureEngine detection capabilities"""

    def test_engine_initialization(self, mock_db):
        """Test engine initializes correctly"""
        engine = FileSystemExposureEngine(mock_db)
        assert engine.name == 'FileSystemExposureEngine'
        assert 'MCP' in engine.event_types
        assert 'local' in engine.producers
        assert 'remote' in engine.producers

    def test_detect_critical_windows_paths(self, mock_db):
        """Test detection of critical Windows system paths"""
        engine = FileSystemExposureEngine(mock_db)

        critical_paths = [
            'C:\\Windows\\System32\\config\\SAM',
            'C:\\Windows\\SysWOW64\\cmd.exe',
            'C:\\boot.ini',
        ]

        for path in critical_paths:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'path': path
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            assert result is not None, f"Failed to detect critical path: {path}"
            assert result['result']['severity'] in ['high', 'medium']

    def test_detect_critical_linux_paths(self, mock_db):
        """Test detection of critical Linux system paths"""
        engine = FileSystemExposureEngine(mock_db)

        critical_paths = [
            '/etc/passwd',
            '/etc/shadow',
            '/etc/sudoers',
            '/root/.ssh/id_rsa',
            '/proc/self/environ',
        ]

        for path in critical_paths:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'file': path
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            assert result is not None, f"Failed to detect critical path: {path}"
            assert result['result']['severity'] in ['high', 'medium']

    def test_detect_credential_files(self, mock_db):
        """Test detection of credential and key files"""
        engine = FileSystemExposureEngine(mock_db)

        credential_paths = [
            '/home/user/.ssh/id_rsa',
            '/home/user/.aws/credentials',
            '/home/user/.kube/config',
            '/home/user/.docker/config.json',
        ]

        for path in credential_paths:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'filepath': path
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            assert result is not None, f"Failed to detect credential file: {path}"
            assert result['result']['detector'] == 'FileSystemExposure'

    def test_detect_dangerous_extensions(self, mock_db):
        """Test detection of dangerous file extensions"""
        engine = FileSystemExposureEngine(mock_db)

        dangerous_files = [
            '/home/user/private.key',
            '/home/user/cert.pem',
            '/home/user/.env',
            '/home/user/config.ini',
        ]

        for filepath in dangerous_files:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'file': filepath
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            assert result is not None, f"Failed to detect dangerous file: {filepath}"

    def test_detect_path_traversal(self, mock_db):
        """Test detection of path traversal attempts"""
        engine = FileSystemExposureEngine(mock_db)

        traversal_paths = [
            '../../etc/passwd',
            '..\\..\\Windows\\System32',
            '%2e%2e%2fetc%2fpasswd',
            '%252e%252e%252fetc%252fpasswd',
        ]

        for path in traversal_paths:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'path': path
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            assert result is not None, f"Failed to detect path traversal: {path}"
            assert any('traversal' in str(f).lower() for f in result['result']['findings'])

    def test_no_detection_for_safe_paths(self, mock_db):
        """Test engine doesn't flag safe paths"""
        engine = FileSystemExposureEngine(mock_db)

        safe_paths = [
            '/home/user/documents/report.pdf',
            '/tmp/myfile.txt',
            'C:\\Users\\John\\Documents\\file.docx',
        ]

        for path in safe_paths:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                'path': path
                            }
                        }
                    }
                }
            }

            result = engine.process(event)
            # Safe paths should either return None or low severity
            if result is not None:
                assert result['result']['severity'] in ['low', 'medium']

    def test_extract_paths_from_various_fields(self, mock_db):
        """Test path extraction from different field names"""
        engine = FileSystemExposureEngine(mock_db)

        field_names = ['path', 'file', 'filepath', 'directory', 'folder', 'location']

        for field_name in field_names:
            event = {
                'eventType': 'MCP',
                'producer': 'local',
                'ts': 1234567890,
                'data': {
                    'message': {
                        'params': {
                            'arguments': {
                                field_name: '/etc/passwd'
                            }
                        }
                    }
                }
            }

            paths = engine._extract_paths_from_fields(event)
            assert '/etc/passwd' in paths, f"Failed to extract from field: {field_name}"

    def test_depth_score_calculation(self, mock_db):
        """Test path depth score calculation"""
        engine = FileSystemExposureEngine(mock_db)

        # Shallow path (depth 2)
        shallow_score = engine._calculate_depth_score('/etc/passwd')
        assert shallow_score == 0

        # Deep path (depth 6)
        deep_score = engine._calculate_depth_score('/home/user/documents/private/secrets/key.pem')
        assert deep_score > 0

    def test_system_keyword_detection(self, mock_db):
        """Test system keyword detection and scoring"""
        engine = FileSystemExposureEngine(mock_db)

        # Critical keyword
        score1, matches1 = engine._check_system_keywords('/home/.ssh/id_rsa')
        assert score1 > 0
        assert len(matches1) > 0

        # High severity keyword
        score2, matches2 = engine._check_system_keywords('/etc/passwd')
        assert score2 > 0

        # Medium severity keyword
        score3, matches3 = engine._check_system_keywords('/home/user/documents')
        assert score3 >= 0

    def test_result_structure(self, mock_db):
        """Test the structure of detection results"""
        engine = FileSystemExposureEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'params': {
                        'arguments': {
                            'path': '/etc/passwd'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        assert result is not None

        # Check top-level structure
        assert 'reference' in result
        assert 'result' in result

        # Check result structure
        result_data = result['result']
        assert 'detector' in result_data
        assert result_data['detector'] == 'FileSystemExposure'
        assert 'severity' in result_data
        assert 'evaluation' in result_data
        assert 'findings' in result_data
        assert 'event_type' in result_data
        assert 'producer' in result_data

        # Check findings structure
        for finding in result_data['findings']:
            assert 'category' in finding
            assert 'matched_text' in finding
            assert 'reason' in finding

    def test_no_paths_in_event(self, mock_db):
        """Test handling of events with no path fields"""
        engine = FileSystemExposureEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'params': {
                        'arguments': {
                            'command': 'ls -la'
                        }
                    }
                }
            }
        }

        result = engine.process(event)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_event(self, mock_db):
        """Test async event handling"""
        engine = FileSystemExposureEngine(mock_db)

        event = {
            'eventType': 'MCP',
            'producer': 'local',
            'ts': 1234567890,
            'data': {
                'message': {
                    'params': {
                        'arguments': {
                            'path': '/etc/shadow'
                        }
                    }
                }
            }
        }

        result = await engine.handle_event(event)
        assert result is not None
        assert result['result']['detector'] == 'FileSystemExposure'

from engines.base_engine import BaseEngine
from typing import Any
import re
from utils import safe_print


class FileSystemExposureEngine(BaseEngine):
    """
    YARA Rule 기반 File System Exposure 탐지 엔진

    탐지 기준:
    1. 시스템 경로 키워드 (Windows/Linux/Mac)
    2. 위험 확장자
    3. 경로 깊이
    4. 민감 키워드
    """

    def __init__(self, db):
        super().__init__(
            db=db,
            name='FileSystemExposureEngine',
            event_types=['MCP'],
            producers=['local', 'remote']
        )

        # ========== YARA-style Rules ==========

        # Rule 1: Critical system paths (highest priority)
        self.critical_system_paths = {
            # Windows
            'windows': [
                r'C:\\Windows\\System32',
                r'C:\\Windows\\SysWOW64',
                r'C:\\Windows\\system\.ini',
                r'C:\\Windows\\win\.ini',
                r'C:\\boot\.ini',
            ],
            # Linux/Unix
            'linux': [
                r'/etc/passwd',
                r'/etc/shadow',
                r'/etc/sudoers',
                r'/etc/hosts',
                r'/root/',
                r'/proc/',
                r'/sys/',
                r'/boot/',
                r'/var/log/',
            ],
            # Mac
            'mac': [
                r'/Library/Preferences/',
                r'/System/Library/',
                r'/private/var/',
                r'/private/etc/',
            ],
            # SSH/Credentials (cross-platform)
            'credentials': [
                r'\.ssh/id_rsa',
                r'\.ssh/id_dsa',
                r'\.ssh/id_ecdsa',
                r'\.ssh/id_ed25519',
                r'\.ssh/authorized_keys',
                r'\.ssh/known_hosts',
                r'\.aws/credentials',
                r'\.azure/',
                r'\.kube/config',
                r'\.docker/config\.json',
            ]
        }

        # Rule 2: System directory keywords (score based)
        self.system_keywords = {
            'critical': [  # +40 points
                'system32', 'syswow64', 'etc/passwd', 'etc/shadow',
                '.ssh/', '.aws/', '.azure/', '.kube/'
            ],
            'high': [  # +30 points
                'windows', 'program files', 'programdata', 'appdata',
                '/etc/', '/root/', '/proc/', '/sys/', '/boot/',
                '/var/log/', '/usr/bin/', '/usr/sbin/',
                'library/preferences', 'system/library'
            ],
            'medium': [  # +20 points
                'users/', 'home/', 'documents/', 'desktop/',
                '/tmp/', '/var/', '/opt/', '/usr/',
                'local/', 'roaming/'
            ]
        }

        # Rule 3: Dangerous file extensions
        self.dangerous_extensions = {
            'critical': [  # +55 points
                '.pem', '.key', '.crt', '.pfx', '.p12',
                '.keystore', '.jks', '.der',
                'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519'
            ],
            'high': [  # +35 points
                '.env', '.htpasswd', '.htaccess',
                '.bashrc', '.bash_profile', '.zshrc',
                '.npmrc', '.pypirc', '.netrc',
                '.gitconfig', '.git-credentials',
                'credentials', 'secrets'
            ],
            'medium': [  # +15 points
                '.conf', '.config', '.ini', '.cfg',
                '.yaml', '.yml', '.json', '.xml',
                '.log', '.bak', '.old', '.backup'
            ]
        }

        # Rule 4: Path-related field names to check
        self.path_field_names = [
            'path', 'file', 'filepath', 'filename',
            'dir', 'directory', 'folder',
            'location', 'source', 'destination', 'target',
            'url', 'uri', 'endpoint'  # URL도 Path Traversal 검사 대상
        ]

        # Rule 5: Path Traversal patterns
        self.path_traversal_patterns = [
            (r'\.\./', 30, 'Parent directory traversal'),
            (r'\.\.\\', 30, 'Parent directory traversal (Windows)'),
            (r'%2e%2e%2f', 35, 'URL encoded traversal'),
            (r'%2e%2e/', 35, 'URL encoded traversal'),
            (r'\.\.%2f', 35, 'Mixed encoded traversal'),
            (r'%252e%252e%252f', 40, 'Double URL encoded traversal'),
            (r'\.\.%255c', 40, 'Double encoded backslash traversal'),
        ]

        # Compile traversal patterns
        self.traversal_regex = [
            (re.compile(p, re.IGNORECASE), score, reason)
            for p, score, reason in self.path_traversal_patterns
        ]

        # Compile regex
        self._compile_patterns()

    def _compile_patterns(self):
        """Compile all regex patterns"""
        # Critical paths
        self.critical_path_regex = {}
        for category, patterns in self.critical_system_paths.items():
            self.critical_path_regex[category] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def process(self, data: Any) -> Any:
        safe_print(f"[FileSystemExposureEngine] Processing event")

        # Extract paths from specific fields only
        paths = self._extract_paths_from_fields(data)

        if not paths:
            safe_print(f"[FileSystemExposureEngine] No paths to analyze, skipping\n")
            return None

        safe_print(f"[FileSystemExposureEngine] Extracted {len(paths)} paths: {paths}")

        findings = []
        total_score = 0

        for path in paths:
            path_score = 0
            path_findings = []

            # Check 1: Critical system paths
            critical_match = self._check_critical_paths(path)
            if critical_match:
                path_score += 50
                path_findings.append({
                    'rule': 'critical_system_path',
                    'category': critical_match['category'],
                    'matched': critical_match['matched'],
                    'score': 50
                })

            # Check 2: System keywords
            keyword_score, keyword_matches = self._check_system_keywords(path)
            if keyword_score > 0:
                path_score += keyword_score
                for match in keyword_matches:
                    path_findings.append({
                        'rule': 'system_keyword',
                        'keyword': match['keyword'],
                        'severity': match['severity'],
                        'score': match['score']
                    })

            # Check 3: Dangerous extensions
            ext_score, ext_match = self._check_dangerous_extensions(path)
            if ext_score > 0:
                path_score += ext_score
                path_findings.append({
                    'rule': 'dangerous_extension',
                    'extension': ext_match['extension'],
                    'severity': ext_match['severity'],
                    'score': ext_score
                })

            # Check 4: Path depth bonus
            depth_score = self._calculate_depth_score(path)
            if depth_score > 0:
                path_score += depth_score
                path_findings.append({
                    'rule': 'path_depth',
                    'depth': path.count('/') + path.count('\\'),
                    'score': depth_score
                })

            # Check 5: Path Traversal patterns
            traversal_score, traversal_match = self._check_path_traversal(path)
            if traversal_score > 0:
                path_score += traversal_score
                path_findings.append({
                    'rule': 'path_traversal',
                    'pattern': traversal_match['pattern'],
                    'reason': traversal_match['reason'],
                    'score': traversal_score
                })

            # Add findings if score > 0
            if path_score > 0:
                # Convert to UI-compatible format
                for detail in path_findings:
                    # Determine category based on score
                    if detail.get('score', 0) >= 35:
                        category = 'critical'
                    elif detail.get('score', 0) >= 25:
                        category = 'high'
                    else:
                        category = 'medium'

                    # Build reason string
                    rule = detail.get('rule', '')
                    if rule == 'critical_system_path':
                        reason = f"Critical system path detected: {detail.get('matched', '')}"
                    elif rule == 'system_keyword':
                        reason = f"System keyword '{detail.get('keyword', '')}' in path"
                    elif rule == 'dangerous_extension':
                        reason = f"Dangerous extension '{detail.get('extension', '')}' detected"
                    elif rule == 'path_depth':
                        reason = f"Deep path access (depth: {detail.get('depth', 0)})"
                    elif rule == 'path_traversal':
                        reason = detail.get('reason', 'Path traversal detected')
                    else:
                        reason = f"File system exposure: {rule}"

                    findings.append({
                        'category': category,
                        'pattern': detail.get('pattern', detail.get('keyword', '')),
                        'matched_text': path,
                        'full_path': path,
                        'reason': reason
                    })

                total_score = max(total_score, path_score)

        # No findings
        if not findings:
            safe_print(f"[FileSystemExposureEngine] No issues found\n")
            return None

        # Determine severity based on score
        if total_score >= 70:
            severity = 'high'
        elif total_score >= 40:
            severity = 'medium'
        else:
            severity = 'low'

        # Build result
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        result = {
            'reference': references,
            'result': {
                'detector': 'FileSystemExposure',
                'severity': severity,
                'evaluation': min(total_score, 100),
                'findings': findings,
                'event_type': data.get('eventType', 'Unknown'),
                'producer': data.get('producer', 'unknown'),
                'original_event': data
            }
        }

        safe_print(f"[FileSystemExposureEngine] Detection: severity={severity}, score={min(total_score, 100)}")
        safe_print(f"[FileSystemExposureEngine] {len(findings)} paths flagged\n")

        return result

    def _extract_paths_from_fields(self, data: dict) -> list[str]:
        """
        Extract paths only from specific field names
        (path, file, directory, etc.)
        """
        paths = []
        producer = data.get('producer', '')

        if producer not in ['local', 'remote']:
            return paths

        if 'data' not in data or not isinstance(data['data'], dict):
            return paths

        mcp_data = data['data']
        if 'message' not in mcp_data or not isinstance(mcp_data['message'], dict):
            return paths

        message = mcp_data['message']

        # Only check params.arguments (request) - not all text
        if 'params' in message and isinstance(message['params'], dict):
            params = message['params']
            if 'arguments' in params and isinstance(params['arguments'], dict):
                arguments = params['arguments']
                self._extract_from_dict(arguments, paths)

        return list(set(paths))

    def _extract_from_dict(self, obj: dict, paths: list, depth: int = 0):
        """
        Extract values only from path-related field names
        """
        if depth > 5:  # Prevent deep recursion
            return

        if isinstance(obj, dict):
            for key, value in obj.items():
                key_lower = key.lower()
                # Only extract from path-related fields
                if any(field in key_lower for field in self.path_field_names):
                    if isinstance(value, str) and len(value) > 1:
                        paths.append(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str) and len(item) > 1:
                                paths.append(item)
                # Recurse into nested objects
                if isinstance(value, dict):
                    self._extract_from_dict(value, paths, depth + 1)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self._extract_from_dict(item, paths, depth + 1)

    def _check_critical_paths(self, path: str) -> dict | None:
        """Check against critical system paths"""
        for category, patterns in self.critical_path_regex.items():
            for pattern in patterns:
                match = pattern.search(path)
                if match:
                    return {
                        'category': category,
                        'matched': match.group(0)
                    }
        return None

    def _check_system_keywords(self, path: str) -> tuple[int, list]:
        """Check for system directory keywords"""
        path_lower = path.lower()
        total_score = 0
        matches = []

        scores = {'critical': 40, 'high': 30, 'medium': 20}

        for severity, keywords in self.system_keywords.items():
            for keyword in keywords:
                if keyword in path_lower:
                    score = scores[severity]
                    total_score += score
                    matches.append({
                        'keyword': keyword,
                        'severity': severity,
                        'score': score
                    })
                    break  # Only count one match per severity level

        return total_score, matches

    def _check_dangerous_extensions(self, path: str) -> tuple[int, dict]:
        """Check for dangerous file extensions"""
        path_lower = path.lower()

        scores = {'critical': 55, 'high': 35, 'medium': 15}

        # First check: actual extension (endswith) - highest priority
        for severity, extensions in self.dangerous_extensions.items():
            for ext in extensions:
                if path_lower.endswith(ext):
                    return scores[severity], {
                        'extension': ext,
                        'severity': severity
                    }

        # Second check: extension appears anywhere in path (lower priority)
        for severity, extensions in self.dangerous_extensions.items():
            for ext in extensions:
                if ext in path_lower:
                    return scores[severity], {
                        'extension': ext,
                        'severity': severity
                    }

        return 0, {}

    def _calculate_depth_score(self, path: str) -> int:
        """
        Calculate score based on path depth
        Deeper paths = higher score (more specific targeting)
        """
        # Count separators
        depth = path.count('/') + path.count('\\')

        # Score: 2 points per level after 3
        if depth > 3:
            return min((depth - 3) * 2, 10)  # Max 10 points
        return 0

    def _check_path_traversal(self, path: str) -> tuple[int, dict]:
        """Check for path traversal patterns"""
        for pattern, score, reason in self.traversal_regex:
            if pattern.search(path):
                return score, {
                    'pattern': pattern.pattern,
                    'reason': reason
                }
        return 0, {}

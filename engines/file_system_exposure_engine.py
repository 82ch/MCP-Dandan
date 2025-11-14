from engines.base_engine import BaseEngine
from typing import Any
import re
from utils import safe_print


class FileSystemExposureEngine(BaseEngine):

    def __init__(self, db):
        super().__init__(
            db=db,
            name='FileSystemExposureEngine',
            event_types=['MCP'],
            producers=['local', 'remote']  # local과 remote producer만 검사
        )

        # Critical patterns (very dangerous system paths)
        self.critical_patterns = [
            # Windows system directories
            r'C:\\Windows\\System32',
            r'C:\\Windows\\SysWOW64',
            r'\\\\Windows\\\\System32',
            r'\\\\Windows\\\\SysWOW64',

            # Unix/Linux system directories
            r'/etc/passwd',
            r'/etc/shadow',
            r'/etc/sudoers',
            r'/root/',
            r'/proc/',
            r'/sys/',

            # Sensitive config files
            r'\.ssh/id_rsa',
            r'\.ssh/id_dsa',
            r'\.ssh/id_ecdsa',
            r'\.ssh/id_ed25519',
            r'\.aws/credentials',
            r'\.azure/credentials',
        ]

        # High-risk patterns
        self.high_risk_patterns = [
            # Absolute paths (Windows)
            r'[A-Z]:\\',
            r'\\\\[A-Za-z0-9_-]+\\\\',  # UNC path

            # Absolute paths (Unix/Linux)
            r'^/',  # Starting from root

            # Directory traversal
            r'\.\.[/\\]',
            r'\.\.[/\\]\.\.[/\\]',

            # User home directories
            r'C:\\Users\\[^\\]+',
            r'/home/[^/]+',
            r'~/',

            # Environment variables
            r'%USERPROFILE%',
            r'%APPDATA%',
            r'%LOCALAPPDATA%',
            r'%TEMP%',
            r'\$HOME',
            r'\$USER',
        ]

        # Medium-risk patterns
        self.medium_risk_patterns = [
            # Relative path parent reference
            r'\.\.',

            # Specific extensions
            r'\.config$',
            r'\.conf$',
            r'\.ini$',
            r'\.env$',

            # Common sensitive directory names
            r'[/\\]config[/\\]',
            r'[/\\]configs[/\\]',
            r'[/\\]secrets[/\\]',
            r'[/\\]private[/\\]',
            r'[/\\]\.git[/\\]',
        ]

        # Compile regex patterns
        self.critical_regex = [re.compile(p, re.IGNORECASE) for p in self.critical_patterns]
        self.high_risk_regex = [re.compile(p) for p in self.high_risk_patterns]
        self.medium_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.medium_risk_patterns]

        # Sensitive path keywords
        self.sensitive_keywords = [
            'password', 'secret', 'token', 'key', 'credential',
            'private', 'config', 'auth', 'ssl', 'cert'
        ]

    def process(self, data: Any) -> Any:
        safe_print(f"[FileSystemExposureEngine] Input data: {data}")

        # Extract paths to analyze
        paths = self._extract_paths(data)

        if not paths:
            safe_print(f"[FileSystemExposureEngine] No paths to analyze, skipping\n")
            return None

        safe_print(f"[FileSystemExposureEngine] Extracted paths: {paths}")

        findings = []
        severity = 'none'

        # Check each path
        for path in paths:
            # Critical pattern check (maps to 'high' severity)
            for pattern in self.critical_regex:
                matches = pattern.finditer(path)
                for match in matches:
                    findings.append({
                        'category': 'critical',
                        'pattern': pattern.pattern,
                        'matched_text': match.group(0),
                        'full_path': path,
                        'reason': self._get_reason(pattern.pattern, 'critical')
                    })
                    if severity not in ['high']:
                        severity = 'high'

            # High-risk pattern check (maps to 'high' severity)
            if severity not in ['high']:
                for pattern in self.high_risk_regex:
                    matches = pattern.finditer(path)
                    for match in matches:
                        findings.append({
                            'category': 'high',
                            'pattern': pattern.pattern,
                            'matched_text': match.group(0),
                            'full_path': path,
                            'reason': self._get_reason(pattern.pattern, 'high')
                        })
                        if severity not in ['high']:
                            severity = 'high'

            # Medium-risk pattern check (maps to 'medium' severity)
            if severity == 'none':
                for pattern in self.medium_risk_regex:
                    matches = pattern.finditer(path)
                    for match in matches:
                        findings.append({
                            'category': 'medium',
                            'pattern': pattern.pattern,
                            'matched_text': match.group(0),
                            'full_path': path,
                            'reason': self._get_reason(pattern.pattern, 'medium')
                        })
                        if severity != 'medium':
                            severity = 'medium'

            # Sensitive keyword check (maps to 'high' severity)
            keyword_found = self._check_sensitive_keywords(path)
            if keyword_found:
                for keyword in keyword_found:
                    findings.append({
                        'category': 'high' if severity == 'none' else severity,
                        'pattern': f'sensitive_keyword:{keyword}',
                        'matched_text': keyword,
                        'full_path': path,
                        'reason': f'Sensitive keyword in path: {keyword}'
                    })
                if severity == 'none':
                    severity = 'high'

        # severity가 'none'인 경우 (탐지되지 않음) None 반환
        if severity == 'none':
            safe_print(f"[FileSystemExposureEngine] No issues found, 탐지되지 않음\n")
            return None

        # Calculate score based on severity and findings count
        score = self._calculate_score(severity, len(findings))

        # Return result (탐지된 경우만 반환)
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        result = {
            'reference': references,
            'result': {
                'detector': 'FileSystemExposure',
                'severity': severity,
                'evaluation': score,
                'findings': findings,
                'event_type': data.get('eventType', 'Unknown'),
                'exposed_paths': paths,
                'original_event': data
            }
        }

        safe_print(f"[FileSystemExposureEngine] WARNING - File System Exposure detected! severity={severity}, score={score}")
        safe_print(f"[FileSystemExposureEngine] Detection result: {len(findings)} findings\n")

        return result

    def _calculate_score(self, severity: str, findings_count: int) -> int:
        """
        Calculate risk score based on severity and number of findings
        Score range: 0-100
        """
        # Base score by severity
        base_scores = {
            'high': 80,
            'medium': 50,
            'low': 20,
            'none': 0
        }

        base_score = base_scores.get(severity, 0)

        # Add points for multiple findings (max +20 points)
        findings_bonus = min(findings_count * 4, 20)

        total_score = min(base_score + findings_bonus, 100)

        return total_score

    def _extract_paths(self, data: dict) -> list[str]:
        """
        Extract file paths from event data
        """
        paths = []
        producer = data.get('producer', '')

        # local 또는 remote producer만 처리
        if producer in ['local', 'remote']:
            if 'data' in data and isinstance(data['data'], dict):
                mcp_data = data['data']

                if 'message' in mcp_data and isinstance(mcp_data['message'], dict):
                    message = mcp_data['message']

                    # Extract from params.arguments
                    if 'params' in message and isinstance(message['params'], dict):
                        params = message['params']
                        if 'arguments' in params and isinstance(params['arguments'], dict):
                            self._extract_paths_recursive(params['arguments'], paths)

                    # Extract from result
                    if 'result' in message and isinstance(message['result'], dict):
                        result = message['result']
                        if 'content' in result and isinstance(result['content'], list):
                            for item in result['content']:
                                if isinstance(item, dict) and 'text' in item:
                                    text_paths = self._find_paths_in_text(str(item['text']))
                                    paths.extend(text_paths)
                        if 'structuredContent' in result:
                            self._extract_paths_recursive(result['structuredContent'], paths)

        return list(set(paths))  # Remove duplicates

    def _extract_paths_recursive(self, obj: Any, paths: list):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if any(k in key.lower() for k in ['path', 'file', 'dir', 'directory', 'location', 'uri']):
                    if isinstance(value, str):
                        paths.append(value)
                    elif isinstance(value, (list, dict)):
                        self._extract_paths_recursive(value, paths)
                else:
                    self._extract_paths_recursive(value, paths)
        elif isinstance(obj, list):
            for item in obj:
                self._extract_paths_recursive(item, paths)
        elif isinstance(obj, str):
            paths.extend(self._find_paths_in_text(obj))

    def _find_paths_in_text(self, text: str) -> list[str]:
        paths = []

        windows_pattern = r'(?:[A-Z]:\\|\\\\)[^\s<>"|?*\n]+'
        for match in re.finditer(windows_pattern, text):
            paths.append(match.group(0))

        unix_pattern = r'(?:^|[\s"\'`])([/~][^\s<>"|?*\n]+)'
        for match in re.finditer(unix_pattern, text, re.MULTILINE):
            paths.append(match.group(1))

        relative_pattern = r'\.{1,2}/[^\s<>"|?*\n]+'
        for match in re.finditer(relative_pattern, text):
            paths.append(match.group(0))

        return paths

    def _check_sensitive_keywords(self, text: str) -> list[str]:
        found = []
        text_lower = text.lower()
        for keyword in self.sensitive_keywords:
            if keyword in text_lower:
                found.append(keyword)
        return found

    def _get_reason(self, pattern: str, category: str) -> str:
        reasons = {
            # Critical
            r'C:\\Windows\\System32': 'Windows System32 directory exposure',
            r'C:\\Windows\\SysWOW64': 'Windows SysWOW64 directory exposure',
            r'\\\\Windows\\\\System32': 'Windows System32 directory exposure',
            r'\\\\Windows\\\\SysWOW64': 'Windows SysWOW64 directory exposure',
            r'/etc/passwd': 'Unix password file exposure',
            r'/etc/shadow': 'Unix shadow file exposure',
            r'/etc/sudoers': 'Sudoers file exposure',
            r'/root/': 'Root directory exposure',
            r'/proc/': 'Process information exposure',
            r'/sys/': 'System information exposure',
            r'\.ssh/id_rsa': 'SSH private key exposure',
            r'\.ssh/id_dsa': 'SSH private key exposure',
            r'\.ssh/id_ecdsa': 'SSH private key exposure',
            r'\.ssh/id_ed25519': 'SSH private key exposure',
            r'\.aws/credentials': 'AWS credentials exposure',
            r'\.azure/credentials': 'Azure credentials exposure',

            # High-risk
            r'[A-Z]:\\': 'Absolute Windows path exposure',
            r'\\\\[A-Za-z0-9_-]+\\\\': 'UNC path exposure',
            r'^/': 'Absolute Unix path exposure',
            r'\.\.[/\\]': 'Directory traversal detected',
            r'\.\.[/\\]\.\.[/\\]': 'Multiple directory traversal detected',
            r'C:\\Users\\[^\\]+': 'User directory exposure',
            r'/home/[^/]+': 'Home directory exposure',
            r'~/': 'Home directory reference',
            r'%USERPROFILE%': 'User profile environment variable',
            r'%APPDATA%': 'AppData environment variable',
            r'%LOCALAPPDATA%': 'Local AppData environment variable',
            r'%TEMP%': 'Temp directory environment variable',
            r'\$HOME': 'HOME environment variable',
            r'\$USER': 'USER environment variable',

            # Medium-risk
            r'\.\.': 'Relative path parent reference',
            r'\.config$': 'Config file exposure',
            r'\.conf$': 'Configuration file exposure',
            r'\.ini$': 'INI file exposure',
            r'\.env$': 'Environment file exposure',
            r'[/\\]config[/\\]': 'Config directory in path',
            r'[/\\]configs[/\\]': 'Configs directory in path',
            r'[/\\]secrets[/\\]': 'Secrets directory in path',
            r'[/\\]private[/\\]': 'Private directory in path',
            r'[/\\]\.git[/\\]': 'Git repository directory exposure',
        }

        pattern_lower = pattern.lower()
        for key, reason in reasons.items():
            if key.lower() == pattern_lower:
                return reason

        return f'{category.capitalize()} file system exposure pattern detected'

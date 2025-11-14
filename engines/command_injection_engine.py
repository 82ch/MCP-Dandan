from engines.base_engine import BaseEngine
from typing import Any
import re
from utils import safe_print


class CommandInjectionEngine(BaseEngine):

    def __init__(self, db):
        super().__init__(
            db=db,
            name='CommandInjectionEngine',
            event_types=['MCP'],  # MCP 이벤트 처리
            producers=['local', 'remote']  # local과 remote producer만 검사
        )

        # Critical 패턴 (매우 위험)
        self.critical_patterns = [
            # 쉘 메타문자 체이닝
            r';\s*(rm|del|format|mkfs)',
            r'\|\s*(rm|del|format|mkfs)',
            r'&&\s*(rm|del|format|mkfs)',
            r'\$\(.*rm.*\)',
            r'`.*rm.*`',

            # 위험한 명령어 실행
            r'eval\s*\(',
            r'exec\s*\(',
            r'system\s*\(',
            r'popen\s*\(',
            r'subprocess\.(call|run|Popen)',
            r'os\.system',
            r'shell=True',

            # 권한 상승 시도
            r'sudo\s+',
            r'su\s+-',
            r'runas\s+',

            # 데이터 유출
            r'\|\s*nc\s+',
            r'\|\s*netcat\s+',
            r'>\s*/dev/tcp/',
            r'curl.*-d\s*@',
            r'wget.*-O.*-',
        ]

        # High-risk 패턴
        self.high_risk_patterns = [
            # 쉘 메타문자 - 실제 명령어 주입 문맥에서만 탐지
            r';\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)',
            r'&&\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)',
            r'\|\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)',
            r'`[^`]*\b(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)\b[^`]*`',

            # 명령어 치환 (실제 명령어 실행 문맥)
            r'\$\{[^}]*(rm|del|wget|curl|bash|sh|cmd)[^}]*\}',
            r'\$\([^)]*(rm|del|wget|curl|bash|sh|cmd)[^)]*\)',

            # 환경 변수 악용
            r'%COMSPEC%',
            r'%SYSTEMROOT%',
            r'\$PATH\s*=',
            r'\$LD_PRELOAD',

            # 스크립트 인젝션
            r'<script',
            r'javascript:',
            r'onerror\s*=',
            r'onload\s*=',
        ]

        # Medium-risk 패턴
        self.medium_risk_patterns = [
            # 일반 명령어
            r'\bcmd\b',
            r'\bsh\b',
            r'\bbash\b',
            r'\bpowershell\b',
            r'\bwmic\b',

            # 파일 작업
            r'\bmove\b',
            r'\bcopy\b',
            r'\bcp\b',
            r'\bmv\b',

            # 네트워크
            r'\bping\b.*-[tn]\s+\d+',
            r'\btelnet\b',
            r'\bftp\b',
        ]

        # Regex 컴파일
        self.critical_regex = [re.compile(p, re.IGNORECASE) for p in self.critical_patterns]
        self.high_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.high_risk_patterns]
        self.medium_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.medium_risk_patterns]

        # 위험한 명령어 리스트
        self.dangerous_commands = [
            'rm', 'del', 'format', 'mkfs', 'dd', 'fdisk',
            'kill', 'killall', 'taskkill',
            'wget', 'curl', 'nc', 'netcat',
            'chmod', 'chown', 'icacls',
            'reg', 'regedit',
            'net', 'netsh',
        ]

    def process(self, data: Any) -> Any:
        safe_print(f"[CommandInjectionEngine] 입력 데이터: {data}")

        # 분석할 텍스트 추출
        analysis_text = self._extract_analysis_text(data)

        if not analysis_text:
            safe_print(f"[CommandInjectionEngine] 분석할 텍스트 없음, 무시\n")
            return None

        safe_print(f"[CommandInjectionEngine] 분석 중: {analysis_text[:200]}")

        findings = []
        severity = 'none'

        # Critical 패턴 검사 (maps to 'high' severity)
        for pattern in self.critical_regex:
            matches = pattern.finditer(analysis_text)
            for match in matches:
                findings.append({
                    'category': 'critical',
                    'pattern': pattern.pattern,
                    'matched_text': match.group(0),
                    'position': match.span(),
                    'reason': self._get_reason(pattern.pattern, 'critical')
                })
                if severity not in ['high']:
                    severity = 'high'

        # High-risk 패턴 검사 (maps to 'high' severity)
        if severity not in ['high']:
            for pattern in self.high_risk_regex:
                matches = pattern.finditer(analysis_text)
                for match in matches:
                    findings.append({
                        'category': 'high',
                        'pattern': pattern.pattern,
                        'matched_text': match.group(0),
                        'position': match.span(),
                        'reason': self._get_reason(pattern.pattern, 'high')
                    })
                    if severity not in ['high']:
                        severity = 'high'

        # Medium-risk 패턴 검사 (maps to 'medium' severity)
        if severity == 'none':
            for pattern in self.medium_risk_regex:
                matches = pattern.finditer(analysis_text)
                for match in matches:
                    findings.append({
                        'category': 'medium',
                        'pattern': pattern.pattern,
                        'matched_text': match.group(0),
                        'position': match.span(),
                        'reason': self._get_reason(pattern.pattern, 'medium')
                    })
                    if severity != 'medium':
                        severity = 'medium'

        # 위험한 명령어 체크 (maps to 'high' severity)
        dangerous_found = self._check_dangerous_commands(analysis_text)
        if dangerous_found:
            for cmd in dangerous_found:
                findings.append({
                    'category': 'high' if severity == 'none' else severity,
                    'pattern': f'dangerous_command:{cmd}',
                    'matched_text': cmd,
                    'reason': f'Potentially dangerous command: {cmd}'
                })
            if severity == 'none':
                severity = 'high'

        # severity가 'none'인 경우 (탐지되지 않음) None 반환
        if severity == 'none':
            safe_print(f"[CommandInjectionEngine] 이상 없음, 탐지되지 않음\n")
            return None

        # Calculate score based on severity and findings count
        score = self._calculate_score(severity, len(findings))

        # 결과 반환 (탐지된 경우만 반환)
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        result = {
            'reference': references,
            'result': {
                'detector': 'CommandInjection',
                'severity': severity,
                'evaluation': score,
                'findings': findings,
                'event_type': data.get('eventType', 'Unknown'),
                'analysis_text': analysis_text[:500] if analysis_text else '',
                'original_event': data
            }
        }

        safe_print(f"[CommandInjectionEngine] Command Injection 의심! severity={severity}, score={score}")
        safe_print(f"[CommandInjectionEngine] 탐지 결과: {len(findings)}개 발견\n")

        return result

    def _calculate_score(self, severity: str, findings_count: int) -> int:
        """
        Calculate risk score based on severity and number of findings
        Score range: 0-100
        """
        # Base score by severity
        base_scores = {
            'high': 85,
            'medium': 50,
            'low': 20,
            'none': 0
        }

        base_score = base_scores.get(severity, 0)

        # Add points for multiple findings (max +15 points)
        findings_bonus = min(findings_count * 3, 15)

        total_score = min(base_score + findings_bonus, 100)

        return total_score

    def _extract_analysis_text(self, data: dict) -> str:
        producer = data.get('producer', '')

        # local 또는 remote producer만 처리
        if producer in ['local', 'remote']:
            texts = []

            if 'data' in data and isinstance(data['data'], dict):
                mcp_data = data['data']

                if 'task' in mcp_data:
                    texts.append(str(mcp_data['task']))

                if 'message' in mcp_data and isinstance(mcp_data['message'], dict):
                    message = mcp_data['message']

                    if 'method' in message:
                        texts.append(str(message['method']))

                    if 'params' in message and isinstance(message['params'], dict):
                        params = message['params']

                        if 'name' in params:
                            texts.append(str(params['name']))

                        if 'arguments' in params:
                            texts.append(str(params['arguments']))

                    if 'result' in message and isinstance(message['result'], dict):
                        result = message['result']

                        if 'content' in result and isinstance(result['content'], list):
                            for item in result['content']:
                                if isinstance(item, dict) and 'text' in item:
                                    texts.append(str(item['text']))

                        if 'structuredContent' in result:
                            texts.append(str(result['structuredContent']))

            return ' '.join(texts)

        return ''

    def _check_dangerous_commands(self, text: str) -> list[str]:
        found = []
        text_lower = text.lower()

        for cmd in self.dangerous_commands:
            pattern = r'\b' + re.escape(cmd) + r'\b'
            if re.search(pattern, text_lower):
                found.append(cmd)

        return found

    def _get_reason(self, pattern: str, category: str) -> str:
        reasons = {
            r';\s*(rm|del|format|mkfs)': 'Command chaining with destructive operation',
            r'\|\s*(rm|del|format|mkfs)': 'Pipe to destructive command',
            r'&&\s*(rm|del|format|mkfs)': 'Command chaining with destructive operation',
            r'\$\(.*rm.*\)': 'Command substitution with destructive operation',
            r'`.*rm.*`': 'Command substitution with destructive operation',
            r'eval\s*\(': 'Dynamic code evaluation (eval)',
            r'exec\s*\(': 'Direct code execution (exec)',
            r'system\s*\(': 'System command execution',
            r'popen\s*\(': 'Process execution via popen',
            r'subprocess\.(call|run|Popen)': 'Subprocess execution',
            r'os\.system': 'OS system call',
            r'shell=True': 'Shell execution enabled',
            r'sudo\s+': 'Privilege escalation attempt',
            r'su\s+-': 'User switching attempt',
            r'runas\s+': 'Run as different user (Windows)',
            r'\|\s*nc\s+': 'Data exfiltration via netcat',
            r'\|\s*netcat\s+': 'Data exfiltration via netcat',
            r'>\s*/dev/tcp/': 'Network communication via file descriptor',
            r'curl.*-d\s*@': 'Data upload via curl',
            r'wget.*-O.*-': 'Data download to stdout',
            # High-risk
            r';\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)': 'Command chaining with dangerous command',
            r'&&\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)': 'Command chaining with dangerous command',
            r'\|\s*(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)': 'Pipe to dangerous command',
            r'`[^`]*\b(rm|del|wget|curl|bash|sh|cmd|powershell|python|perl|ruby|node)\b[^`]*`': 'Command substitution with dangerous command',
            r'\$\{[^}]*(rm|del|wget|curl|bash|sh|cmd)[^}]*\}': 'Variable expansion with command execution',
            r'\$\([^)]*(rm|del|wget|curl|bash|sh|cmd)[^)]*\)': 'Command substitution with dangerous command',
            r'%COMSPEC%': 'Windows command interpreter reference',
            r'%SYSTEMROOT%': 'Windows system directory reference',
            r'\$PATH\s*=': 'PATH environment variable manipulation',
            r'\$LD_PRELOAD': 'LD_PRELOAD injection attempt',
            r'\.\.[/\\]': 'Directory traversal attempt',
            r'/etc/passwd': 'System password file access',
            r'/etc/shadow': 'System shadow file access',
            r'C:\\Windows\\System32': 'Windows system directory access',
            r'<script': 'Script injection attempt',
            r'javascript:': 'JavaScript protocol handler',
            r'onerror\s*=': 'Event handler injection',
            r'onload\s*=': 'Event handler injection',
            # Medium-risk
            r'\bcmd\b': 'Windows command interpreter',
            r'\bsh\b': 'Shell execution',
            r'\bbash\b': 'Bash shell execution',
            r'\bpowershell\b': 'PowerShell execution',
            r'\bwmic\b': 'Windows Management Instrumentation',
            r'\bmove\b': 'File move operation',
            r'\bcopy\b': 'File copy operation',
            r'\bcp\b': 'File copy operation',
            r'\bmv\b': 'File move operation',
            r'\bping\b.*-[tn]\s+\d+': 'Network ping command',
            r'\btelnet\b': 'Telnet connection',
            r'\bftp\b': 'FTP connection',
        }

        pattern_lower = pattern.lower()
        for key, reason in reasons.items():
            if key.lower() == pattern_lower:
                return reason

        return f'{category.capitalize()} command injection pattern detected'

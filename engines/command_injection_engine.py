from engines.base_engine import BaseEngine
from typing import Any
import re


class CommandInjectionEngine(BaseEngine):
    """
    Command Injection 탐지 엔진

    Process 및 ProxyLog 이벤트를 분석하여 잠재적인 Command Injection 공격을 탐지합니다.
    - 쉘 메타문자 (;, |, &, $, `, etc.)
    - 위험한 명령어 조합
    - 파일 경로 조작 시도
    - 환경변수 주입
    """

    def __init__(self, logger):
        """
        Command Injection 탐지 엔진 초기화

        Args:
            logger: Logger 인스턴스
        """
        super().__init__(
            logger=logger,
            name='CommandInjectionEngine',
            event_types=['MCP', 'ProxyLog']  # MCP 및 ProxyLog 이벤트 처리
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
            # 기본 쉘 메타문자
            r'[;&|`$]',
            r'\$\{.*\}',
            r'\$\(.*\)',

            # 명령어 치환
            r'%COMSPEC%',
            r'%SYSTEMROOT%',

            # 파일 시스템 조작 
            # r'\.\.[/\\]',  # 디렉토리 트래버설
            # r'/etc/passwd',
            # r'/etc/shadow',
            # r'C:\\Windows\\System32',

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
        """
        MCP 이벤트를 분석하여 Command Injection 시도 탐지
        """
        print(f"[CommandInjectionEngine] 입력 데이터: {data}")

        # 분석할 텍스트 추출
        analysis_text = self._extract_analysis_text(data)

        if not analysis_text:
            print(f"[CommandInjectionEngine] 분석할 텍스트 없음, 무시\n")
            return None

        print(f"[CommandInjectionEngine] 분석 중: {analysis_text[:200]}")

        findings = []
        severity = 'none'

        # Critical 패턴 검사
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
                severity = 'critical'

        # High-risk 패턴 검사
        if severity != 'critical':
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
                    if severity != 'high':
                        severity = 'high'

        # Medium-risk 패턴 검사
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

        # 위험한 명령어 체크
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

        # 결과 반환
        if len(findings) > 0:
            references = []
            if 'ts' in data:
                references.append(f"id-{data['ts']}")

            result = {
                'detected': True,
                'reference': references,
                'result': {
                    'detector': 'CommandInjection',
                    'severity': severity,
                    'findings': findings,
                    'event_type': data.get('eventType', 'Unknown'),
                    'analysis_text': analysis_text[:500],  # 처음 500자만 저장
                    'original_event': data
                }
            }
            print(f"[CommandInjectionEngine] ⚠️ Command Injection 의심! severity={severity}")
            print(f"[CommandInjectionEngine] 탐지 결과: {len(findings)}개 발견\n")
            return result

        print(f"[CommandInjectionEngine] 이상 없음\n")
        return None

    def _extract_analysis_text(self, data: dict) -> str:
        """
        이벤트 데이터에서 분석할 텍스트를 추출합니다.
        """
        event_type = data.get('eventType', '')

        # MCP 이벤트
        if event_type == 'MCP':
            texts = []

            if 'data' in data and isinstance(data['data'], dict):
                mcp_data = data['data']

                # task (SEND/RECV)
                if 'task' in mcp_data:
                    texts.append(str(mcp_data['task']))

                # message 내용 추출
                if 'message' in mcp_data and isinstance(mcp_data['message'], dict):
                    message = mcp_data['message']

                    # method (예: tools/call)
                    if 'method' in message:
                        texts.append(str(message['method']))

                    # params
                    if 'params' in message and isinstance(message['params'], dict):
                        params = message['params']

                        # tool name
                        if 'name' in params:
                            texts.append(str(params['name']))

                        # arguments
                        if 'arguments' in params:
                            texts.append(str(params['arguments']))

                    # result (응답 데이터)
                    if 'result' in message and isinstance(message['result'], dict):
                        result = message['result']

                        # content 배열
                        if 'content' in result and isinstance(result['content'], list):
                            for item in result['content']:
                                if isinstance(item, dict) and 'text' in item:
                                    texts.append(str(item['text']))

                        # structuredContent
                        if 'structuredContent' in result:
                            texts.append(str(result['structuredContent']))

            return ' '.join(texts)

        # ProxyLog 이벤트
        elif event_type == 'ProxyLog':
            texts = []

            if 'data' in data and isinstance(data['data'], dict):
                log_data = data['data']

                if 'message' in log_data:
                    texts.append(str(log_data['message']))
                if 'command' in log_data:
                    texts.append(str(log_data['command']))
                if 'args' in log_data:
                    texts.append(str(log_data['args']))

            return ' '.join(texts)

        # 기타: 전체 데이터를 문자열로 변환
        return str(data)

    def _check_dangerous_commands(self, text: str) -> list[str]:
        """
        텍스트에서 위험한 명령어를 찾습니다.
        """
        found = []
        text_lower = text.lower()

        for cmd in self.dangerous_commands:
            # 단어 경계를 고려한 검색
            pattern = r'\b' + re.escape(cmd) + r'\b'
            if re.search(pattern, text_lower):
                found.append(cmd)

        return found

    def _get_reason(self, pattern: str, category: str) -> str:
        """
        패턴에 대한 설명을 반환합니다.
        """
        reasons = {
            # Critical
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
            r'[;&|`$]': 'Shell metacharacter detected',
            r'\$\{.*\}': 'Variable expansion',
            r'\$\(.*\)': 'Command substitution',
            r'%COMSPEC%': 'Windows command interpreter reference',
            r'%SYSTEMROOT%': 'Windows system directory reference',
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

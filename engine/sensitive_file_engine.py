from engine.base_engine import BaseEngine
from config_loader import ConfigLoader
from typing import Any
import re


class SensitiveFileEngine(BaseEngine):
    """
    민감 파일 탐지 엔진

    File 이벤트를 분석하여 SSH 키, 암호화폐 지갑, 브라우저 쿠키 등
    민감한 파일 접근을 탐지합니다.
    """

    def __init__(self):
        """민감 파일 탐지 엔진 초기화"""
        # 설정 파일에서 엔진별 설정 로드
        config = ConfigLoader()

        super().__init__(
            consumer_group=config.get_sensitive_file_consumer_group(),
            input_topics=config.get_sensitive_file_input_topics(),
            output_topic=config.get_sensitive_file_output_topic()
        )

        # Critical 패턴 (항상 차단해야 함)
        self.critical_patterns = [
            # SSH Keys
            r'\.ssh[/\\]id_rsa$',
            r'\.ssh[/\\]id_dsa$',
            r'\.ssh[/\\]id_ecdsa$',
            r'\.ssh[/\\]id_ed25519$',
            r'\.ssh[/\\].*\.pem$',
            r'\.ssh[/\\].*_rsa$',

            # Cryptocurrency wallets
            r'wallet\.dat$',
            r'\.bitcoin[/\\]wallet\.dat$',
            r'\.ethereum[/\\]keystore[/\\]',
            r'\.electrum[/\\]wallets[/\\]',

            # Browser stored credentials
            r'appdata[/\\].*[/\\]google[/\\]chrome[/\\].*[/\\]login data$',
            r'appdata[/\\].*[/\\]microsoft[/\\]edge[/\\].*[/\\]login data$',
            r'appdata[/\\].*[/\\]mozilla[/\\]firefox[/\\].*[/\\]logins\.json$',
            r'appdata[/\\].*[/\\]brave[/\\].*[/\\]login data$',

            # Browser cookies
            r'appdata[/\\].*[/\\]google[/\\]chrome[/\\].*[/\\]cookies$',
            r'appdata[/\\].*[/\\]microsoft[/\\]edge[/\\].*[/\\]cookies$',
            r'appdata[/\\].*[/\\]mozilla[/\\]firefox[/\\].*[/\\]cookies\.sqlite$',

            # Cloud provider credentials
            r'\.aws[/\\]credentials$',
            r'\.aws[/\\]config$',
            r'\.azure[/\\]credentials$',
            r'\.gcloud[/\\].*\.json$',

            # Private keys and certificates
            r'.*\.key$',
            r'.*\.pem$',
            r'.*\.ppk$',
            r'.*\.pfx$',
            r'.*\.p12$',
        ]

        # High-risk 패턴
        self.high_risk_patterns = [
            r'password.*\.txt$',
            r'credential.*\.txt$',
            r'secret.*\.txt$',
            r'token.*\.txt$',
            r'\.env$',
            r'\.env\.local$',
            r'\.env\.production$',
            r'config[/\\].*password',
            r'config[/\\].*credential',
        ]

        # Medium-risk 패턴
        self.medium_risk_patterns = [
            r'[/\\]temp[/\\]',
            r'[/\\]tmp[/\\]',
        ]

        # Regex 컴파일 (성능 향상)
        self.critical_regex = [re.compile(p, re.IGNORECASE) for p in self.critical_patterns]
        self.high_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.high_risk_patterns]
        self.medium_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.medium_risk_patterns]

    def process(self, data: Any) -> Any:
        """
        File 이벤트를 분석하여 민감한 파일 접근 탐지

        Args:
            data: 입력 이벤트 (dict)

        Returns:
            탐지 결과 (탐지되지 않으면 None)
        """
        # 들어오는 모든 값 콘솔 출력
        print(f"[SensitiveFileEngine] 입력 데이터: {data}")

        # File 이벤트가 아니면 무시
        if data.get('eventType') != 'File':
            print(f"[SensitiveFileEngine] File 이벤트 아님, 무시: eventType={data.get('eventType')}")
            return None

        # filePath 추출 (최상위 또는 data 객체 내부)
        file_path = data.get('filePath')
        if not file_path and 'data' in data and isinstance(data['data'], dict):
            file_path = data['data'].get('filePath')

        if not file_path:
            print(f"[SensitiveFileEngine] filePath 없음, 무시")
            return None

        print(f"[SensitiveFileEngine] 파일 경로 분석 중: {file_path}")

        # 패턴 매칭
        findings = []
        severity = 'none'

        # Critical 패턴 확인
        for pattern in self.critical_regex:
            if pattern.search(file_path):
                findings.append({
                    'category': 'critical',
                    'pattern': pattern.pattern,
                    'file_path': file_path,
                    'reason': self._get_reason(pattern.pattern)
                })
                severity = 'critical'
                break

        # High-risk 패턴 확인
        if severity == 'none':
            for pattern in self.high_risk_regex:
                if pattern.search(file_path):
                    findings.append({
                        'category': 'high',
                        'pattern': pattern.pattern,
                        'file_path': file_path,
                        'reason': self._get_reason(pattern.pattern)
                    })
                    severity = 'high'
                    break

        # Medium-risk 패턴 확인
        if severity == 'none':
            for pattern in self.medium_risk_regex:
                if pattern.search(file_path):
                    findings.append({
                        'category': 'medium',
                        'pattern': pattern.pattern,
                        'file_path': file_path,
                        'reason': self._get_reason(pattern.pattern)
                    })
                    severity = 'medium'
                    break

        # 탐지된 것만 출력
        if len(findings) > 0:
            # reference 생성 (리스트 형식)
            references = []
            if 'ts' in data:
                references.append(f"id-{data['ts']}")
            # 추가 reference가 있다면 여기에 추가 가능
            # 예: references.append(f"pid-{data.get('pid')}")

            result = {
                'detected': True,
                'reference': references,  # 리스트 형식
                'result': {
                    'detector': 'SensitiveFile',
                    'severity': severity,
                    'findings': findings,
                    'event_type': 'File',
                    'file_path': file_path,
                    'original_event': data
                }
            }
            print(f"[SensitiveFileEngine] ⚠️  민감 파일 탐지! severity={severity}, file={file_path}")
            print(f"[SensitiveFileEngine] 탐지 결과: {result}")
            return result

        print(f"[SensitiveFileEngine] 민감 파일 아님: {file_path}")
        return None

    def _get_reason(self, pattern: str) -> str:
        """패턴에 대한 사람이 읽을 수 있는 이유 반환"""
        reasons = {
            'ssh': 'SSH private key access',
            'wallet': 'Cryptocurrency wallet access',
            'login data': 'Browser stored credentials access',
            'cookies': 'Browser cookies access',
            'aws': 'AWS credentials access',
            'azure': 'Azure credentials access',
            'gcloud': 'Google Cloud credentials access',
            '.key': 'Private key file access',
            '.pem': 'Private certificate access',
            '.ppk': 'PuTTY private key access',
            'password': 'Password file access',
            'credential': 'Credential file access',
            'secret': 'Secret file access',
            'token': 'Token file access',
            '.env': 'Environment configuration access',
            'appdata': 'User application data access',
            'programdata': 'Program data directory access',
            'temp': 'Temporary directory access',
        }

        pattern_lower = pattern.lower()
        for key, reason in reasons.items():
            if key in pattern_lower:
                return reason

        return 'Sensitive file pattern detected'

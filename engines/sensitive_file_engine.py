from engines.base_engine import BaseEngine
from typing import Any
import re


class SensitiveFileEngine(BaseEngine):
    """
    민감 파일 탐지 엔진

    File 이벤트를 분석하여 SSH 키, 암호화폐 지갑, 브라우저 쿠키 등
    민감한 파일 접근을 탐지합니다.
    """

    def __init__(self, db):
        """
        민감 파일 탐지 엔진 초기화 (Queue 제거 버전)
        Args:
            db: Database 인스턴스
        """
        super().__init__(
            db=db,
            name='SensitiveFileEngine',
            event_types=['File']  # File 이벤트만 처리
        )

        # Critical 패턴 (항상 차단해야 함)
        self.critical_patterns = [
            r'\.ssh[/\\]id_rsa$',
            r'\.ssh[/\\]id_dsa$',
            r'\.ssh[/\\]id_ecdsa$',
            r'\.ssh[/\\]id_ed25519$',
            r'\.ssh[/\\].*\.pem$',
            r'\.ssh[/\\].*_rsa$',
            r'wallet\.dat$',
            r'\.bitcoin[/\\]wallet\.dat$',
            r'\.ethereum[/\\]keystore[/\\]',
            r'\.electrum[/\\]wallets[/\\]',
            r'appdata[/\\].*[/\\]google[/\\]chrome[/\\].*[/\\]login data$',
            r'appdata[/\\].*[/\\]microsoft[/\\]edge[/\\].*[/\\]login data$',
            r'appdata[/\\].*[/\\]mozilla[/\\]firefox[/\\].*[/\\]logins\.json$',
            r'appdata[/\\].*[/\\]brave[/\\].*[/\\]login data$',
            r'appdata[/\\].*[/\\]google[/\\]chrome[/\\].*[/\\]cookies$',
            r'appdata[/\\].*[/\\]microsoft[/\\]edge[/\\].*[/\\]cookies$',
            r'appdata[/\\].*[/\\]mozilla[/\\]firefox[/\\].*[/\\]cookies\.sqlite$',
            r'\.aws[/\\]credentials$',
            r'\.aws[/\\]config$',
            r'\.azure[/\\]credentials$',
            r'\.gcloud[/\\].*\.json$',
            r'.*\.key$',
            r'.*\.pem$',
            r'.*\.ppk$',
            r'.*\.pfx$',
            r'.*\.p12$',
        ]

        # High-risk 및 Medium-risk 패턴
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

        self.medium_risk_patterns = [
            r'[/\\]temp[/\\]',
            r'[/\\]tmp[/\\]',
        ]

        # Regex 컴파일
        self.critical_regex = [re.compile(p, re.IGNORECASE) for p in self.critical_patterns]
        self.high_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.high_risk_patterns]
        self.medium_risk_regex = [re.compile(p, re.IGNORECASE) for p in self.medium_risk_patterns]

    def process(self, data: Any) -> Any:
        """
        File 이벤트를 분석하여 민감한 파일 접근 탐지
        BaseEngine에서 이미 File 이벤트만 필터링되어 전달됩니다.
        """
        print(f"[SensitiveFileEngine] 입력 데이터: {data}")

        # filePath 추출
        file_path = data.get('filePath')
        if not file_path and 'data' in data and isinstance(data['data'], dict):
            file_path = data['data'].get('filePath')

        if not file_path:
            print(f"[SensitiveFileEngine] filePath 없음, 무시")
            return None

        print(f"[SensitiveFileEngine] 파일 경로 분석 중: {file_path}")

        findings = []
        severity = 'none'

        # Critical
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

        # High-risk
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

        # Medium-risk
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

        # 결과 출력
        if len(findings) > 0:
            references = []
            if 'ts' in data:
                references.append(f"id-{data['ts']}")

            result = {
                'detected': True,
                'reference': references,
                'result': {
                    'detector': 'SensitiveFile',
                    'severity': severity,
                    'findings': findings,
                    'event_type': 'File',
                    'file_path': file_path,
                    'original_event': data
                }
            }
            print(f"[SensitiveFileEngine] ⚠️ 민감 파일 탐지! severity={severity}, file={file_path}")
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

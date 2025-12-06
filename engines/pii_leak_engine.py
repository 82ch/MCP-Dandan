from engines.base_engine import BaseEngine
from typing import Any
from utils import safe_print
import yara
import os


class PIILeakEngine(BaseEngine):
    """Detection engine for Personal Identifiable Information (PII) leaks using YARA rules."""

    def __init__(self, db):
        super().__init__(
            db=db,
            name='PIILeakEngine',
            event_types=['MCP'],
            producers=['local', 'remote']
        )

        # Load YARA rules from external file
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            yara_file = os.path.join(project_root, 'yara_rules', 'pii_leak_rules.yar')

            if not os.path.exists(yara_file):
                raise FileNotFoundError(f"YARA rules file not found: {yara_file}")

            self.rules = yara.compile(filepath=yara_file)
            safe_print(f"[PIILeakEngine] YARA rules loaded from {yara_file}")

        except Exception as e:
            safe_print(f"[PIILeakEngine] Failed to load YARA rules: {e}")
            self.rules = None

    def should_process(self, data: dict) -> bool:
        """Check if this event should be processed (tools/call requests and responses)."""
        if not super().should_process(data):
            return False

        mcp_data = data.get('data', {})
        message = mcp_data.get('message', {})

        if not isinstance(message, dict):
            return False

        # Process tools/call Request
        if message.get('method') == 'tools/call':
            return True

        # Process tools/call Response
        if mcp_data.get('task') == 'RECV' and 'result' in message:
            return True

        return False

    def process(self, data: Any) -> Any:
        """Process event and detect PII leaks."""
        if not self.rules:
            safe_print("[PIILeakEngine] YARA rules not loaded, skipping")
            return None

        # Extract and analyze text
        analysis_text = self._extract_analysis_text(data)
        if not analysis_text:
            return None

        safe_print(f"[PIILeakEngine] Analyzing: {analysis_text[:100]}...")

        # Detect PII using YARA
        pii_matches = self._detect_pii(analysis_text)
        if not pii_matches:
            return None

        # Calculate severity and score
        severity = self._calculate_severity(pii_matches)
        score = self._calculate_score(severity, len(pii_matches))

        safe_print(f"[PIILeakEngine] Detected {len(pii_matches)} PII(s): {severity} (score={score})")

        # Build result
        return {
            'reference': [f"id-{data['ts']}"] if 'ts' in data else [],
            'result': {
                'detector': 'PIIFilter',
                'severity': severity,
                'evaluation': score,
                'findings': pii_matches,
                'event_type': data.get('eventType', 'Unknown'),
                'original_event': data
            }
        }

    def _detect_pii(self, text: str) -> list[dict]:
        """Detect PII using YARA rules."""
        try:
            matches = self.rules.match(data=text)
            findings = []

            for match in matches:
                for string_match in match.strings:
                    instance = string_match.instances[0]
                    findings.append({
                        'rule': match.rule,
                        'category': match.meta.get('category', 'Unknown'),
                        'description': match.meta.get('description', match.rule),
                        'matched_text': instance.matched_data.decode('utf-8', errors='ignore'),
                        'reason': f"{match.meta.get('description', match.rule)}: {instance.matched_data.decode('utf-8', errors='ignore')}"
                    })

            return findings
        except Exception as e:
            safe_print(f"[PIILeakEngine] YARA matching error: {e}")
            return []

    def _extract_analysis_text(self, data: dict) -> str:
        """Extract text from MCP request and response for analysis."""
        mcp_data = data.get('data', {})
        message = mcp_data.get('message', {})

        if not isinstance(message, dict):
            return ''

        texts = []

        # Extract from Request params
        params = message.get('params', {})
        if isinstance(params, dict):
            if 'arguments' in params:
                texts.append(str(params['arguments']))

        # Extract from Response result
        result = message.get('result', {})
        if isinstance(result, dict):
            # Extract content[].text
            content = result.get('content', [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        texts.append(str(item['text']))

            # Extract structuredContent
            if 'structuredContent' in result:
                texts.append(str(result['structuredContent']))

        return ' '.join(texts)

    def _calculate_severity(self, matches: list[dict]) -> str:
        """Calculate severity based on PII category (Financial/Medical = high, PII = medium)."""
        categories = {m['category'] for m in matches}

        if categories & {'Financial PII', 'Medical PII'}:
            return 'high'
        elif 'PII' in categories:
            return 'medium'
        else:
            return 'low'

    def _calculate_score(self, severity: str, findings_count: int) -> int:
        """Calculate risk score (0-100) based on severity and findings count."""
        base_scores = {'high': 85, 'medium': 50, 'low': 20}
        base_score = base_scores.get(severity, 0)
        findings_bonus = min(findings_count * 5, 15)  # Max +15

        return min(base_score + findings_bonus, 100)

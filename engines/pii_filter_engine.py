from engines.base_engine import BaseEngine
from typing import Any
from utils import safe_print
import yara


# Embedded YARA rules
YARA_RULES = r"""
rule KR_ResidentRegistrationNumber
{
    meta:
        description = "Korean RRN"
        category = "PII"
    strings:
        $rrn1 = /[0-9]{6}-[1-4][0-9]{6}/
    condition:
        $rrn1
}

rule KR_PassportNumber
{
    meta:
        description = "Korean Passport Number"
        category = "PII"
    strings:
        $pass = /[A-Z][0-9]{8}/
    condition:
        $pass
}

rule KR_DriverLicenseNumber
{
    meta:
        description = "Korean Driver License Number"
        category = "PII"
    strings:
        $dl = /[0-9]{2}-[0-9]{2}-[0-9]{6}-[0-9]{2}/
    condition:
        $dl
}

rule KR_MobilePhone
{
    meta:
        description = "Korean Mobile Phone Number"
        category = "PII"
    strings:
        $phone1 = /010-[0-9]{4}-[0-9]{4}/
        $phone2 = /011-[0-9]{3,4}-[0-9]{4}/
        $phone3 = /016-[0-9]{3,4}-[0-9]{4}/
        $phone4 = /017-[0-9]{3,4}-[0-9]{4}/
        $phone5 = /018-[0-9]{3,4}-[0-9]{4}/
        $phone6 = /019-[0-9]{3,4}-[0-9]{4}/
    condition:
        any of them
}

rule Email_Address
{
    meta:
        description = "Generic Email Address"
        category = "PII"
    strings:
        $email = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/
    condition:
        $email
}

rule IPv4_Address
{
    meta:
        description = "IPv4 Address"
        category = "Network PII"
    strings:
        $ip = /[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/
    condition:
        $ip
}

rule US_SSN
{
    meta:
        description = "United States Social Security Number"
        category = "PII"
    strings:
        $ssn = /[0-9]{3}-[0-9]{2}-[0-9]{4}/
    condition:
        $ssn
}

rule Credit_Card_Number
{
    meta:
        description = "Credit Card Number (Visa/Mastercard/Amex/Discover)"
        category = "Financial PII"
    strings:
        $visa = /4[0-9]{15}/
        $visa_short = /4[0-9]{12}/
        $mc   = /5[1-5][0-9]{14}/
        $amex = /3[47][0-9]{13}/
        $disc = /6011[0-9]{12}/
        $disc2 = /65[0-9]{14}/
    condition:
        any of them
}

rule KR_BankAccount
{
    meta:
        description = "Korean Bank Account Number"
        category = "Financial PII"
    strings:
        $acct1 = /[0-9]{3}-[0-9]{2}-[0-9]{6}/
        $acct2 = /[0-9]{3}-[0-9]{3}-[0-9]{6}/
        $acct3 = /[0-9]{2}-[0-9]{6}-[0-9]{1}/
    condition:
        any of them
}

rule Medical_PHI
{
    meta:
        description = "Medical PHI Keyword Indicators"
        category = "Medical PII"
    strings:
        $patient = "Patient" nocase
        $diagnosis = "Diagnosis" nocase
        $medical = "Medical Record" nocase
        $prescription = "Prescription" nocase
        $doctor = "Doctor" nocase
        $clinic = "Clinic" nocase
    condition:
        any of them
}
"""


class PIIFilterEngine(BaseEngine):

    def __init__(self, db):
        super().__init__(
            db=db,
            name='PIIFilterEngine',
            event_types=['MCP'],
            producers=['local', 'remote']
        )

        # Load YARA rules from embedded string
        try:
            self.rules = yara.compile(source=YARA_RULES)
            safe_print(f"[PIIFilterEngine] YARA rules loaded successfully (embedded)")
        except Exception as e:
            safe_print(f"[PIIFilterEngine] Failed to load YARA rules: {e}")
            import traceback
            safe_print(f"[PIIFilterEngine] Traceback: {traceback.format_exc()}")
            self.rules = None

    def should_process(self, data: dict) -> bool:
        if not super().should_process(data):
            return False

        if 'data' in data and isinstance(data['data'], dict):
            mcp_data = data['data']
            if 'message' in mcp_data and isinstance(mcp_data['message'], dict):
                message = mcp_data['message']
                method = message.get('method', '')

                # tools/call Request only
                if method == 'tools/call' and 'id' in message and 'result' not in message:
                    return True

        return False

    def process(self, data: Any) -> Any:
        safe_print(f"[PIIFilterEngine] Processing event")

        if not self.rules:
            safe_print(f"[PIIFilterEngine] YARA rules not loaded, skipping\n")
            return None

        # Extract text from tools/call request
        analysis_text = self._extract_analysis_text(data)

        if not analysis_text:
            safe_print(f"[PIIFilterEngine] No text to analyze\n")
            return None

        safe_print(f"[PIIFilterEngine] Analyzing: {analysis_text[:200]}")

        # Detect PII using YARA
        pii_matches = self._detect_pii(analysis_text)

        if not pii_matches:
            safe_print(f"[PIIFilterEngine] No PII detected\n")
            return None

        # Calculate severity based on matches
        severity = self._calculate_severity(pii_matches)
        score = self._calculate_score(severity, len(pii_matches))

        # Build detail messages
        details = []
        for match in pii_matches:
            detail_msg = f"[{match['rule']}] {match['description']}: '{match['matched_text']}'"
            details.append(detail_msg)

        # Build result
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        result = {
            'reference': references,
            'result': {
                'detector': 'PIIFilter',
                'severity': severity,
                'evaluation': score,
                'detail': details,
                'findings': pii_matches,
                'event_type': data.get('eventType', 'Unknown'),
                'analysis_text': analysis_text[:500] if analysis_text else '',
                'original_event': data
            }
        }

        safe_print(f"[PIIFilterEngine] PII detected! severity={severity}, score={score}, matches={len(pii_matches)}\n")
        return result

    def _detect_pii(self, text: str) -> list[dict]:
        """Detect PII using YARA rules."""
        if not self.rules:
            return []

        try:
            matches = self.rules.match(data=text)
            findings = []

            for match in matches:
                for string_match in match.strings:
                    findings.append({
                        'rule': match.rule,
                        'category': match.meta.get('category', 'Unknown'),
                        'description': match.meta.get('description', match.rule),
                        'matched_text': string_match.instances[0].matched_data.decode('utf-8', errors='ignore'),
                        'offset': string_match.instances[0].offset
                    })

            return findings
        except Exception as e:
            safe_print(f"[PIIFilterEngine] Error during YARA matching: {e}")
            return []

    def _extract_analysis_text(self, data: dict) -> str:
        """Extract text from tools/call request."""
        texts = []

        if 'data' in data and isinstance(data['data'], dict):
            mcp_data = data['data']

            if 'message' in mcp_data and isinstance(mcp_data['message'], dict):
                message = mcp_data['message']

                # Extract from params
                if 'params' in message and isinstance(message['params'], dict):
                    params = message['params']

                    # Tool name
                    if 'name' in params:
                        texts.append(str(params['name']))

                    # Tool arguments
                    if 'arguments' in params:
                        texts.append(str(params['arguments']))

        return ' '.join(texts)

    def _calculate_severity(self, matches: list[dict]) -> str:
        """Calculate severity based on PII types detected."""
        high_risk_categories = ['Financial PII', 'Medical PII']
        medium_risk_categories = ['PII']

        categories = [m['category'] for m in matches]

        if any(cat in high_risk_categories for cat in categories):
            return 'high'
        elif any(cat in medium_risk_categories for cat in categories):
            return 'medium'
        else:
            return 'low'

    def _calculate_score(self, severity: str, findings_count: int) -> int:
        """Calculate risk score based on severity and number of findings."""
        base_scores = {
            'high': 85,
            'medium': 50,
            'low': 20,
            'none': 0
        }

        base_score = base_scores.get(severity, 0)
        findings_bonus = min(findings_count * 5, 15)
        total_score = min(base_score + findings_bonus, 100)

        return total_score

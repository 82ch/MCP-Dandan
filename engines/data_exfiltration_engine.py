from engines.base_engine import BaseEngine
from typing import Any, Dict
import re
from utils import safe_print
from datetime import datetime


class DataExfiltrationEngine(BaseEngine):
    """
    Zero-Click Data Exfiltration Detection Engine

    Detects data exfiltration where email addresses from previous MCP communications
    (tool descriptions, tool responses) are later used in email send tool calls.

    Attack Pattern:
    1. Attacker poisons tool description/response with their email (e.g., "contact: attacker@evil.com")
    2. LLM sees this email in context
    3. LLM calls send_email with poisoned email in to/cc/bcc fields
    4. User data is exfiltrated without user explicitly providing the email
    """

    def __init__(self, db):
        super().__init__(
            db=db,
            name='DataExfiltrationEngine',
            event_types=['MCP'],
            producers=['local', 'remote']
        )

        # In-memory cache of suspicious email addresses found in MCP communications
        # Structure: {email: {'source': str, 'mcpTag': str, 'timestamp': str, 'context': str}}
        self.suspicious_emails: Dict[str, Dict[str, Any]] = {}

        # Email regex pattern (basic but effective)
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )

        # Keywords that indicate email/gmail functionality
        self.email_tool_keywords = [
            'send_email', 'GMAIL_SEND_EMAIL'
        ]

        # Email recipient field names
        self.recipient_fields = ['to', 'cc', 'bcc', 'recipient_email']

    def process(self, data: Any) -> Any:
        """
        Main processing logic:
        1. Extract and track emails from tool descriptions and responses
        2. Check send_email calls for tracked emails
        """
        safe_print(f"[DataExfiltrationEngine] Processing event")
        
        message = data.get('data', {}).get('message', {})
        method = message.get('method', '')
        task = data.get('data', {}).get('task', '')
        
        # Debug/logging: surface key values for triage
        safe_print(f"[DataExfiltrationEngine] Debug - method={method}, task={task}")
        safe_print(f"[DataExfiltrationEngine] Debug - producer={data.get('producer')}, eventType={data.get('eventType')}, ts={data.get('ts')}, mcpTag={self._get_mcp_tag(data)}")
        safe_print(f"[DataExfiltrationEngine] Debug - message={message}")

        # Step 1: Track emails from incoming responses
        if task == 'RECV' and 'result' in message:
            safe_print(f"[DataExfiltrationEngine] Tracking emails from tool call response")
            self._track_emails_from_response(message, data)
            return None  # Just tracking, no detection yet

        # Step 2: Detect exfiltration in outgoing tool calls
        if method == 'tools/call' and task == 'SEND':
            safe_print(f"[DataExfiltrationEngine] Checking for exfiltration in tool call")
            detection_result =  self._detect_exfiltration_in_tool_call(message, data)
            if detection_result:
                return detection_result

        return None

    def _track_emails_from_response(self, message: dict, data: dict):
        """
        Extract and track emails from tool call responses
        Attackers can inject emails in response data
        """
        result = message.get('result', {})

        if not result:
            return

        mcpTag = self._get_mcp_tag(data)
        timestamp = datetime.fromtimestamp(data.get('ts', 0) / 1000).isoformat()

        # Extract all text content from result
        result_text = self._extract_text_from_dict(result)

        if not result_text:
            return

        # Find emails in response
        emails = self.email_pattern.findall(result_text)

        for email in emails:
            # Get context (surrounding text)
            email_index = result_text.find(email)
            start = max(0, email_index - 50)
            end = min(len(result_text), email_index + len(email) + 50)
            context = result_text[start:end]

            self.suspicious_emails[email.lower()] = {
                'source': 'tool_response',
                'mcpTag': mcpTag,
                'timestamp': timestamp,
                'context': context
            }
            safe_print(f"[DataExfiltrationEngine] 📧 Tracked email from tool response: {email} (server: {mcpTag})")

    def _detect_exfiltration_in_tool_call(self, message: dict, data: dict) -> dict | None:
        """
        Check if send_email tool call contains tracked suspicious emails
        This indicates zero-click exfiltration
        """
        params = message.get('params', {})
        arguments = params.get('arguments', {})
        params = arguments.get('params', {})
        tool_name = params.get('tool_slug', '')
        arguments = params.get('arguments', {})

        # Check if this is an email tool
        if not self._is_email_tool(tool_name):
            return None

        # Extract recipient emails from arguments
        recipient_emails = self._extract_recipient_emails(arguments)

        if not recipient_emails:
            return None

        # Check if any recipient was previously tracked (suspicious)
        findings = []
        severity = 'none'

        for field_name, email in recipient_emails:
            email_lower = email.lower()

            if email_lower in self.suspicious_emails:
                # DETECTED: Zero-click exfiltration!
                tracked_info = self.suspicious_emails[email_lower]

                finding = {
                    'category': 'critical',
                    'type': 'zero_click_exfiltration',
                    'tool_name': tool_name,
                    'field': field_name,
                    'exfiltration_target': email,
                    'origin_source': tracked_info['source'],
                    'origin_mcpTag': tracked_info.get('mcpTag', 'unknown'),
                    'origin_tool': tracked_info.get('tool_name', 'unknown'),
                    'origin_timestamp': tracked_info['timestamp'],
                    'origin_context': tracked_info['context'],
                    'reason': f"Email '{email}' in '{field_name}' field originated from {tracked_info['source']} - zero-click exfiltration detected"
                }

                findings.append(finding)
                severity = 'high'

                safe_print(f"[DataExfiltrationEngine] 🚨 ZERO-CLICK EXFILTRATION DETECTED!")
                safe_print(f"  Tool: {tool_name}, Field: {field_name}, Email: {email}")
                safe_print(f"  Origin: {tracked_info['source']} from {tracked_info.get('mcpTag', 'unknown')}")

        if severity == 'none':
            return None

        # Calculate risk score
        score = self._calculate_score(severity, len(findings))

        # Build result
        references = []
        if 'ts' in data:
            references.append(f"id-{data['ts']}")

        result = {
            'reference': references,
            'result': {
                'detector': 'DataExfiltration',
                'severity': severity,
                'evaluation': score,
                'findings': findings,
                'event_type': data.get('eventType', 'Unknown'),
                'producer': data.get('producer', 'unknown'),
                'tool_name': tool_name,
                'tracked_emails_count': len(self.suspicious_emails),
                'original_event': data
            }
        }

        safe_print(f"[DataExfiltrationEngine] Detection complete: severity={severity}, score={score}\n")

        return result

    def _get_mcp_tag(self, data: dict) -> str:
        """Get mcpTag based on producer type"""
        producer = data.get('producer', '')
        if producer == 'local':
            return data.get('mcpTag', 'unknown')
        elif producer == 'remote':
            return data.get('data', {}).get('mcpTag', 'unknown')
        else:
            return data.get('mcpTag') or data.get('data', {}).get('mcpTag', 'unknown')

    def _is_email_tool(self, text: str) -> bool:
        """Check if tool name indicates email functionality"""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.email_tool_keywords)

    def _extract_recipient_emails(self, arguments: dict) -> list[tuple[str, str]]:
        """
        Extract recipient emails from tool call arguments
        Returns list of (field_name, email) tuples
        """
        recipients = []

        for field in self.recipient_fields:
            if field in arguments:
                value = arguments[field]

                # Handle different value types
                if isinstance(value, str):
                    # Single email string
                    emails = self.email_pattern.findall(value)
                    for email in emails:
                        recipients.append((field, email))

                elif isinstance(value, list):
                    # List of emails
                    for item in value:
                        if isinstance(item, str):
                            emails = self.email_pattern.findall(item)
                            for email in emails:
                                recipients.append((field, email))

        return recipients

    def _extract_text_from_dict(self, obj: Any, max_depth: int = 10) -> str:
        """
        Recursively extract all text content from a dictionary/object
        """
        if max_depth <= 0:
            return ""

        texts = []

        if isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, str):
                    texts.append(value)
                elif isinstance(value, (dict, list)):
                    texts.append(self._extract_text_from_dict(value, max_depth - 1))

        elif isinstance(obj, list):
            for item in obj:
                if isinstance(item, str):
                    texts.append(item)
                elif isinstance(item, (dict, list)):
                    texts.append(self._extract_text_from_dict(item, max_depth - 1))

        elif isinstance(obj, str):
            texts.append(obj)

        return ' '.join(texts)

    def _extract_emails_from_schema(self, schema: dict) -> list[tuple[str, str]]:
        """
        Extract emails from JSON schema (descriptions, examples, etc.)
        Returns list of (email, context) tuples
        """
        emails_found = []
        schema_text = self._extract_text_from_dict(schema)

        if schema_text:
            emails = self.email_pattern.findall(schema_text)
            for email in emails:
                # Get context
                email_index = schema_text.find(email)
                start = max(0, email_index - 30)
                end = min(len(schema_text), email_index + len(email) + 30)
                context = schema_text[start:end]
                emails_found.append((email, context))

        return emails_found

    def _calculate_score(self, severity: str, findings_count: int) -> int:
        """
        Calculate risk score based on severity and findings count
        Zero-click exfiltration is always HIGH severity
        """
        base_scores = {
            'high': 95,      # Zero-click exfiltration detected
            'medium': 60,
            'low': 30,
            'none': 0
        }

        base_score = base_scores.get(severity, 0)

        # Add bonus for multiple findings (max +5 points)
        findings_bonus = min(findings_count * 1, 5)

        total_score = min(base_score + findings_bonus, 100)

        return total_score

    def get_tracked_emails_summary(self) -> dict:
        """
        Get summary of currently tracked suspicious emails
        Useful for debugging and monitoring
        """
        return {
            'total_tracked': len(self.suspicious_emails),
            'by_source': {
                'tool_description': sum(1 for e in self.suspicious_emails.values() if e['source'] == 'tool_description'),
                'tool_schema': sum(1 for e in self.suspicious_emails.values() if e['source'] == 'tool_schema'),
                'tool_response': sum(1 for e in self.suspicious_emails.values() if e['source'] == 'tool_response'),
            },
            'emails': list(self.suspicious_emails.keys())
        }

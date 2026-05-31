import re
import urllib.parse
import logging

logger = logging.getLogger(__name__)

class DeepPacketWAF:
    def __init__(self):
        # Advanced SQLi signatures
        self.sqli_patterns = [
            re.compile(r"(?i)(union\s+select|select\s+.*\s+from|insert\s+into|drop\s+table|update\s+.*\s+set|delete\s+from)"),
            re.compile(r"(?i)(\bexec\b|\bexecute\b|\bwaitfor\s+delay\b|\bpg_sleep\b)"),
            re.compile(r"(?i)(or\s+\d+=\d+|and\s+\d+=\d+|or\s+'.*?'='.*?'|and\s+'.*?'='.*?')"),
            re.compile(r"(?i)(--\s|#|\/\*.*?\*\/)")
        ]
        
        # Advanced XSS signatures
        self.xss_patterns = [
            re.compile(r"(?i)(<script.*?>.*?</script>|<script.*?>)"),
            re.compile(r"(?i)(javascript:|vbscript:|data:text\/html)"),
            re.compile(r"(?i)(onload=|onerror=|onmouseover=|prompt\(|alert\(|confirm\()"),
            re.compile(r"(?i)(document\.cookie|document\.write|window\.location)")
        ]
        
    def analyze_payload(self, payload: str) -> bool:
        """
        Performs Deep Packet Inspection on the HTTP payload.
        Returns True if a malicious signature is detected, False otherwise.
        """
        # Hackers often URL encode their payloads to bypass simple filters
        decoded_payload = urllib.parse.unquote(payload)
        
        for pattern in self.sqli_patterns:
            if pattern.search(decoded_payload):
                logger.warning(f"WAF SQLi Signature Detected! Match: {pattern.pattern}")
                return True
                
        for pattern in self.xss_patterns:
            if pattern.search(decoded_payload):
                logger.warning(f"WAF XSS Signature Detected! Match: {pattern.pattern}")
                return True
                
        return False

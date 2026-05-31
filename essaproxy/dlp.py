import re
import logging

logger = logging.getLogger(__name__)

class DLPEngine:
    def __init__(self):
        # Regex for common PII
        # Visa, MasterCard, Amex, Discover
        self.cc_regex = re.compile(r'\b(?:\d[ -]*?){13,16}\b')
        # SSN
        self.ssn_regex = re.compile(r'\b\d{3}[- ]?\d{2}[- ]?\d{4}\b')
        # Email
        self.email_regex = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

    def mask_pii(self, payload: bytes) -> bytes:
        """
        Scans a byte payload for PII and masks it before it goes to the client.
        """
        try:
            text = payload.decode('utf-8')
            
            # Mask Credit Cards
            text = self.cc_regex.sub('****-****-****-****', text)
            
            # Mask SSNs
            text = self.ssn_regex.sub('***-**-****', text)
            
            # Mask Emails (keep first letter and domain)
            def email_mask(match):
                email = match.group(0)
                if '@' in email:
                    name, domain = email.split('@')
                    if len(name) > 1:
                        name = name[0] + '*' * (len(name) - 1)
                    return f"{name}@{domain}"
                return email
                
            text = self.email_regex.sub(email_mask, text)
            
            return text.encode('utf-8')
        except UnicodeDecodeError:
            # If payload is binary (image/video), skip masking
            return payload

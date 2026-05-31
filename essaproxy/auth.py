import base64
import json
import hmac
import hashlib
import time

class JWTValidator:
    def __init__(self, secret: str):
        self.secret = secret.encode('utf-8') if secret else b""

    def _b64_decode(self, data: str) -> bytes:
        # Add padding if needed
        data += '=' * (-len(data) % 4)
        # Convert urlsafe base64 to standard base64 characters
        data = data.replace('-', '+').replace('_', '/')
        return base64.b64decode(data)

    def validate(self, token: str) -> bool:
        if not self.secret or not token:
            return False
            
        parts = token.split('.')
        if len(parts) != 3:
            return False
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Validate signature
        msg = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(self.secret, msg, hashlib.sha256).digest()
        # Encode to urlsafe base64 without padding to match JWT spec
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode('utf-8').rstrip('=')
        
        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            return False
            
        # Validate expiration if present
        try:
            payload_json = self._b64_decode(payload_b64).decode('utf-8')
            payload = json.loads(payload_json)
            if 'exp' in payload:
                if time.time() > payload['exp']:
                    return False
        except Exception:
            return False
            
        return True

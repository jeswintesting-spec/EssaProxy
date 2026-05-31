import json
import logging
import re

logger = logging.getLogger(__name__)

class LLMHallucinationFilter:
    def __init__(self):
        # A lightweight set of heuristics for LLM hallucinations or restricted phrases
        self.forbidden_phrases = [
            r"as an ai language model",
            r"i cannot fulfill this request",
            r"i'm sorry, but i can't",
            r"i don't have personal opinions",
            r"hallucinat", 
            r"ignore previous instructions"
        ]
        self.compiled_phrases = [re.compile(phrase, re.IGNORECASE) for phrase in self.forbidden_phrases]
        
    def filter_response(self, payload: bytes) -> bool:
        """
        Scans a JSON response from an LLM backend for hallucinations or restricted phrases.
        Returns True if the response is SAFE. Returns False if it should be blocked.
        """
        try:
            text = payload.decode('utf-8')
            # Attempt to parse JSON to look specifically at "content" or "text" fields
            try:
                data = json.loads(text)
                # Just stringify the whole json back to check if it's deeply nested
                text_to_scan = json.dumps(data)
            except Exception:
                text_to_scan = text
                
            for regex in self.compiled_phrases:
                if regex.search(text_to_scan):
                    logger.warning(f"LLM Filter: Detected restricted phrase matching '{regex.pattern}'. Blocking response!")
                    return False
                    
            return True
        except UnicodeDecodeError:
            # Binary data, skip filtering
            return True

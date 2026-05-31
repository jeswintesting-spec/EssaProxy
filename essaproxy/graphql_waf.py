import json
import logging

logger = logging.getLogger(__name__)

class GraphQLWAF:
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        
    def analyze_payload(self, body_bytes: bytes) -> bool:
        """
        Parses JSON payload, extracts the GraphQL 'query' string,
        and calculates the AST depth. Returns True if depth > max_depth.
        """
        try:
            payload = json.loads(body_bytes.decode('utf-8'))
            query = payload.get('query', '')
            if not query:
                return False
                
            # Basic AST Depth calculation by counting nested braces
            depth = 0
            max_detected_depth = 0
            
            for char in query:
                if char == '{':
                    depth += 1
                    if depth > max_detected_depth:
                        max_detected_depth = depth
                elif char == '}':
                    depth -= 1
                    
            if max_detected_depth > self.max_depth:
                logger.warning(f"GraphQL WAF: Blocked query with depth {max_detected_depth} (Max allowed: {self.max_depth})")
                return True
                
            return False
        except Exception:
            return False

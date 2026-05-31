import time
import os
import binascii
import logging
import asyncio
import json
import urllib.request

logger = logging.getLogger(__name__)

class Tracer:
    def __init__(self, jaeger_url: str = None):
        self.jaeger_url = jaeger_url # e.g. http://localhost:14268/api/traces
        
    def generate_trace_id(self) -> str:
        # W3C standard: 16 bytes (32 hex chars)
        return binascii.hexlify(os.urandom(16)).decode('utf-8')
        
    def generate_span_id(self) -> str:
        # W3C standard: 8 bytes (16 hex chars)
        return binascii.hexlify(os.urandom(8)).decode('utf-8')

    async def emit_span(self, trace_id: str, span_id: str, name: str, start_time: float, end_time: float, tags: dict):
        """
        Formats a trace span and asynchronously pushes it to Jaeger (via Zipkin v2 API).
        """
        duration_us = int((end_time - start_time) * 1_000_000)
        start_time_us = int(start_time * 1_000_000)
        
        span = {
            "traceId": trace_id,
            "id": span_id,
            "name": name,
            "timestamp": start_time_us,
            "duration": duration_us,
            "localEndpoint": {"serviceName": "essaproxy"},
            "tags": {k: str(v) for k, v in tags.items()}
        }
        
        # If no collector URL is provided, we just log it at debug level
        if not self.jaeger_url:
            logger.debug(f"Distributed Trace [{trace_id}] Span [{name}] Duration: {duration_us/1000:.2f}ms")
            return
            
        try:
            # Send to Zipkin V2 compatible endpoint (supported by Jaeger out of the box)
            # Use asyncio to offload the HTTP POST to prevent blocking the event loop
            await asyncio.to_thread(self._post_span, span)
        except Exception as e:
            logger.error(f"Failed to emit trace span to Jaeger: {e}")
            
    def _post_span(self, span: dict):
        req = urllib.request.Request(
            self.jaeger_url, 
            data=json.dumps([span]).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}, 
            method='POST'
        )
        try:
            with urllib.request.urlopen(req, timeout=1.0) as response:
                pass
        except Exception:
            # Silently fail if Jaeger is down so we don't spam logs or crash the proxy
            pass

import asyncio
import logging
from .config import ProxyConfig

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self):
        self.requests_total = 0
        self.cache_hits_total = 0
        self.rate_limit_drops = 0
        self.waf_blocks_total = 0

    def generate_metrics(self, config: ProxyConfig) -> str:
        lines = []
        
        lines.append("# HELP essaproxy_requests_total Total number of HTTP requests processed")
        lines.append("# TYPE essaproxy_requests_total counter")
        lines.append(f"essaproxy_requests_total {self.requests_total}")
        
        lines.append("# HELP essaproxy_cache_hits_total Total number of GET request cache hits")
        lines.append("# TYPE essaproxy_cache_hits_total counter")
        lines.append(f"essaproxy_cache_hits_total {self.cache_hits_total}")
        
        lines.append("# HELP essaproxy_rate_limit_drops Total requests dropped due to rate limiting")
        lines.append("# TYPE essaproxy_rate_limit_drops counter")
        lines.append(f"essaproxy_rate_limit_drops {self.rate_limit_drops}")
        
        lines.append("# HELP essaproxy_waf_blocks_total Total connections dropped by IP Blocklist")
        lines.append("# TYPE essaproxy_waf_blocks_total counter")
        lines.append(f"essaproxy_waf_blocks_total {self.waf_blocks_total}")
        
        # We will collect the connection gauges and health status in a unified pass
        conn_lines = []
        health_lines = []
        
        seen_backends = set()
        for backends in config.routes.values():
            for b in backends:
                if b.url not in seen_backends:
                    seen_backends.add(b.url)
                    conn_lines.append(f'essaproxy_active_connections{{backend="{b.url}"}} {b.active_connections}')
                    healthy = 1 if b.healthy else 0
                    health_lines.append(f'essaproxy_backend_healthy{{backend="{b.url}"}} {healthy}')
        
        lines.append("# HELP essaproxy_active_connections Active connections per backend")
        lines.append("# TYPE essaproxy_active_connections gauge")
        lines.extend(conn_lines)
        
        lines.append("# HELP essaproxy_backend_healthy Status of backend (1=healthy, 0=dead)")
        lines.append("# TYPE essaproxy_backend_healthy gauge")
        lines.extend(health_lines)
                    
        return "\n".join(lines) + "\n"

class MetricsServer:
    def __init__(self, port: int, config: ProxyConfig, collector: MetricsCollector):
        self.port = port
        self.config = config
        self.collector = collector
        self.server = None

    async def start(self):
        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                '0.0.0.0',
                self.port
            )
            logger.info(f"Prometheus Metrics Server listening on http://0.0.0.0:{self.port}/metrics")
        except Exception as e:
            logger.error(f"Failed to start Metrics Server on port {self.port}: {e}")

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            request_data = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), timeout=2.0)
            if b"GET /metrics" in request_data:
                metrics_data = self.collector.generate_metrics(self.config)
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; version=0.0.4\r\n"
                    b"Connection: close\r\n"
                    + f"Content-Length: {len(metrics_data)}\r\n".encode('utf-8') +
                    b"\r\n"
                ) + metrics_data.encode('utf-8')
            else:
                response = b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n"
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

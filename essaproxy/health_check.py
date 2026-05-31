import asyncio
import logging
from typing import List
from .config import ProxyConfig, BackendServer

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.running = False
        self.task = None

    async def start(self):
        self.running = True
        self.task = asyncio.create_task(self._health_check_loop())
        logger.info("Health checker started")

    async def stop(self):
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Health checker stopped")

    def _get_all_backends(self):
        all_backends = []
        seen = set()
        for backends in self.config.routes.values():
            for b in backends:
                if b.url not in seen:
                    seen.add(b.url)
                    all_backends.append(b)
        return all_backends

    async def _health_check_loop(self):
        while self.running:
            unique_backends = self._get_all_backends()
            tasks = [self._check_server(server) for server in unique_backends]
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.sleep(self.config.health_check_interval)

    async def _check_server(self, server: BackendServer):
        try:
            # We will do a simple TCP connection check.
            # For a more advanced Layer 7 check, we could send an HTTP GET request to self.config.health_check_path
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(server.host, server.port),
                timeout=self.config.health_check_timeout
            )
            
            # Send simple HTTP request
            request = f"GET {self.config.health_check_path} HTTP/1.0\r\nHost: {server.host}\r\n\r\n"
            writer.write(request.encode('utf-8'))
            await writer.drain()
            
            # Read response
            response = await asyncio.wait_for(
                reader.read(1024),
                timeout=self.config.health_check_timeout
            )
            
            writer.close()
            await writer.wait_closed()
            
            if not server.healthy:
                logger.info(f"Server {server.url} is now HEALTHY")
                server.healthy = True
        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            if server.healthy:
                logger.warning(f"Server {server.url} is now DEAD (reason: {str(e) or type(e).__name__})")
                server.healthy = False

import asyncio
import logging
from typing import Dict, Set

logger = logging.getLogger(__name__)

class SSEMultiplexer:
    def __init__(self):
        # Maps an SSE path (e.g. /api/stream) to a set of client writers
        self.streams: Dict[str, Set[asyncio.StreamWriter]] = {}
        # Maps an SSE path to the backend reader task
        self.backend_tasks: Dict[str, asyncio.Task] = {}

    async def subscribe(self, path: str, client_writer: asyncio.StreamWriter, proxy_instance):
        """
        Subscribes a client to the SSE multiplexer. If no backend connection exists
        for this path, it establishes exactly one.
        """
        if path not in self.streams:
            self.streams[path] = set()
            self.backend_tasks[path] = asyncio.create_task(self._connect_backend(path, proxy_instance))
            
        self.streams[path].add(client_writer)
        logger.info(f"SSE Multiplexer: Client joined {path}. Total clients sharing one connection: {len(self.streams[path])}")
        
        try:
            # Hold the client connection open forever until client disconnects
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if path in self.streams:
                self.streams[path].discard(client_writer)
                if len(self.streams[path]) == 0:
                    logger.info(f"SSE Multiplexer: No more clients for {path}. Closing backend stream.")
                    task = self.backend_tasks.pop(path, None)
                    if task:
                        task.cancel()
                    del self.streams[path]
                    
    async def _connect_backend(self, path: str, proxy_instance):
        try:
            # Find backend server using standard Load Balancer
            selected_lb = proxy_instance.load_balancers.get(path)
            if not selected_lb:
                selected_lb = proxy_instance.load_balancers.get('/')
                
            backend = selected_lb.get_server("127.0.0.1", None)
            if not backend:
                return
                
            backend_reader, backend_writer = await asyncio.wait_for(
                asyncio.open_connection(backend.host, backend.port),
                timeout=3.0
            )
            
            # Initiate standard SSE request
            request = f"GET {path} HTTP/1.1\r\nHost: {backend.host}\r\nAccept: text/event-stream\r\nConnection: keep-alive\r\n\r\n".encode()
            backend_writer.write(request)
            await backend_writer.drain()
            
            # Read streaming bytes and fan-out broadcast to all connected clients!
            while True:
                data = await backend_reader.read(4096)
                if not data:
                    break
                    
                if path in self.streams:
                    dead_clients = set()
                    for writer in list(self.streams[path]):
                        try:
                            writer.write(data)
                            await writer.drain()
                        except Exception:
                            dead_clients.add(writer)
                            
                    for dead in dead_clients:
                        self.streams[path].discard(dead)
                            
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"SSE Multiplexer Backend Error for {path}: {e}")
        finally:
            if 'backend_writer' in locals():
                backend_writer.close()

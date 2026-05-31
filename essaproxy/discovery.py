import asyncio
import json
import logging
import socket
from typing import Dict, List, Any
from .config import BackendServer

logger = logging.getLogger(__name__)

class DockerServiceDiscovery:
    def __init__(self, proxy, interval: int = 10):
        self.proxy = proxy
        self.interval = interval
        self.task: asyncio.Task = None
        self.docker_sock = "/var/run/docker.sock"

    async def start(self):
        if not self.proxy.config.docker_discovery:
            return
            
        self.task = asyncio.create_task(self._discovery_loop())
        logger.info(f"Docker Service Discovery started (polling every {self.interval}s)")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _fetch_containers(self) -> List[Dict[str, Any]]:
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(2.0)
            client.connect(self.docker_sock)
            
            request = b"GET /containers/json HTTP/1.0\r\n\r\n"
            client.sendall(request)
            
            response = bytearray()
            while True:
                chunk = client.recv(8192)
                if not chunk:
                    break
                response.extend(chunk)
                
            client.close()
            
            if b"\r\n\r\n" in response:
                _, body = response.split(b"\r\n\r\n", 1)
                return json.loads(body.decode('utf-8'))
        except FileNotFoundError:
            # Docker socket not mounted
            return []
        except Exception as e:
            logger.error(f"Failed to fetch Docker containers: {e}")
            
        return []

    async def _discovery_loop(self):
        while True:
            try:
                # We offload the blocking socket call to a thread
                containers = await asyncio.to_thread(self._fetch_containers)
                
                new_routes: Dict[str, List[BackendServer]] = {}
                discovered = False
                
                for container in containers:
                    labels = container.get("Labels", {})
                    if labels.get("essaproxy.enable") == "true":
                        discovered = True
                        route = labels.get("essaproxy.route", "/")
                        port = int(labels.get("essaproxy.port", "80"))
                        weight = int(labels.get("essaproxy.weight", "1"))
                        
                        # Get IP Address (usually from bridge or custom network)
                        networks = container.get("NetworkSettings", {}).get("Networks", {})
                        ip_address = None
                        for net_name, net_info in networks.items():
                            ip_address = net_info.get("IPAddress")
                            if ip_address:
                                break
                                
                        if ip_address:
                            if route not in new_routes:
                                new_routes[route] = []
                            new_routes[route].append(BackendServer(
                                host=ip_address,
                                port=port,
                                weight=weight
                            ))
                            
                # If we discovered ANY containers with labels, we dynamically override the config routes!
                if discovered:
                    # Check if routes actually changed to avoid unnecessary reloads
                    routes_changed = self._routes_changed(self.proxy.config.routes, new_routes)
                    if routes_changed:
                        logger.info("Docker Topology Changed! Dynamically reloading proxy routes...")
                        
                        # Override existing static routes with dynamic Docker routes
                        merged_routes = {}
                        for path, backends in self.proxy.config.routes.items():
                            merged_routes[path] = list(backends)
                            
                        for path, backends in new_routes.items():
                            merged_routes[path] = backends
                            
                        # Update ProxyConfig
                        new_config = self.proxy.config
                        new_config.routes = merged_routes
                        
                        # Reload proxy (which updates load balancers instantly)
                        self.proxy.reload_config(new_config)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Docker discovery error: {e}")
                
            await asyncio.sleep(self.interval)
            
    def _routes_changed(self, old_routes, new_routes) -> bool:
        old_repr = {p: sorted([f"{b.host}:{b.port}:{b.weight}" for b in bs]) for p, bs in old_routes.items()}
        new_repr = {p: sorted([f"{b.host}:{b.port}:{b.weight}" for b in bs]) for p, bs in new_routes.items()}
        
        for path, servers in new_repr.items():
            if path not in old_repr or old_repr[path] != servers:
                return True
        return False

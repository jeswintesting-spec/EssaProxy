import asyncio
import logging
import traceback
import ssl
import traceback
import gzip
from typing import Optional, Tuple
from .config import ProxyConfig, BackendServer
from .load_balancer import create_load_balancer
from .rate_limiter import TokenBucketRateLimiter
from .health_check import HealthChecker
from .cache import ResponseCache
from .metrics import MetricsCollector, MetricsServer
from .auth import JWTValidator
from .discovery import DockerServiceDiscovery
from .waf import DeepPacketWAF
from .geoip import GeoIPResolver
from .chaos import ChaosEngine
from .admin import AdminServer
from .plugins import PluginManager
from .autossl import AutoSSLManager
from .websocket import WebSocketBackplane
from .tracing import Tracer
from .dlp import DLPEngine
from .ha import HAClusterManager
from .graphql_waf import GraphQLWAF
from .sse import SSEMultiplexer
from .tarpit import TarpitEngine
from .wasm_edge import WasmEdgeEngine
from .llm_filter import LLMHallucinationFilter
import random

logger = logging.getLogger(__name__)

class EssaProxy:
    def __init__(self, config: ProxyConfig):
        self.config = config
        self.redis_client = None
        if config.redis_url:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(config.redis_url)
            except ImportError:
                logger.warning("redis library not installed. Distributed state disabled.")
                
        self.load_balancer = create_load_balancer(config)
        self.rate_limiter = TokenBucketRateLimiter(
            config.rate_limit_capacity, config.rate_limit_rate, self.redis_client, config.geo_rate_limits
        )
        self.health_checker = HealthChecker(config)
        self.cache = ResponseCache(max_size_bytes=config.cache_max_size, redis_client=self.redis_client)
        self.active_tasks = set()
        self.server: Optional[asyncio.AbstractServer] = None
        self.ssl_server: Optional[asyncio.AbstractServer] = None
        self.jwt_validator = JWTValidator(config.jwt_secret) if config.jwt_secret else None
        self.metrics_collector = MetricsCollector()
        self.metrics_server = MetricsServer(config.metrics_port, config, self.metrics_collector)
        self.discovery = DockerServiceDiscovery(self)
        self.dpi_waf = DeepPacketWAF() if config.enable_dpi_waf else None
        self.geoip_resolver = GeoIPResolver(self.redis_client)
        self.chaos_engine = ChaosEngine(config.chaos)
        self.admin_server = AdminServer(self)
        self.plugin_manager = PluginManager(config.plugins_dir)
        self.plugin_manager.load_plugins()
        self.autossl = AutoSSLManager(config.autossl_domain, config.autossl_email) if config.autossl_domain else None
        self.ws_backplane = WebSocketBackplane(self.redis_client)
        self.tracer = Tracer(config.jaeger_url) if config.enable_tracing else None
        self.dlp_engine = DLPEngine() if config.enable_dlp else None
        self.ha_manager = HAClusterManager(self.redis_client)
        self.graphql_waf = GraphQLWAF(config.graphql_max_depth) if config.enable_graphql_waf else None
        self.sse_multiplexer = SSEMultiplexer()
        self.tarpit_engine = TarpitEngine() if config.enable_tarpit else None
        self.wasm_engine = WasmEdgeEngine(config.wasm_plugins_dir)
        self.llm_filter = LLMHallucinationFilter() if config.enable_llm_filter else None
        self.load_balancers = {}
        self._init_load_balancers()

    def _init_load_balancers(self):
        self.load_balancers = {}
        # Sort routes by length descending so more specific routes match first (e.g. /api before /)
        sorted_routes = sorted(self.config.routes.items(), key=lambda x: len(x[0]), reverse=True)
        for path, backends in sorted_routes:
            self.load_balancers[path] = create_load_balancer(self.config.algorithm, backends)

    def reload_config(self, new_config: ProxyConfig):
        logger.info("Reloading configuration dynamically...")
        
        # Preserve active_connections and healthy status of existing backends across all routes
        existing_backends = {}
        for backends in self.config.routes.values():
            for b in backends:
                existing_backends[b.url] = b
                
        for path, backends in new_config.routes.items():
            merged = []
            for b in backends:
                if b.url in existing_backends:
                    merged.append(existing_backends[b.url])
                else:
                    merged.append(b)
            new_config.routes[path] = merged
            
        # Re-create load balancers based on new config routes
        self.config = new_config
        self._init_load_balancers()
        logger.info(f"Load balancing algorithm is {new_config.algorithm}")
        
        # Update Rate Limiter
        self.rate_limiter.capacity = new_config.rate_limit_capacity
        self.rate_limiter.rate = new_config.rate_limit_rate
        
        # Update Health Checker config reference
        self.health_checker.config = new_config
        
        # Update Cache config
        self.cache.max_size_bytes = new_config.cache_max_size
        if new_config.cache_ttl == 0:
            self.cache.clear()
            
        # Update metrics config reference
        self.metrics_server.config = new_config
        
        # Update JWT Auth and WAF
        self.jwt_validator = JWTValidator(new_config.jwt_secret) if new_config.jwt_secret else None
        self.dpi_waf = DeepPacketWAF() if new_config.enable_dpi_waf else None
        
        # Update Chaos Engine
        self.chaos_engine.config = new_config.chaos
        
        # Reload Plugins
        self.plugin_manager.plugins_dir = new_config.plugins_dir
        self.plugin_manager.load_plugins()
        
        logger.info("Configuration reloaded successfully")

    async def start(self):
        await self.health_checker.start()
        await self.metrics_server.start()
        await self.discovery.start()
        await self.ws_backplane.start()
        await self.ha_manager.start()
        
        # Start HTTP server
        self.server = await asyncio.start_server(
            self.handle_client_wrapper,
            self.config.host,
            self.config.port
        )
        
        addr = self.server.sockets[0].getsockname()
        logger.info(f"EssaProxy serving HTTP on {addr}")
        
        # Start HTTPS server if SSL is configured
        ssl_context = None
        if self.autossl:
            await self.autossl.provision_certificate()
            ssl_context = self.autossl.ssl_context
        elif self.config.ssl_cert and self.config.ssl_key:
            try:
                ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ssl_context.load_cert_chain(self.config.ssl_cert, self.config.ssl_key)
                
                # Zero-Trust mTLS
                if self.config.mtls_ca_cert:
                    ssl_context.verify_mode = ssl.CERT_REQUIRED
                    ssl_context.load_verify_locations(cafile=self.config.mtls_ca_cert)
                    logger.info("Zero-Trust mTLS Enabled. Requiring cryptographically signed Client Certificates.")
            except Exception as e:
                logger.error(f"Failed to start static HTTPS server: {e}")
                
        if ssl_context:
            try:
                self.ssl_server = await asyncio.start_server(
                    self.handle_client_wrapper,
                    self.config.host,
                    self.config.ssl_port,
                    ssl=ssl_context
                )
                ssl_addr = self.ssl_server.sockets[0].getsockname()
                logger.info(f"EssaProxy serving HTTPS on {ssl_addr}")
            except Exception as e:
                logger.error(f"Failed to start HTTPS server: {e}")
        
        logger.info(f"Load Balancing Algorithm: {self.config.algorithm}")
        logger.info(f"Rate Limiting: {self.config.rate_limit_rate} req/s (burst {self.config.rate_limit_capacity})")
        
        servers = [self.server.serve_forever()]
        if self.ssl_server:
            servers.append(self.ssl_server.serve_forever())
            
        await asyncio.gather(*servers)

    async def stop(self):
        logger.info("Initiating graceful shutdown (Connection Draining)...")
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        if self.ssl_server:
            self.ssl_server.close()
            await self.ssl_server.wait_closed()
            
        if self.active_tasks:
            logger.info(f"Draining {len(self.active_tasks)} active connections (Timeout: {self.config.drain_timeout}s)...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.active_tasks, return_exceptions=True),
                    timeout=self.config.drain_timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Connection draining timed out. Forcefully closing remaining connections.")
                
        await self.health_checker.stop()
        await self.metrics_server.stop()
        await self.discovery.stop()
        logger.info("EssaProxy stopped")

    async def handle_client_wrapper(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        task = asyncio.current_task()
        self.active_tasks.add(task)
        
        trace_id = None
        span_id = None
        start_time = time.time()
        
        if self.tracer:
            trace_id = self.tracer.generate_trace_id()
            span_id = self.tracer.generate_span_id()
            
        try:
            await self.handle_client(client_reader, client_writer, trace_id, span_id)
        finally:
            self.active_tasks.discard(task)
            if self.tracer:
                end_time = time.time()
                try:
                    client_ip = client_writer.get_extra_info('peername')[0]
                except Exception:
                    client_ip = "unknown"
                asyncio.create_task(self.tracer.emit_span(
                    trace_id, span_id, "HTTP Proxy Request", start_time, end_time, {"client_ip": client_ip}
                ))

    async def handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter, trace_id: str = None, span_id: str = None):
        if self.ha_manager and not self.ha_manager.is_leader and self.redis_client:
            response = b"HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n\r\nNode is in STANDBY mode."
            client_writer.write(response)
            try:
                await client_writer.drain()
            except Exception:
                pass
            client_writer.close()
            return
            
        client_address = client_writer.get_extra_info('peername')
        if not client_address:
            client_writer.close()
            return
            
        client_ip = client_address[0]
        
        country_code = await self.geoip_resolver.get_country(client_ip)
        
        # 0. Lightweight WAF (IP Blocklist)
        if client_ip in self.config.blocked_ips:
            self.metrics_collector.waf_blocks_total += 1
            logger.warning(f"WAF BLOCK: Dropped connection from blocklisted IP {client_ip} ({country_code})")
            client_writer.close()
            return
        self.metrics_collector.requests_total += 1
        
        # 1.5 Rate Limiting Check
        allowed = await self.rate_limiter.allow_request(client_ip)
        if not allowed:
            self.metrics_collector.rate_limit_blocks_total += 1
            if self.config.enable_tarpit and self.tarpit_engine:
                asyncio.create_task(self.tarpit_engine.trap(client_writer, client_ip))
                return
            response = (
                b"HTTP/1.1 429 Too Many Requests\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                b"429 Too Many Requests\n"
            )
            client_writer.write(response)
            await client_writer.drain()
            client_writer.close()
            return
            
        # 1.7 Chaos Engineering (Fault Injection)
        if self.chaos_engine:
            fault = await self.chaos_engine.inject_faults()
            if fault == 'drop':
                client_writer.close()
                return
            elif fault == 'error':
                response = (
                    b"HTTP/1.1 500 Internal Server Error\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    b"500 Internal Server Error: Chaos Engine Fault Injected.\n"
                )
                client_writer.write(response)
                await client_writer.drain()
                client_writer.close()
                return

        # 2. Read initial HTTP request (Headers)
        try:
            # Read until the end of HTTP headers (\r\n\r\n)
            header_data = await client_reader.readuntil(b'\r\n\r\n')
        except asyncio.exceptions.IncompleteReadError:
            # Client closed connection early
            client_writer.close()
            return
        except asyncio.exceptions.LimitOverrunError:
            # Headers too large
            client_writer.close()
            return
        except Exception as e:
            logger.error(f"Error reading headers from {client_ip}: {e}")
            client_writer.close()
            return
            
        # 2.05 Edge Compute Plugins
        plugin_context = await self.plugin_manager.execute_request_plugins(client_ip, header_data)
        if plugin_context.get("drop"):
            logger.warning(f"Edge Plugin dropped connection from {client_ip}")
            client_writer.close()
            return
        if plugin_context.get("short_circuit_response"):
            client_writer.write(plugin_context["short_circuit_response"])
            await client_writer.drain()
            client_writer.close()
            return
            
        # Re-assign header data in case plugins modified it
        header_data = plugin_context.get("header_data", header_data)
            
        is_attacker = False
        is_honeypot_reroute = False
        # 2.1 Deep-Packet Inspection (WAF)
        if self.dpi_waf:
            is_malicious = self.dpi_waf.analyze_payload(header_data)
            if is_malicious:
                self.metrics_collector.waf_blocks_total += 1
                logger.warning(f"WAF Blocked malicious request from {client_ip}")
                
                if self.config.enable_honeypot and self.config.honeypot_backend:
                    logger.info(f"Honeypot: Rerouting attacker {client_ip} to honeypot backend.")
                    is_honeypot_reroute = True
                elif self.config.enable_tarpit and self.tarpit_engine:
                    asyncio.create_task(self.tarpit_engine.trap(client_writer, client_ip))
                    return
                else:
                    response = (
                        b"HTTP/1.1 403 Forbidden\r\n"
                        b"Content-Type: text/plain\r\n"
                        b"Connection: close\r\n"
                        b"\r\n"
                        b"403 Forbidden: WAF rule triggered.\n"
                    )
                    client_writer.write(response)
                    await client_writer.drain()
                    client_writer.close()
                    return

        # 2.5 Extract Method and Path
        method = "UNKNOWN"
        path = "/"
        try:
            first_line = header_data.split(b'\r\n')[0].decode('utf-8')
            parts = first_line.split(' ')
            if len(parts) >= 2:
                method = parts[0].upper()
                path = parts[1]
        except Exception:
            pass
            
        # 2.5.2 WASM Edge Compute Filter
        if not self.wasm_engine.execute_request_filter(path):
            response = b"HTTP/1.1 403 Forbidden\r\nConnection: close\r\n\r\nBlocked by WASM Edge Policy."
            client_writer.write(response)
            try:
                await client_writer.drain()
            except Exception:
                pass
            client_writer.close()
            return
            
        # 2.5.5 Admin GUI Intercept
        if path.startswith("/admin"):
            await self.admin_server.handle_request(client_reader, client_writer, method, path, header_data)
            return

        # 2.6 Detect WebSocket & Gzip
        headers_str = header_data.decode('utf-8', errors='ignore')
        headers_lower = headers_str.lower()
        is_websocket = "upgrade: websocket" in headers_lower
        client_accepts_gzip = "accept-encoding: " in headers_lower and "gzip" in headers_lower

        if is_websocket:
            logger.info(f"WebSocket Upgrade detected for {client_ip} on path {path}")
            
            # Check for Redis Backplane intercept
            if self.config.enable_ws_backplane and path.startswith("/ws/"):
                sec_websocket_key = None
                for line in headers_str.split('\r\n'):
                    if line.lower().startswith('sec-websocket-key:'):
                        sec_websocket_key = line.split(':')[1].strip()
                        break
                
                if sec_websocket_key:
                    logger.info(f"Intercepting WebSocket connection for Redis Backplane from {client_ip}")
                    await self.ws_backplane.handle_client(client_reader, client_writer, sec_websocket_key)
                    return
                    
        # 2.6.5 SSE Multiplexer Check
        is_sse = "text/event-stream" in headers_lower and method == "GET"
        if is_sse and self.config.enable_sse_multiplexer:
            logger.info(f"SSE Multiplexer intercepted request for {path}")
            await self.sse_multiplexer.subscribe(path, client_writer, self)
            return

        # 2.7 API Gateway JWT Authentication
        is_protected = any(path.startswith(route) for route in self.config.protected_routes)
        if is_protected:
            authorized = False
            if self.jwt_validator:
                for line in headers_str.split('\r\n'):
                    if line.lower().startswith('authorization: bearer '):
                        token = line[22:].strip()
                        if self.jwt_validator.validate(token):
                            authorized = True
                        break
            
            if not authorized:
                self.metrics_collector.waf_blocks_total += 1
                logger.warning(f"Unauthorized access attempt to protected route {path} from {client_ip}")
                response = (
                    b"HTTP/1.1 401 Unauthorized\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    b'{"error": "Unauthorized"}\n'
                )
                client_writer.write(response)
                await client_writer.drain()
                client_writer.close()
                return

        # 2.8 GraphQL WAF
        if self.config.enable_graphql_waf and path.startswith("/graphql") and self.graphql_waf:
            content_length = 0
            for line in headers_str.split('\r\n'):
                if line.lower().startswith('content-length:'):
                    try:
                        content_length = int(line.split(':')[1].strip())
                    except Exception:
                        pass
                    break
                    
            if 0 < content_length < 1024 * 1024:
                try:
                    body_data = await client_reader.readexactly(content_length)
                    if self.graphql_waf.analyze_payload(body_data):
                        response = (
                            b"HTTP/1.1 403 Forbidden\r\n"
                            b"Content-Type: application/json\r\n"
                            b"Connection: close\r\n"
                            b"\r\n"
                            b'{"error": "GraphQL query too complex."}\n'
                        )
                        client_writer.write(response)
                        await client_writer.drain()
                        client_writer.close()
                        return
                    graphql_body = body_data
                except Exception:
                    pass

        # Check Cache for GET requests (SKIP if WebSocket)
        cache_key = path
        if method == "GET" and self.config.cache_ttl > 0 and not is_websocket:
            cached_data = await self.cache.get(cache_key)
            if cached_data:
                self.metrics_collector.cache_hits_total += 1
                # Add a custom header to show it was a cache hit
                response_str = cached_data.decode('utf-8', errors='ignore')
                
                if "\r\n\r\n" in response_str:
                    headers_part, body_part = cached_data.split(b"\r\n\r\n", 1)
                    headers_str_mut = headers_part.decode('utf-8', errors='ignore') + "\r\nX-Cache: HIT"
                    
                    if self.config.enable_compression and client_accepts_gzip and b"Content-Encoding:" not in headers_part:
                        compressed_body = gzip.compress(body_part)
                        new_headers = [line for line in headers_str_mut.split("\r\n") if not line.lower().startswith("content-length:")]
                        new_headers.append(f"Content-Length: {len(compressed_body)}")
                        new_headers.append("Content-Encoding: gzip")
                        cached_data = "\r\n".join(new_headers).encode('utf-8') + b"\r\n\r\n" + compressed_body
                    else:
                        cached_data = headers_str_mut.encode('utf-8') + b"\r\n\r\n" + body_part
                
                client_writer.write(cached_data)
                await client_writer.drain()
                client_writer.close()
                return

        # 3. Path-Based Routing & Load Balancing
        selected_lb = None
        for route_path, lb in self.load_balancers.items():
            if path.startswith(route_path):
                selected_lb = lb
                break
                
        if not selected_lb:
            # Fallback to default route if exists
            selected_lb = self.load_balancers.get('/')
            
        if not selected_lb:
            logger.error(f"No route found for path {path}")
            response = (
                b"HTTP/1.1 404 Not Found\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                b"404 Not Found: No routing rule matched.\n"
            )
            client_writer.write(response)
            await client_writer.drain()
            client_writer.close()
            return
            
        # 5. Circuit Breaker & Silent Auto-Retries
        backend_reader = None
        backend_writer = None
        backend = None
        
        if is_attacker and self.config.honeypot_backend:
            backend = self.config.honeypot_backend
            backend.active_connections += 1
            try:
                backend_reader, backend_writer = await asyncio.wait_for(
                    asyncio.open_connection(backend.host, backend.port),
                    timeout=3.0
                )
            except Exception as e:
                backend.active_connections -= 1
                logger.error(f"Failed to connect to honeypot backend {backend.url}: {e}")
        else:
            for attempt in range(self.config.max_retries):
                backend = selected_lb.get_server(client_ip, country_code)
                if not backend:
                    break
                    
                backend.active_connections += 1
                try:
                    # Add a timeout to connection attempt
                    backend_reader, backend_writer = await asyncio.wait_for(
                        asyncio.open_connection(backend.host, backend.port),
                        timeout=3.0
                    )
                    break # Success!
                except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
                    backend.active_connections -= 1
                    logger.warning(f"Circuit Breaker: Backend {backend.url} failed (attempt {attempt+1}). Marking as dead.")
                    backend.healthy = False
                    backend_reader = None
                    backend_writer = None
                    # Loop continues to automatically try the next server

        if not backend_reader or not backend_writer:
            logger.error(f"No healthy backends available to serve request from {client_ip} for path {path}")
            response = (
                b"HTTP/1.1 502 Bad Gateway\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                b"502 Bad Gateway: Upstream connection failed after retries.\n"
            )
            client_writer.write(response)
            await client_writer.drain()
            client_writer.close()
            return
            
        try:
            # 4. Modify Headers (Add X-Forwarded-For and X-Forwarded-Proto)
            is_ssl = client_writer.get_extra_info('sslcontext') is not None
            scheme = "https" if is_ssl else "http"
            modified_headers = self._modify_headers(header_data, client_ip, scheme, trace_id, span_id)
            
            # 4.5 Canary Traffic Shadowing
            shadow_writer = None
            for route_path, shadow_cfg in self.config.shadow_routes.items():
                if path.startswith(route_path):
                    if random.random() < shadow_cfg.get('percent', 0.1):
                        try:
                            _, shadow_writer = await asyncio.wait_for(
                                asyncio.open_connection(shadow_cfg['backend']['host'], shadow_cfg['backend']['port']),
                                timeout=1.0
                            )
                            shadow_writer.write(modified_headers)
                            await shadow_writer.drain()
                            logger.info(f"Traffic Shadowing: Duplicated request to {path} to dark backend.")
                        except Exception as e:
                            logger.warning(f"Failed to connect to shadow backend: {e}")
                            shadow_writer = None
                    break
            
            # Send modified headers to backend
            backend_writer.write(modified_headers)
            if 'graphql_body' in locals():
                backend_writer.write(graphql_body)
            await backend_writer.drain()
            
            # Create bidirectional pipe
            task1 = asyncio.create_task(self._pipe(client_reader, backend_writer, shadow_writer))
            
            if self.config.enable_dlp and not is_websocket:
                task2 = asyncio.create_task(self._buffer_compress_and_send(backend_reader, client_writer, cache_key, client_accepts_gzip, apply_dlp=True))
            elif method == "GET" and self.config.cache_ttl > 0 and not is_websocket:
                task2 = asyncio.create_task(self._buffer_compress_and_send(backend_reader, client_writer, cache_key, client_accepts_gzip, apply_dlp=False))
            else:
                # Use standard infinite pipe for POST/PUT and WebSockets
                task2 = asyncio.create_task(self._pipe(backend_reader, client_writer))
            
            # Wait for either connection to close
            await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
            
        except (ConnectionRefusedError, asyncio.TimeoutError, OSError) as e:
            logger.error(f"Failed to connect to backend {backend.url}: {e}")
            response = (
                b"HTTP/1.1 502 Bad Gateway\r\n"
                b"Content-Type: text/plain\r\n"
                b"Connection: close\r\n"
                b"\r\n"
                b"502 Bad Gateway: Upstream connection failed.\n"
            )
            client_writer.write(response)
            try:
                await client_writer.drain()
            except Exception:
                pass
        finally:
            backend.active_connections -= 1
            client_writer.close()
            try:
                # Need to try to close backend writer if it was created
                backend_writer.close()
            except NameError:
                pass

    def _modify_headers(self, header_data: bytes, client_ip: str, scheme: str, trace_id: str = None, span_id: str = None) -> bytes:
        """
        Parses raw HTTP headers and injects/appends X-Forwarded-For and X-Forwarded-Proto, plus W3C traceparent.
        """
        try:
            # Decode headers to string for manipulation
            headers_str = header_data.decode('utf-8')
        except UnicodeDecodeError:
            # Fallback if invalid utf-8: just prepend X-Forwarded-* after the first line
            lines = header_data.split(b'\r\n')
            if len(lines) > 1:
                x_forwarded = f"X-Forwarded-For: {client_ip}\r\nX-Forwarded-Proto: {scheme}\r\n".encode('utf-8')
                return lines[0] + b'\r\n' + x_forwarded + b'\r\n'.join(lines[1:])
            return header_data
            
        lines = headers_str.split('\r\n')
        if len(lines) < 2:
            return header_data
            
        modified_lines = []
        # First line is the request line: GET /path HTTP/1.1
        modified_lines.append(lines[0])
        
        has_x_forwarded = False
        has_x_proto = False
        
        for line in lines[1:]:
            if line.lower().startswith('x-forwarded-for:'):
                modified_lines.append(f"{line}, {client_ip}")
                has_x_forwarded = True
            elif line.lower().startswith('x-forwarded-proto:'):
                modified_lines.append(f"X-Forwarded-Proto: {scheme}")
                has_x_proto = True
            elif line == "":
                # Empty line indicates end of headers
                if not has_x_forwarded:
                    modified_lines.append(f"X-Forwarded-For: {client_ip}")
                if not has_x_proto:
                    modified_lines.append(f"X-Forwarded-Proto: {scheme}")
                if trace_id and span_id:
                    modified_lines.append(f"traceparent: 00-{trace_id}-{span_id}-01")
                    
                modified_lines.append("") # Keep the empty line
            else:
                modified_lines.append(line)
                
        return '\r\n'.join(modified_lines).encode('utf-8')

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, shadow_writer: asyncio.StreamWriter = None):
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
                
                if shadow_writer:
                    try:
                        shadow_writer.write(data)
                        await shadow_writer.drain()
                    except Exception:
                        shadow_writer.close()
                        shadow_writer = None
        except Exception:
            pass
        finally:
            writer.close()
            if shadow_writer:
                shadow_writer.close()

    async def _buffer_compress_and_send(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cache_key: str, client_accepts_gzip: bool, apply_dlp: bool = False):
        buffer = bytearray()
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                buffer.extend(data)
                if len(buffer) > 5 * 1024 * 1024 and not apply_dlp:
                    # Too big to buffer! Fallback to standard pipe
                    writer.write(buffer)
                    await writer.drain()
                    await self._pipe(reader, writer)
                    return
        except Exception:
            pass

        if not buffer:
            writer.close()
            return

        # 4.5 Live PII Masking (DLP) & LLM Hallucination Filter
        if (apply_dlp and self.dlp_engine) or self.config.enable_llm_filter:
            if b"\r\n\r\n" in buffer:
                headers_part, body_part = buffer.split(b"\r\n\r\n", 1)
                headers_str = headers_part.decode('utf-8', errors='ignore').lower()
                
                if "content-type: application/json" in headers_str or "content-type: text/" in headers_str:
                    # 4.5.1 LLM Hallucination Filter
                    if self.config.enable_llm_filter and self.llm_filter:
                        if not self.llm_filter.filter_response(body_part):
                            response = b"HTTP/1.1 451 Unavailable For Legal Reasons\r\nConnection: close\r\n\r\nBlocked by AI Safety Filter."
                            writer.write(response)
                            writer.close()
                            return
                            
                    # 4.5.2 Live DLP Masking
                    if apply_dlp and self.dlp_engine:
                        masked_body = self.dlp_engine.mask_pii(body_part)
                        
                        if b"content-length:" in headers_part.lower():
                            new_headers = []
                            for line in headers_part.decode('utf-8', errors='ignore').split('\r\n'):
                                if line.lower().startswith('content-length:'):
                                    new_headers.append(f"Content-Length: {len(masked_body)}")
                                else:
                                    new_headers.append(line)
                            headers_part = '\r\n'.join(new_headers).encode('utf-8')
                            
                        buffer = bytearray(headers_part + b"\r\n\r\n" + masked_body)

        # Save to cache UNCOMPRESSED
        if buffer.startswith(b"HTTP/1.1 200") or buffer.startswith(b"HTTP/1.0 200"):
            await self.cache.set(cache_key, bytes(buffer), self.config.cache_ttl)
            
        final_response = bytes(buffer)
        
        # Compress on-the-fly for the client
        if self.config.enable_compression and client_accepts_gzip:
            if b"\r\n\r\n" in buffer:
                headers_part, body_part = buffer.split(b"\r\n\r\n", 1)
                headers_str = headers_part.decode('utf-8', errors='ignore')
                
                # Only compress if not already compressed and body exists
                if "content-encoding:" not in headers_str.lower() and len(body_part) > 100:
                    compressed_body = gzip.compress(body_part)
                    
                    new_headers = [line for line in headers_str.split("\r\n") if not line.lower().startswith("content-length:")]
                    new_headers.append(f"Content-Length: {len(compressed_body)}")
                    new_headers.append("Content-Encoding: gzip")
                    
                    final_response = "\r\n".join(new_headers).encode('utf-8') + b"\r\n\r\n" + compressed_body
                    
        writer.write(final_response)
        try:
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

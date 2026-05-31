from dataclasses import dataclass, field
from typing import List, Dict
import json

@dataclass
class BackendServer:
    host: str
    port: int
    weight: int = 1
    country: str = None
    healthy: bool = True
    active_connections: int = 0

    @property
    def url(self) -> str:
        return f"{self.host}:{self.port}"

@dataclass
class ChaosConfig:
    enabled: bool = False
    fault_percent: float = 0.0      # Overall probability to trigger ANY fault
    latency_ms: int = 0             # if > 0, injects latency
    drop_percent: float = 0.0       # 0.0 to 1.0 (Given a fault occurs, chance it's a drop)
    error_percent: float = 0.0      # 0.0 to 1.0 (Given a fault occurs, chance it's an error)

@dataclass
class ProxyConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    routes: Dict[str, List[BackendServer]] = field(default_factory=dict)
    # Load balancing algorithm: 'round_robin', 'least_connections', 'ip_hash'
    algorithm: str = "round_robin"
    
    # Rate Limiting config
    rate_limit_capacity: int = 100  # Max requests burst
    rate_limit_rate: float = 10.0   # Requests per second per IP
    geo_rate_limits: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    # Health Check config
    health_check_interval: int = 5  # seconds
    health_check_timeout: int = 2   # seconds
    health_check_path: str = "/"    # path to check
    
    # SSL/TLS config
    ssl_cert: str = None
    ssl_key: str = None
    ssl_port: int = 8443
    autossl_domain: str = None
    autossl_email: str = None
    mtls_ca_cert: str = None
    
    # Cache & Compression config
    cache_ttl: int = 10  # Seconds to cache GET responses. 0 disables caching.
    cache_max_size: int = 50 * 1024 * 1024  # 50MB
    enable_compression: bool = True
    
    # Metrics config
    metrics_port: int = 9090
    
    # Security & API Gateway config
    blocked_ips: List[str] = field(default_factory=list)
    enable_dpi_waf: bool = True
    enable_honeypot: bool = False
    honeypot_backend: BackendServer = None
    enable_ws_backplane: bool = False
    enable_dlp: bool = False
    enable_graphql_waf: bool = False
    graphql_max_depth: int = 5
    enable_sse_multiplexer: bool = False
    enable_tarpit: bool = False
    wasm_plugins_dir: str = "./wasm_plugins"
    enable_llm_filter: bool = False
    jwt_secret: str = None
    protected_routes: List[str] = field(default_factory=list)
    
    # OpenTelemetry Tracing
    enable_tracing: bool = False
    jaeger_url: str = None
    
    # Canary Traffic Shadowing
    shadow_routes: Dict[str, Any] = field(default_factory=dict)
    
    # Discovery config
    docker_discovery: bool = False
    
    # Distributed State config
    redis_url: str = None
    
    # Resilience & Chaos config
    max_retries: int = 3
    drain_timeout: int = 15
    chaos: ChaosConfig = field(default_factory=ChaosConfig)
    
    # Edge Compute Plugins
    plugins_dir: str = "plugins"

    @classmethod
    def load_from_file(cls, filepath: str) -> 'ProxyConfig':
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        routes = {}
        # Backward compatibility for flat backends array (maps to '/')
        if 'backends' in data:
            routes['/'] = [BackendServer(host=b['host'], port=b['port'], weight=b.get('weight', 1)) for b in data['backends']]
            
        # Advanced Path-Based Routing
        if 'routes' in data:
            for path, servers in data['routes'].items():
                routes[path] = [BackendServer(host=b['host'], port=b['port'], weight=b.get('weight', 1), country=b.get('country')) for b in servers]
                
        if not routes:
            routes['/'] = []
            
        return cls(
            host=data.get('host', '0.0.0.0'),
            port=data.get('port', 8080),
            routes=routes,
            algorithm=data.get('algorithm', 'round_robin'),
            rate_limit_capacity=data.get('rate_limit_capacity', 100),
            rate_limit_rate=data.get('rate_limit_rate', 10.0),
            health_check_interval=data.get('health_check_interval', 5),
            health_check_timeout=data.get('health_check_timeout', 2),
            health_check_path=data.get('health_check_path', '/'),
            ssl_cert=data.get('ssl_cert'),
            ssl_key=data.get('ssl_key'),
            ssl_port=data.get('ssl_port', 8443),
            autossl_domain=data.get('autossl_domain'),
            autossl_email=data.get('autossl_email'),
            mtls_ca_cert=data.get('mtls_ca_cert'),
            cache_ttl=data.get('cache_ttl', 10),
            cache_max_size=data.get('cache_max_size', 50 * 1024 * 1024),
            enable_compression=data.get('enable_compression', True),
            metrics_port=data.get('metrics_port', 9090),
            blocked_ips=data.get('blocked_ips', []),
            enable_dpi_waf=data.get('enable_dpi_waf', True),
            enable_honeypot=data.get('enable_honeypot', False),
            honeypot_backend=BackendServer(host=data['honeypot_backend']['host'], port=data['honeypot_backend']['port']) if data.get('honeypot_backend') else None,
            enable_ws_backplane=data.get('enable_ws_backplane', False),
            enable_dlp=data.get('enable_dlp', False),
            enable_graphql_waf=data.get('enable_graphql_waf', False),
            graphql_max_depth=data.get('graphql_max_depth', 5),
            enable_sse_multiplexer=data.get('enable_sse_multiplexer', False),
            enable_tarpit=data.get('enable_tarpit', False),
            wasm_plugins_dir=data.get('wasm_plugins_dir', './wasm_plugins'),
            enable_llm_filter=data.get('enable_llm_filter', False),
            jwt_secret=data.get('jwt_secret'),
            protected_routes=data.get('protected_routes', []),
            enable_tracing=data.get('enable_tracing', False),
            jaeger_url=data.get('jaeger_url', None),
            shadow_routes=data.get('shadow_routes', {}),
            max_retries=data.get('max_retries', 3),
            drain_timeout=data.get('drain_timeout', 15),
            docker_discovery=data.get('docker_discovery', False),
            redis_url=data.get('redis_url', None),
            geo_rate_limits=data.get('geo_rate_limits', {}),
            chaos=ChaosConfig(**data.get('chaos', {})),
            plugins_dir=data.get('plugins_dir', 'plugins')
        )

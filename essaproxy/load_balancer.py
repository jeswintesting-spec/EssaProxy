import hashlib
from typing import List, Optional
from .config import BackendServer, ProxyConfig

class LoadBalancer:
    def __init__(self, backends: List[BackendServer]):
        self.backends = backends

    def get_healthy_servers(self, country_code: str = "UNKNOWN") -> List[BackendServer]:
        healthy = [s for s in self.backends if s.healthy]
        
        # GeoIP Filter
        geo_matched = [s for s in healthy if s.country == country_code]
        if geo_matched:
            return geo_matched
            
        # Fallback to servers without a country tag
        neutral = [s for s in healthy if not s.country]
        return neutral if neutral else healthy

    def get_server(self, client_ip: str, country_code: str = "UNKNOWN") -> Optional[BackendServer]:
        raise NotImplementedError

class RoundRobinBalancer(LoadBalancer):
    def __init__(self, backends: List[BackendServer]):
        super().__init__(backends)
        self.current_index = 0

    def get_server(self, client_ip: str, country_code: str = "UNKNOWN") -> Optional[BackendServer]:
        healthy_servers = self.get_healthy_servers(country_code)
        if not healthy_servers:
            return None
        
        server = healthy_servers[self.current_index % len(healthy_servers)]
        self.current_index = (self.current_index + 1) % len(healthy_servers)
        return server

class WeightedRoundRobinBalancer(LoadBalancer):
    def __init__(self, backends: List[BackendServer]):
        super().__init__(backends)
        self.current_index = 0

    def get_server(self, client_ip: str, country_code: str = "UNKNOWN") -> Optional[BackendServer]:
        healthy_servers = self.get_healthy_servers(country_code)
        if not healthy_servers:
            return None
            
        expanded_pool = []
        for server in healthy_servers:
            expanded_pool.extend([server] * server.weight)
            
        if not expanded_pool:
            return None
            
        server = expanded_pool[self.current_index % len(expanded_pool)]
        self.current_index = (self.current_index + 1) % len(expanded_pool)
        return server

class LeastConnectionsBalancer(LoadBalancer):
    def get_server(self, client_ip: str, country_code: str = "UNKNOWN") -> Optional[BackendServer]:
        healthy_servers = self.get_healthy_servers(country_code)
        if not healthy_servers:
            return None
        
        # Select the server with the minimum active connections
        # If there's a tie, min() returns the first one it encounters
        selected_server = min(healthy_servers, key=lambda s: s.active_connections)
        return selected_server

class IPHashBalancer(LoadBalancer):
    def get_server(self, client_ip: str, country_code: str = "UNKNOWN") -> Optional[BackendServer]:
        healthy_servers = self.get_healthy_servers(country_code)
        if not healthy_servers:
            return None
        
        hash_val = int(hashlib.md5(client_ip.encode('utf-8')).hexdigest(), 16)
        index = hash_val % len(healthy_servers)
        return healthy_servers[index]

def create_load_balancer(algorithm: str, backends: List[BackendServer]) -> LoadBalancer:
    if algorithm == "round_robin":
        return RoundRobinBalancer(backends)
    elif algorithm == "weighted_round_robin":
        return WeightedRoundRobinBalancer(backends)
    elif algorithm == "least_connections":
        return LeastConnectionsBalancer(backends)
    elif algorithm == "ip_hash":
        return IPHashBalancer(backends)
    else:
        raise ValueError(f"Unknown load balancing algorithm: {algorithm}")

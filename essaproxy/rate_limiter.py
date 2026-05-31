import time
import asyncio
from typing import Dict
from .config import ProxyConfig

class TokenBucketRateLimiter:
    def __init__(self, capacity: int, rate: float, redis_client=None, geo_limits=None):
        self.capacity = capacity
        self.rate = rate
        # Maps IP address -> [tokens, last_refill_time]
        self.clients: Dict[str, list] = {}
        self.lock = asyncio.Lock()
        self.redis = redis_client
        self.geo_limits = geo_limits or {}

    async def is_allowed(self, client_ip: str, country_code: str = "UNKNOWN") -> bool:
        cap = self.capacity
        rt = self.rate
        if country_code in self.geo_limits:
            cap = self.geo_limits[country_code].get("capacity", cap)
            rt = self.geo_limits[country_code].get("rate", rt)
        if self.redis:
            try:
                # Distributed Fixed-Window Rate Limiting
                current_window = int(time.time())
                key = f"ratelimit:{client_ip}:{current_window}"
                
                async with self.redis.pipeline() as pipe:
                    pipe.incr(key)
                    pipe.expire(key, 2)
                    results = await pipe.execute()
                
                count = results[0]
                # In a pure fixed window without tokens, we use capacity as the max burst per second
                if count > cap:
                    return False
                return True
            except Exception:
                pass # Fallback to local memory limiter if Redis fails

        async with self.lock:
            current_time = time.monotonic()
            
            if client_ip not in self.clients:
                self.clients[client_ip] = [cap - 1, current_time]
                return True
                
            state = self.clients[client_ip]
            tokens, last_time = state
            
            elapsed = current_time - last_time
            # Refill tokens based on elapsed time and rate
            tokens += elapsed * rt
            if tokens > cap:
                tokens = cap
                
            if tokens >= 1.0:
                self.clients[client_ip] = [tokens - 1.0, current_time]
                return True
            else:
                self.clients[client_ip] = [tokens, current_time]
                return False

    @staticmethod
    def get_limiter_for_config(config: ProxyConfig):
        return TokenBucketRateLimiter(config.rate_limit_capacity, config.rate_limit_rate)

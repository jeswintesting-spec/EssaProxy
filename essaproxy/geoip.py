import asyncio
import urllib.request
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class GeoIPResolver:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.local_cache = {} # IP -> Country Code
        
    def _fetch_from_api(self, ip: str) -> Optional[str]:
        # Handle localhost/private networks
        if ip.startswith("127.") or ip.startswith("192.168.") or ip.startswith("10.") or ip == "::1" or ip == "localhost":
            return "LOCAL"
            
        try:
            url = f"http://ip-api.com/json/{ip}"
            req = urllib.request.Request(url, headers={'User-Agent': 'EssaProxy'})
            with urllib.request.urlopen(req, timeout=2.0) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data.get('status') == 'success':
                    return data.get('countryCode')
        except Exception as e:
            logger.error(f"GeoIP Lookup failed for {ip}: {e}")
        return "UNKNOWN"

    async def get_country(self, ip: str) -> str:
        # 1. Fast path: Local RAM Cache
        if ip in self.local_cache:
            return self.local_cache[ip]
            
        # 2. Distributed path: Redis Cache
        if self.redis:
            try:
                cached = await self.redis.get(f"geoip:{ip}")
                if cached:
                    country = cached.decode('utf-8')
                    self.local_cache[ip] = country
                    return country
            except Exception:
                pass
                
        # 3. Slow path: Async external API fetch
        country = await asyncio.to_thread(self._fetch_from_api, ip)
        if not country:
            country = "UNKNOWN"
            
        # 4. Save to caches
        self.local_cache[ip] = country
        if self.redis:
            try:
                await self.redis.setex(f"geoip:{ip}", 86400, country) # Cache for 24 hours
            except Exception:
                pass
                
        return country

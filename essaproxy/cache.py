import time
import asyncio
import logging

logger = logging.getLogger(__name__)

class ResponseCache:
    def __init__(self, max_size_bytes: int = 50 * 1024 * 1024, redis_client=None):
        # Maps path -> (expiration_time_float, response_bytes)
        self.cache = {}
        self.max_size_bytes = max_size_bytes
        self.current_size = 0
        self.lock = asyncio.Lock()
        self.redis = redis_client

    async def get(self, key: str) -> bytes:
        if self.redis:
            try:
                data = await self.redis.get(f"cache:{key}")
                if data:
                    logger.info(f"REDIS CACHE HIT: {key}")
                    return data
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                
        async with self.lock:
            if key in self.cache:
                exp_time, data = self.cache[key]
                if time.time() < exp_time:
                    logger.info(f"LOCAL CACHE HIT: {key}")
                    return data
                else:
                    logger.info(f"LOCAL CACHE EXPIRED: {key}")
                    self._remove(key)
            return None

    async def set(self, key: str, data: bytes, ttl: int):
        if self.redis:
            try:
                await self.redis.setex(f"cache:{key}", ttl, data)
                logger.info(f"REDIS CACHED: {key} for {ttl}s ({len(data)} bytes)")
                return
            except Exception as e:
                logger.error(f"Redis set error: {e}")

        async with self.lock:
            # If item is larger than max cache size, don't cache
            if len(data) > self.max_size_bytes:
                return

            # Simple eviction: if adding this exceeds size, clear everything (simplistic LRU)
            if self.current_size + len(data) > self.max_size_bytes:
                logger.info("Local Cache full. Evicting all items.")
                self.cache.clear()
                self.current_size = 0
                
            self.cache[key] = (time.time() + ttl, data)
            self.current_size += len(data)
            logger.info(f"LOCAL CACHED: {key} for {ttl}s ({len(data)} bytes)")
            
    def _remove(self, key: str):
        if key in self.cache:
            _, data = self.cache.pop(key)
            self.current_size -= len(data)

    def clear(self):
        self.cache.clear()
        self.current_size = 0

import asyncio
import random
import logging
from .config import ChaosConfig

logger = logging.getLogger(__name__)

class ChaosEngine:
    def __init__(self, config: ChaosConfig):
        self.config = config

    async def inject_faults(self) -> str:
        """
        Returns 'drop', 'error', or None.
        May artificially delay execution to inject latency.
        """
        if not self.config.enabled:
            return None
            
        # 1. Latency Injection
        if self.config.latency_ms > 0 and random.random() < self.config.fault_percent:
            # Add +- 50% jitter to make it realistic
            jitter = random.uniform(0.5, 1.5)
            delay = (self.config.latency_ms * jitter) / 1000.0
            logger.warning(f"CHAOS ENGINE: Injecting {delay:.2f}s artificial latency.")
            await asyncio.sleep(delay)
            
        # 2. Connection Drop Injection (Simulates TCP reset or network partition)
        if self.config.drop_percent > 0 and random.random() < self.config.drop_percent:
            logger.warning("CHAOS ENGINE: Simulating Network Partition (DROP).")
            return 'drop'
            
        # 3. HTTP 500 Error Injection (Simulates backend crash)
        if self.config.error_percent > 0 and random.random() < self.config.error_percent:
            logger.warning("CHAOS ENGINE: Simulating Backend Crash (HTTP 500).")
            return 'error'
            
        return None

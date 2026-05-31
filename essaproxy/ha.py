import asyncio
import logging
import uuid
import time

logger = logging.getLogger(__name__)

class HAClusterManager:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.node_id = str(uuid.uuid4())
        self.is_leader = False
        self.leader_task = None
        self.lock_key = "essaproxy:leader_lock"
        
    async def start(self):
        if not self.redis_client:
            logger.warning("HA Cluster: Redis not configured. Node assumes leader role by default.")
            self.is_leader = True
            return
            
        self.leader_task = asyncio.create_task(self._election_loop())
        logger.info(f"HA Cluster: Node {self.node_id} participating in Leader Election.")
        
    async def _election_loop(self):
        while True:
            try:
                # Try to acquire the distributed lock for 5 seconds
                acquired = await self.redis_client.set(self.lock_key, self.node_id, nx=True, ex=5)
                
                if acquired:
                    if not self.is_leader:
                        logger.warning(f"HA Cluster: This node ({self.node_id}) has been elected LEADER!")
                        self.is_leader = True
                    # We are leader, just sleep for a bit before renewing
                    await asyncio.sleep(2)
                else:
                    # Lock is held by someone else, check who it is
                    current_leader = await self.redis_client.get(self.lock_key)
                    if current_leader and current_leader.decode() == self.node_id:
                        # We are still leader, renew the TTL lock
                        await self.redis_client.expire(self.lock_key, 5)
                        await asyncio.sleep(2)
                    else:
                        if self.is_leader:
                            logger.error("HA Cluster: Lost leadership! Transitioning to Standby FOLLOWER.")
                            self.is_leader = False
                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"HA Cluster Election Error: {e}")
                await asyncio.sleep(2)

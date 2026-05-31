import base64
import hashlib
import asyncio
import logging
import struct

logger = logging.getLogger(__name__)

class WebSocketBackplane:
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.clients = set()
        self.pubsub = None
        self.pubsub_task = None

    async def start(self):
        if not self.redis_client:
            logger.warning("WebSocket Backplane: No Redis client available. Falling back to local in-memory broadcast.")
            return
            
        self.pubsub = self.redis_client.pubsub()
        await self.pubsub.subscribe('essa_ws_backplane')
        self.pubsub_task = asyncio.create_task(self._listen_redis())
        logger.info("WebSocket Backplane successfully subscribed to Redis channel 'essa_ws_backplane'")

    async def _listen_redis(self):
        try:
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    data = message['data']
                    # Broadcast to all connected clients on this proxy instance
                    frame = self.encode_frame(data, opcode=1) # text frame
                    for writer in list(self.clients):
                        try:
                            writer.write(frame)
                            await writer.drain()
                        except Exception:
                            self.clients.discard(writer)
        except Exception as e:
            logger.error(f"WebSocket Backplane Redis error: {e}")

    def generate_accept_key(self, sec_websocket_key: str) -> str:
        magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        return base64.b64encode(hashlib.sha1((sec_websocket_key + magic).encode()).digest()).decode()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, sec_websocket_key: str):
        # 1. Terminate the connection and upgrade to WebSocket
        accept_key = self.generate_accept_key(sec_websocket_key)
        response = (
            b"HTTP/1.1 101 Switching Protocols\r\n"
            b"Upgrade: websocket\r\n"
            b"Connection: Upgrade\r\n"
            + f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n".encode()
        )
        writer.write(response)
        await writer.drain()
        
        self.clients.add(writer)
        logger.info(f"WebSocket client connected to backplane. Local Clients: {len(self.clients)}")
        
        try:
            while True:
                # 2. Read Frame (RFC 6455 Standard)
                header = await reader.readexactly(2)
                b1, b2 = header[0], header[1]
                fin = b1 & 0x80
                opcode = b1 & 0x0F
                
                if opcode == 8: # Close Connection
                    break
                    
                is_masked = b2 & 0x80
                payload_len = b2 & 0x7F
                
                if payload_len == 126:
                    ext = await reader.readexactly(2)
                    payload_len = struct.unpack(">H", ext)[0]
                elif payload_len == 127:
                    ext = await reader.readexactly(8)
                    payload_len = struct.unpack(">Q", ext)[0]
                    
                masking_key = None
                if is_masked:
                    masking_key = await reader.readexactly(4)
                    
                payload = await reader.readexactly(payload_len)
                
                # 3. Unmask Payload
                if is_masked:
                    unmasked = bytearray(payload_len)
                    for i in range(payload_len):
                        unmasked[i] = payload[i] ^ masking_key[i % 4]
                    payload = unmasked
                    
                # 4. Distributed Broadcast
                if opcode == 1: # Text frame
                    if self.redis_client:
                        # Publish to cluster!
                        await self.redis_client.publish('essa_ws_backplane', payload)
                    else:
                        # Echo back to all local clients if no redis is configured
                        frame = self.encode_frame(payload, opcode=1)
                        for c in list(self.clients):
                            try:
                                c.write(frame)
                                await c.drain()
                            except Exception:
                                self.clients.discard(c)
        except Exception:
            pass
        finally:
            self.clients.discard(writer)
            writer.close()
            logger.info(f"WebSocket client disconnected. Local Clients: {len(self.clients)}")

    def encode_frame(self, data: bytes, opcode=1) -> bytes:
        """Encodes an unmasked WebSocket frame to send to the client."""
        frame = bytearray()
        frame.append(0x80 | opcode) # FIN bit set + opcode
        
        length = len(data)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack(">H", length))
        else:
            frame.append(127)
            frame.extend(struct.pack(">Q", length))
            
        frame.extend(data)
        return bytes(frame)

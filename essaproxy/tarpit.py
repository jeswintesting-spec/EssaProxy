import asyncio
import logging
import random

logger = logging.getLogger(__name__)

class TarpitEngine:
    def __init__(self):
        self.garbage_headers = [
            b"X-Tarpit-Junk: ",
            b"X-Botnet-Waste: ",
            b"X-Endless-Void: "
        ]
        
    async def trap(self, writer: asyncio.StreamWriter, client_ip: str):
        """
        Traps a malicious client in an endless connection, dripping 1 byte every 10 seconds
        to exhaust the attacker's resources (Slowloris defense inversion).
        """
        logger.warning(f"Tarpit Engine: Trapping malicious IP {client_ip} in an endless void.")
        try:
            # Send an incomplete HTTP response header
            writer.write(b"HTTP/1.1 200 OK\r\n")
            await writer.drain()
            
            while True:
                # Drip a random garbage header byte by byte
                header_prefix = random.choice(self.garbage_headers)
                writer.write(header_prefix)
                await writer.drain()
                
                for _ in range(20):
                    # Write 1 random byte every 5-15 seconds
                    random_byte = bytes([random.randint(65, 90)])
                    writer.write(random_byte)
                    await writer.drain()
                    await asyncio.sleep(random.uniform(5, 15))
                    
                writer.write(b"\r\n")
                await writer.drain()
                
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            logger.info(f"Tarpit Engine: Attacker {client_ip} finally disconnected.")
        except Exception:
            pass
        finally:
            writer.close()

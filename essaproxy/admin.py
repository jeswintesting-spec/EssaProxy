import json
import os
import asyncio
from typing import Any

class AdminServer:
    def __init__(self, proxy: Any):
        self.proxy = proxy
        self.gui_dir = os.path.join(os.path.dirname(__file__), 'admin_gui')

    async def handle_request(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, method: str, path: str, header_data: bytes):
        """Handle incoming requests to the /admin namespace"""
        try:
            if method == "GET" and (path == "/admin" or path == "/admin/"):
                await self._serve_gui(writer)
            elif method == "GET" and path == "/admin/api/state":
                await self._serve_state(writer)
            elif method == "POST" and path == "/admin/api/block":
                await self._handle_block(reader, writer, header_data)
            elif method == "POST" and path == "/admin/api/unblock":
                await self._handle_unblock(reader, writer, header_data)
            else:
                await self._send_response(writer, 404, "Not Found")
        except Exception as e:
            await self._send_response(writer, 500, f"Internal Server Error: {str(e)}")
        finally:
            writer.close()

    async def _serve_gui(self, writer: asyncio.StreamWriter):
        index_path = os.path.join(self.gui_dir, 'index.html')
        try:
            with open(index_path, 'rb') as f:
                content = f.read()
            
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html; charset=utf-8\r\n"
                + f"Content-Length: {len(content)}\r\n".encode() +
                b"Connection: close\r\n\r\n" +
                content
            )
            writer.write(response)
            await writer.drain()
        except FileNotFoundError:
            await self._send_response(writer, 404, "GUI files not found")

    async def _serve_state(self, writer: asyncio.StreamWriter):
        routes_dump = {}
        for route, lb in self.proxy.load_balancers.items():
            routes_dump[route] = [
                {
                    "host": b.host,
                    "port": b.port,
                    "weight": b.weight,
                    "country": b.country,
                    "healthy": b.healthy,
                    "active_connections": b.active_connections
                }
                for b in lb.backends
            ]

        state = {
            "metrics": {
                "requests_total": self.proxy.metrics_collector.requests_total,
                "waf_blocks_total": self.proxy.metrics_collector.waf_blocks_total,
                "rate_limit_drops_total": self.proxy.metrics_collector.rate_limit_drops_total,
                "cache_hits_total": self.proxy.metrics_collector.cache_hits_total,
            },
            "routes": routes_dump,
            "config": {
                "blocked_ips": self.proxy.config.blocked_ips
            }
        }
        
        body = json.dumps(state).encode('utf-8')
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n".encode() +
            b"Connection: close\r\n\r\n" +
            body
        )
        writer.write(response)
        await writer.drain()

    async def _read_json_body(self, reader: asyncio.StreamReader, header_data: bytes) -> dict:
        headers = header_data.decode('utf-8', errors='ignore').split('\r\n')
        content_length = 0
        for h in headers:
            if h.lower().startswith('content-length:'):
                content_length = int(h.split(':')[1].strip())
                break
                
        if content_length > 0:
            body_bytes = await reader.readexactly(content_length)
            return json.loads(body_bytes.decode('utf-8'))
        return {}

    async def _handle_block(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, header_data: bytes):
        body = await self._read_json_body(reader, header_data)
        ip = body.get('ip')
        if ip and ip not in self.proxy.config.blocked_ips:
            self.proxy.config.blocked_ips.append(ip)
            
        await self._send_response(writer, 200, json.dumps({"status": "success", "ip": ip}))

    async def _handle_unblock(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, header_data: bytes):
        body = await self._read_json_body(reader, header_data)
        ip = body.get('ip')
        if ip and ip in self.proxy.config.blocked_ips:
            self.proxy.config.blocked_ips.remove(ip)
            
        await self._send_response(writer, 200, json.dumps({"status": "success", "ip": ip}))

    async def _send_response(self, writer: asyncio.StreamWriter, status_code: int, body_str: str):
        body = body_str.encode('utf-8')
        status_text = "OK" if status_code == 200 else "Error"
        response = (
            f"HTTP/1.1 {status_code} {status_text}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n".encode() +
            body
        )
        writer.write(response)
        await writer.drain()

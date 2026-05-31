import asyncio
import logging
import argparse
import sys
import os
from .config import ProxyConfig, BackendServer
from .proxy import EssaProxy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

async def config_watcher(proxy: EssaProxy, config_path: str):
    logger = logging.getLogger("ConfigWatcher")
    try:
        last_mtime = os.path.getmtime(config_path)
    except FileNotFoundError:
        return

    while True:
        await asyncio.sleep(2)
        try:
            current_mtime = os.path.getmtime(config_path)
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                logger.info(f"Detected changes in {config_path}. Reloading...")
                new_config = ProxyConfig.load_from_file(config_path)
                proxy.reload_config(new_config)
        except Exception as e:
            logger.error(f"Failed to reload config from {config_path}: {e}")

async def run_proxy():
    parser = argparse.ArgumentParser(description="EssaProxy - Layer 7 HTTP Reverse Proxy")
    parser.add_argument("--config", help="Path to JSON configuration file")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind")
    parser.add_argument("--backends", nargs="+", help="Backend servers in host:port format")
    parser.add_argument("--algorithm", choices=["round_robin", "least_connections", "ip_hash", "weighted_round_robin"], default="round_robin")
    parser.add_argument("--rate-limit", type=float, default=10.0, help="Requests per second per IP")
    parser.add_argument("--rate-burst", type=int, default=100, help="Max burst requests per IP")
    
    args = parser.parse_args()

    if args.config:
        config = ProxyConfig.load_from_file(args.config)
    else:
        if not args.backends:
            print("Error: --backends is required if --config is not specified")
            sys.exit(1)
        backends = []
        for b in args.backends:
            parts = b.split(":")
            if len(parts) != 2:
                print(f"Invalid backend format: {b}. Expected host:port")
                sys.exit(1)
            backends.append(BackendServer(host=parts[0], port=int(parts[1])))

        config = ProxyConfig(
            host=args.host,
            port=args.port,
            routes={'/': backends},
            algorithm=args.algorithm,
            rate_limit_rate=args.rate_limit,
            rate_limit_capacity=args.rate_burst,
            health_check_interval=5,
            health_check_timeout=2
        )

    proxy = EssaProxy(config)
    watcher_task = None
    if args.config:
        watcher_task = asyncio.create_task(config_watcher(proxy, args.config))
        
    try:
        await proxy.start()
    except KeyboardInterrupt:
        await proxy.stop()
        if watcher_task:
            watcher_task.cancel()

def main():
    try:
        asyncio.run(run_proxy())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

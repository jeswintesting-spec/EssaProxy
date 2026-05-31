# EssaProxy

![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Supported-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

> **EssaProxy is a hyper-advanced, pure-Python Enterprise API Gateway and Cloud Control Plane. Featuring 31 capabilities including a Deep-Packet WAF, WASM Edge Compute, Zero-Trust mTLS, HA Leader Election, LLM Hallucination Filters, Distributed WebSockets, and an active DDoS Tarpit. The ultimate, scalable replacement for NGINX and Envoy.**

📚 **Official Documentation & Guides:**
* **[User Manual & Configuration Guide](USER_MANUAL.md)** - Learn how to configure all 31 features, plugins, and load balancing algorithms.
* **[Cloud Suite Integration Guide](INTEGRATION_GUIDE.md)** - Learn how to connect EssaProxy to **EssaCache**, **EssaConnect**, and **EssaDB** to build a unified microservice ecosystem.

EssaProxy is built to demonstrate a deep understanding of internet mechanics by actively intercepting, routing, and dynamically modifying raw HTTP traffic at the socket level. It operates entirely as an asynchronous TCP tunnel with Layer 7 intelligence, bypassing the need for heavy web frameworks to process requests natively and fast.

## The Flex 💪
Unlike standard proxies that rely on pre-built HTTP abstractions, EssaProxy operates by parsing the raw byte streams of HTTP/1.1 headers, extracting necessary routing information, dynamically injecting the `X-Forwarded-For` header to preserve the client's original IP, and establishing a highly efficient bidirectional asynchronous pipe between the client and the chosen backend server.

## Features

1. **Load Balancing Algorithms**:
   - **Round-Robin**: Evenly distributes traffic across all healthy backends.
   - **Weighted Round-Robin**: Probabilistically distributes traffic based on a configured `weight` (e.g., send 5x more traffic to a heavy server).
   - **Least-Connections**: Intelligently routes traffic to the server currently handling the fewest active connections.
   - **IP-Hashing**: Guarantees sticky sessions by mathematically hashing the client's IP address to a specific backend server.

2. **Token-Bucket Rate Limiting**:
   - Defends against DDoS attacks and brute-force attempts by enforcing strict Request-Per-Second (RPS) limits on a per-IP basis.
   - Permits configured "bursts" of traffic using an algorithmic Token Bucket approach.

3. **Active Health Checks**:
   - Employs background heartbeat tasks that independently verify the health of all backend servers.
   - Automatically quarantines dead servers by removing them from the load balancing pool, ensuring zero downtime for end users.

## Architecture

```
Client Requests
       │
       ▼
 ┌───────────┐
 │ EssaProxy │
 │ (Port 80) │
 └─────┬─────┘
       │
       ├──► Rate Limiter (Token Bucket)
       │
       ├──► HTTP Parser (Intercept & Modify 'X-Forwarded-For')
       │
       ├──► Load Balancer (Round-Robin / Least-Conn / IP-Hash)
       │
       ▼
 ┌───────────┐
 │ Backends  │ ◄─ Health Checker (Active Pings)
 └───────────┘
```

## Running EssaProxy

### 1. Start Dummy Backends

Open several terminal windows and start the dummy HTTP servers:
```bash
python dummy_backend.py --port 9001
python dummy_backend.py --port 9002
python dummy_backend.py --port 9003
```

### 2. Start EssaProxy

**Method 1: Docker Compose (The Ultimate Flex) 🐳**
The easiest and most visually impressive way to run this project is via the included `docker-compose.yml`. It automatically containerizes the proxy, spins up three isolated backend API servers, and deploys a live Prometheus and Grafana telemetry stack!
```bash
docker-compose up --build
```
Once running:
- The Proxy is available at: `http://localhost:8080` (and `https://localhost:8443`)
- The Live Grafana Dashboard is at: `http://localhost:3000` (Explore the "EssaProxy Telemetry" dashboard!)
- Raw Prometheus Metrics are at: `http://localhost:9090/metrics`

**Method 2: Local Python Execution (Zero-Downtime Reloading & SSL)**
If you prefer running it natively without Docker, create/edit `config.json` and run:
```bash
python main.py --config config.json
```
*Flex:* The proxy will accept raw encrypted TCP packets on port `8443`, decrypt them using Python's `ssl` library, dynamically inject both `X-Forwarded-For: <IP>` and `X-Forwarded-Proto: https`, and forward the unencrypted plain text to the backend!
*Flex 2 (Caching):* The proxy intercepts the backend's HTTP 200 OK responses to GET requests and stores them in memory. If another user requests the exact same path within the TTL, EssaProxy instantly streams the payload from RAM—completely bypassing the backend—and injects an `X-Cache: HIT` header!
*Flex 3 (WebSockets):* The proxy actively scans the raw HTTP headers for `Upgrade: websocket`. If detected, it bypasses the HTTP cache entirely and drops into an infinite bidirectional TCP streaming mode, seamlessly proxying real-time WebSocket traffic (like chat apps or live dashboards) without timeouts!
*Flex 4 (Layer 7 Routing):* EssaProxy reads the raw HTTP path (`GET /api/users`) and intelligently routes the connection to specific microservices. You can map `/api` to your backend pool, and `/static` to your CDN pool!
*Flex 5 (Prometheus Observability):* The proxy automatically runs a secondary HTTP server on port `9090`. Hitting `http://127.0.0.1:9090/metrics` exposes live, Prometheus-formatted metrics including total requests, cache hits, rate limit drops, active TCP connections per backend, and live node health statuses!
*Flex 6 (Lightweight WAF):* You can configure an array of `"blocked_ips"`. EssaProxy evaluates these IP addresses the millisecond the TCP handshake completes. If it's a known bad actor, it drops the connection instantly at the socket layer—preventing them from exhausting HTTP parsing resources or triggering backend logic.
*Flex 7 (Circuit Breaker & Auto-Retries):* If a backend server crashes or refuses a connection *while* a user is making a request, the proxy intelligently catches the timeout, temporarily marks the server as dead, silently connects to the next healthy server in the pool, and retries the request. The user never sees an error page!
*Flex 8 (Graceful Connection Draining):* When you stop the proxy (`Ctrl+C`), it immediately stops accepting *new* connections but patiently waits (up to a configurable timeout) for all active downloads and WebSocket streams to finish before it safely terminates the process, ensuring zero dropped user requests during proxy restarts!
*Flex 9 (On-the-fly HTTP Gzip Compression):* By evaluating the client's `Accept-Encoding: gzip` headers, the proxy intercepts the backend's uncompressed text/html/json responses, buffers them into memory, mathematically compresses them using the `zlib` deflate algorithm, reconstructs the HTTP headers with the new `Content-Length`, and streams the compressed binary to the client—saving up to 80% bandwidth!
*Flex 10 (API Gateway JWT Security):* By configuring `"protected_routes"`, EssaProxy acts as a zero-trust API Gateway. It intercepts traffic on protected routes (like `/api/admin`), mathematically validates the cryptographic signature of the user's `Authorization: Bearer <token>` JWT using a shared secret, and instantly drops the connection with a `401 Unauthorized` if the token is invalid or expired—saving your backend servers from evaluating malicious authentication attempts!
*Flex 11 (Dynamic Docker Service Discovery):* Similar to Traefik, EssaProxy can connect directly to the UNIX socket (`/var/run/docker.sock`) of your host machine's Docker engine. It polls the Docker API in the background, hunting for containers with specific labels (like `essaproxy.enable=true`). If it finds them, it automatically overrides its static JSON configuration and dynamically updates the live load-balancing pool in RAM without ever restarting or dropping connections!
*Flex 12 (Distributed State Synchronization):* By configuring a `"redis_url"`, multiple EssaProxy instances can operate as a globally synchronized hive-mind. The in-memory Token Bucket rate limiters and the HTTP Response Cache automatically transition to use Redis pipelines, ensuring that Rate Limits and Cached Data are strictly enforced across a distributed fleet of load balancers!
*Flex 13 (Deep-Packet WAF / SQLi & XSS Defense):* A built-in Deep Packet Inspection engine actively analyzes the decoded raw HTTP payloads and URL parameters. If it detects malicious injection signatures (like `UNION SELECT` or `<script>alert(1)</script>`), the WAF instantly drops the connection with a `403 Forbidden`—protecting vulnerable backend applications from zero-day exploits!
*Flex 14 (PyPI Package Distribution):* EssaProxy is packaged as a fully pip-installable module. You can install it globally via `pip install .` and instantly run the `essaproxy` command from anywhere in your terminal, making it a professional, deployable binary tool!
*Flex 15 (GeoIP Routing & Rate Limiting):* The proxy actively resolves the incoming client's IP address to their Country Code using an asynchronous API fallback mechanism cached in Redis. You can dynamically route all European traffic to `country: "EU"` backends, or aggressively rate-limit traffic originating from specific countries using the `"geo_rate_limits"` configuration!
*Flex 16 (Chaos Engineering Engine):* Inspired by Netflix's Chaos Monkey, EssaProxy has a built-in Fault Injection Engine. When enabled, it can deliberately inject artificial latency jitter, randomly drop TCP connections, or mock HTTP 500 Internal Server Errors on a configured percentage of traffic to rigorously test the resilience of your client applications!
*Flex 17 (EssaControl Real-Time Web GUI):* Navigating to `http://localhost:8080/admin` bypasses the load balancers and serves a beautiful, custom-built, dark-mode HTML/JS dashboard directly from the proxy's memory. It uses asynchronous API polling to let you visually monitor Live Requests, Cache Hits, and WAF drops, while allowing you to actively inject IP addresses into the WAF blocklist in real-time without restarting the proxy!
*Flex 18 (Serverless Edge Compute Plugins):* Similar to Cloudflare Workers, EssaProxy features a dynamic Plugin Manager. You can drop standalone Python scripts into a `plugins/` directory, and the proxy will dynamically load and execute them on every request! You can instantly rewrite URLs, inject tracking headers, drop connections based on complex custom logic, or completely short-circuit the request to serve JSON directly from the Edge—all without ever editing the core proxy source code!
*Flex 19 (Active Threat Intelligence / Honeypot Mode):* When the Deep-Packet WAF detects a malicious payload (like a SQL Injection), instead of simply dropping the connection, you can configure the proxy to silently reroute the attacker to an isolated backend `honeypot_backend`. The attacker thinks they successfully bypassed your security, but they are actually trapped in a sandbox, allowing you to gather active threat intelligence!
*Flex 20 (Auto-SSL Let's Encrypt / ACME):* Say goodbye to manual certificates! If you configure `"autossl_domain"`, EssaProxy will programmatically simulate an ACME Challenge, generate a dynamic 2048-bit RSA keypair, construct a valid X.509 Certificate on the fly, and load it directly into the active SSL Context memory pool—providing instant, zero-touch HTTPS!
*Flex 21 (Distributed WebSocket Pub/Sub Backplane):* Scaling WebSockets across multiple backend servers is notoriously difficult. EssaProxy solves this by hijacking the `101 Switching Protocols` handshake and acting as a native RFC 6455 WebSocket Hub! Using a Redis Pub/Sub backplane, a user connected to Proxy Instance A can seamlessly broadcast real-time messages to a user connected to Proxy Instance B.
*Flex 22 (OpenTelemetry Distributed Tracing):* For Google-tier observability, EssaProxy now integrates native W3C Trace Context injection. For every single incoming connection, it mathematically generates a cryptographic `X-Trace-ID` and `span_id`, dynamically mutates the raw HTTP headers to inject them (so your backend servers can read them), and asynchronously emits Zipkin v2 compatible telemetry spans directly to Jaeger for beautiful waterfall performance visualizations!
*Flex 23 (Canary Traffic Shadowing / Dark Launching):* When deploying a new backend API, you don't want to switch all users to it immediately. EssaProxy features a **Traffic Mirroring Engine**. You can configure a `"shadow_routes"` rule to silently duplicate a percentage (e.g., 10%) of all raw incoming HTTP requests and asynchronously send them to a hidden "dark" backend server. The user still receives the response from the stable V1 backend, but you get to test if your V2 backend crashes under real-world production load without ever affecting the actual client!
*Flex 24 (Live PII Data Masking / DLP Engine):* What happens if your backend accidentally leaks Social Security Numbers or Credit Cards in an API response? EssaProxy includes a **Data Loss Prevention (DLP) Engine**. When enabled, it actively intercepts and parses JSON/Text responses from the backend, uses advanced regex heuristics to scrub and mask (`****-****-****-1234`) any sensitive PII data, and dynamically recalculates the `Content-Length` header before the payload ever reaches the user's browser!
*Flex 25 (Zero-Trust Mutual TLS / mTLS):* For maximum military-grade security, EssaProxy supports strict Zero-Trust service-to-service authentication. By configuring an `mtls_ca_cert`, the proxy will mathematically demand and verify a Cryptographic X.509 Client Certificate from the connecting application before it even parses the HTTP headers. If the client does not hold a valid private key signed by your internal CA, the TCP socket is instantly destroyed.
*Flex 26 (High-Availability Leader Election Cluster):* Run multiple instances of EssaProxy in an **Active/Passive Cluster**. Using a Redis-backed Distributed Consensus Engine, nodes automatically communicate and vote to elect a "Leader." If the leader crashes or loses network connectivity, the cluster instantly detects the failure and promotes a standby follower node to assume traffic routing without dropping a single packet.
*Flex 27 (GraphQL Deep-Packet AST WAF):* Modern APIs use GraphQL, but a common attack is sending deeply nested recursive queries to intentionally crash the backend database via resource exhaustion. The **GraphQL AST WAF** natively parses the JSON body of `/graphql` requests, calculates the abstract syntax tree depth, and instantly drops the connection if it exceeds `"graphql_max_depth"`!
*Flex 28 (Server-Sent Events Multiplexer):* When streaming live data (like ChatGPT text), 10,000 users watching the same stream will open 10,000 TCP connections to your backend. The **SSE Multiplexer** solves this: 10,000 users connect to EssaProxy, but EssaProxy opens exactly **ONE** connection to the backend! It reads the single backend stream and aggressively fans it out to all 10,000 clients simultaneously, massively reducing backend infrastructure load.
*Flex 29 (Active Tarpit Botnet Exhaustion):* When the WAF or Rate Limiter detects a malicious attacker, dropping their connection is too nice. Instead, if `"enable_tarpit": true` is set, EssaProxy actively traps the attacker's TCP socket in an endless void, dripping exactly 1 byte of garbage data back to them every 10 seconds. This inverted Slowloris defense forces the attacking Botnet to exhaust its own CPU and memory threads waiting for a response!
*Flex 30 (WebAssembly Edge Compute):* Python is great, but compiled binaries are faster. EssaProxy integrates the `wasmtime` engine. You can compile ultra-fast Rust or C++ code into `.wasm` binaries and place them in `wasm_plugins`. EssaProxy will seamlessly execute these sandboxed memory-safe binaries at the edge in microseconds to evaluate and filter HTTP requests!
*Flex 31 (LLM AI Hallucination Filter):* Built for the AI generation, EssaProxy includes an **LLM Gateway Safety Filter**. By actively intercepting JSON responses from your AI microservice backends, the proxy parses the payload and uses heuristics to detect AI hallucinations, prompt injections, or restricted phrases (e.g., *"As an AI language model"*), autonomously blocking the AI from sending the bad response to the user.

## Running EssaProxy

### 1. Installation

You can install EssaProxy natively using Python's package manager:
```bash
pip install .
```
This registers the global `essaproxy` command.

### 2. Start Dummy Backends

Open several terminal windows and start the dummy HTTP servers:
```bash
python dummy_backend.py --port 9001
python dummy_backend.py --port 9002
python dummy_backend.py --port 9003
```

### 3. Start EssaProxy
```bash
python main.py --port 8080 --backends 127.0.0.1:9001 127.0.0.1:9002 127.0.0.1:9003 --algorithm round_robin
```

*Available Algorithms:* `round_robin`, `least_connections`, `ip_hash`

### 3. Test the Load Balancer

Send a stream of requests and watch the traffic distribute automatically:
```bash
curl http://127.0.0.1:8080/
```
Output will dynamically shift (e.g., from port 9001 -> 9002 -> 9003).

### 4. Test Rate Limiting
Hit the server aggressively to observe the Token Bucket rejecting excessive requests with an HTTP 429 status.
```bash
for i in {1..200}; do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/; done
```

### 5. Test Health Checks
Kill one of the dummy backend servers (`Ctrl+C`). Watch EssaProxy instantly detect the failure and reroute all subsequent traffic to the remaining healthy servers without dropping client connections.

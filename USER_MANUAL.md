# EssaProxy - The Ultimate Enterprise Edge Gateway
**Official User Manual & Integration Guide**

EssaProxy is a hyper-advanced, 31-feature Layer 7 Edge Infrastructure platform written entirely in asynchronous Python. It acts as an API Gateway, Web Application Firewall (WAF), Load Balancer, Chaos Engineering Engine, Edge Compute Framework, and Zero-Trust Proxy.

This manual will guide you through configuring and utilizing every enterprise feature built into EssaProxy.

---

## Table of Contents
1. [Installation & Quick Start](#1-installation--quick-start)
2. [Basic Routing & Load Balancing](#2-basic-routing--load-balancing)
3. [Security & Zero-Trust Architecture](#3-security--zero-trust-architecture)
4. [Traffic Shaping & Scalability](#4-traffic-shaping--scalability)
5. [Edge Compute (Python & WASM)](#5-edge-compute-python--wasm)
6. [Advanced AI & Data Defense](#6-advanced-ai--data-defense)
7. [Observability & Chaos Engineering](#7-observability--chaos-engineering)
8. [Docker & Container Orchestration](#8-docker--container-orchestration)

---

## 1. Installation & Quick Start

EssaProxy requires **Python 3.9+** and optionally a **Redis** instance for distributed clustering and Pub/Sub features.

### Setup
```bash
# Clone the repository
git clone https://github.com/your-org/EssaProxy.git
cd EssaProxy

# Install dependencies
pip install -r requirements.txt
```

### Running the Proxy
EssaProxy is driven entirely by a `config.json` file. 
```bash
python main.py --config config.json
```
By default, the proxy runs on port `8080`, the Real-Time Admin GUI on `9090`, and metrics on `9091`.

---

## 2. Basic Routing & Load Balancing

Your primary method of configuring EssaProxy is defining **Routes** in your `config.json`. 

```json
{
  "host": "0.0.0.0",
  "port": 8080,
  "routes": {
    "/api/v1": {
      "backends": [
        {"host": "127.0.0.1", "port": 5001, "weight": 2},
        {"host": "127.0.0.1", "port": 5002, "weight": 1}
      ],
      "algorithm": "round_robin"
    },
    "/": {
      "backends": [
        {"host": "10.0.0.5", "port": 80}
      ]
    }
  }
}
```
**Load Balancing Algorithms Supported:**
- `round_robin`: Distributes traffic equally.
- `least_connections`: Routes traffic to the backend with the fewest active HTTP requests.
- `ip_hash`: Ensures a specific client IP always hits the same backend (Sticky Sessions).
- `geo_latency`: Routes traffic based on Redis GeoIP resolution.

---

## 3. Security & Zero-Trust Architecture

EssaProxy contains military-grade security defenses.

### 3.1 Deep-Packet Inspection (WAF)
```json
  "enable_dpi_waf": true
```
Enables native SQL Injection (SQLi) and Cross-Site Scripting (XSS) payload blocking. 

### 3.2 Active Tarpit (Botnet Exhaustion)
```json
  "enable_tarpit": true
```
Instead of dropping attackers, the proxy keeps their TCP connection open and drips 1 byte of garbage data every 10 seconds, exhausting the attacker's resources (Inverted Slowloris).

### 3.3 Active Threat Intelligence (Honeypot)
```json
  "enable_honeypot": true,
  "honeypot_backend": {"host": "127.0.0.1", "port": 9999}
```
Silently reroutes attackers triggering the WAF to an isolated sandbox backend to gather threat intelligence.

### 3.4 Zero-Trust Mutual TLS (mTLS)
```json
  "mtls_ca_cert": "ca.pem"
```
Forces the proxy to demand a cryptographic X.509 Client Certificate before establishing a connection. Instantly destroys unauthorized internal traffic.

### 3.5 JWT Authentication
```json
  "jwt_secret": "super-secret-key",
  "protected_routes": ["/api/admin"]
```
Enforces bearer token validation at the edge.

---

## 4. Traffic Shaping & Scalability

### 4.1 HA Leader Election (Active/Passive)
When running multiple proxy nodes pointing to the same Redis cluster, nodes will automatically vote to elect a **Leader**. Standby nodes will wait passively. If the leader crashes, a standby node promotes itself in under 5 seconds.

### 4.2 Distributed WebSocket Pub/Sub Backplane
```json
  "enable_ws_backplane": true
```
Scaling WebSockets is hard. EssaProxy acts as an RFC 6455 Hub. If User A connects to Node 1, and User B connects to Node 2, they can seamlessly message each other over the Redis Backplane!

### 4.3 Server-Sent Events (SSE) Multiplexer
```json
  "enable_sse_multiplexer": true
```
If 10,000 clients request the same live stream, EssaProxy opens exactly **ONE** connection to your backend server, and broadcasts the chunks to all 10,000 clients simultaneously.

### 4.4 Canary Traffic Shadowing (Dark Launching)
```json
  "shadow_routes": {
    "/api/v2": {
      "backend": {"host": "dark_backend", "port": 9005},
      "percent": 0.1
    }
  }
```
Silently duplicates 10% of live HTTP traffic and asynchronously fires it at a hidden "Dark" backend for zero-risk production testing.

---

## 5. Edge Compute (Python & WASM)

Run logic directly at the Edge!

### 5.1 Python Plugin Engine
Create Python scripts in the `./plugins` directory. EssaProxy dynamically imports them.
```python
# plugins/add_headers.py
def process_request(request_headers: dict) -> dict:
    request_headers['X-Edge-Processed'] = 'True'
    return request_headers
```

### 5.2 WebAssembly (WASM) Edge Compute
```json
  "wasm_plugins_dir": "./wasm_plugins"
```
Compile ultra-fast Rust, C++, or Go code into `.wasm` binaries. EssaProxy utilizes `wasmtime` to execute these sandboxed memory-safe binaries at the edge in microseconds to filter paths.

---

## 6. Advanced AI & Data Defense

### 6.1 LLM Gateway Hallucination Filter
```json
  "enable_llm_filter": true
```
When sitting in front of AI models, EssaProxy actively intercepts JSON responses and blocks restricted phrases (e.g., *"As an AI language model"*), returning a 451 Error instead of exposing hallucinations.

### 6.2 Live PII Data Masking (DLP)
```json
  "enable_dlp": true
```
Actively scrubs and masks (`****-****-****-1234`) Credit Cards, SSNs, and Emails from backend JSON responses, dynamically recalculating the `Content-Length` header on the fly.

### 6.3 GraphQL Deep-Packet AST WAF
```json
  "enable_graphql_waf": true,
  "graphql_max_depth": 5
```
Parses the Abstract Syntax Tree (AST) of GraphQL POST requests. Drops the connection if a client attempts a deeply nested, recursive query designed to exhaust your database.

---

## 7. Observability & Chaos Engineering

### 7.1 OpenTelemetry Distributed Tracing (Jaeger)
```json
  "enable_tracing": true,
  "jaeger_url": "http://jaeger:14268/api/traces"
```
Generates W3C Trace Contexts (`X-Trace-ID`) for every request, mutates the HTTP headers, and fires Zipkin v2 compatible telemetry spans to your Jaeger cluster.

### 7.2 Chaos Engineering Engine
```json
  "chaos": {
    "enabled": true,
    "latency_injection_ms": 500,
    "fault_injection_rate": 0.05
  }
```
Test your system's resilience by intentionally injecting 500ms of latency into random routes, and outright dropping 5% of requests!

---

## 8. Docker & Container Orchestration

EssaProxy features native Docker Socket Service Discovery. It will automatically detect containers with specific labels and dynamically update its routing tables without a reboot!

**Run via Docker Compose:**
```yaml
version: '3.8'
services:
  essaproxy:
    build: .
    ports:
      - "8080:8080"
      - "9090:9090"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: ["python", "main.py", "--config", "docker_config.json"]
```

Launch the stack:
```bash
docker-compose up --build
```

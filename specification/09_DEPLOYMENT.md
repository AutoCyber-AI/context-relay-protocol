<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# CRP v2.0 — Deployment Architecture

> **Status**: Normative. This document specifies CRP's deployment model, resource requirements, and operational characteristics.
> **Core Principle**: CRP is an embedded library. It adds zero infrastructure overhead to your application.

---

## 1. WHY CRP IS AN EMBEDDED LIBRARY

### 1.1 The Fundamental Architectural Decision

CRP is an embedded library — imported directly into the application process. Not a server. Not a sidecar by default. Not a subprocess.

This is not a limitation. It is the **correct architecture** for what CRP does.

**The question**: MCP uses stdio and HTTP. gRPC uses HTTP/2. LSP uses stdio. Why doesn't CRP use any of these?

**The answer**: Because those protocols connect **two separate systems**. CRP manages context **within one system**.

| Protocol | What It Connects | Why Transport Exists |
|---|---|---|
| **MCP** | LLM host ↔ external tools | Tools run in separate processes with different lifecycles |
| **gRPC** | Microservice ↔ microservice | Services on different machines or containers |
| **LSP** | Editor ↔ language analyzer | Analyzer may outlive or restart independently of editor |
| **CRP** | **Nothing ↔ nothing** | CRP and the application are **one program** |

When you call `dispatch()`, CRP builds an envelope, calls the LLM API, extracts facts, and updates warm state — all in the same process. There are no two systems to connect. Adding a transport layer would introduce complexity, latency, and failure modes for zero architectural benefit.

### 1.2 Why stdio Would Be Wrong

| stdio Concern | Impact on CRP |
|---|---|
| **Serialization overhead** | Every `dispatch()` would serialize the envelope (~400 KB for 100K tokens) to JSON, pipe it to the CRP server, which parses it, does work, serializes the result, and pipes it back. **In-process: zero serialization — CRP reads data structures directly in memory** |
| **Subprocess management** | The application must spawn CRP as a child process, monitor for crashes, restart on failure, handle orphaned processes on parent exit. **In-process: the library lives and dies with the application — no lifecycle management** |
| **Latency** | Each call adds pipe I/O latency (~1-5ms per round trip). A 50-window session accumulates 50-250ms of pure transport overhead. **In-process: function call overhead is nanoseconds** |
| **State sharing** | Warm state (fact graph, embeddings, ANN index) lives in the server process. The application cannot inspect or query `fact_count()` without another round trip. **In-process: the application directly queries session state** |
| **Memory duplication** | The envelope must exist in both processes — the app builds the task, sends it to CRP, CRP builds the envelope (duplicating context). **In-process: single copy** |
| **Debugging** | Errors cross process boundaries. Stack traces are split. Profiling requires correlating two processes. **In-process: single stack trace, single profiler, single debugger** |

### 1.3 Why HTTP Would Be Wrong

| HTTP Concern | Impact on CRP |
|---|---|
| **Network stack for local communication** | HTTP adds TCP/IP overhead, connection management, and potential port conflicts — all for communication that never leaves the machine. **In-process: no network stack** |
| **Authentication & security surface** | An HTTP server on localhost is an attack surface. DNS rebinding attacks (noted in MCP's own security warnings) allow remote sites to access localhost services. Must implement Origin validation, TLS for non-local access. **In-process: process isolation is the security boundary — no attack surface** |
| **Deployment complexity** | Must ensure the HTTP server is running before the client connects, handle port conflicts, manage the server lifecycle. **In-process: `import crp` — done** |
| **Stateless by default** | HTTP is stateless. CRP sessions are deeply stateful (warm state, extraction state, ANN index, fact graph). An HTTP server must artificially persist session state across requests, handle session expiry, manage state serialization. **In-process: state lives naturally in memory** |

### 1.4 Why gRPC / Protocol Buffers Would Be Wrong

| gRPC Concern | Impact on CRP |
|---|---|
| **Schema compilation** | Protocol Buffers require `.proto` file compilation and code generation. CRP's types are JSON Schema (language-neutral, no compilation step). Adding protobuf adds a build-time dependency for zero benefit |
| **HTTP/2 mandatory** | gRPC requires HTTP/2, which requires TLS for most clients. For in-process context management this is absurd — a full TLS stack for communication within the same memory space |
| **Streaming complexity** | gRPC's bidirectional streaming is powerful for network services. CRP's streaming is a simple event iterator on a function call — no network stream management needed |
| **Service mesh assumption** | gRPC assumes a distributed system with service discovery, load balancing, and health checking. CRP is a library call |

### 1.5 The One Legitimate Exception

When CRP is called from a language that doesn't have a native SDK (e.g., a Go application calling a Python CRP library), the **HTTP Sidecar** (Section 3.3) bridges the gap. This is an accommodation for polyglot environments, not the designed deployment model.

**Summary**: CRP is an embedded library because that is the architecturally correct choice for managing context within a single application. The only network communication CRP needs is the LLM API call — and that's a standard HTTP client request, not a protocol concern.

---

## 2. HOW LIGHTWEIGHT CRP IS

### 2.1 Resource Footprint

CRP is designed to disappear. Its resource consumption should never be the bottleneck in any application:

| Configuration | RAM | Disk | CPU | Startup Time |
|---|---|---|---|---|
| **Minimal** (regex + statistical extraction only, Stages 1-2) | ~50 MB | ~10 MB | Single core | **< 100ms** |
| **Standard** (+ GLiNER base + UIE, Stages 1-4) | ~200 MB | ~150 MB | Single core | ~2s (model load) |
| **Full** (all 6 stages + embeddings + ANN index) | ~500 MB | ~400 MB | 2+ cores recommended | ~5s (all models) |
| **With local LLM** (CRP + Ollama/vLLM serving a model) | ~500 MB + model size | ~400 MB + model size | GPU recommended | ~10-30s |

**For comparison — CRP Minimal (50 MB) is smaller than**:

| Component | Typical RAM |
|---|---|
| A Next.js development server | ~300 MB |
| A Java Spring Boot application | ~200-500 MB |
| A PostgreSQL instance | ~50-200 MB |
| A Docker daemon | ~100 MB |
| Chrome with 3 tabs | ~500 MB+ |
| **CRP Minimal** | **~50 MB** |

### 2.2 Lazy Loading

Extraction stages 3-6 MUST be loaded **lazily** — only when first needed:

- Session processing simple text with regex (Stage 1): **50 MB, < 100ms startup**
- First entity extraction triggers Stage 3 GLiNER load: ~200ms load time, +150 MB
- First complex discourse triggers Stage 5 parser load: ~100ms load time, +50 MB

A session that never encounters entity-rich text NEVER loads the GLiNER model. A session that never encounters reasoning-dense text NEVER loads the discourse parser. CRP pays only for what it uses.

### 2.3 Memory Growth

Warm state memory is proportional to fact count:

| Facts | Memory (facts + embeddings + ANN index) | Retrieval Latency |
|---|---|---|
| 1,000 | ~5 MB | < 1ms |
| 10,000 | ~50 MB | ~2ms |
| 100,000 | ~500 MB (compaction recommended) | ~5ms |

### 2.4 Startup Sequence

What `init()` does, and how fast:

```
FUNCTION init(config) -> SessionHandle:
  1. Resolve configuration (5-layer hierarchy)            ~1ms
  2. Validate configuration (JSON Schema)                 ~5ms
  3. Authenticate application (binding handshake)          ~1ms
  4. Connect to LLM provider:
     a. Auto-detect provider from endpoint               ~1ms
     b. Run diagnostic sequence                          ~200-500ms (network)
     c. Probe capabilities (or use cached)               ~0-200ms
  5. Initialize session state:
     a. Create session lock                               ~1ms
     b. Initialize warm state (empty fact graph + ANN)    ~5ms
     c. Load cold state if resuming session              ~50-500ms (disk)
  6. Start event emitter                                   ~1ms
  7. Emit crp.session.init event                           ~1ms
  8. RETURN SessionHandle

  TOTAL: < 500ms (cloud LLM), < 3s (local model first call)
```

**Cost breakdown**: Steps 1-3, 5-8 total ~15ms. The bottleneck is Step 4 — the LLM provider health check (a single HTTP round trip). CRP itself initializes in milliseconds.

### 2.5 Graceful Shutdown

```
FUNCTION close(session: SessionHandle):
  1. Reject new dispatch/ingest calls (CRPError 1021 SESSION_EXPIRED)
  2. Wait for in-flight operations to complete (timeout: 30s, configurable)
  3. Flush warm state to cold storage (if persistence enabled)
  4. Flush pending events to event sinks
  5. Emit crp.session.close event
  6. Release session lock
  7. Release extraction model resources (unload from memory)
```

Signal handling:

- **SIGTERM**: Trigger graceful shutdown with 10s timeout, then force-exit
- **SIGKILL / crash**: On next `init()` with the same session ID, detect incomplete cold storage and replay from event log (see 02_CORE §24.6)

---

## 3. DEPLOYMENT MODELS

### 3.1 Model 1: Embedded Library (RECOMMENDED)

```
┌─────────────────────────────────────┐
│         Application Process         │
│                                     │
│  ┌──────────┐    ┌──────────────┐   │
│  │ App Code │───▶│  CRP Library  │──▶ LLM API
│  └──────────┘    └──────────────┘   │
│                  │ SessionState  │   │
│                  │ KB / Warm     │   │
│                  │ Extraction    │   │
│                  └──────────────┘   │
└─────────────────────────────────────┘
```

- **Import and call**: `import crp; session = crp.init(...); result = session.dispatch(...)`
- Zero network overhead for CRP operations (only LLM API calls go over the network)
- Session state lives in the application's memory space
- Smallest possible footprint: library code + extraction models (~50-500 MB depending on pipeline stages loaded)
- Cold storage uses local filesystem by default

### 3.2 Model 2: CLI Wrapper

For shell scripts, pipelines, and non-native environments:

```bash
$ crp init --endpoint https://api.openai.com/v1 --api-key $OPENAI_API_KEY --model gpt-4o
Session: crp_sess_abc123

$ crp dispatch --session crp_sess_abc123 --task "Analyze this codebase" --input @./src/
{ "output": "...", "facts_extracted": 47, "quality": { ... } }

$ crp status --session crp_sess_abc123
{ "warm_state_facts": 47, "windows_dispatched": 1, "session_uptime_s": 12.3 }
```

- Stateful CLI — session state persisted to disk between invocations
- UNIX-friendly — reads stdin, writes stdout, JSON output
- Composable with pipes: `cat document.md | crp ingest --session abc123`

### 3.3 Model 3: HTTP Sidecar

For microservices, polyglot environments, and container deployments where the application language lacks a native CRP SDK:

```
┌──────────────┐     HTTP/JSON     ┌──────────────┐
│  App (any    │ ◀──────────────▶ │ CRP Sidecar  │──▶ LLM API
│  language)   │   localhost:9470  │ (single proc) │
└──────────────┘                   └──────────────┘
```

- Exposes CRP operations as a REST API on `localhost:9470` (default, configurable)
- Single-process sidecar — NOT a multi-tenant server
- Binds to `127.0.0.1` only (MUST NOT bind to `0.0.0.0` without explicit `--bind-all` flag)
- Implements the CRP API Formalism (02_CORE §6.10) over HTTP with JSON-RPC transport

---

## 4. WHERE CRP CAN RUN

CRP's embedded architecture enables deployment in environments that server-based protocols cannot reach. This is the direct advantage of the embedded deployment decision.

### 4.1 Deployment Reach

| Environment | Why CRP Works Here | Why Server Protocols Struggle |
|---|---|---|
| **Cloud Applications** | `pip install crprotocol` in any VM, container, or managed service. CRP is a library dependency — nothing to deploy separately | Server protocols work too, but add infrastructure for what's fundamentally an in-process concern |
| **Serverless Functions** (AWS Lambda, GCP Cloud Functions, Azure Functions) | CRP initializes in < 500ms. Negligible cold start. State persists to external cold storage between invocations | Subprocess-based protocols can't spawn servers in serverless. HTTP servers need persistent processes that serverless doesn't provide |
| **Edge Devices** | 50 MB footprint with minimal config. Runs on any device with Python 3.10+ or native SDK | Server protocols need networking, ports, process management — hostile to constrained environments |
| **CI/CD Pipelines** | `crp dispatch` in a GitHub Action, GitLab CI, or Jenkins pipeline. No server to start, no port to expose, no cleanup needed | Starting an MCP server in CI requires subprocess management, port allocation, and teardown |
| **Jupyter Notebooks** | `import crp` in a cell. Full interactive session. Zero setup | Running a subprocess or HTTP server from a notebook is awkward, fragile, and clutters output |
| **Desktop Applications** | Embedded in Electron, Tauri, PyQt, or native desktop apps. No background services, no port conflicts with other apps | Users shouldn't manage a separate service process for their desktop application |
| **Mobile** (via native SDK) | Native Rust/C SDK embedded in iOS/Android apps via FFI. ~10 MB binary + models on demand | HTTP/stdio servers are hostile to mobile lifecycle (backgrounding, suspension, battery management) |
| **WebAssembly** (future) | CRP core logic compiled to WASM, running in browser or WASM runtime. No server possible, no network for CRP — only the LLM API call | Server protocols require a server. WASM environments have no subprocess or local network capability |
| **IoT / Embedded Systems** | Minimal CRP (Stages 1-2) on constrained devices with remote LLM API access. 50 MB, single core | Multiple processes, pipe management, HTTP servers are untenable on constrained hardware |
| **Air-Gapped Environments** | CRP + local LLM (Ollama). Entire system runs without internet. No external services needed | Same capability, but embedded deployment eliminates even local networking between CRP and the app |
| **Multi-Tenant SaaS** | Each tenant request gets an independent CRP session. No shared server state, no session routing, no session confusion | Server protocols need complex session routing and state management across tenants |
| **Plugin Systems** | CRP embedded as a plugin in larger applications (VS Code extensions, JetBrains plugins, Obsidian plugins). Library loads into the host process | Plugin hosts typically can't reliably manage external server processes |
| **Test Suites** | `import crp` in unit tests. Spin up a session, run assertions, tear down. No test infrastructure | Server protocols require test fixtures to start/stop servers, manage ports, handle timeouts |

### 4.2 Scenarios Enabled by Embedded Deployment

**Scenario 1 — Serverless Document Processing**:
```
AWS Lambda → import crp → process document → extract facts → write to S3 → terminate
```
Each Lambda invocation loads CRP (~200ms), processes the input, writes results. No persistent infrastructure. Pay per invocation. CRP's state flushes to S3 (cold storage) and resumes on next invocation.

**Scenario 2 — CLI Pipeline Composition**:
```bash
find . -name "*.py" | crp ingest --session analysis | crp dispatch --task "Find security issues"
```
CRP composes with UNIX tools. No servers to start or stop. Pipe semantics work naturally because CRP is just a program, not a client-server pair.

**Scenario 3 — Real-Time Web Application**:
```python
# Inside a FastAPI endpoint
@app.post("/analyze")
async def analyze(request: AnalyzeRequest):
    result = await crp_session.dispatch(task_input=request.text)
    return {"analysis": result.output, "quality": result.quality}
```
CRP is a library call within the request handler. Sub-millisecond overhead for CRP operations; total latency is dominated by the LLM API call — where it should be.

**Scenario 4 — Offline / Air-Gapped**:
```python
session = crp.init(endpoint="http://localhost:11434", model="llama3.1")
# Entire system: application + CRP + Ollama + LLM model. No internet required.
# CRP's 50 MB + Ollama + model = complete AI system on a single machine.
```

**Scenario 5 — Notebook-Driven Research**:
```python
# Jupyter cell 1
import crp
session = crp.init(endpoint="http://localhost:11434", model="llama3.1")

# Cell 2
result = session.dispatch(task_input=open("paper.pdf").read())
print(f"Extracted {result.quality.facts_extracted} facts")

# Cell 3 — session persists across cells, interactive exploration
followup = session.dispatch(task_input="What are the key findings?")
```
The session lives as long as the kernel. No server management, no port conflicts, no connection timeouts between cells.

---

## 5. PROTOCOL DEPLOYMENT COMPARISON

| Dimension | MCP | gRPC | LSP | **CRP** |
|---|---|---|---|---|
| **Architecture** | Client-server (separate processes) | Client-server (network) | Client-server (separate processes) | **Embedded library (in-process)** |
| **Transport** | stdio (subprocess) or Streamable HTTP | HTTP/2 + Protocol Buffers | stdio or TCP/pipe | **Function calls (in-process)** |
| **Process model** | Client launches server subprocess OR connects to HTTP server | Service must be deployed and running | Editor launches language server | **Library import — no separate process** |
| **Network requirement** | stdio: none. HTTP: localhost or network | Always network (even localhost) | stdio: none. TCP: localhost | **None for CRP itself; only for LLM API calls** |
| **Startup overhead** | subprocess spawn (~50-200ms for stdio) | connection setup + TLS (~100-500ms) | subprocess spawn (~100-500ms) | **Zero — library loaded at import time** |
| **Session management** | `Mcp-Session-Id` header, server-managed state | gRPC metadata, application-managed | LSP `initialize` handshake | **`crp.init()` → `SessionHandle`, in-process state** |
| **Failure mode** | Server crash = dead subprocess, client must detect & restart | Connection failure, retry with backoff | Server crash, editor must restart | **Library exception — normal try/catch** |
| **Scaling** | One server per client (stdio) or shared server (HTTP) | Load balancer + replicas | One server per editor window | **One session per instance, sessions independent** |
| **Configuration** | Server config file + client capability negotiation | `.proto` files + service config | `initializationOptions` + capability exchange | **JSON/YAML/env vars, 5-layer hierarchy** |
| **Operational overhead** | Process lifecycle, port management, restart policies, log correlation | Deployment, TLS, service discovery, health checks | Process spawn, restart, crash recovery | **Zero** |
| **Security surface** | stdio: low. HTTP: DNS rebinding, port exposure, auth | TLS required, certificate management | stdio: low. TCP: port exposure | **Zero new attack surface** |

---

## 6. COMPARISON WITH MCP OPERATIONAL MODEL

MCP's operational complexity illustrates why CRP chose a different path.

### 6.1 MCP stdio Transport

The client (e.g., Claude Desktop, VS Code) spawns the MCP server as a subprocess. The server reads JSON-RPC from `stdin` and writes to `stdout`. This is elegant for tool integration but introduces operational challenges:

- The client must manage subprocess lifecycle (spawn, monitor, restart on crash)
- Each tool server is a separate process with its own dependencies
- Debugging requires capturing and correlating stdin/stdout across multiple processes
- The server cannot outlive the client — closing the client kills all servers
- State lives in the server process memory; crash = state loss

### 6.2 MCP Streamable HTTP Transport

The server is a standalone HTTP service. Clients connect via POST (sending messages) and GET (receiving SSE streams). Session management uses `Mcp-Session-Id` headers. This adds:

- Server deployment and hosting (must be running before client connects)
- Network configuration (ports, TLS, authentication)
- Session state management across connections (resumability, redelivery)
- DNS rebinding attack surface (security warning in MCP spec)

### 6.3 CRP Comparison

| MCP Operational Concern | CRP Equivalent |
|---|---|
| Spawn and monitor server subprocess | `import crp` (in-process) |
| Configure stdin/stdout JSON-RPC transport | Function calls (native language) |
| Manage `Mcp-Session-Id` across HTTP requests | `SessionHandle` returned from `init()` |
| Handle SSE stream disconnection & resumability | Not applicable (in-process) |
| Deploy & host HTTP server | Not applicable (embedded library) |
| TLS, DNS rebinding, port management | Not applicable (no network for CRP itself) |
| Coordinate multiple server processes | Single library, multiple sessions |
| Server crash recovery | Exception handling + event log replay |

**When CRP does need network**: The ONLY network dependency is the LLM API call. This is a single, well-understood HTTP client request with standard retry/timeout policies (Section 7). CRP does not introduce any new network services, ports, or protocols.

---

## 7. RETRY & TIMEOUT POLICIES

CRP's only network dependency is the LLM API call. Retry and timeout for this single external dependency:

### 7.1 Retry Policy

| Failure Category | Retryable | Strategy | Max Retries |
|---|---|---|---|
| HTTP 429 (Rate Limited) | Yes | Exponential backoff + `Retry-After` header | 5 |
| HTTP 500, 502, 503, 504 (Server Error) | Yes | Exponential backoff (1s, 2s, 4s, 8s, 16s) | 3 |
| HTTP 401, 403 (Auth Error) | No | Fail immediately | 0 |
| HTTP 400 (Bad Request) | No | Fail immediately | 0 |
| HTTP 404 (Not Found) | No | Fail immediately (model or endpoint wrong) | 0 |
| Network timeout | Yes | Exponential backoff | 3 |
| Connection refused | Yes (with delay) | Fixed 5s delay, then retry | 2 |
| TLS error | No | Fail immediately | 0 |
| Malformed response | Yes (once) | Single retry; if repeated, fail | 1 |

**Backoff formula**: `delay = min(backoff_base_ms × 2^attempt, backoff_max_ms) + jitter` where `jitter` is a random value in `[0, backoff_base_ms)`.

### 7.2 Timeout Budget

| Operation | Default Timeout | Configurable Via |
|---|---|---|
| Provider health check (init) | 10s | `timeout_ms` |
| Non-streaming completion | 120s | `timeout_ms` |
| Streaming first chunk | 30s | `timeout_ms / 4` |
| Streaming inter-chunk | 12s | `timeout_ms / 10` |
| Cold storage read | 5s | `CRP_COLD_STORAGE_TIMEOUT_MS` |
| Cold storage write | 10s | `CRP_COLD_STORAGE_TIMEOUT_MS` |
| Extraction (per stage) | 30s | `CRP_EXTRACTION_TIMEOUT_MS` |

All timeouts MUST be configurable. All retries MUST emit `crp.provider.retry` events.

---

## 8. HEALTH MONITORING

### 8.1 HTTP Sidecar Health Endpoints

Implementations exposing CRP via HTTP sidecar (Model 3) MUST provide:

| Endpoint | Method | Purpose | Response |
|---|---|---|---|
| `/health` | GET | Liveness probe — is the process alive? | `200 {"status": "ok"}` |
| `/ready` | GET | Readiness probe — is the session ready? | `200 {"status": "ready", "session_id": "..."}` or `503 {"status": "not_ready", "reason": "..."}` |
| `/metrics` | GET | Prometheus-format metrics (02_CORE §24.4) | `200` text/plain |

### 8.2 Embedded Library Health

For embedded library deployments (Model 1), equivalent information is available via:

```
FUNCTION health(session: SessionHandle) -> HealthStatus:
  RETURN HealthStatus {
    status: "ready" | "degraded" | "unhealthy",
    provider: session.provider_diagnostic(),  // current provider status
    warm_state_facts: session.fact_count(),
    uptime_s: session.uptime(),
    last_dispatch_s: session.time_since_last_dispatch(),
    extraction_stages_loaded: session.loaded_stages()
  }
```

---

## 9. CONTAINER & CLOUD DEPLOYMENT

CRP's embedded library model makes containerization trivial:

```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install CRP with standard extraction (Stages 1-4)
RUN pip install crprotocol[standard] --no-cache-dir

COPY . .

# CRP cold storage persists to /data (mount a volume)
ENV CRP_COLD_STORAGE_PATH=/data/crp
ENV CRP_LLM_ENDPOINT=https://api.openai.com/v1
# API key via secret mount, NOT env var in production
# ENV CRP_LLM_API_KEY injected at runtime

EXPOSE 8000
CMD ["python", "app.py"]
```

### Container Guidance

| Concern | Recommendation |
|---|---|
| **State persistence** | Mount a volume at `CRP_COLD_STORAGE_PATH`. Without it, cold state is lost on restart |
| **Secrets** | Use container secret mounts (Docker secrets, K8s secrets) for `CRP_LLM_API_KEY`. NEVER bake API keys into the image |
| **Memory limits** | Set container memory ≥ CRP RAM requirement for chosen config + application overhead. OOM kills lose in-flight state |
| **Health checks** | For sidecar mode: `HEALTHCHECK CMD curl -f http://localhost:9470/health`. For embedded: application-level health that calls `session.health()` |
| **Horizontal scaling** | Each container gets its own CRP session. Sessions do NOT share warm state by default. For shared knowledge, use cold storage on shared filesystem or object storage |
| **GPU** | Only needed if running a local LLM alongside CRP. CRP's extraction models are CPU-only by default |

---

## 10. THE DEPLOYMENT VALUE PROPOSITION

CRP's embedded deployment is not a compromise — it is the defining advantage.

| Property | Value |
|---|---|
| **Footprint** | 50 MB minimal, 200 MB standard, 500 MB full — smaller than most frameworks |
| **Startup** | < 100ms minimal, < 500ms with cloud LLM, < 3s with local model |
| **Infrastructure** | Zero. No servers, no ports, no containers for CRP itself, no orchestration. `import crp` |
| **Deployment reach** | Cloud, edge, serverless, notebooks, CI/CD, desktop, mobile (native), WASM (future), IoT, air-gapped, plugin systems, test suites |
| **Operational overhead** | Zero. CRP fails the way libraries fail — with exceptions in your stack trace |
| **Security surface** | Zero new attack surface. Process isolation is the security boundary. No DNS rebinding, no port exposure, no auth endpoints to protect |
| **Debugging** | Single process, single stack trace, single profiler. No cross-process correlation |
| **Scaling** | Your application's scaling strategy IS CRP's scaling strategy. No separate scaling concerns |

**CRP adds zero operational complexity to your application.** The only network call is to the LLM API — and you were already making that call.

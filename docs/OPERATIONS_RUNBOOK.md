# CRP Operational Runbook

> **Version:** 2.0.0  
> **Last Updated:** April 2026  
> **Audience:** DevOps, SRE, Platform Engineers

---

## 1. Deployment

### 1.1 Prerequisites

- Python ≥ 3.11
- `cryptography` package (mandatory — AES-256-GCM encryption)
- `sentence-transformers` (recommended — embedding + cross-encoder)
- LLM provider accessible (local or API)

### 1.2 Installation

```bash
pip install crprotocol[all]        # Full installation with all optional deps
pip install crprotocol[cli]        # CLI only (includes click)
pip install crprotocol             # Core library only
```

### 1.3 Configuration

CRP uses a 5-layer configuration hierarchy (later overrides earlier):

1. **Hardcoded defaults** — see the SDK source
2. **Environment variables** — `CRP_*` prefix (e.g., `CRP_MAX_CONTINUATIONS=100`)
3. **Config file** — `~/.crp/config.yaml`, `.crp.yaml` in CWD, or `CRP_CONFIG_FILE` env var
4. **Client constructor kwargs** — `crp.Client(max_continuations=100)`
5. **Runtime `configure()`** — `client.configure(log_envelopes=True)`

#### Config File Example (YAML)

```yaml
max_continuations: 100
max_dispatch_rate: 120
session_timeout: 3600
max_ram_mb: 1024
max_model_ram_mb: 512
process_priority: normal
encrypt_cold_state: true
log_envelopes: false
```

#### Important Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CRP_ENABLED` | `true` | Master enable/disable switch |
| `CRP_MAX_CONTINUATIONS` | `50` | Max continuation windows per task |
| `CRP_SESSION_TIMEOUT` | `86400` | Session timeout in seconds |
| `CRP_MAX_RAM_MB` | `512` | Memory budget in MB |
| `CRP_BINDING_SECRET` | `""` | HMAC session binding secret |
| `CRP_CONFIG_FILE` | — | Path to config file |

### 1.4 Docker Deployment

```dockerfile
FROM python:3.12-slim
RUN pip install crprotocol[all]
EXPOSE 9470
CMD ["crp", "serve", "--port", "9470", "--auth-token", "${CRP_AUTH_TOKEN}"]
```

### 1.5 Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: crp-sidecar
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: crp
        image: crp:2.0.0
        ports:
        - containerPort: 9470
        livenessProbe:
          httpGet:
            path: /health
            port: 9470
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /ready
            port: 9470
          periodSeconds: 10
        env:
        - name: CRP_AUTH_TOKEN
          valueFrom:
            secretKeyRef:
              name: crp-secrets
              key: auth-token
```

---

## 2. Scaling

### 2.1 Resource Guidelines

| Workload | RAM | Threads | Concurrency |
|----------|-----|---------|-------------|
| Light (< 100 facts) | 256 MB | 2 | 1-2 concurrent |
| Medium (100-1K facts) | 512 MB | 2-4 | 2-4 concurrent |
| Heavy (1K-10K facts) | 1-2 GB | 4-8 | 4-8 concurrent |
| Embedding models loaded | +300 MB | — | — |

### 2.2 Performance Tuning

- **Disable unused extraction stages** to reduce latency
- **Set `short_circuit_threshold`** to skip expensive ML stages when enough facts are extracted
- **Set `idle_model_timeout_s`** to unload ML models after idle period (default: 300s)
- **Adjust `max_dispatch_rate`** based on LLM provider limits
- **Use connection pooling** (built-in for Ollama, LM Studio providers)

### 2.3 Horizontal Scaling

CRP sessions are stateful — each session must remain on the same instance.  
For horizontal scaling:

1. Use sticky sessions (session affinity) at the load balancer
2. Deploy multiple sidecar instances behind a reverse proxy
3. Use `--max-sessions` to cap per-instance load

---

## 3. Backup & Restore

### 3.1 Session State

Session state is stored in the configured session directory (e.g. `sessions/`)
as JSON files.

```bash
# Backup
tar czf sessions_backup.tar.gz sessions/

# Restore
tar xzf sessions_backup.tar.gz
```

### 3.2 Telemetry Data

Telemetry JSONL files stored at the configured `telemetry_path`.

### 3.3 CKF Cold Storage

CKF persists to the configured cold-storage path.

---

## 4. Monitoring

### 4.1 Health Check

```bash
curl http://localhost:9470/health
```

Response:
```json
{"status": "ok", "active_sessions": 2, "max_sessions": 64, "version": "2.0.0"}
```

### 4.2 Readiness Probe

```bash
curl http://localhost:9470/ready
```

Returns 503 when at max session capacity.

### 4.3 Prometheus Metrics

```bash
curl http://localhost:9470/metrics
```

Key metrics:
- `crp_sidecar_active_sessions` — current session count
- `crp_dispatch_count` — total dispatches
- `crp_dispatch_latency_ms` — dispatch latency histogram
- `crp_overhead_ratio` — current overhead ratio

### 4.4 Session Status

```bash
curl http://localhost:9470/sessions/{session_id}/status
```

---

## 5. Incident Response

### 5.1 High Latency

1. Check `crp_dispatch_latency_ms` metrics
2. Check LLM provider health: `curl {provider_url}/health`
3. Look for circuit breaker state in logs: `"circuit_breaker"`
4. Check fact count: high warm store count (>5K) may slow envelope construction
5. Consider reducing `max_continuations` or enabling pipeline short-circuit

### 5.2 Memory Growth

1. Check `crp_facts_in_warm_store` gauge
2. Long sessions accumulate facts — use `session_timeout` to bound session lifetime
3. Check for ML model memory: embedding + cross-encoder ≈ 600 MB total
4. Set `idle_model_timeout_s` to unload unused models

### 5.3 Provider Failures

1. CRP implements circuit breaker with automatic recovery
2. Check logs for "circuit_breaker.opened" events
3. Half-open recovery occurs after 60s by default
4. All providers retry with exponential backoff (3 attempts)

### 5.4 Session File Accumulation

1. Session cleanup runs automatically with TTL (configurable)
2. Manual cleanup: `find sessions/ -mtime +7 -delete`
3. Check `CRP_SESSION_TIMEOUT` environment variable

### 5.5 Encryption Errors

1. CRP requires `cryptography` package — hard failure if missing
2. Check: `python -c "from cryptography.hazmat.primitives.ciphers.aead import AESGCM"`
3. Session keys are derived per-session — key rotation is automatic

---

## 6. Key Rotation

### 6.1 Session Binding Secret

The `CRP_BINDING_SECRET` can be rotated during deployment:

1. Set new secret in environment
2. New sessions use new key automatically
3. Existing sessions continue with their derived keys until timeout
4. The binding system supports versioned keys with graceful rollover

### 6.2 Encryption Keys

Session encryption keys are derived per-session from the binding secret.  
No manual key rotation needed — keys expire with sessions.

---

## 7. Security Checklist

- [ ] Set `CRP_BINDING_SECRET` to a strong random value
- [ ] Use `--auth-token` when running the sidecar
- [ ] Never use `--bind-all` without `--auth-token`
- [ ] Deploy behind TLS-terminating reverse proxy (nginx, Caddy)
- [ ] Set appropriate `max_sessions` and `rate_limit` values
- [ ] Review session timeout settings
- [ ] Ensure `cryptography` package is installed (hard requirement)
- [ ] Monitor `/metrics` endpoint for anomalies

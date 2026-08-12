# Running Tests

> Run the exact test files that validate each CRP module - one file at a time is
> safest, and a few optional settings prevent slow or stuck tests from blocking
> your workflow.

## Prerequisites

```bash
# Install CRP with dev dependencies
pip install -e ".[dev]"

# Verify pytest is available
python -m pytest --version
```

Dev dependencies include: `pytest>=7.4`, `pytest-asyncio>=0.21`, `pytest-cov>=4.1`.

## Test Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

## Running Tests

### One File at a Time (Recommended)

```bash
# Run a specific test file
python -m pytest tests/test_smoke.py -v --tb=short

# Run a specific test class
python -m pytest tests/test_phase1.py::TestErrors -v

# Run a specific test function
python -m pytest tests/test_phase2.py::TestStage1Regex::test_ipv4 -v

# Run with coverage
python -m pytest tests/test_phase3.py --cov=crp --cov-report=term
```

!!! danger "Never run all tests in parallel"
    Running the full suite simultaneously will max out CPU and memory. Always
    run one file at a time.

### Avoiding Stuck Tests

Some tests probe provider auto-detection, model loading, or network endpoints. If a
run hangs, install `pytest-timeout` and apply a per-test ceiling:

```bash
pip install pytest-timeout
python -m pytest tests/test_phase1.py -v --timeout=60
```

This is especially useful for the live-LLM, Gateway, and Comply proxy tests, which
may wait on external services.

### Windows GLiNER/torch mitigation

On Windows the full suite can hit an OpenMP duplicate-runtime crash inside GLiNER.
Disable GLiNER for test runs; rule-based extraction still runs and the suite remains
valid:

```powershell
$env:CRP_GLINER_DISABLED = "1"
python -m pytest tests/ -q --tb=short --ignore=tests/test_gap_fixes_live.py --ignore=tests/test_live_comprehensive.py --ignore=tests/test_live_full_capture.py --ignore=tests/test_live_long_generation.py --ignore=tests/test_live_verification.py
```

```bash
# Git Bash / WSL
export CRP_GLINER_DISABLED=1
python -m pytest tests/ -q --tb=short --ignore=tests/test_gap_fixes_live.py --ignore=tests/test_live_comprehensive.py --ignore=tests/test_live_full_capture.py --ignore=tests/test_live_long_generation.py --ignore=tests/test_live_verification.py
```

The `test_gap_fixes_live.py` and `test_live_*.py` files require a running local LLM
endpoint. Exclude them unless LM Studio/Ollama is available at the default URL.

## Shared Fixtures

Defined in `tests/conftest.py`:

| Fixture | Type | Purpose |
|---------|------|---------|
| `sample_task_intent` | `TaskIntent` | Minimal task with system prompt and input |
| `sample_system_prompt` | `str` | `"You are a helpful assistant."` |
| `sample_task_input` | `str` | `"What is CRP?"` |

Individual test files define additional fixtures inline for their specific needs.

---

## Test Categories

### Smoke Tests

**File**: `test_smoke.py`

Fast sanity checks that CRP imports correctly:

- Package version is a valid string
- `CRPError` exists and is an `Exception`
- `TaskIntent` has correct default values
- Core modules are importable

```bash
python -m pytest tests/test_smoke.py -v
# ~2 seconds
```

### Unit Tests: Core Phases

9 files covering all SDK phases:

| File | Phase | What It Tests |
|------|-------|--------------|
| `test_phase1.py` | Errors & Config | Error codes, session config, window sizing, orchestrator lifecycle, provider registration |
| `test_phase2.py` | Extraction | All 6 extraction stages, quality gate, contradiction detection, complexity analysis |
| `test_phase3.py` | Envelope | All 6 envelope building phases, token budgeting, fact packing, saturation |
| `test_phase4.py` | State & CKF | StateFact lifecycle, WarmStateStore, snapshots, compaction, cold storage, graph serialization |
| `test_phase5.py` | Continuation | Wall detection, gap analysis, stitch algorithm, echo detection, voice profiles, termination |
| `test_phase6.py` | Security | Session binding, fact HMAC integrity, encryption, input validation, injection detection, RBAC, rate limiting |
| `test_phase7.py` | Advanced | Auto-ingest, scale mode, hierarchical/parallel strategies, curator, meta-learning, batch, idempotency, cost model |
| `test_phase8.py` | CLI & Deploy | CLI commands, startup sequence, event emitter, deployment configuration |
| `test_phase9.py` | Observability | Metrics collection, audit trail, quality scores, telemetry, overhead measurement |

```bash
# Run Phase 2 (extraction)
python -m pytest tests/test_phase2.py -v --tb=short

# Run just the envelope tests
python -m pytest tests/test_phase3.py -v --tb=short
```

### Unit Tests: Specialized

Deep module-level coverage:

| File | Module |
|------|--------|
| `test_adaptive_allocator.py` | Resource allocator, hardware detection, EWMA, model unloading |
| `test_adversarial_provenance.py` | Edge cases: empty strings, unicode attacks, HTML injection, null bytes |
| `test_agentic.py` | Agentic architecture (§22): facilitator, task analysis, strategy routing |
| `test_ckf_gate.py` | CKF gate threshold, budget, retriever |
| `test_compliance_security.py` | Privacy, consent, audit trail, GDPR (§7.12–§7.15) |
| `test_compliance_wiring.py` | Audit entries for session/dispatch/ingest, PII scanning, lineage |
| `test_decision_provenance.py` | Envelope audit, LLM call audit, fact extraction audit |
| `test_decision_provenance_engine.py` | DPE: claim detection, attribution, provenance chains, reports |
| `test_entailment_risk.py` | NLI verification, hallucination risk scoring, heuristic fallback |
| `test_fidelity_verification.py` | Distortion, omission, fabrication, contradiction detection |
| `test_relay_strategies.py` | Reflexive, progressive, stream-augmented strategies (§21) |
| `test_resource_manager.py` | Resource lifecycle, meta-learning calibration, WindowMetrics |
| `test_security_modules.py` | Audit trail, privacy, injection, RBAC, encryption, integrity modules |
| `test_tool_relay.py` | Tool-mediated relay (§20), pull architecture, tool loop, fallback |

```bash
# Run provenance engine tests
python -m pytest tests/test_decision_provenance_engine.py -v

# Run security module tests
python -m pytest tests/test_security_modules.py -v
```

### v5 Feature Tests

CRP v5.1.0 adds dedicated test files for the new SDK, safety surface, and product
layers:

| File | Feature |
|------|---------|
| `test_sdk_level0.py` | Progressive SDK Level 0 - `complete()` governance summary |
| `test_sdk_level2.py` | Progressive SDK Level 2 - depth, tools, inspectable reasoning |
| `test_safety_control_plane.py` | Safety control plane registry and coverage maps |
| `test_unified_config.py` | `crp.config.yaml` and 5-layer config hierarchy |
| `test_cso.py` | Cognitive State Object preservation |
| `test_horizons.py` | Multi-horizon context blending |
| `test_scratch_buffer.py` | Ephemeral tool context / scratch buffer |
| `test_retrieval_integrity.py` | Recency decay, contradiction detection, coverage isolation |
| `test_stl.py` | Semantic Task Layer operations and orchestration |
| `test_gateway.py` | Gateway OpenAI-compatible lifecycle |
| `test_gateway_client.py` | Comply Gateway swap client |
| `test_github_app.py` | GitHub App token minting and remediation PRs |
| `test_scan_r3.py` | Scan remediation and semantic ingestion |
| `test_no_code.py` | No-code governance loop |
| `test_comply_billing.py` | Billing entitlement checks |
| `test_comply_quota_gate.py` | Quota enforcement |
| `test_checkpoint_inbox.py` | Human-in-the-loop checkpoint resolution |
| `test_orchestrator_perf.py` | Cold/warm init performance |
| `test_signup.py` | Signup flow |

```bash
# Run all SDK tests
python -m pytest tests/test_sdk_level0.py tests/test_sdk_level2.py -v

# Run v4 safety surface tests
python -m pytest tests/test_safety_control_plane.py -v

# Run STL tests
python -m pytest tests/test_stl.py -v
```

### Integration Tests

**File**: `test_integration.py`

Cross-module end-to-end tests using `CustomProvider` with controlled
`generate_fn`. No external APIs needed - everything runs locally with
mock responses.

```bash
python -m pytest tests/test_integration.py -v --tb=short
```

### Production Hardening

**File**: `test_production_hardening.py`

Tests for production reliability:

- Circuit breaker behavior
- Configuration validation
- Retry logic with backoff
- Session cleanup on crash
- Structured logging format
- Key rotation

```bash
python -m pytest tests/test_production_hardening.py -v
```

### Performance Benchmarks

**File**: `test_benchmarks.py`

Performance regression tests with specific targets:

| Benchmark | Target |
|-----------|--------|
| Cold session init | < 200ms |
| Warm session init | < 50ms |
| Dispatch overhead | < 100ms |
| Envelope assembly | < 50ms |
| Ingest throughput | > 100 facts/sec |
| Cache hit | < 1ms |
| Event emission | < 5ms |
| Metrics export | < 10ms |

```bash
python -m pytest tests/test_benchmarks.py -v
```

### Live Tests

**Requires a running LLM** (LM Studio or Ollama):

| File | What It Verifies |
|------|-----------------|
| `test_gap_fixes_live.py` | Gap fixes A–E against real LLM |
| `test_live_comprehensive.py` | Full protocol verification |
| `test_live_full_capture.py` | Output capture and analysis |
| `test_live_long_generation.py` | Long generation (standalone script) |
| `test_live_verification.py` | Additional live verification |

```bash
# Start LM Studio first, then:
python -m pytest tests/test_gap_fixes_live.py -v --tb=short
```

!!! info "LM Studio connection"
    Live tests connect to LM Studio at `http://192.168.0.6:1234` by default.
    Update the connection URL in the test file if your setup differs.

### Killer Test Suite

Standalone adversarial/stress test scripts in `tests/killer_test/`:

- `crp_killer_test.py` - Comprehensive stress test
- `debug_gap.py`, `debug_gap2.py` - Gap debugging utilities

Run directly with Python:

```bash
python tests/killer_test/crp_killer_test.py
```

## Tips

!!! tip "Use `--tb=short` for cleaner output"
    ```bash
    python -m pytest tests/test_phase2.py -v --tb=short
    ```

!!! tip "Run a specific test by keyword"
    ```bash
    python -m pytest tests/ -k "extraction" -v
    ```

!!! tip "Check coverage for a specific module"
    ```bash
    python -m pytest tests/test_phase6.py --cov=crp.security --cov-report=term-missing
    ```

!!! tip "Guard against hangs with pytest-timeout"
    ```bash
    pip install pytest-timeout
    python -m pytest tests/test_gateway.py -v --timeout=60
    ```

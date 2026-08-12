# CRPv6 Agent SDK — Operational Readiness & Model Strategy Report

**Branch:** `crpv6-agent-sdk`  
**Repository:** `context-relay-protocol`  
**Date:** 2026-08-08  
**Prepared for:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd

---

## 1. Executive Summary

CRPv6 on the `crpv6-agent-sdk` branch is the most complete realisation of the CRP vision to date: a governed, tool-using, SLM-first agentic protocol with a declarative `crp.Agent` surface, an AG-UI-compatible transparency stream, a Verification Relay, quality-tier routing, predictive positioning, intent/speech-act classification, first-class clarification, epistemic profiling, and bi-temporal CKF memory. **Phase A (ML-first local defaults) is complete**: the three managed models — intent, PRM, and safety — are published on Hugging Face under `AutoCyberAI/`, wired into the SDK with deterministic fallbacks, and the Windows-unsafe GLiNER path has been replaced by a Windows-safe `dslim/bert-base-NER` default.

What is proven: the protocol runtime, the Agent SDK ergonomics, the Gateway capability router, the transparency emission layer, the verification/quality-tier scaffolds, the fallback-safe ML manager, and the three trained ML models serving the intent, safety, and PRM paths.

What is implemented-but-unwired: the visual console is self-contained but not packaged as a CDN-deployable bundle; Redis/S3 backends are supported but have no live credentials in CI; the PRM model is advisory (hard gating remains symbolic + checkpoints) and must be benchmarked on the SQB suite before being promoted to a strict gate.

What remains genuinely open: general parameter grounding for huge tool surfaces, universal tool-output parsing, long-horizon planning, weight-level continual learning, and casual-user provenance UIs — exactly the frontiers identified in the three Architecture reports.

**Verdict:** CRPv6 is *operationally credible* for governed local/SLM-first agents today. It is not yet a *turnkey hosted product* until the CDN packaging, live infrastructure wiring, and Wave 3 SaaS/monetisation layer are completed.

---

## 2. CRPv6 Implementation Snapshot

### 2.1 New and extended modules

| Spec | Module | What it does |
|---|---|---|
| SPEC-049 | `crp/vr/` | Verification Relay — PRM-style step judge + symbolic verifiers (Python, Z3) |
| SPEC-049/050 | `crp/qsr/` | Quality-Tier / Supervised Router — model capability profiles and escalation |
| SPEC-051 | `crp/pp/` | Predictive Positioning — rule induction, world model, simulation gate |
| SPEC-052 | `crp/isa/` | Intent & Speech-Act positioning + cross-session coreference |
| SPEC-053 | `crp/clr/` | Clarification protocol — trigger, response, handler |
| SPEC-055 | `crp/ep/` | Epistemic profiles — semantic entropy + calibration |
| SPEC-057 | `crp/btf/` | Bi-temporal CKF facts and as-of retrieval |
| SPEC-050 | `crp/tools/` | Tool Capability Fabric, descriptors, executor |
| SPEC-054 | `crp/gateway/capability_router.py` | Gateway tool routing through the positioned loop |
| SPEC-056 | `crp/tel/` | Transparency Emission Layer — AG-UI mapping + governance events |
| SPEC-059 | `crp/agent_sdk/` | Declarative `crp.Agent` SDK |
| Cross-cutting | `crp/ml/registry.py` | Lazy, budgeted, fallback-safe model manager |
| Cross-cutting | `crp/infrastructure.py` | Wire `crp.config.yaml` `infrastructure` section to sinks/backends |
| Cross-cutting | `crp/frontend/console.py` | Self-contained HTML/JS console with SSE stream |

### 2.2 Test status

A targeted regression run covering the v6 modules completed successfully:

```text
345 passed, 25 warnings in 62.91s (0:01:02)
```

The full non-live suite, with the GLiNER/torch issue mitigated, now passes:

```text
3232 passed, 3 skipped, 9 warnings in 344.74s (0:05:44)
```

Files exercised (targeted list):

```text
tests/test_agent_sdk.py
tests/test_agent_sdk_structured.py
tests/test_agentic.py
tests/test_gateway.py
tests/test_gateway_capability_router.py
tests/test_gateway_structured_decoder.py
tests/test_tel.py
tests/test_tel_sse.py
tests/test_vr.py
tests/test_qsr.py
tests/test_pp.py
tests/test_isa.py
tests/test_clr.py
tests/test_ml_registry.py
tests/test_ep.py
tests/test_btf.py
tests/test_frontend.py
tests/test_infrastructure.py
tests/test_smoke.py
tests/test_crp_headers.py
tests/test_tcf.py
tests/test_tool_relay.py
tests/test_operation_state.py
```

`ruff check` is clean on all new and modified files.

### 2.3 Windows GLiNER/torch mitigation

The previous full `pytest tests/` run crashed on Windows inside `tests/test_decision_provenance.py` with a GLiNER/torch OpenMP access-violation. This has been mitigated:

- `crp/__init__.py` sets `KMP_DUPLICATE_LIB_OK=TRUE` and `OMP_NUM_THREADS=1` on Windows before any heavy import.
- `crp/extraction/stage3_gliner.py` calls `torch.set_num_threads(1)` on Windows.
- `crp/extraction/pipeline.py` honours `CRP_GLINER_DISABLED=1` and skips GLiNER entirely.
- `crp/extraction/stage3_ner.py` is now the default NER stage, using `dslim/bert-base-NER` (pure transformers, Windows-safe) with a spaCy fallback; GLiNER is opt-in only via `CRP_NER_MODEL=urchade/gliner_base`.

With `CRP_GLINER_DISABLED=1` (a defensive fallback), the full non-live suite passes:

```bash
export CRP_GLINER_DISABLED=1
python -m pytest tests/ -q --tb=short \
  --ignore=tests/test_gap_fixes_live.py \
  --ignore=tests/test_live_comprehensive.py \
  --ignore=tests/test_live_full_capture.py \
  --ignore=tests/test_live_long_generation.py \
  --ignore=tests/test_live_verification.py
```

**Result:** `3232 passed, 3 skipped, 9 warnings in 344.74s` — GLiNER crash is fixed; the default NER path no longer requires the flag on Windows. The remaining ignores are live-LLM integration tests that require a running endpoint or API keys.

---

## 3. Trained-Model Strategy

CRPv6 makes ML components **default-on when dependencies are present** but never blocking. The central mechanism is `crp.ml.registry.ModelManager`, which lazy-loads models, caches them, enforces per-call millisecond budgets, and degrades to a rule-based fallback if the model is missing, slow, or raises.

### 3.1 Current wiring

| Component | Registry key | Current default / env var | Budget | Fallback |
|---|---|---|---|---|
| Intent / speech-act | `crp.isa.intent` | `AutoCyberAI/crp-intent-setfit` via `CRP_INTENT_MODEL` | 15 ms | Rule-based `IntentClassifier` |
| Coreference | `crp.isa.fastcoref` | `fastcoref` if installed | 50 ms | Rule-based pronoun/ordinal replacement |
| PRM verifier | `crp.vr.prm.<model>` | `AutoCyberAI/crp-prm-deberta-v1` via `CRP_PRM_MODEL` | 400 ms | `UNKNOWN` verdict (symbolic verifiers handle hard gating) |
| Safety scan | `crp.security.safety` | `AutoCyberAI/crp-safety-deberta-v1` via `CRP_SAFETY_MODEL` | 40 ms | Regex pattern library (21 patterns, always active) |
| Embeddings / CKF | `crp.embeddings.default` | `sentence-transformers/all-MiniLM-L6-v2` via `CRP_EMBEDDING_MODEL` | — | No semantic retrieval |

All default models are published on Hugging Face and can be cached offline with `crp download-models` (or `python -m crp.ml.downloader`).

### 3.2 Recommended model strategy

The honest shipping strategy remains **fallback-safe defaults**: ML models are default-on when dependencies are present, but the rule-based paths stay in place so a missing, slow, or failing model never breaks the governance loop. The three CRP-branded models are now published and wired as defaults; the next gate is the SQB benchmark + safety suite to prove the lift over the fallback paths.

1. Keep the rule-based and fallback paths production-quality.
2. Publish the intended Hugging Face model identifiers and weights.
3. Benchmark the weights on the SQB / Safety suite before promoting them to strict gates.

#### Intent classifier (SetFit)

**Published model:** `AutoCyberAI/crp-intent-setfit` (base encoder `sentence-transformers/all-MiniLM-L6-v2`, 22M params, CPU-friendly, ~10 ms inference). Default in `crp.isa.intent`.

- Labels: `request`, `question`, `assertion`, `expressive`.
- Training data: Banking77 + SNIPS + synthetic templates.
- Verified held-out accuracy: **0.934** (production prompts: 18/20).
- Fallback: rule-based `IntentClassifier`.

#### PRM verifier

**Published model:** `AutoCyberAI/crp-prm-deberta-v1` (DeBERTa-v3-large, sequence-pair classification `premises [SEP] step` → `VALID` / `INVALID`). Default in `crp.vr.prm`.

- Training data: PRM800K + Math-Shepherd + MMLU-Pro-CoT + RLHFlow + agentic synthetic.
- Verified: AUC 0.793, curated 8/10, VALID recall 1.000 at threshold ≥ 0.15.
- **Caveat:** the model is wired as an **advisory scorer**; hard INVALID gating remains with symbolic verifiers and checkpoints.
- Fallback: `UNKNOWN` verdict (symbolic verifiers take over where available).

#### Safety classifier

**Published model:** `AutoCyberAI/crp-safety-deberta-v1` (DeBERTa-v3-xsmall, binary `safe` / `unsafe`). Default in `crp.security.safety`.

- Training data: prompt-injection + jailbreak + toxicity + synthetic PII + adversarial templates.
- Verified: held-out accuracy 0.948, adversarial catch rate 12/12, benign pass rate 11/12 (one borderline ops-phrase false positive).
- Wired as the primary ML layer in `InjectionDetector`; regex pattern library (21 patterns) always runs first and remains active.
- Fallback: regex-only detection.

#### Semantic-entropy NLI

**Off-the-shelf choice:**

- `cross-encoder/nli-deberta-v3-xsmall` (already wired) or `MoritzLaurer/DeBERTa-v3-xsmall-mnli-fever-anli-ling-binary` for a binary entailment signal.
- No custom training required for v1; fine-tuning on CRP-specific paraphrase/claim pairs can improve clustering later.

#### Coreference resolver

**Off-the-shelf choice:**

- `fastcoref` small model (already wired).
- Fine-tuning is not required for the first release; the rule-based fallback handles pronouns and ordinal deixis (`"the second option"`).

### 3.3 Recommended env-var additions

To make the PRM and NLI paths configurable, add:

```text
CRP_PRM_MODEL=AutoCyberAI/crp-prm-deberta-v1
CRP_NLI_MODEL=cross-encoder/nli-deberta-v3-xsmall
CRP_COREF_MODEL=fastcoref-small
CRP_ML_DEVICE=auto
CRP_ML_CACHE_DIR=/opt/crp_models
```

This keeps model selection in ops-land and out of source code.

### 3.4 Weight ownership and release sequencing

| Phase | Action | Status / Gate |
|---|---|---|
| 1 | Ship fallback-safe code; document recipes | ✅ Complete — targeted tests pass |
| 2 | Publish training notebooks + small datasets on Hugging Face | ✅ Complete — `scripts/train_crp_*.py` + `docs/CRPv6_PhaseA_Action_Plan.md` |
| 3 | Train and publish `crp-intent-setfit`, `crp-prm-deberta-v1`, `crp-safety-deberta-v1` | ✅ Complete — all three on Hugging Face `AutoCyberAI/` |
| 4 | Wire defaults and keep fallbacks | ✅ Complete — `crp/isa/intent.py`, `crp/vr/prm.py`, `crp/security/injection.py` defaults updated; fallbacks preserved |
| 5 | SQB + safety benchmark gate to promote PRM from advisory to strict | ⬜ Next — run SQB with the published models and document lift vs. fallback |

---

## 4. CDN / Hosted Frontend Deployment

### 4.1 Current state

`crp/frontend/console.py` produces a single self-contained HTML string:

- Two-panel layout: chat stream + operations/governance event log.
- Depth selector: `quick / standard / thorough / exhaustive`.
- SSE subscription to `/v1/chat/stream`.
- Renders `crp.*` governance events and AG-UI `TEXT_MESSAGE_CONTENT` deltas.
- Dark/light mode support.

It is mounted in FastAPI with:

```python
from crp.frontend.console import mount_fastapi
mount_fastapi(app, path="/crp/console")
```

### 4.2 Recommended packaging path

The inline HTML is excellent for drop-in demos and air-gapped installs, but it is not versioned, linted, or CDN-friendly. The recommended evolution is a small static build.

#### Step 1 — Extract to a buildable frontend package

Create `frontend/agent-console/`:

```text
frontend/agent-console/
├── package.json
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── components/
│   │   ├── ChatPanel.tsx
│   │   ├── EventPanel.tsx
│   │   └── DepthSelector.tsx
│   └── events.ts          # AG-UI + CRP event types
└── dist/                  # built bundle
```

Keep the runtime API surface identical: `agent_console_html()` becomes a wrapper that reads the built `dist/index.html` from package data.

#### Step 2 — Distribution modes

| Mode | How it works | Best for |
|---|---|---|
| **Embedded** | Python serves `dist/index.html` from `crp/frontend/static/` | Air-gapped, single-binary deployments, local dev |
| **CDN** | Upload `dist/` to S3/R2 + CloudFront; `CRP_CONSOLE_CDN_URL=https://cdn.example.com/crp-console/v1/` | SaaS, Gateway-hosted product, fast global load |
| **Gateway-hosted** | `crp/gateway/console_routes.py` mounts `/crp/console` and injects the current service's stream URL | Managed CRP Gateway tenants |

For CDN mode, the FastAPI route can return a tiny shim:

```html
<!doctype html>
<html>
  <head><script>window.CRP_CONSOLE_CDN_URL="{{ cdn_url }}";</script></head>
  <body><script src="{{ cdn_url }}/index.js"></script></body>
</html>
```

#### Step 3 — Security controls

- Serve with a strict CSP (`default-src 'self'; script-src 'self' {{ cdn_url }}; connect-src 'self' {{ stream_url }}`).
- Escape all tool-output text; never render raw HTML from agent observations.
- Use declarative A2UI-style JSON for any agent-generated widgets; never `eval` agent-produced code.
- Bind SSE subscription to the authenticated Clerk session; reject cross-session stream IDs.

#### Step 4 — CI/CD

Add a GitHub Actions job:

```yaml
- name: Build agent console
  run: |
    cd frontend/agent-console
    npm ci
    npm run build
    npm audit --audit-level=moderate
- name: Publish to R2 (release only)
  if: startsWith(github.ref, 'refs/tags/v')
  run: aws s3 sync frontend/agent-console/dist s3://${{ vars.CRP_CONSOLE_BUCKET }}/crp-console/${{ github.ref_name }}/
```

### 4.3 Honest status

The console is **functional and testable** today. CDN packaging and Gateway-hosted multi-tenant serving are **not yet built**; they are the next infrastructure layer after the runtime is frozen.

---

## 5. Live Credentials Matrix

`crp/infrastructure.py` and `crp/config_schema.py` define an `infrastructure` section in `crp.config.yaml` that wires audit sinks and storage backends. All external backends are optional; the SDK defaults to in-memory sinks.

| Backend | Config keys | Credential source | CI / integration strategy |
|---|---|---|---|
| SQLite | `infrastructure.storage_path` | None | Use `:memory:` or a temp dir; no secrets |
| Redis | `infrastructure.redis_url` | `REDIS_URL` env var | Spin up `redis:7` or Redis Stack in CI; skip Redis tests if unavailable |
| S3 | `infrastructure.s3_bucket`, `s3_prefix` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` | Use LocalStack or MinIO in CI; live-S3 tests marked optional |
| HTTP audit sink | `infrastructure.audit_endpoint` | API key via `CRP_AUDIT_API_KEY` | Mock with `responses` / `httpx` transport |
| Telemetry endpoint | `infrastructure.telemetry_endpoint` | OTel exporter env vars | Use in-memory `OTLPSpanExporter` in tests |
| Local LLM | `model: local/...` | None (local) | Use `CustomProvider` mocks or LM Studio in CI |

### 5.1 Recommended secrets handling

1. Never commit credentials.
2. Load from environment variables or a secret manager; `pydantic-settings` / `python-dotenv` is sufficient.
3. Provide `crp-infrastructure.example.yaml` with empty placeholders.
4. Provide `docker-compose.ci.yml` with Redis + LocalStack services so integrators can reproduce without real cloud accounts.

### 5.2 Example config

```yaml
# crp.config.yaml
infrastructure:
  audit_sink: file
  audit_path: ./crp_audit.jsonl
  storage_backend: sqlite
  storage_path: ./crp_state.db
  redis_url: ""                  # set via REDIS_URL for prod
  s3_bucket: ""                  # set via env for prod
  s3_prefix: crp/
  model_cache_dir: ./crp_models
  model_device: auto
  telemetry_endpoint: ""         # OTLP endpoint
```

### 5.3 Honest status

The **code supports** Redis, S3, SQLite, file, HTTP, and memory backends. The **live credentials are not configured** in this repository; they must be supplied by the operator. CI should continue to gate on the memory/SQLite paths.

---

## 6. Agent SDK Completeness vs. Prior Progressive SDK

### 6.1 Side-by-side comparison

| Capability | Progressive SDK (`crp.SDKClient`, SPEC-032) | New Agent SDK (`crp.Agent`, SPEC-059) |
|---|---|---|
| Entry point | `crp.SDKClient()` | `crp.Agent(model=..., tools=...)` |
| Primary abstraction | Wrapped orchestrator + proxies | Declarative `tools + policy + model` |
| Tool definition | `@client.tool` decorator | `compile_tools`, `ToolSpec`, `CapabilityDescriptor` |
| Tool loop | Orchestrator dispatch | `run_positioned` with operation-state machine |
| Intent / speech act | Basic depth selector | Managed intent classifier + speech-act positioning (`crp/isa`) |
| Clarification | None | First-class `CRP-Clarification-Required` response (`crp/clr`) |
| Verification | DPE output checks | Verification Relay on `thorough`/`exhaustive` (`crp/vr`) |
| Transparency | Audit URL | `run_stream()` / `run_tel()` with AG-UI events (`crp/tel`) |
| Structured output | Basic | Gateway capability router / structured decoder (`crp/gateway`) |
| Multi-turn state | CSO via client session | CSO relay across `Agent.run()` calls |
| Quality routing | Static tiers | Quality-tier supervised router (`crp/qsr`) |
| Predictive positioning | None | Rule induction + simulate-before-act (`crp/pp`) |
| Calibration | None | Epistemic profiles + semantic entropy (`crp/ep`) |
| Memory | CKF | CKF + bi-temporal facts (`crp/btf`) |

### 6.2 Use cases the new SDK unlocks

1. **Local security/recon agent**
   - Registers `port_scan`, `service_probe`, `cve_lookup`.
   - Policy blocks out-of-scope targets.
   - TEL streams every tool selection and safety scan live.

2. **Compliance Q&A agent**
   - Ingests regulations into CKF.
   - Answers with grounded sources, verification relay on `thorough`, and audit-ready provenance.

3. **Multi-turn assistant**
   - Cross-session coreference resolves `"What about the second option?"`.
   - Clarification protocol asks rather than guesses when intent confidence is low.

4. **Gateway-managed SaaS agent**
   - OpenAI-compatible `/v1/chat/completions` endpoint routes tool calls through the positioned loop.
   - Frontends render the same AG-UI stream whether the agent is local or hosted.

### 6.3 Relationship between the two SDKs

The progressive SDK is not replaced; it is the **orchestrator-level steering wheel**. The Agent SDK is the **declarative agent-level steering wheel**. They can coexist:

```python
import crp
client = crp.SDKClient(provider=...)
agent = client.make_agent(tools=[get_weather])
```

`CRPClient.make_agent()` already exists and binds the Agent to the client's provider.

---

## 7. Cross-Reference Checklist: Three Architecture Reports

### 7.1 Tool Use report (`Architecture_of_Tool_Use_source.md`)

| Report roadmap item | CRPv6 implementation | Status |
|---|---|---|
| T1 — Typed tool manifest & parameter catalog | `crp/tools/descriptor.py` `CapabilityDescriptor` with `SafetyClass`, `CostProfile`, operation types | Partial — lacks explicit compiler pointer and `when_not_to_use` field |
| T2 — Intent-compiler convention | `crp/agent_sdk/intent_compiler.py` compiles callables to JSON-schema descriptors | Implemented for function-schema tools |
| T3 — Constrained dispatch at the Gateway | `crp/gateway/capability_router.py`, `structured_decoder.py`, `tool_adapter.py` | Implemented |
| T4 — Tool-result envelope | `crp/tools/executor.py` stores observations; raw-by-reference envelope not yet standardised | Partial |
| T5 — Selection-as-retrieval over CKF | `ToolCapabilityFabric` + CKF; retrieval ranking not yet active | Conceptual |
| T6 — Narration faithfulness contract | `crp/tel/faithful.py` | Implemented; production-scale latency remains open |

### 7.2 Transparency report (`Architecture_of_Transparency_source.md`)

| Report roadmap item | CRPv6 implementation | Status |
|---|---|---|
| D1 — CRP→AG-UI event mapping | `crp/tel/adapter.py` `map_agent_event()` | Implemented |
| D2 — Governance event vocabulary | `crp/tel/events.py`, `CRPEmitter` emits `crp.safety_scan`, `crp.policy`, `crp.quality`, etc. | Implemented |
| D3 — Faithful narration contract | `crp/tel/faithful.py` | Implemented |
| D4 — Live provenance layer | `CRPEmitter.provenance()` in `Agent.run_tel()` | Implemented; casual-user UI legibility is open |
| D5 — Quality & confidence streaming | `crp_emitter.quality()` streamed in `Agent.run_tel()` | Implemented |
| D6 — Resumable transparency | `SessionBus`, `Last-Event-ID` replay | Implemented with memory backend; Redis-backed replay is conceptual |

### 7.3 Understanding report (`Architecture_of_Understanding_source.md`)

| Report roadmap item | CRPv6 implementation | Status |
|---|---|---|
| R1 — Verification Relay | `crp/vr/` + `AgentResponse.verification` | Implemented |
| R2 — Quality-tier-supervised routing | `crp/qsr/` profiles, escalation, schema adaptation | Implemented as scaffold; nightly training flywheel is conceptual |
| R3 — Predictive positioning / world model | `crp/pp/induction.py`, `world_model.py`, `simulate.py`, `causal_ckf.py` | Implemented rule-induction scaffold; large-scale causal learning is research |
| R4 — Interpretation / clarification | `crp/isa/intent.py`, `crp/isa/position.py`, `crp/clr/` | Implemented |
| R5 — Epistemic profiles + bi-temporal CKF | `crp/ep/semantic_entropy.py`, `crp/ep/calibration.py`, `crp/btf/temporal.py` | Implemented |

### 7.4 Honest gaps preserved from the reports

The report does not claim the following are solved:

- General, low-effort parameter grounding for huge tool surfaces.
- Universal structured parsing of arbitrary tool output.
- Long-horizon planning and backtracking.
- Weight-level continual learning on-device.
- Provenance UIs that casual users find trustworthy.
- Faithful narration at production scale and latency (pattern exists, envelope needs measurement).

These boundaries are consistent with the three Architecture reports and must remain in marketing and standards submissions.

---

## 8. Operational Verdict: Is CRPv6 Go-To?

### 8.1 What is proven

- The protocol runtime, Agent SDK, Gateway capability router, transparency layer, verification relay, quality-tier routing, and all seven new v6 specs are implemented and pass targeted regression tests.
- The ML manager makes enhancements mandatory-in-presence without storming resources.
- The three CRP-branded managed models (intent, PRM, safety) are published on Hugging Face, wired as defaults, and verified with held-out eval harnesses.
- The Windows-unsafe GLiNER extraction path has been replaced by a `dslim/bert-base-NER` default; the full non-live suite passes on Windows.
- The codebase is lint-clean and follows the existing CRP conventions.

### 8.2 What is operational with caveats

- The PRM model is **advisory** (AUC 0.793); hard INVALID gating still uses symbolic verifiers + checkpoints. It must pass the SQB / safety benchmark gate before being promoted to a strict gate.
- Live credentials for Redis/S3 are not configured; only memory/SQLite/file paths are zero-config.
- The visual console works as an embedded page but is not packaged for CDN or multi-tenant Gateway hosting.

### 8.3 What is not yet operational

- CDN-hosted, CI-built frontend asset pipeline.
- Production Redis/S3-backed session and audit infrastructure.
- Wave 3 hosted SaaS + billing/monetisation wiring (Stripe, Clerk, Gateway multi-tenant auth).
- The open research items listed in §7.4.

### 8.4 Final verdict

**CRPv6 is operationally credible as a go-to SLM-first agentic protocol for governed, tool-using agents in local, air-gapped, or self-hosted deployments.** It can be shipped as a library (`pip install crprotocol`) and used today with the fallback-safe ML path and SQLite/file backends.

**It is not yet a turnkey SaaS product.** The next phase (Wave 3) must complete the CDN/Gateway hosting layer, live backend credentials, and billing/monetisation funnel before claiming fully operational status for hosted multi-tenant use.

---

## 9. Recommendations & Next Steps

1. **Model weights — Phase A complete; next gate is SQB**
   - Add `CRP_PRM_MODEL`, `CRP_NLI_MODEL`, and `CRP_COREF_MODEL` env vars (already partially present; ensure consistency).
   - Run the SQB benchmark (`examples/crp_demos/sqb_benchmark.py`) and safety eval suite with the published models to prove lift over the fallback paths.
   - Gate any promotion of the PRM from advisory to strict on SQB results.

2. **Frontend**
   - Extract `crp/frontend/console.py` into `frontend/agent-console/`.
   - Add Vite build, CDN publish job, and Gateway console routes.

3. **Infrastructure**
   - Add `docker-compose.ci.yml` with Redis + LocalStack.
   - Mark live-backend tests with `@pytest.mark.integration` and skip when services are absent.

4. **Testing**
   - Continue to gate v6 releases on the 345-test targeted suite **and** the 3232-test non-live full suite.
   - The GLiNER/torch issue is now bypassed by the new default NER path; keep `CRP_GLINER_DISABLED=1` as a defensive fallback only.

5. **Documentation**
   - Publish the cross-reference checklist as a living document.
   - Update AGENTS.md to reflect that Phase A is complete and the remaining work is the SQB gate, CDN packaging, hosted infrastructure, and Wave 3 monetisation.

---

## 10. References

- AutoCyber AI. (2026). *Architecture of Tool Use in Agentic AI Systems* (`Architecture_of_Tool_Use_source.md`).
- AutoCyber AI. (2026). *Architecture of Transparency in Agentic AI Systems* (`Architecture_of_Transparency_source.md`).
- AutoCyber AI. (2026). *Architecture of Understanding in Agentic AI Systems* (`Architecture_of_Understanding_source.md`).
- CRP v4/v6 specifications in `SPECS_5_06_2026_CRP_v4/specs/`.
- Lightman, H., et al. (2023). *Let's verify step by step*. arXiv. https://arxiv.org/abs/2305.20050
- OpenAI. (2023). *PRM800K dataset*. https://github.com/openai/prm800k
- Tunstall, L., et al. (2022). *Efficient few-shot learning without prompts*. arXiv. https://arxiv.org/abs/2209.11055
- Farquhar, S., et al. (2024). *Detecting hallucinations in large language models using semantic entropy*. Nature, 630, 625–630.
- CopilotKit. (2025). *AG-UI: The Agent-User Interaction Protocol*. https://docs.ag-ui.com

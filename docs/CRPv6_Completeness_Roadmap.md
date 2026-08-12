# CRPv6 Completeness Roadmap — ML-First Local SDK → Hosted Ecosystem

**Goal:** CRPv6 is a complete, ML-driven agentic AI ecosystem. `pip install crprotocol` gives you AI-first agents with SLMs locally; hosted mode gives you multi-tenant SaaS. Rule-based logic becomes the **degraded/offline path**, not the default.

---

## 1. Design principle: ML-first, fallback-second

Current state: ML components are optional enhancements with rule-based fallbacks.
Target state: every AI subsystem has a default trained model; rule-based code only activates when:

- the user explicitly opts into `crp[nominl]` or sets `CRP_ML_MODE=disabled`.
- the model has not been downloaded yet and the network is unavailable.
- latency budget is exceeded.
- a strict air-gapped deployment chooses deterministic mode.

This changes the contract from "works without ML" to "works best with ML, survives without it."

---

## 2. Local `pip install crprotocol` completeness

### 2.1 Core ML weights that must exist and be downloaded automatically

| Subsystem | Model | Current placeholder | What needs to happen |
|---|---|---|---|
| Intent / speech-act | SetFit text classifier | `AutoCyberAI/crp-intent-setfit` | Train and publish the SetFit model; make it the default. Package should download it on first use and cache it. |
| Process reward / step verification | DeBERTa-v3-small sequence classifier | `AutoCyberAI/crp-prm-deberta-v1` | Train on PRM800K and publish. Used by `crp.vr.prm.ProcessRewardVerifier` as default. |
| Semantic entropy / NLI | `cross-encoder/nli-deberta-v3-xsmall` | Already wired | Keep as default. Optional fine-tune on CRP-specific entailment pairs. |
| Coreference | `fastcoref` | Already optional | Make `fastcoref` part of `[full]` extras and default-on; publish a smaller CRP coref model if needed. |
| Entity extraction | GLiNER small | `urchade/gliner_base` | Replace with a smaller, Windows-safe NER model or quantize GLiNER; `CRP_GLINER_DISABLED` becomes unnecessary. |
| Injection / safety scan | Small text-classifier | Regex-only default today | Train/publish a small safety classifier (`AutoCyberAI/crp-safety-deberta-v1`) for prompt-injection, toxicity, PII. |
| Claim / fact extraction | Small span classifier | Regex/statistical stages | Add a small generative/extractive model for claim detection in `crp.provenance`. |

**Concrete deliverables:**

1. Publish Hugging Face repos under `autocyber/` for each placeholder model.
2. Update defaults in:
   - `crp/isa/intent.py` → default `AutoCyberAI/crp-intent-setfit`
   - `crp/vr/prm.py` → default `AutoCyberAI/crp-prm-deberta-v1`
   - `crp/security/injection.py` → add managed safety classifier
   - `crp/provenance/claim_detector.py` → add managed claim extractor
3. Add `crp.cli download-models` command that pre-downloads and verifies all weights.

### 2.2 Model delivery and runtime management

Current: `crp.ml.registry.ModelManager` is good scaffolding but uses placeholder IDs.
Missing:

- **Version-pinned model manifest** (`crp/ml/manifest.json`) shipped with each `crprotocol` release.
- **Offline/air-gapped mode**: `crp download-models --dir ./crp_weights` + `CRP_MODEL_DIR=./crp_weights`.
- **Quantization path**: GGUF/ONNX variants for CPU-only SLM deployments.
- **GPU/CPU auto-selection** with memory guards (unload models when RAM is low).
- **Model health endpoint**: `crp.ml.MANAGER.status()` reporting loaded / failed / budget-exceeded models.

Files to extend:

- `crp/ml/registry.py` → manifest loading, offline mode, quantization hooks.
- `crp/ml/manifest.json` (new) → pinned model IDs, revisions, hashes, optional variants.
- `crp/cli/main.py` → `download-models`, `model-status` commands.

### 2.3 Local SLM runtime stack

Current: providers for OpenAI, Anthropic, Ollama, llama.cpp, LM Studio exist.
Target: local SLM is a first-class citizen, not an adapter.

Needed:

- **Default local model profile**: a recommended 3B–7B model list (Qwen2.5, Phi-4, Llama-3.2, Gemma-2) with tested tool-call templates.
- **Built-in tool-call parsers** for models without native function calling.
- **SLM-specific prompt templates** per model family.
- **One-command local runtime**: `crp serve --local-model Qwen/Qwen2.5-7B-Instruct` that downloads and runs via `llama-cpp-python` or vLLM (if GPU).
- **Structured output for SLMs**: constrained decoding, retries, schema repair.

Files to extend:

- `crp/providers/openai.py`, `crp/providers/ollama.py`, `crp/providers/llamacpp.py`.
- `crp/gateway/structured_decoder.py` (already exists; expand model coverage).
- `crp/tools/executor.py` → better tool-result parsing and error narration.
- Add `crp/providers/local_model_catalog.py`.

### 2.4 Knowledge, retrieval, and memory stack

Current: CKF graph, CDR/CDGR, multi-horizon context, scratch buffers, bi-temporal CKF.
Missing for ML-first completeness:

- **Default local embedding model** (e.g. `sentence-transformers/all-MiniLM-L6-v2`) shipped and cached.
- **Local vector index** (FAISS or HNSW) as default, not just graph traversal.
- **Document ingestion pipeline** with format support (PDF, DOCX, markdown, code).
- **Automatic chunking + relation extraction** using a small model.
- **Persistent local knowledge** via SQLite + vector store out of the box.

Files to extend:

- `crp/state/backends/sqlite.py` → add vector extension or companion FAISS index.
- `crp/ckf/` → add `vector_retriever.py` and `document_ingester.py`.
- `crp/extraction/pipeline.py` → use small extraction model by default.

### 2.5 Tool and agent execution stack

Current: Tool Capability Fabric, capability executor, Agent SDK.
Missing:

- **Built-in tool library**: web search, file system, Python execution, shell (sandboxed), database query, HTTP client.
- **Tool result summarization model** so small models see compact observations.
- **Multi-tool planning model** for long-horizon tasks.
- **Agent templates**: `crp.Agent.research()`, `crp.Agent.coder()`, `crp.Agent.compliance_reviewer()`.

Files to extend:

- `crp/tools/builtins/` (new package).
- `crp/agent_sdk/agent.py` → add templates and planner hooks.
- `crp/stl/orchestrator.py` → use model-based planning.

### 2.6 Safety, provenance, and verification stack

Current: Safety control plane, DPE, provenance chain, verification relay.
Missing:

- **ML-based safety classifier** as default (toxicity, injection, PII, secrets).
- **Grounding / attribution model** for claim-to-source matching.
- **Hallucination-risk model** fine-tuned on CRP-specific failure modes.
- **Contradiction detection model** beyond heuristics.

Files to extend:

- `crp/security/injection.py`, `crp/security/privacy.py`.
- `crp/provenance/attribution_scorer.py`, `crp/provenance/hallucination_scorer.py`.
- `crp/vr/prm.py` and `crp/vr/relay.py`.

### 2.7 Developer experience

Needed:

- `crp init` scaffolds a project with `crp.config.yaml`, `.env.example`, and sample agent.
- `crp doctor` checks models, backends, and provider connectivity.
- `crp bench` runs the SQB benchmark locally.
- Rich error messages when a model is missing with a download command.

### 2.8 Packaging

Current extras: `[full]`, `[nlp]`, `[security]`, `[cli]`.
Target extras:

- `pip install crprotocol` → core SDK with small CPU models auto-downloaded.
- `pip install crprotocol[local-llm]` → llama.cpp + local model catalog.
- `pip install crprotocol[gpu]` → CUDA variants of managed models.
- `pip install crprotocol[airgap]` → no network; expects pre-downloaded weights.

---

## 3. Hosted / SaaS completeness

### 3.1 Gateway service

Current: `crp/gateway/capability_router.py` and `api.py` exist.
Needed:

- Multi-tenant tenant isolation (org ID in path/header).
- Authentication middleware (Clerk/Auth0/API keys).
- Provider key vault with per-tenant encryption.
- Rate limiting and quota enforcement.
- `/v1/chat/completions` OpenAI-compatible endpoint.
- `/v1/chat/stream` SSE endpoint.
- `/crp/console` route serving the console.
- Webhook endpoints for Stripe, Clerk, GitHub App.

Files to extend:

- `crp/gateway/api.py`.
- `crp/gateway/key_vault.py` (exists; harden).
- `crp/gateway/auth.py` (new).
- `crp/gateway/rate_limit.py` (new).

### 3.2 Model serving infrastructure

Needed:

- Hosted inference for managed models (intent, PRM, safety, NLI) via vLLM/TGI or dedicated microservices.
- Option to bring-your-own LLM API key.
- Model router that picks cheapest/fastest provider per request.
- GPU fleet for hosted SLMs if user does not bring a key.

### 3.3 Console and CDN

Current: `crp/frontend/console.py` is a self-contained HTML page.
Needed:

- Extract to `frontend/agent-console/` (Vite + React/Vue/Svelte).
- CI pipeline that builds and uploads `dist/` to S3/R2 + CloudFront.
- `CRP_CONSOLE_CDN_URL` support.
- Tenant-branded console (logo, colors).

### 3.4 Persistent backends

Current: SQLite default; Redis/S3 supported but not configured.
Hosted default should be:

- Redis for hot session state + SSE replay.
- S3/R2 for session archives and audit cold storage.
- PostgreSQL for user/tenant/billing data.
- ClickHouse or similar for analytics/audit warehouse.

### 3.5 Observability

Current: basic audit sinks.
Needed:

- OpenTelemetry traces and metrics.
- Structured JSON logs.
- Cost accounting per tenant/request.
- Dashboards (Grafana templates).

### 3.6 Billing and monetization

Current: `crp/monetisation/` scaffolding.
Needed:

- Stripe webhook handler robustly tested.
- Usage metering (tokens, operations, storage).
- Plan/tier enforcement.
- Clerk org metadata sync.

### 3.7 Compliance products

- **CRP Comply**: consumes Gateway evidence packs.
- **CRP Scan**: GitHub App for repo scanning + remediation PRs.
- These are separate products but must be first-class integrations.

---

## 4. Exact sequencing recommendation

### Phase A — Local ML-first defaults (highest priority)

1. Train and publish the SetFit intent model.
2. Train and publish the PRM DeBERTa model.
3. Add `crp/ml/manifest.json` and offline download command.
4. Switch defaults to the published models; keep rule-based as explicit fallback.
5. Replace GLiNER with a Windows-safe small NER model.
6. Add built-in local embedding + FAISS vector index.
7. Add `crp doctor` and `crp download-models`.

**Exit criteria:** `pip install crprotocol[full]` downloads all default models on first use and the full non-live suite passes without `CRP_GLINER_DISABLED`.

### Phase B — SLM runtime excellence

1. Add local model catalog and SLM-specific prompt templates.
2. Improve tool-call parsing for non-function-call models.
3. Add `crp serve --local-model <model>`.
4. Add built-in tools (search, Python, file, DB, HTTP).
5. Add agent templates.

**Exit criteria:** A user can build a useful tool-using agent with a 7B local model in < 10 lines without external APIs.

### Phase C — Hosted SaaS

1. Harden Gateway with auth, key vault, rate limiting.
2. Build CDN console pipeline.
3. Add Redis/S3/Postgres defaults in `crp.config.yaml`.
4. Add OTel observability.
5. Add Stripe/Clerk billing webhooks.
6. Add Comply and Scan integrations.

**Exit criteria:** A tenant can sign up, get an API key, and make governed AI calls through a hosted Gateway with a web console.

---

## 5. Honest current gaps

| Claim | Today | Needed for completeness |
|---|---|---|
| ML-first intent | Rule-based default, SetFit optional | Published SetFit model as default |
| Step verification | Rule/symbolic default, PRM optional | Published PRM as default |
| Safety scan | Regex/heuristic default | ML safety classifier as default |
| Local knowledge | CKF graph, no vector index by default | FAISS + embedding model default |
| Local SLM runtime | Adapters exist | First-class catalog + serve command |
| Hosted console | Inline HTML | Vite build + CDN |
| Hosted backends | Memory/SQLite default | Redis/S3/Postgres default |
| Billing | Scaffolding | End-to-end Stripe/Clerk flow |

---

## 6. Decision for you

The fastest path to a **credible ML-first v6.0.0** is:

1. **Train and publish the three core models** (intent, PRM, safety) — this is the blocker.
2. **Make model download automatic and offline-capable**.
3. **Replace GLiNER** so Windows does not need a special flag.
4. **Add a local vector index**.

Once those four are done, CRPv6 is a genuinely complete local agentic SDK. Hosting is then packaging and operations on top of that foundation.

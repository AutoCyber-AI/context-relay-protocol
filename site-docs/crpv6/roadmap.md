# CRPv6 Roadmap & TODOs

**Assumption:** [Phase A — ML-first local defaults](#phase-a-ml-first-local-defaults) is complete. Everything else is listed here with repo locations, AI components, skills, rationale, and implementation hints.

For the strategic rationale see the [Completeness Roadmap](completeness-roadmap.md). For training recipes see the [Model Training Guide](model-training-guide.md).

---

## Legend

- ✅ Complete
- 🔄 In Progress / Partial
- ⬜ Not Started

Each TODO includes:

- **AI component** — the model or technique involved.
- **Skill gained** — what you learn by doing it.
- **Why needed** — why it blocks a complete ecosystem.
- **Where** — file or directory in the repo.
- **How** — high-level path.

---

## Phase A — ML-First Local Defaults ✅

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| A1 | Publish SetFit intent model | SetFit classifier on `all-MiniLM-L6-v2` | Few-shot intent classification | Replaces rule-based intent default | [`crp/isa/intent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/isa/intent.py), [`scripts/train_crp_intent_setfit.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/scripts/train_crp_intent_setfit.py) | Train on Banking77+SNIPS+synthetic templates, push `AutoCyberAI/crp-intent-setfit`, flip default |
| A2 | Publish PRM DeBERTa model | DeBERTa-v3-small classifier | Process reward modeling | Replaces UNKNOWN default in verification relay | [`crp/vr/prm.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/vr/prm.py), [`scripts/train_crp_prm.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/scripts/train_crp_prm.py) | Fine-tune on PRM800K, push `AutoCyberAI/crp-prm-deberta-v1`, flip default |
| A3 | Publish safety classifier | Small DeBERTa multi-label classifier | AI safety, injection detection | Replaces regex/heuristic safety scan | [`crp/security/injection.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/security/injection.py) | Train on injection/toxicity/PII data, push `AutoCyberAI/crp-safety-deberta-v1`, wire into control plane |
| A4 | Replace GLiNER on Windows | Small NER/span model or quantized GLiNER | NER under constraints | Eliminates `CRP_GLINER_DISABLED=1` | [`crp/extraction/stage3_gliner.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/extraction/stage3_gliner.py) | Evaluate small NER models, default to Windows-safe option |
| A5 | Model manifest + offline download | Hugging Face caching + registry | MLOps, model versioning | Reproducible, air-gapped deployments | [`crp/ml/registry.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/ml/registry.py) | Add `crp/ml/manifest.json`, `crp download-models`, `CRP_MODEL_DIR` |
| A6 | Default embedding + vector index | `all-MiniLM-L6-v2` + FAISS/HNSW | Dense retrieval | CKF needs semantic retrieval | [`crp/state/backends/sqlite.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/state/backends/sqlite.py), [`crp/ckf/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/ckf) | Add FAISS helper, default embedding, hybrid graph+vector retrieval |

**Exit criteria:** `pip install crprotocol[full]` auto-downloads all default models and `pytest tests/` passes without `CRP_GLINER_DISABLED`.

---

## Phase B — SLM Runtime Excellence ⬜

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| B1 | Local model catalog | SLM chat templates | Prompt engineering for SLMs | Tested defaults for local models | [`crp/providers/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/providers) | Add `crp/providers/local_model_catalog.py` |
| B2 | Tool-call parsing for non-tool-native SLMs | Constrained decoding + retry | Structured generation | 7B models often lack function calling | [`crp/gateway/structured_decoder.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/gateway/structured_decoder.py), [`crp/tools/executor.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/tools/executor.py) | Regex/JSON-schema parsers + LLM repair |
| B3 | `crp serve --local-model` | llama.cpp / vLLM launcher | Local model serving | One-command local runtime | [`crp/cli/main.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/cli/main.py), [`crp/providers/llamacpp.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/providers/llamacpp.py) | Auto-download GGUF, start server, connect adapter |
| B4 | Built-in tool library | Web search, Python exec, filesystem, DB, HTTP | Tool design, sandboxing | Useful tools out of the box | [`crp/tools/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/tools) | Add `crp/tools/builtins/` package |
| B5 | Tool-result summarization | Extractive summarizer | Observation compression | SLMs need compact observations | [`crp/tools/executor.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/tools/executor.py) | Summarize JSON output before next turn |
| B6 | Agent templates | Task-specific prompts/tools | Agent pattern design | Reusable agent archetypes | [`crp/agent_sdk/agent.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/agent_sdk/agent.py) | Add `.research()`, `.coder()`, `.analyst()` |
| B7 | Long-horizon planner | Planning model | Hierarchical task planning | Long tasks need explicit plans | [`crp/stl/orchestrator.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/stl/orchestrator.py), [`crp/pp/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/pp) | Extend predictive positioning |

---

## Phase C — Hosted SaaS ⬜

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| C1 | Gateway auth + tenant isolation | — | Multi-tenant API design | Per-tenant boundaries | [`crp/gateway/api.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/gateway/api.py) | Clerk/Auth0 middleware, org-scoped sessions |
| C2 | Provider key vault | KMS encryption | Secrets management | Protect tenant LLM keys | [`crp/gateway/key_vault.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/gateway/key_vault.py) | Encrypt provider keys per tenant |
| C3 | Rate limiting + quotas | Redis counters | Scalable API governance | Prevent abuse | `crp/gateway/rate_limit.py` | Redis-backed token buckets |
| C4 | Console CDN build | Vite frontend | Frontend build pipelines | Cacheable console | [`crp/frontend/console.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/frontend/console.py) | Extract to `frontend/agent-console/`, CI upload to S3/R2+CloudFront |
| C5 | Hosted model serving | vLLM/TGI | Model serving at scale | Hosted SLM option | Infrastructure repo | Deploy managed-model containers |
| C6 | Production backend defaults | Redis + S3/R2 + Postgres | Cloud-native state | Multi-tenant persistence | [`crp/infrastructure.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/infrastructure.py) | Add Postgres backend, default Redis/S3 |
| C7 | Observability | OpenTelemetry | SRE for AI | Latency/cost/quality dashboards | [`crp/observability/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/observability) | OTLP exporter, Grafana templates |
| C8 | Billing + monetization | Stripe webhooks | AI product billing | Paid tiers | [`crp/monetisation/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/monetisation) | End-to-end Stripe/Clerk flow |

---

## Phase D — Ecosystem Integrations ⬜

| # | TODO | AI Component | Skill Gained | Why Needed | Where | How |
|---|------|--------------|--------------|------------|-------|-----|
| D1 | MCP server implementation | MCP protocol | Model Context Protocol | Expose CRP tools/knowledge as MCP server | [`crp/mcp/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/mcp) (new) | Implement MCP server over stdio/SSE |
| D2 | MCP client / tool consumer | MCP tool discovery | Consuming external tools | Use any MCP server | [`crp/tools/adapters.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/tools/adapters.py) | Add MCP client adapter |
| D3 | Coding agent compatibility | Code graph, AST RAG | Code intelligence | IDE/coding agents | [`crp/scan/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/scan), [`crp/ckf/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/ckf) | Semantic code ingestion, repo-wide fact graph |
| D4 | LangChain / LlamaIndex adapters | Adapter pattern | Framework interop | Lower adoption friction | [`crp/integrations/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/crp/integrations) | Add `CRPAgentExecutor`, callback handlers |
| D5 | A2A integration | A2A protocol | Inter-agent communication | Negotiate with other agents | `crp/a2a/` (new) | Implement A2A task cards |
| D6 | GitHub App for Scan | GitHub App auth | DevSecOps for AI | Auto-remediation PRs | [`crp/scan/github_app.py`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/crp/scan/github_app.py) | Installation tokens, remediation PRs |

---

## Phase E — Standards & Adoption ⬜

| # | TODO | Why Needed | Where | How |
|---|------|------------|-------|-----|
| E1 | Publish SQB benchmark results | Prove quality gains | [`BENCHMARKS.md`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/BENCHMARKS.md) | Run SQB baseline vs. CRPv6 |
| E2 | Conformance suite pass | Protocol compliance | [`tests/conformance/`](https://github.com/AutoCyber-AI/context-relay-protocol/tree/crpv6-agent-sdk/tests/conformance) | Extend vectors, run suite |
| E3 | arXiv technical report | Academic credibility | `docs/` | Write empirical evaluation |
| E4 | IETF Internet-Draft | Formal standards track | `rfcs/` | Submit draft |
| E5 | PyPI `v6.0.0` release | Distribution milestone | [`pyproject.toml`](https://github.com/AutoCyber-AI/context-relay-protocol/blob/crpv6-agent-sdk/pyproject.toml) | Bump, build, publish |

---

## Pick your contribution

- **ML research:** A1–A3, B5, B7
- **Systems / SRE:** C4, C6, C7, D1, D6
- **Frontend / product:** C4
- **Developer tools:** B3, B4, B6, D2, D4
- **Standards:** E2–E4

Open a GitHub issue with the TODO number (e.g., `TODO-A1`) to claim it.

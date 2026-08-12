# CRPv6 Agent SDK — Executive Summary

**Verdict:** CRPv6 is **operationally credible** for governed, tool-using, SLM-first agents in local or self-hosted deployments. It is **not yet a turnkey hosted product**.

## What is proven

- The `crpv6-agent-sdk` branch implements all nine v6 specs (049–057) plus the new Agent SDK (SPEC-059).
- A targeted regression suite of **345 tests passes** in ~63 seconds.
- `ruff check` is clean on all new and modified files.
- Key new capabilities:
  - Declarative `crp.Agent` with tool loop, policy, intent, clarification, and verification.
  - Gateway capability router for OpenAI-compatible tool calls.
  - AG-UI-compatible Transparency Emission Layer (`run_tel`).
  - Verification Relay, quality-tier routing, predictive positioning, epistemic profiles, and bi-temporal CKF.
  - Fallback-safe managed ML via `crp.ml.registry.ModelManager`.

## What is implemented but unwired

| Area | Status | What is missing |
|---|---|---|
| Trained models | Code present, fallbacks active | Actual Hugging Face weights for intent SetFit, PRM, and coref |
| Visual console | Functional embedded page | CDN build, Gateway-hosted routes, CI packaging |
| Live backends | Supported via config | Redis/S3 credentials and CI services |
| Full Windows suite | GLiNER/torch crash | Mitigated via `CRP_GLINER_DISABLED=1`; non-live full suite passes (`2952 passed, 1 skipped` in ~5:44). Live-LLM files must be excluded unless a local endpoint is running. |

## Model strategy in one paragraph

Ship the ML scaffolding now with graceful rule-based fallbacks; do not block releases on proprietary weights. The intent classifier should be a SetFit model fine-tuned on Banking77/SNIPS plus synthetic speech-act templates. The PRM should be a small DeBERTa-v3 classifier trained on the MIT-licensed PRM800K dataset. NLI can use the already-wired `cross-encoder/nli-deberta-v3-xsmall` off-the-shelf. Coreference can rely on `fastcoref`. Publish training recipes, then flip defaults after SQB benchmarking.

## Hosting strategy in one paragraph

Extract the self-contained `crp/frontend/console.py` HTML into a Vite-built package at `frontend/agent-console/`. Support three distribution modes: **embedded** (Python serves the bundle), **CDN** (S3/R2 + CloudFront referenced by `CRP_CONSOLE_CDN_URL`), and **Gateway-hosted** (a new `/crp/console` route on the Gateway). Apply CSP, output escaping, and authenticated SSE subscriptions before exposing to tenants.

## Credentials strategy in one paragraph

Keep the core SDK zero-config with in-memory/SQLite defaults. External backends (Redis, S3, HTTP audit sink, telemetry) must be opt-in and loaded from environment variables. Provide `docker-compose.ci.yml` with Redis and LocalStack so CI and integrators can reproduce without real cloud credentials. Never commit secrets.

## Competitive position

CRPv6 matches the industry on streaming mechanics (SSE, AG-UI) and exceeds it on three axes no competitor owns:

1. **Faithfulness** — narration entailment-checked against the event trace.
2. **Governance legibility** — safety, policy, risk, and quality streamed as first-class events.
3. **Verifiable provenance** — HMAC-linked audit chain surfaced live.

## Go / no-go recommendation

**Go** for:
- Library release (`pip install crprotocol`) to self-hosted, local-SLM, or air-gapped users.
- Early integrators who can supply their own models and backends.
- Standards conversations where CRP's governance vocabulary and AG-UI mapping are differentiators.

**No-go** for:
- Fully managed SaaS without trained weights, CDN packaging, and live backend credentials.
- Claims that CRPv6 solves general parameter grounding, universal parsing, or long-horizon planning.

## Next three milestones

1. Add `CRP_PRM_MODEL` / `CRP_NLI_MODEL` / `CRP_COREF_MODEL` env vars and publish weight training recipes.
2. Build `frontend/agent-console/`, CDN publish pipeline, and Gateway console routes.
3. Add `docker-compose.ci.yml` with Redis + LocalStack and mark live-backend tests optional.

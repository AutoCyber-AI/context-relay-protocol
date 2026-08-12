# CRPv6 Site Update Plan

## Current state of the site

The public MkDocs site (`site-docs/`) is currently aligned with **CRP v5.1**:

- Hero title: "Agentic Positioning Protocol for SLM-first AI — CRP v5.1"
- Navigation lists specs **SPEC-001 through SPEC-048** only.
- SDK guide focuses on the progressive `crp.SDKClient` and orchestrator APIs.
- Products page lists Gateway, Comply, Scan, Visualise, Scribe but does not reflect the v6 Agent SDK or visual console.
- No mention of `crp.Agent`, `crp/isa`, `crp/clr`, `crp/vr`, `crp/qsr`, `crp/pp`, `crp/ep`, `crp/btf`, `crp/tel`, or `crp/ml`.

**Verdict: the site is not comprehensively updated for v6.** A v6 section has been added to the nav as a starting point, but the main narrative and product pages still describe v5.1.

## What must be updated before claiming v6 is live

### Phase 1 — Add v6 landing content (do this now)

- [x] Add `site-docs/crpv6/index.md` overview.
- [x] Add v6 section to `mkdocs.yml` navigation.
- [x] Add `site-docs/crpv6/roadmap.md`.
- [x] Update `site-docs/index.md` hero from "CRP v5.1" to "CRP v6" and mention the Agent SDK.
- [x] Update hero stats to include agentic/tool-loop evidence ("declarative agent SDK", "AG-UI transparency stream").
- [x] Replace the "Positioned tool loop (v5)" capability card with an "Agent SDK (v6)" card.

### Phase 2 — Update product pages (do this at beta)

- [ ] `products/gateway.md` — document Gateway capability router, `/v1/chat/completions` tool loop, and console hosting.
- [ ] `products/visualise.md` — document the visual console, AG-UI event stream, and progressive disclosure tiers.
- [ ] `products/comply.md` and `products/scan.md` — note that these remain on the v4/v5 roadmap and are not part of the v6 agentic release.

### Phase 3 — Update protocol specs on the site (do this at beta)

- [ ] Add SPEC-049 through SPEC-059 pages under `site-docs/spec/`.
- [ ] Cross-link them from the v6 overview and SDK guide.
- [ ] Mark SPEC-018 through SPEC-023 and SPEC-044 through SPEC-046 as deferred to v6.1+ if still unbuilt.

### Phase 4 — Update guides and SDK reference (do this at beta)

- [ ] Rewrite `guides/sdk.md` to lead with `crp.Agent` and progressive SDK coexistence.
- [ ] Add `guides/agent-sdk.md` with the examples from `docs/CRPv6_Agent_SDK_Usage_Guide.md`.
- [ ] Add `guides/transparency-stream.md` covering `run_tel()`, SSE, and AG-UI mapping.
- [ ] Add `guides/models-and-fallbacks.md` covering the managed ML components and env vars.
- [ ] Update `sdk/tools-and-agents.md` to reference `crp.Agent` and the Tool Capability Fabric.

### Phase 5 — Update API reference (do this at release)

- [x] Regenerate API module pages to include `crp/agent_sdk/`, `crp/vr/`, `crp/qsr/`, `crp/pp/`, `crp/isa/`, `crp/clr/`, `crp/ep/`, `crp/btf/`, `crp/tel/`, `crp/ml/`, `crp/frontend/`, `crp/infrastructure.py`.
- [ ] Update `api/client.md` to document `CRPClient.make_agent()`.

### Phase 6 — Versioning and announcement (do this at release)

- [ ] Bump version references from v5.1 to v6 across site copy.
- [ ] Add a blog / changelog entry announcing v6.
- [ ] Update `crpv5-roadmap.md` to indicate completed items and link to the v6 section.

## Recommended timing

| Milestone | When | Site action |
|---|---|---|
| v6 alpha (now) | After targeted tests pass | Phase 1: v6 overview + nav |
| v6 beta | After model weights CDN/Gateway wiring land | Phases 2–4: product + guide updates |
| v6.0.0 release | After SQB final + full suite green | Phase 5–6: API ref + version bump + announcement |

## Immediate next step

Run a local build to confirm the new v6 section renders:

```bash
pip install mkdocs-material mkdocstrings[python] mkdocs-minify-plugin mkdocs-glightbox
mkdocs serve
```

Then open http://localhost:8000/crpv6/.

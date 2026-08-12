# CRPv6 — Agent SDK & SLM-first Agentic Protocol

CRPv6 is the agentic execution layer. It builds on CRP v5's governance spine and adds:

- A declarative **`crp.Agent`** SDK (`tools + policy + model`).
- **Tool Capability Fabric** and Gateway capability routing.
- **Verification Relay** and quality-tier supervised routing.
- **Predictive positioning** / world-model induction.
- **Intent & speech-act positioning**, cross-session coreference, and first-class clarification.
- **Epistemic profiles** and **bi-temporal CKF** memory.
- An **AG-UI-compatible Transparency Emission Layer** with a built-in visual console.

## Status

**Branch:** `crpv6-agent-sdk` · **Version:** `v6.0.0-alpha` · **Tests:** `2952 passed, 1 skipped` (non-live suite)

CRPv6 is **operationally credible today** for building governed, tool-using agents with local/SLM models. The runtime, Agent SDK, Gateway capability router, transparency stream, verification relay, and storage backends are implemented and tested.

The big shift for full completeness is moving from **rule-based defaults with optional ML** to **ML-first defaults with rule-based survival fallback**. See the roadmaps for the exact TODO list.

## Learn more

- [CRPv6 Roadmap & TODOs](roadmap.md) — every remaining task with repo links
- [Completeness Roadmap](completeness-roadmap.md) — strategic local → hosted plan
- [Operational Readiness Report](operational-readiness.md)
- [Model Training Guide](model-training-guide.md)
- [Hosting & Backends Guide](hosting-and-backends.md)
- [Agent SDK Usage Guide](agent-sdk-usage.md)

## Specifications

CRPv6 corresponds to specifications **SPEC-049** through **SPEC-059**:

| Spec | Title | Module |
|---|---|---|
| SPEC-049 | Tool Capability Fabric & Verification Relay | `crp/vr/`, `crp/tools/` |
| SPEC-050 | Quality-Tier / Supervised Router | `crp/qsr/`, `crp/gateway/capability_router.py` |
| SPEC-051 | Predictive Positioning / World-Model Induction | `crp/pp/` |
| SPEC-052 | Intent & Speech-Act Positioning | `crp/isa/` |
| SPEC-053 | Clarification Protocol | `crp/clr/` |
| SPEC-054 | Gateway Capability Router | `crp/gateway/` |
| SPEC-055 | Epistemic Profiles & Calibration | `crp/ep/` |
| SPEC-056 | Transparency Emission Layer | `crp/tel/` |
| SPEC-057 | Bi-Temporal CKF | `crp/btf/` |
| SPEC-059 | Agent SDK | `crp/agent_sdk/` |

The canonical spec source files live in `SPECS_5_06_2026_CRP_v4/specs/` in the repository.

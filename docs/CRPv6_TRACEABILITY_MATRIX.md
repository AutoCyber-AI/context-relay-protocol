# CRPv6 Traceability Matrix

This matrix links the research roadmaps (R, T, D), the planned CRPv6 specifications, and the code modules/tests that will implement them.

| Roadmap ID | Description | CRPv6 Spec | Code Module(s) | Test File(s) |
|------------|-------------|------------|----------------|--------------|
| **R1** | Specification-first positioning | SPEC-031 (STL), SPEC-050 (QSR), SPEC-059 | `crp/stl/positioned.py`, `crp/agent_sdk/agent.py` | `tests/test_agent_sdk.py`, `tests/test_quality_tier_router.py` |
| **R2** | Declarative typed tool manifest | SPEC-059 | `crp/agent_sdk/tool_manifest.py`, `crp/agent_sdk/intent_compiler.py` | `tests/test_agent_sdk.py` |
| **R3** | Structured / constrained decoding | SPEC-054 | `crp/gateway/structured_decoder.py`, `crp/gateway/tool_adapter.py` | `tests/test_gateway_structured_decoder.py`, `tests/test_agent_sdk_structured.py` |
| **R4** | Plan repair / multi-hop reasoning | SPEC-049 | `crp/stl/verification.py` | `tests/test_verification_relay.py` |
| **R5** | Multi-agent / distributed execution | *deferred* | — | — |
| **T1** | Tool Capability Fabric | SPEC-050 (v5 archived), SPEC-059 | `crp/tools/capability_fabric.py`, `crp/gateway/capability_router.py` | `tests/test_agent_sdk.py`, `tests/test_gateway_capability_router.py` |
| **T2** | Constrained decoding grammar | SPEC-054 | `crp/gateway/structured_decoder.py` | `tests/test_gateway_structured_decoder.py` |
| **T3** | Unified tool registry | SPEC-059 | `crp/agent_sdk/intent_compiler.py`, `wasa_ai/mcp/crp_adapter.py` | `tests/test_agent_sdk.py`, Wasa adapter demo |
| **T4** | Streaming, recoverable execution | SPEC-056 | `crp/tel/emitter.py`, `crp/agent_sdk/agent.py` | `tests/test_tel.py`, `tests/test_tel_sse.py` |
| **T5** | Tool learning / recommendation | *deferred* | — | — |
| **T6** | Cross-agent tool contracts | *deferred* | — | — |
| **D1** | Declared transparency | SPEC-056 | `crp/tel/events.py` | `tests/test_tel.py` |
| **D2** | Localised transparency | SPEC-056 | `crp/tel/report.py` | `tests/test_tel.py` |
| **D3** | Verified transparency | SPEC-049, SPEC-056 | `crp/stl/verification.py`, `crp/tel/emitter.py` | `tests/test_verification_relay.py`, `tests/test_tel.py` |
| **D4–D6** | Causal / contested / epistemic transparency | *deferred* | — | — |

## Launch-cut vs. deferred

- **Launch-cut (Phases 1–7)**: R1–R3, T1–T4, D1–D3.
- **Deferred (Phase 8)**: R5, T5–T6, D4–D6, plus advanced forms of R4 (full backtracking).

## Spec numbering note

Existing v5 specs `CRP-SPEC-049-slm-agent-execution.md` and `CRP-SPEC-050-tool-capability-fabric.md` were archived as `-v5.md`. New v6 specs will reuse numbers 049–059.

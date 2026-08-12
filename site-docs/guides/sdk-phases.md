# CRP SDK Coverage Phases

The CRP Python SDK is rolled out in phases so that each layer of coverage is
tested, documented, and discoverable before the next layer lands.

## Phase 0 - Foundation

* Package structure, version, and response types.
* `CRPClient` constructor, unified config adapter, and lazy orchestrator
  initialisation.

## Phase 1 - Level 0–2 developer surface

* `client.complete()`, `client.ask()`, `client.ingest()`, `client.stream()`,
  `client.tool()` / `client.call_tool()`.
* Basic storage, knowledge, audit, and compliance helpers.

## Phase 2 - Curated namespace proxies (common subsystems)

Typed, docstring-rich proxies for the subsystems most applications touch:

| Property | Subsystem | Spec |
|----------|-----------|------|
| `client.safety` | Safety Control Plane | SPEC-033, SPEC-034 |
| `client.ckf` | Contextual Knowledge Fabric | SPEC-009, SPEC-025 |
| `client.cso` | Cognitive State Object | SPEC-030 |
| `client.provenance` | Decision Provenance Engine | SPEC-005 |
| `client.reasoning` | Reasoning scaffolds, CQS, cross-window validation | §2.4 |
| `client.activation` | Activation-mode detection | SPEC-017 |
| `client.agent` | Multi-agent safety budget and chain tools | SPEC-012 |
| `client.events` | Protocol event bus | §9 |
| `client.providers` | LLM provider registration and discovery | SPEC-008 |
| `client.extract` | Graduated extraction pipeline | §2.5 |

Plus product-facing helpers:

| Property | Subsystem | Spec |
|----------|-----------|------|
| `client.gateway` | CRP Gateway | SPEC-016 |
| `client.headers` | CRP HTTP headers | SPEC-002 |
| `client.observability` | Audit, metrics, telemetry | §6 |
| `client.policy` | Safety policy engine | SPEC-006 |
| `client.scan` | Code scanning | SPEC-013, SPEC-036, SPEC-039 |
| `client.comply` | Compliance gateway | SPEC-040, SPEC-042, SPEC-047, SPEC-048 |

## Phase 3 - Full internal-subsystem coverage *(current)*

Typed proxies for the remaining top-level subsystems, so every major CRP
component has a curated SDK entry point:

| Property | Subsystem |
|----------|-----------|
| `client.core` | Orchestrator, session, DAG, config, ledger |
| `client.continuation` | Continuation manager, document map, flow, voice |
| `client.envelope` | Envelope builder, packer, reranker, CDR, formatter |
| `client.state` | Warm store, cold storage, snapshots, event log, facts |
| `client.security` | Audit trail, consent, RBAC, checkpoints, encryption |
| `client.resources` | Adaptive allocator, cost model, resource manager |
| `client.advanced` | Curator, feedback, meta-learning, source grounding |
| `client.cli` | Sidecar handler and startup helpers |
| `client.errors` | Public exception classes |

## Phase 4 - Escape hatches

* `client.orchestrator` exposes the live `CRPOrchestrator` instance.
* `client.modules` dynamically mirrors every public `crp.*` submodule/class/
  function.
* Auto-generated module reference pages document every public symbol.

## Phase 5 - Docstring completeness

* Mechanical docstring pass for public methods and properties.
* Manual refinement of high-leverage symbols, spec references, and examples.

## Using the phases

For day-to-day work, start with Phase 1–2 helpers. When you need a lower-level
API, use Phase 3 proxies or Phase 4 escape hatches. The generated module
reference covers every symbol for precise signature details.

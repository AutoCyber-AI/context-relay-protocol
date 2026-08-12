# Changelog

All notable changes to `crprotocol` are documented in this file.

## [6.0.0] — CRPv6 Launch

### Added
- CRP v6 Agent SDK (`crp.Agent`): declarative agents with tools + policy + model.
- Managed ML models published on Hugging Face `AutoCyberAI/`:
  - `crp-intent-setfit` — intent classifier for operation framing.
  - `crp-prm-deberta-v1` — process-reward model for step validation.
  - `crp-safety-deberta-v1` — safety classifier for input/policy risk.
- `crp download-models` CLI command and lazy model registry.
- Progressive SDK: `crp.Client()` / `crp.SDKClient()` levels 0–2.
- Tool Capability Fabric and positioned execution loop.
- Semantic Task Layer (STL): RETRIEVE, COMPARE, ANALYSE, SYNTHESISE, GENERATE,
  VERIFY, CLARIFY, REVISE.
- Multi-horizon context: PERSISTENT, CONVERSATIONAL, EPHEMERAL.
- Safety Control Plane, Coverage Map, Checkpoint, and kill-switch.
- Pluggable storage backends: in-memory, SQLite, Redis, S3.
- Reference agent examples: weather, RAG, GDPR DSR, report.
- Ready-to-use agent templates: customer support, code review, research report,
  data analyst, local SLM.
- Gateway capability router, GBNF constrained decoding, TEL SSE transparency stream.
- Audit Merkle proofs and Ed25519 anchoring.

### Changed
- Version bumped to 6.0.0 to mark the CRPv6 protocol release.
- README rewritten for launch with agent templates and v6 status.

### Fixed
- Per-product entitlement keys (`comply_plan`, `gateway_plan`, `scan_plan`)
  across Comply billing webhook and entitlement reads.
- Gateway Docker Compose port mapping (8080).
- Scan GitHub Action self-test now uses the local action code.

### Test Status
- 3,232 passed, 3 skipped in the non-live suite (Windows, GLiNER disabled).

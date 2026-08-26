# Changelog

All notable changes to `crprotocol` are documented in this file.

## [6.0.1] — SDK/DX hardening

### Fixed
- **`crp.Client()`/`crp.SDKClient()` auto-detection never checked LM Studio.**
  `_auto_detect_provider()` (`crp/core/orchestrator.py`) only checked
  `OPENAI_API_KEY` → `ANTHROPIC_API_KEY` → Ollama; a user with only LM Studio
  running got a misleading error, or — via `crp/sdk/client.py` — a silent
  fallback to a stub provider that always returns empty output with no error.
  Added `_detect_lmstudio_provider()`, checked before Ollama.
- **Continuation engine could loop forever on short, complete answers.**
  Gap-analysis (tuned for long-form generation) never marked a trivial,
  correct factual answer as complete, and the old
  `gap_override_min_output_tokens=16` safety net was too low. Added a
  raw-output repetition guard (`crp/continuation/manager.py`) and raised the
  threshold to 48 (`crp/continuation/trigger.py`).
- **Opaque OpenAI-provider error logging.** `OpenAIAdapter`'s error logs
  included only the exception type name, never the message — made a live
  `BadRequestError` undiagnosable. Both log sites now include the full
  exception message.

### Changed
- `research_assistant_agent.py`'s `web_search()` no longer scrapes the
  undocumented `https://html.duckduckgo.com/html/` HTML surface — it now
  calls Wikipedia's real, versioned, free, publicly documented MediaWiki
  Search API (no key required).
- README's auto-detect claims now explicitly mention LM Studio; the Output
  Guarantee section now discloses the license watermark append
  (`CRP_DISABLE_WATERMARK=1` to opt out).
- `CHEATSHEET.md` rewritten with a full `CRPClient`/`SDKClient` method
  reference, a `crp.Client` vs `crp.SDKClient` disambiguation, ingestion/
  storage documentation (including the honest "no built-in URL fetcher" note),
  a concrete checkpoint walkthrough, and elevator-pitch summaries throughout.

### Added
- `examples/crp_demos/checkpoint_console.py` — a real, live, browser-based
  human-in-the-loop checkpoint console (Approve/Deny buttons that genuinely
  block/unblock the running agent thread), verified against both the
  approve and deny paths.
- `examples/crp_demos/live_llm_vs_crp.py` now writes a structured JSON proof
  artifact (`_video_proof.json`) alongside its console output, with an
  optional real-Wikipedia-search tool set (`CRP_DEMO_REAL_SEARCH=1`).
- `docs/CRP_SDK_HARDENING_STATUS_2026-08-26.md` — full honest done/not-done
  accounting for this release.

### Test Status
- Full non-live suite: 3232 passed, 2 skipped, 1 pre-existing environment-flaky
  test (`test_phase7.py::test_ingest_updates_warm_state` — depends on the
  `transformers` NER backend, which is unstable on this Windows dev machine
  independent of any change in this release; falls back to spaCy correctly,
  just extracts one fewer fact than the test expects on an unlucky run).
  210s, unrelated to this release's changes.
- 102/102 targeted regression tests pass (`test_orchestrator_perf.py`,
  `test_phase5.py`, `test_production_hardening.py`).

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

# Changelog

All notable changes to `crprotocol` are documented in this file.

## [6.1.3] — OpenAI-Compatible Base URL Normalization

### Fixed
- **`OpenAIAdapter` normalizes `base_url` to include `/v1`** — passing a bare
  host (`http://192.168.0.6:1234`) previously made the SDK post to
  `/chat/completions`, which LM Studio answers with HTTP 200 and a body that
  parses into an empty completion (`choices=None`), surfacing as a cryptic
  `TypeError: 'NoneType' object is not subscriptable`. The adapter now appends
  `/v1` when missing (found and reproduced live against LM Studio).
- **Clear error on empty completions** — `generate_chat` and
  `generate_chat_with_tools` now raise a descriptive `ValueError` naming the
  model and effective base URL when a provider returns `choices=None`, instead
  of an opaque subscript error.

## [6.1.2] — Human-Readable Halts & Console Accuracy

### Added
- **New `HaltReason` values** (`crp.headers.halt`) — `GROUNDING_BELOW_THRESHOLD`,
  `QUALITY_TIER_REJECTED`, `UNTRUSTED_SOURCE`, `PROMPT_INJECTION_DETECTED`,
  `SAFETY_POLICY_VIOLATION` — so callers report the dominant, real violation
  instead of always claiming an EU-AI-Act umbrella prohibition. Existing enum
  values are unchanged (stable wire contract).
- **`HALT_REASON_INFO` / `halt_reason_info()`** (`crp.headers.halt`) — a
  `HaltReason → (short title, one-sentence plain-English explanation)` mapping.
- **HTTP 451 body now includes `crp_halt_explanation`** — a human-readable
  sentence alongside the unchanged `crp_halt_reason` wire value. Backwards
  compatible (new optional field only).

### Fixed
- **Demo consoles reported an accurate halt reason** (`examples/crp_demos/pipeline.py`,
  `examples/crp_demos/v4/server.py`) — the safety console previously emitted
  `UNACCEPTABLE_EU_AI_ACT` for every halt regardless of the actual violation;
  it now derives the reason from the dominant policy violation (prompt
  injection > first halting violation > CRITICAL-risk > generic policy).
- **Stale protocol version in demo consoles** — `PROTOCOL_VERSION` is now
  derived from the installed `crprotocol` package version (was hardcoded
  `"3.0"` / `"5.0.0"` while shipping 6.1.x).
- **Ollama context-length detection** (`crp.providers.discovery`) — reads
  `num_ctx` from Ollama's `/api/show` `parameters` field (dict or Modelfile
  lines), not just `<arch>.context_length` model-info keys.
- **Console readability pass** (`static/safety.js`, `static/context.js`,
  `static/app.js`) — halt reasons, policy violation codes, enforcement
  actions, retry conditions and `CRP-Quality-Completeness` values render as
  plain English with raw wire values kept in small tags / collapsible raw
  views; unknown context lengths show an explicit "unknown" label.

## [6.1.1] — Launch Hardening

### Added
- **Agent Console "connect to your backend" bar** — the CDN-hosted console (`console.crprotocol.io`) can be pointed at any local backend from the UI; the choice is remembered in the browser. No HTML editing.
- **CORS support in `crp.frontend.console.mount_fastapi`** — allows the CDN console origin by default; configurable via `cors_origins`.
- **MCP bridges** — `crp_mcp.connectors.mcp_to_crp.load_mcp_tools()` consumes any MCP server's tools as CRP tools; `crp_to_mcp.serve_crp_tools()` exposes CRP tools as an MCP server.
- **Hard reasoning enforcement** — a preset phase's `depth` now caps the per-operation evidence budget and scales the continuation budget; phase guidance text is injected into each step's operation frame.
- **Tool-intent enforcement** — `ParsedToolCall.requested_id` preserves the tool the model actually requested before snap-to-capability remapping; phase tool allowlists halt with `PHASE_PLAN_VIOLATION` on out-of-allowlist intent.

### Fixed
- Snap-to-capability remap no longer shadows phase tool-allowlist halts (a model asking for a disallowed tool when one tool was offered was silently remapped and never halted).
- Repo-wide quality gates: 343 ruff errors and 792 mypy errors fixed (both now zero); 4 broken documentation links; dependabot ecosystems configured; GitHub Actions moved to Node 24 (`actions/checkout@v5`).
- CI dependency declarations: pinned `mcp<2` (FastMCP → MCPServer rename in mcp 2.x is a breaking API change); added `fastapi`, `asyncpg`, and `webauthn` to the `dev` extra so `crp_shared` test modules collect in a clean environment.
- Test count badges refreshed to 3,482 (README and site ticker).

### Docs
- New: `CRP_AGENT_CONSOLE_DEPLOYMENT_GUIDE.md`, `CRPv6_ANNOUNCEMENT_READINESS_REPORT.md`, `CRPv6_LATENT_BUG_PUNCHLIST.md`, `CRPv6_SLM_RECOMMENDATIONS.md`, `CRPv6_COGNITIVE_PRESETS_GUIDE.md`, `CRPv6_TOOLS_AND_MCP.md`, `CRPv6_AGENTIC_ECOSYSTEM_CAPABILITIES.md`, `CRPv6_VIDEO_STORYBOARD.md`, `CRPv6_VIDEO_ASSETS.md`.

## [6.1.0] — Transparent Display & User-Defined Cognition

### Added
- **User-defined cognition layer (`crp.cognition`).**
  - `CognitivePreset` — declarative persona, reasoning scaffold, operating modes,
    safeguards, emotion/affect config, and output profile.
  - `PresetCompiler` — compiles a preset into system prompt, policy hints,
    depth, operations, tool ids, and safeguard engine.
  - Built-in presets in `crp/cognition/presets/`: `default`, `socratic_tutor`,
    `security_analyst`, `research_assistant`, `compassionate_companion`.
  - `crp.Agent(..., preset=...)` — apply any built-in preset id, YAML/JSON file
    path, dict, or `CognitivePreset` object to an agent in one argument.
  - Rule-based emotion detection (`crp.cognition.emotion`) with optional
    transformers-backed ML recognizer and graceful fallback.
  - Declarative safeguard engine (`crp.cognition.safeguard`) evaluating rules
    against user input, tool selection, tool arguments, and output.
  - Example agents: `examples/templates/robot_safeguard_agent.py` and
    `examples/templates/socratic_tutor_agent.py`.
- **Transparency narrative generator (`crp.tel.narrative`).**
  - `NarrativeBuilder` consumes AG-UI + CRP events and produces a readable,
    exportable chain-of-thought: intent → operations → tool calls → safety
    scans → verification → provenance.
  - Output formats: `.to_dict()`, `.to_markdown()`, `.to_html()`.
- **Richer embedded agent console (`crp/frontend/console.py`).**
  - Governance cards: risk, grounded, chain validity, quality tier,
    confidence, sources.
  - Reasoning narrative tab showing a human-readable story of what the agent
    did and why.
  - Provenance tab visualising the HMAC chain link-by-link.
  - Operations & governance event log with colour-coded AG-UI + CRP events.
  - Theme toggle and mobile-responsive layout.
- **CDN-ready frontend package (`frontend/agent-console/`).**
  - Vite + TypeScript build with no heavy framework dependency.
  - Replicates the embedded console UI with typed event handling and narrative
    rendering.
  - `npm run build` produces `crp/frontend/static/`; `mount_fastapi()` serves the
    built bundle when present and falls back to the inline HTML console.
  - Built static assets are included in the wheel/sdist via
    `pyproject.toml` force-include.
- **Company announcement messaging brief**
  (`docs/CRPv6_COMPANY_ANNOUNCEMENT.md`) with positioning, target audiences,
  differentiators, honest boundaries, and a marketable status verdict.
- **CDN deployment guide**
  (`docs/CRP_AGENT_CONSOLE_DEPLOYMENT_GUIDE.md`) explaining why the console is
  a separate Node/Vite package and how to deploy it to a CDN.
- **Cognitive presets guide**
  (`docs/CRPv6_COGNITIVE_PRESETS_GUIDE.md`) documenting user-defined reasoning,
  safeguards, emotions, and output profiles.
- **Video storyboard**
  (`docs/CRPv6_VIDEO_STORYBOARD.md`) for a CRP-vs-raw-LLM product video.

### Changed
- `site-docs/index.md` and `site-docs/why-crp.md` refreshed with CRP v6
  messaging: declarative `crp.Agent`, AG-UI transparency stream, three
  open-source SLM models, and the "governed agentic protocol" positioning.
- `CHEATSHEET.md` adds §5.10 documenting cognitive presets and the
  `crp.Agent(..., preset=...)` surface.
- `crp/__init__.py` exposes `CognitivePreset` and `PresetCompiler` as lazy
  imports.

### Test Status
- Full non-live suite: **3275 passed, 3 skipped** (including the 15 new visual-output
  tests in `tests/test_visual_outputs.py`).
- New tests: `tests/test_visual_outputs.py` (15), `tests/test_cognition.py` (12),
  `tests/test_tel_narrative.py` (6), frontend bundle tests.

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

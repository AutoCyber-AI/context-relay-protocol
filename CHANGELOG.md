# Changelog

All notable changes to `crprotocol` are documented in this file.

## [6.2.3] — 2026-10-16 — Long-gen duplicate-collapse hardening

### Fixed (calibrated on a real user run: qwen2.5-7b, custom 5-section
### 'Philosophy & Cognitive Science' topic, grounding on)
- **Renumbered section rewrites surviving collapse** — the model re-announced
  an already-written section as `### 3. 2. Language, Perception...` (and
  outline-depth headings like `5.4. ...`). `_normalize_heading` stripped only
  ONE numeric prefix, so the heading never matched and the rewrite stayed in
  the document. The normalizer now strips stacked prefixes to the bare title.
- **Recycled fragments inside a kept block** — a window closed `## Conclusion`,
  then appended paragraphs recycling earlier sections with no markdown heading
  of their own. Two gaps combined: single-block output skipped collapse
  entirely, and when the fragment pushed the WHOLE block over the 0.50
  block-overlap bar, the empty-kept guard resurrected the original verbatim.
  A paragraph-level pass now drops near-verbatim (>= 0.50) recycled paragraphs
  inside kept blocks; the salvage path keeps the genuine content (the real
  conclusion) instead of discarding the whole block.
- **Pasted instruction lines becoming sections** — pasting an LLM-style
  prompt ('Conduct a comprehensive ... 1. ... 2. ...') into the section-titles
  box made line 1 a section, so window 1 wrote the instruction text as content
  and a real section fell off the plan. `parse_section_titles` (longgen +
  comparison demos) now uses only numbered lines as sections when any are
  present, strips their numbers (the strategy re-adds canonical numbering),
  and keeps the one-line-one-title behaviour for unnumbered pastes.
- **Word target stranding on a thin window** — the planned-window margin is
  +3 (was +2): live runs showed one ~250-word window against a ~500-word
  estimate still leaving the document below target. The near-duplicate and
  low-novelty stop guards (6.1.7+, 6.2.2) keep the extra budget from
  runaway.

### Docs
- `docs/DEMO_REPRODUCTION_AND_VIDEO_GUIDE.md`: rewrote the stale v6.1.1
  mega-blockquote preamble as proper sections current for 6.2.3, and
  documented the 6.2.3 custom-section-title parsing in the Long-Gen
  recording section.

## [6.2.2] — 2026-10-14 — Production audit hardening (upstream U-C1…U-C15, latents, conformance gates)

### Added (this release, cross-batch)
- **Selection hook seam** (`run_positioned(selection_pre_hook=…, selection_post_hook=…)`)
  — first-class host steering for tool selection (policy/query/embedding/k
  adjustment pre-selection, offered-set observability post-selection),
  replacing consumer-side source patching (audit I-C4). Conformance:
  `tests/test_selection_hooks.py`.
- **Torch thread guards (U-C1)** — `crp/ml/torch_threads.py` save/restore
  helpers; all five process-global `torch.set_num_threads` call sites now
  restore the host's prior value (GLiNER's `set_num_threads(1)` is
  restored after load). Conformance: `tests/test_torch_thread_guard.py`
  (grep-gate bans bare `set_num_threads` in library code).
- **Keyed manifest ledger (U-C5)** — domain-separated HMAC-SHA256 chain via
  injectable `KeyProvider` (`CRP_MANIFEST_SECRET` auto-enables; legacy
  unkeyed SHA-256 byte-identical by default); `anchor()`/`verify_anchored()`.
- **Ledger restart continuity (U-C4)** — `ManifestLedger.record()` reloads
  on-disk entries on cache miss; duplicate genesis raises `LedgerChainError`
  (no silent chain forks). Conformance: `tests/test_ledger_chain_integrity.py`.
- **Dispatch idempotency (U-C6)** — `RequestDeduplicator` wired into
  `dispatch()` (cache hit returns the cached result; concurrent followers
  coalesce via single-flight), `SessionLock` is a real writer-preferring RW
  lock, config keys `dispatch_idempotency`/`_ttl_s`/`_inflight_wait_s`.
  Conformance: `tests/test_dispatch_idempotency.py`.

> **Compatibility note:** `ComplianceEventType` is an open enum — custom
> string event types are accepted by `ComplianceAuditTrail.record()` by
> design. Never assert membership counts across minor versions.

### Fixed
- **Dispatch session-binding tautology removed (U-C7).** `_dispatch_locked`
  signed a session-binding payload and immediately verified it against the
  object that had just signed it — a check that could not fail. Replaced
  with an explanatory note; the binding record itself is unchanged.
- **Per-call `max_continuations` now actually applies (U-C8 / A-PR-1).** All
  five dispatch variants (`dispatch`, `dispatch_with_tools`,
  `dispatch_stream_augmented`, `dispatch_agentic`, `dispatch_stream`) accept
  a per-call `max_continuations` kwarg that overrides the session
  `ContinuationConfig` for that call only (previously the kwarg was accepted
  and silently ignored — WASA's `dispatch_text` depth caps were no-ops).
  Unknown dispatch kwargs now emit a `UserWarning`
  (`CRP_DISPATCH_STRICT_KWARGS=1` promotes to `TypeError`).
- **Audit persistence is atomic, durable, and restart-verifiable (U-C9,
  A-PR-5, U-L5).** Orchestrator `close()` wrote the audit JSONL with a bare
  `open(path, "w")` (a mid-write crash left a truncated file that looked
  authoritative) and the trail existed only in memory during a session.
  Every `record()` now appends to a crash-durable JSONL sink (flush +
  policy fsync) when the orchestrator enables it (default on;
  `CRP_AUDIT_DURABLE_APPEND=0` opts out); the clean close releases the
  append handle BEFORE the atomic tmp+fsync+`os.replace` rewrite (Windows:
  `os.replace` over an open handle fails with `WinError 5`), and writes an
  Ed25519-anchored Merkle tip (`<sid>.audit.jsonl.anchor.json`).
  `ComplianceAuditTrail.verify_file()` recomputes per-entry content hashes
  and linkage (detects one-byte edits and middle-line removal) and,
  with a public key, requires valid audit_v2 receipts on every entry;
  `crp/security/audit_anchor.py::verify_audit_file()` validates the file
  against the anchor on session resume (tail truncation / rewrites fail
  closed). A mixed-version chain (signer at 2.0.0 + transcript events at
  2.1.0) verifies under `verify_chain(verify_receipts=True)`; `export()`
  now stamps `audit_trail_version` with the newest per-entry schema
  version instead of the stale constant.
- **Sessions slide on activity (U-C10).** `expires_at` was fixed at
  `created_at + timeout`, so a long-lived session expired mid-use.
  `SessionHandle.touch()` slides the expiry forward and the orchestrator's
  session check touches it with the configured `session_timeout`
  (inactivity-based expiry per CAP §2.8).
- **Envelope scoring/reranking determinism (U-C11).** The dependency bonus
  depended on the input order of the last 50 scored facts; it now derives
  from the complete base-score map (order-independent). `rerank()` computes
  blended scores into NEW `ScoredFact` objects (no caller mutation) and
  flags them, so a second `rerank` of blended input is a stable fixed point
  instead of compounding the cross-encoder weight (0.4 × 0.4 …). The
  cross-encoder load/predict/unload lifecycle is guarded by a lock (no
  unload mid-predict), and the dead `TASK_SIM_INVALIDATION_THRESHOLD`
  constant is removed.
- **Sentence-transformer loader is race- and network-safe (U-C12).**
  Concurrent first loads of the shared decomposer model could double-load
  or wedge; a module lock plus a negative cache now serialize attempts, and
  offline machines never hang on a HF download unless
  `CRP_ALLOW_MODEL_DOWNLOADS=1` is set explicitly.
- **SQLite backend is process-safe and closable (U-C13).** Rewritten around
  one shared WAL-mode connection with `busy_timeout=5000` (multi-instance
  visibility, no more `database is locked`), plus an explicit `close()` and
  a write-after-close `RuntimeError`.
- **Import-time and shutdown hygiene (U-C15, A-PR-4).** Structured logging
  is now opt-in (`structured_logging=True` / `CRP_STRUCTURED_LOGGING=1`)
  instead of unconditionally reconfiguring the root logger at orchestrator
  construction; orchestrator shutdown uses one module-level weakref atexit
  hook; `close()`/`async_close()` shut the worker pool down before taking
  the state lock (no deadlock when pool tasks call back into `close()`).
- **Unknown config init kwargs surface (A-PR-6).**
  `ConfigurationResolver.resolve()` warns (`UserWarning` + log) on unknown
  init kwargs and raises `ValueError` under `CRP_CONFIG_STRICT=1`.
- **Continuation low-novelty decider guard (A-PR-7).** `ContinuationConfig`
  gains `stop_novelty_threshold` (0.2) / `max_low_novelty_stops` (3): when
  the gap scorer keeps forcing continuations on natural stops but the
  model's output novelty (novel-6-gram fraction) stays sub-threshold, the
  loop terminates with reason `low_novelty_stop` instead of burning the
  whole window cap on a stalled generation (WASA live evidence: 22-window
  stall at finish=stop, gap_score ~0.94). Set `max_low_novelty_stops=0` to
  disable.
- **Positioned per-phase narrowing derives from the pristine caller policy
  (A-PR-2).** `run_positioned` previously narrowed the loop-carried
  (accumulated) policy each phase, so by phase 3–4 of a disjoint-tool
  phase plan the allowlist was empty and `fabric.select` rejected
  everything (silent degradation to prose). Each phase now intersects the
  caller's original policy with that phase's tools.
- **Latent fixes U-L1–U-L10.** Packer: `max_chars < 4` guard, no early
  `break` after a compressed fallback (keeps scanning for smaller later
  facts), post-pack verification shrink loop (U-L1/U-L2). Retrieval
  integrity: word-boundary negation regex (knot/not fix) and correctly
  spelled `detect_contradiction` (deprecated `detect_contradication` alias
  kept, U-L4). Idempotency: canonical JSON key computation — mixed-type
  kwargs no longer crash and nested-dict insertion order no longer changes
  the key (U-L8). Telemetry writer: write+flush under one lock, explicit
  error on write-after-close (U-L6). Ledger backends: `task_done()` in
  `finally` (no queue-slot leak on handler exceptions) and a synchronous
  best-effort drain on close (U-L10). Envelope packer small-window safety
  verified by tests.
- **Documentation truth (audit §6.5).** README test badge/claim and
  `CRP_CAPABILITIES.md` per-area test counts updated to measured numbers
  (3,582 non-live tests; 191 §22-focused), replacing the stale
  "3,482"/"185" figures.

### Added
- `CRPOrchestrator(action_signer=...)` (A-PR-5) — inject an installation
  Ed25519 signer so every audit entry is receipted from entry #0.
- `SessionHandle.touch()`, `ComplianceAuditTrail.verify_file()`,
  `enable_durable_append()/flush_durable()/close_durable()`,
  `atomic_write_text()`, `verify_audit_file()` (see above).
- Conformance suite `tests/test_conformance_batch6d.py` (21 tests):
  idempotency-key canonicalisation, audit ledger integrity incl.
  one-byte-edit / middle-line-removal / anchor tamper / mixed-version
  receipt chain, envelope determinism (order-independent dependency
  bonus, non-mutating + idempotent rerank), per-call continuation caps,
  sliding session expiry, low-novelty continuation stop, per-phase policy
  narrowing.

### Transcript governance hardening (production audit U-C2 / U-C3)

### Fixed
- **Transcript byte cap enforced on the final serialized size (U-C2).**
  Previously only `record.output` was truncated, measured in *characters*
  against `cap/2`, with no post-truncation re-check — the stored `messages`
  array (full assembled prompt) stayed unbounded and multi-byte UTF-8 could
  overshoot the cap (empirically: 22 931 bytes stored under a 4096-byte cap).
  `TranscriptStore.store()` now measures `len(blob.encode())` and shrinks
  stored content in priority order (messages → output → system_prompt →
  task_input), halving the current field per pass until the serialized JSON
  fits; truncation is byte-accurate (never splits a multi-byte char), the
  `truncated` flag is set, and full-content hashes remain on the record so
  the audit chain linkage survives.
- **Transcript PII redaction default-on and covers the message array (U-C3).**
  `audit_transcript_redact_pii` now defaults to **True** whenever transcript
  capture is enabled (explicit `False` / `CRP_AUDIT_TRANSCRIPT_REDACT_PII=false`
  opts out). Redaction previously applied only to the top-level
  `system_prompt` / `task_input` / `output` fields while `messages` persisted
  the full assembled prompt — including PII pulled into the envelope from
  warm-store/CKF facts — raw. Every message's `content` (string and
  text-part list forms) now goes through the same scanner/redactor, and the
  `TRANSCRIPT_RECORDED` event records `pii_recall="scanner-limited"` to
  document the regex scanner's residual-recall limits.

## [6.2.1] — STL model-failure threshold (long-run resilience)

### Added
- **`model_failure_threshold` on `crp/stl/positioned.py::run_positioned`** —
  a single transient `ModelCallError` (provider timeout, wedge, OOM) no
  longer kills a long unattended positioning run. Consecutive model failures
  are counted across the run; only when the count reaches the threshold
  (default 1 = historical behavior, configurable) does the run halt with
  `risk=CRITICAL` / `grounded=False`. Below the threshold the failed
  operation is recorded honestly ("unable to complete this step …") as a
  completed-with-failure operation and the run advances to the next one, so
  one transient provider error abandons one operation without discarding
  the remaining operations. Enacted for WASA AI productionisation: a live
  engagement died 4 tools into a run on one transient `ModelCallError`
  (WASA pairs this with temperature/jittered retries at the runner level,
  commit `114b5ba`).

## [6.2.0] — Transcript Capture + Incident Events (audit schema 2.1.0)

### Added
- **Opt-in transcript capture for the compliance audit chain** (§7.14,
  `docs/FIX_NOTE_transcript_capture.md`). `LLM_CALL_COMPLETED` previously
  recorded only truncated hashes and telemetry — every window minted
  `node.raw_output_id` but nothing persisted content against it. Now:
  - New **`TRANSCRIPT_RECORDED`** compliance event (audit schema **2.1.0**),
    emitted once per window (primary + each continuation) with payload
    `{window_id, raw_output_id, input_hash, output_hash, transcript_ref,
    bytes_in, bytes_out, redacted, pii_types}` — reusing the exact truncated
    SHA-256 convention of `LLM_CALL_COMPLETED` so chain ↔ content joins are
    trivial.
  - New **`crp/security/transcript_store.py`** — content-addressed store
    persisting the assembled messages + raw output per window, keyed by
    `raw_output_id`; per-window JSON files + `manifest.jsonl`, or memory-only
    when no directory is configured. **`verify_transcripts()`** re-hashes
    stored content and proves it matches the chain (stored-content ↔ event
    hashes ↔ unredacted `LLM_CALL_COMPLETED` hashes); an edited transcript
    flags at the exact window. Also `ComplianceAuditTrail.verify_transcripts()`.
  - **Config, OFF by default** (zero overhead unless enabled):
    `audit_capture_transcripts` (env `CRP_AUDIT_CAPTURE_TRANSCRIPTS`),
    `audit_transcript_max_bytes` (env `CRP_AUDIT_TRANSCRIPT_MAX_BYTES`),
    `audit_transcript_redact_pii` (env `CRP_AUDIT_TRANSCRIPT_REDACT_PII`,
    integrates with the existing advisory `_pii_scanner` results — stored
    variant replaces detected spans with `[REDACTED:<type>]` markers and
    records `redacted`/`pii_types` on the event), `audit_transcript_dir`
    (env `CRP_AUDIT_TRANSCRIPT_DIR`). Byte cap honoured on disk; oversized
    outputs are head-truncated with the full-content hash kept for chain
    linkage.
  - **Export**: `export_jsonl(..., include_transcripts=True)` appends
    `record_type="transcript"` lines for a self-contained bundle;
    `export_ocsf(..., include_transcripts=True)` carries transcript refs and
    content hashes in `unmapped`.
  - Wired into **`crp/core/dispatch_router.py`** at every window-completion
    site across all dispatch variants (`dispatch`, `dispatch_with_tools`,
    `dispatch_reflexive`, `dispatch_progressive`, `dispatch_stream_augmented`,
    `dispatch_stream`, continuation windows) — `raw_output_id` stops dangling.
    Capture failures are logged and never break dispatch.
- **INCIDENT_* compliance event types** (SPEC-033 §3.4; for the WASA
  self-healing loop): `INCIDENT_CAPTURED`, `INCIDENT_DIAGNOSED`,
  `INCIDENT_REMEDIATED`, `INCIDENT_VERIFIED` with documented, validated
  payload shapes (`INCIDENT_PAYLOAD_SHAPES` /
  `validate_incident_payload()` in `crp/security/audit_trail.py`):
  incident_id + session id + tool/component throughout; classification +
  evidence hash refs (CAPTURED); hypothesis (DIAGNOSED); action enum +
  before/after state (REMEDIATED); probe result (VERIFIED).
- **`QUARANTINE_VALIDATED`** compliance event (§7.8) — the
  `QuarantineReport` from ingest-quarantine promotion was previously
  discarded by the dispatch variants; promoted/rejected counters and the
  batch-poisoning verdict now reach the compliance chain (batch poisoning
  is additionally recorded as `SECURITY_THREAT_DETECTED`).
- Tests: `tests/test_transcript_capture.py` (33).

## [6.1.12] — Natural-Language Safety Policy Inference

### Added
- **`crp.policy.nl_infer`** (SPEC-033/034 extension) — declare safety policy
  in plain English. `infer_from_text("never let it delete files without
  asking me first")` returns Safety Control Plane settings
  (`human_oversight=automatic`, `oversight_required={"destructive"}`), with
  every matched rule surfaced in `matched_rules` for auditability — an
  inferred policy is never a black box. Two layers:
  - a deterministic keyword/pattern layer (zero cost, always available);
  - an optional LLM-assisted layer (`infer_from_text_with_llm`, pass any
    already-resolved `model_call`) for phrasing the keyword layer misses —
    advisory enrichment that falls back cleanly on provider errors or
    malformed output, and silently drops unknown capability keys or
    safety-class tokens.
  - `looks_like_natural_language()` lets callers (e.g. `crp.Agent(safety=...)`)
    route a string argument to profile parsing vs. NL inference.
- Public API re-exported from `crp.policy`: `InferredPolicy`,
  `infer_from_text`, `infer_from_text_with_llm`,
  `looks_like_natural_language`.

## [6.1.11] — Summarized Section-Rewrite Collapse

### Fixed
- **Summarized section rewrite surviving collapse** — the 6.1.9 heading-match
  bar (0.20 6-gram overlap) missed a real qwen2.5-7b artifact where a window
  closed its section, then appended a *short summarized rewrite* of the same
  section under a new number ("## 5. Caching Strategies" ... then
  "## Section 6: Caching Strategies" with the same opening verbatim).
  The rewrite's summarized body measured 0.19–0.25 overlap — under the bar —
  so it entered the document, the cross-window near-duplicate guard then
  fired on the polluted window, and the loop terminated early below the word
  target. Distinctive section titles now drop a heading-matched block at
  >= 0.10 overlap; a stoplist of boilerplate subheads ("Key Concepts",
  "Trade-offs", "Real-World Patterns", ...) keeps the high 0.50 overlap-only
  path so genuinely fresh content under a repeated subsection title survives.
- **Orphan re-announced headings leaking into the document tail** — a window
  whose token budget cut it off right after re-announcing earlier section
  headings left bare heading lines at the end of the deliverable (observed
  live on the conclusion window). The duplicate-block collapse exempts
  blocks under 40 words, so these one-line orphans passed through. A heading
  line with no body of its own that re-announces an already-written heading
  is now dropped; a first announcement is kept so the next window can still
  write content under it.
- Verified live on qwen2.5-7b-instruct (5 sections / 2,000 words /
  grounding on): full acceptance gate PASS — 2,008 assembled words,
  27 headings, 0.2% 6-gram repetition, 0.0% duplicate sentences, conclusion
  present, 6 windows.

## [6.1.10] — Stitched Deliverable, Budget Off-by-One, Conclusion Directive

### Fixed
- **Deliverable document not stitched** — the long-gen demo assembled its
  document by concatenating raw window outputs, so window boundaries glued
  together without separators ("...Serverless## 3. API Design..."), breaking
  markdown headings at every stitch point in the rendered document and in
  the downloaded file. The strategy now builds the deliverable through the
  real continuation stitcher (echo removal, bridge insertion, section
  dedup); the raw token stream remains live-only.
- **Continuation budget off-by-one** — the strategy passed
  `max_continuations = planned_windows - 1`, but the engine's trigger counts
  the initial window inside that budget and fires at `>=`, so every run
  stopped one window early: below the word target and before the conclusion.
  Passes `planned_windows` now; verified live (6 windows for a 2,000-word /
  5-section plan instead of 5).
- **Vague directive once all sections were complete** — "continue where you
  left off" invited full rewrites of early sections when the plan ran out
  (observed live: a window rewrote Section 1 verbatim). When every planned
  section is written and no conclusion heading exists, the continuation
  envelope now directs the next window to write ONLY `## Conclusion`.

## [6.1.9] — Within-Window Duplicate Collapse + Title-Preserving Continuation Directives

### Fixed
- **Within-window section rewrites entering the document** — a model that
  starts looping mid-window often rewrites a whole section block a second
  time *inside the same window*. The cross-window near-duplicate guard
  (6.1.7) cannot see this: it compares completed windows. The continuation
  manager now collapses duplicate blocks before ingesting a window's output
  — a block is dropped when its normalized heading re-announces an
  already-written heading AND its 6-gram overlap with prior content is
  >= 0.20, or when overlap alone reaches 0.50. Recurring subsection titles
  ("Key Concepts", "Trade-offs") with genuinely new content are preserved
  (calibrated on a real qwen2.5-7b artifact: rewrite measured 0.37 overlap,
  fresh content under a repeated heading ~0.05). Count exposed as
  `ContinuationState.blocks_collapsed` and
  `WindowMetrics.duplicate_blocks_collapsed` in dispatch telemetry.
- **Continuation windows writing the wrong section** — continuation
  directives listed missing sections as bare numbers ("section 3"), while
  the compact task reference in continuation windows drops the original
  numbered list. Small models guessed the topic (observed live twice:
  a window tasked with "3. API Design and Versioning" wrote "Data Modeling
  and Storage"; the next run skipped section 3 entirely). Directives now
  name each missing section by title, instruct the model to write ONLY the
  next missing section, and specify the exact heading to begin with.

## [6.1.8] — Telemetry Serialization Fix

### Fixed
- **`continuation_termination_reason` missing from dispatch telemetry** — the
  field added in 6.1.7 was present on `WindowMetrics` but absent from its
  explicit `to_dict()` field list, so `QualityReport.telemetry` never carried
  it and consumers (e.g. the long-gen demo UI) always saw an empty stop
  reason. The field is now serialized.

## [6.1.7] — Continuation Near-Duplicate Termination

### Fixed
- **Continuation loops accumulating paraphrased repetition** — the existing
  repetition guard only fired on a near-verbatim copy of the *immediately
  preceding* window. Small models that exhaust their instructed content
  instead rephrase an *earlier* window (e.g. rewriting an already-completed
  section with altered wording), and each such window passed the guard and
  added more duplicate material. The continuation manager now computes 6-gram
  overlap against every prior window and terminates with
  `repetition_detected` when one window shares ≥30% of its 6-grams with any
  single earlier window.
- **Opaque continuation stops** — `WindowMetrics.continuation_termination_reason`
  now records why the loop ended (`gap_fulfilled`, `repetition_detected`,
  `max_continuations`, …) in dispatch telemetry.

## [6.1.6] — Continuation Anti-Rewrite Guard

### Fixed
- **Continuation windows re-opening completed sections** — small local models
  frequently ignored the document-map TOC and re-wrote already-completed
  sections on each continuation window, inflating 6-gram repetition and
  burning the continuation budget. `ContinuationManager` now counts every
  heading that re-announces a section the document map already holds
  (`ContinuationState.section_rewrites`, detected against the pre-update map
  so a section is never counted against itself) and the continuation envelope
  carries an explicit `[COMPLETED - DO NOT REWRITE]` block naming every
  finished section verbatim, plus a warning when prior windows rewrote any.

## [6.1.5] — Source-Trust Accuracy & Live Streaming Demos

### Fixed
- **Non-scorable claims no longer trip source-trust policies** — OPINION,
  PROCEDURAL and CONNECTIVE claims were attributed `UNCERTAIN`, which the
  policy layer counted as an untrusted source: a fully context-grounded answer
  that happened to contain an opinion sentence halted with
  `SOURCE_NOT_TRUSTED` ("untrusted source: uncertain") despite 100% grounding.
  These claims now get the distinct `AttributionType.NOT_REQUIRED` and are
  excluded from `uncertain_count`, so `default-src context` only halts on
  genuinely ungrounded factual claims. Verified live: the Acme SLA scenario
  that halted in 6.1.4 now ships with zero violations.
- **Demo server connection noise** — client aborts (browser navigating away
  mid-request) no longer dump `ConnectionAbortedError` tracebacks; favicon 404
  eliminated.
- **Stale protocol version in demo headers** — `PROTOCOL_VERSION` now prefers
  the live `crp.__version__` so editable installs report the current source
  tree (was reading stale distribution metadata).

### Added
- **Streaming safety console** — `POST /api/safety/analyze/stream` streams the
  model's tokens (including native `reasoning_content` from Qwen3/DeepSeek-R1)
  over SSE while generation runs, then delivers the full governance verdict.
  The safety console renders both live, with an "Uncertain" KPI now shown in
  the provenance panel.

## [6.1.4] — Model-Native Reasoning in the Transparency Stream

### Added
- **`AgentEventKind.MODEL_REASONING`** (`crp.agent_sdk.events`) — emitted by the
  Agent SDK whenever the provider exposes `last_reasoning_content` (Qwen3 hybrid
  thinking, DeepSeek-R1, o-series). The model's own thinking now reaches the
  transparency stream alongside CRP's orchestration reasoning.
- **TEL mapping** (`crp/tel/adapter.py`) — `MODEL_REASONING` maps to standard
  AG-UI `REASONING_START`/`REASONING_CONTENT`/`REASONING_END` events with
  `messageId="model"`, so any AG-UI consumer receives model-native thinking.
- **Console renders both reasoning layers** (`crp/frontend/console.py`) —
  reasoning narrative steps are keyed by `messageId` and titled separately
  ("Model reasoning" vs "CRP reasoning") so the two never merge.

### Fixed
- **Demo server branding** (`examples/crp_demos/`) — landing page badge and
  comparison console logo now read "v6" (were stale "v3"); the Comparison app
  is linked from every nav bar and the landing page grid.

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

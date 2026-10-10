# FIX NOTE — Opt-in transcript capture for the compliance audit chain

**Status:** proposed · **Scope:** protocol change (this repo) · **Downstream consumer:** WASA AI
**Filed:** 2026-10-10 · **Base:** `main` @ 342b8de

> Issues are disabled on this repository, so this note is the tracking artifact. It describes a protocol-level gap and a concrete fix design.

---

## 1. Problem

The tamper-evident compliance chain (`crp/security/audit_trail.py`) records **hashes and metadata only** for LLM interactions — never the content. There is no way to obtain a *viewable query–response pair* from the chain or from any CRP-owned store:

- In `crp/core/dispatch_router.py`, `LLM_CALL_COMPLETED` records truncated hashes and telemetry only:

  ```python
  "system_prompt_hash": hashlib.sha256(system_prompt.encode()).hexdigest()[:16],
  "task_input_hash":    hashlib.sha256(task_input.encode()).hexdigest()[:16],
  # + token counts, envelope stats, finish_reason, wall_time_ms, decision_basis
  ```

  The same holds across **all** dispatch variants (`dispatch`, `dispatch_with_tools`, `dispatch_reflexive`, `dispatch_progressive`, `dispatch_stream_augmented`, `dispatch_agentic`, `dispatch_stream`).

- Every window mints `node.raw_output_id = str(uuid.uuid4())` — **but nothing persists the raw output against that ID.** The identifier exists; the store does not. It is a dangling hook.

- Full response text *is* returned to the caller (`QualityReport.output`), so each downstream consumer must build its own content persistence, linked to the chain only by hashes it must recompute itself.

- Precedent that bounded content in payloads is acceptable: `FACTS_EXTRACTED` already carries `text_preview[:120]` per fact.

## 2. Why this must be fixed here (not downstream)

`ComplianceEventType` and the audit entry schema are protocol-owned; consumers install CRP as a package and cannot add chain event types themselves. The window HMAC chain (`crp/provenance/window_chain.py`) already binds `response_hash` per window — a transcript store keyed by the same window identity makes chain ↔ content joins trivial and independently verifiable.

## 3. Fix design

1. **New event type** — `TRANSCRIPT_RECORDED = "compliance.transcript_recorded"` (schema 2.1.0), emitted once per window (primary + each continuation), payload:

   ```
   {window_id, raw_output_id, input_hash, output_hash, transcript_ref,
    bytes_in, bytes_out, redacted: bool, pii_types: [...]}
   ```

2. **Content-addressed transcript store** — new `crp/security/transcript_store.py`: persists the assembled `messages` array and raw `output` per window, keyed by `raw_output_id` / content hash, reusing the hashes already recorded in `LLM_CALL_COMPLETED` so verification can prove a stored transcript matches the chained hashes. JSONL or per-window files on disk; size-capped; oversized payloads go through the existing pointer/compression pattern.

3. **Config, off by default** — `audit_capture_transcripts` (env `CRP_AUDIT_CAPTURE_TRANSCRIPTS`), plus `audit_transcript_max_bytes` and `audit_transcript_redact_pii`. PII handling integrates with the existing `_pii_scanner` results (dispatch already scans input and output — record `pii_types` on the transcript entry; optionally store a redacted variant).

4. **Export support** — extend `export_jsonl` / `export_ocsf` with `include_transcripts=True` so a single bundle contains chain + verdicts + viewable query–response pairs.

5. **Verification linkage** — `verify_transcripts()` companion to `verify_chain()`: re-hashes stored transcripts and confirms they match the `*_hash` fields and window `response_hash`; an edited transcript flags at exactly the right window.

## 4. Acceptance criteria

- [ ] `TRANSCRIPT_RECORDED` emitted per window when enabled; absent when disabled (zero overhead by default)
- [ ] Stored transcript hashes verifiably match chain entries (`verify_transcripts()` green; edited transcript → mismatch at the right window)
- [ ] PII redaction honored; redaction state recorded on the event
- [ ] Size cap honored; oversized outputs use pointer storage
- [ ] `export_jsonl(..., include_transcripts=True)` produces a self-contained bundle
- [ ] Tests: capture on/off, hash linkage, redaction, cap, export round-trip

## 5. Downstream wiring (WASA AI, after this lands)

WASA consumes CRP via `WASACRPSession` (`wasa_ai/llm/crp_session.py`): audit-sink forwarding (`_attach_audit_sink`), close-time per-session export, offline re-verification in `wasa_ai/llm/crp_audit_verifier.py`. Once the flag exists upstream, WASA enables it, includes transcript slices in its paid-tier troubleshooting bundle, and surfaces transcripts in report evidence appendices. No downstream schema workaround is possible until the protocol change lands.

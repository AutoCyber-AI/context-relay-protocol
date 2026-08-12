# CRP-SPEC-011: Audit Trail & HMAC Chain Specification

**Document:** CRP-SPEC-011  
**Title:** Context Relay Protocol (CRP) — Audit Trail & HMAC Chain  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-05-25  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-001, CRP-SPEC-004, CRP-SPEC-015

---

## Abstract

This document specifies the CRP audit trail — the tamper-evident, HMAC-SHA256-chained log of every event in a CRP session. It defines the 30+ event types, the HMAC chain algorithm, the chain verification procedure, export formats, and the integration with CRP Comply for regulatory evidence generation.

---

## 1. Event Types

Each audit event has a type, severity, and a set of fields specific to that type.

### 1.1 Session Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `SESSION_CREATED` | New session initialised | INFO | session_id, api_key_prefix, safety_policy_hash |
| `SESSION_CONTINUED` | Continuation window created | INFO | continuation_id, window_number |
| `SESSION_TERMINATED` | Session explicitly closed or expired | INFO | reason, total_windows, final_safety_budget |

### 1.2 Dispatch Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `DISPATCH_STARTED` | LLM call initiated | INFO | strategy, provider, model, temperature, token_budget |
| `DISPATCH_COMPLETED` | LLM call returned | INFO | response_hash, tokens_used, latency_ms |
| `DISPATCH_FAILED` | LLM call error | ERROR | error_code, error_message, provider |
| `RE_DISPATCH` | DPE triggered re-dispatch | WARN | reason (risk_upgrade / repetition / flow), original_risk |
| `STRATEGY_UPGRADE` | Strategy auto-upgraded | WARN | from_strategy, to_strategy, trigger_risk_level |

### 1.3 DPE Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `DPE_COMPLETED` | Full DPE pipeline finished | INFO | composite_score, risk_level, claim_count, grounding_pct |
| `FABRICATION_DETECTED` | Stage 3a found fabricated entities | WARN | fabrication_count, entity_list |
| `DISTORTION_DETECTED` | Stage 3b found fidelity distortions | WARN | distortion_count, types |
| `CONTRADICTION_DETECTED` | Stage 3c/6 found contradictions | WARN | scope (intra/cross-window), severity, claim_pairs |
| `REPETITION_DETECTED` | Stage 7 found content repetition | WARN | level, overlap_ratio |
| `COMPLETENESS_GAP` | Stage 8 found incomplete coverage | INFO | completeness_score, uncovered_sub_queries |
| `FLOW_REMEDIATION` | Stage 9 triggered flow fix | INFO | flow_score, remediation_type |
| `STOP_INJECT` | Mid-stream hallucination interruption | CRITICAL | pattern_detected, tokens_generated_before_stop |

### 1.4 Safety Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `SAFETY_HALT` | HTTP 451 returned due to policy | CRITICAL | risk_level, policy_directive_violated, audit_trail_uri |
| `SAFETY_BUDGET_DEPLETED` | Budget ≤ 0.10, oversight escalated | CRITICAL | remaining_budget, windows_processed |
| `OVERSIGHT_TRIGGERED` | Human review mode activated | WARN | trigger_reason, oversight_mode |
| `POLICY_VIOLATION` | Safety Policy directive violated | WARN | directive, violation_details |

### 1.5 Compliance Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `PII_DETECTED` | Stage 11 found personal data | WARN | pii_categories, no_store_set |
| `EU_AI_ACT_CLASSIFIED` | Stage 12 classified AI system | INFO | risk_class, system_type |
| `COMPLY_EXPORT` | Audit event streamed to CRP Comply | INFO | comply_event_id, trail_uri |

### 1.6 CKF Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `FACT_RETRIEVED` | Fact included in envelope | DEBUG | fact_id, relevance_score, community |
| `FACT_INGESTED` | New fact added to CKF | INFO | fact_id, source_id, importance_weight |
| `FACT_DELETED` | Fact removed (erasure/cleanup) | INFO | fact_id, reason |
| `FACT_QUARANTINED` | Fact flagged by DPE | WARN | fact_id, quarantine_reason |
| `CKF_ETAG_CHANGED` | CKF state hash changed | INFO | old_etag, new_etag, reason |

### 1.7 Agent Events

| Event Type | Trigger | Severity | Key Fields |
|-----------|---------|----------|------------|
| `TOOL_CALL` | Agentic dispatch invoked a tool | INFO | tool_name, input_hash, output_hash |
| `AGENT_LOOP_ITERATION` | Agentic loop advanced to next phase | INFO | phase, iteration, budget_remaining |
| `FAN_OUT_CREATED` | Fan-out children spawned | INFO | parent_window_id, child_count, child_ids |
| `FAN_IN_MERGED` | Fan-in synthesis completed | INFO | parent_ids, merged_budget |
| `COMPLETENESS_CONTINUATION` | Auto-continuation for incompleteness | INFO | uncovered_topics, auto_window_id |
| `FLOW_STITCH` | Stitch sentence inserted between windows | INFO | stitch_content_hash, prior_window_id |

---

## 2. HMAC Chain Algorithm

### 2.1 Chain Construction

Each audit event receives an HMAC that chains from the previous event:

```
event_hmac = HMAC-SHA256(
  event_type
  || event_timestamp_iso8601
  || event_data_hash            // SHA-256 of the event's key fields (JSON-serialised)
  || window_id
  || previous_event_hmac,       // Chain link (empty string for first event)
  session_hmac_key              // Derived via HKDF per CRP-SPEC-015 §3.1
)
```

### 2.2 Chain Properties

- **Forward integrity:** Modifying any event invalidates all subsequent HMACs
- **Append-only:** Events can only be added, never inserted or reordered
- **Per-session scope:** Each session has its own chain with its own key
- **Verifiable:** Any party holding the session HMAC key can verify the entire chain

### 2.3 Window-Level HMAC

In addition to the per-event chain, each window has a summary HMAC covering all events in that window:

```
window_hmac = HMAC-SHA256(
  session_id
  || window_number
  || window_timestamp
  || response_content_hash
  || dpe_report_hash
  || previous_window_hmac,       // Previous window (or empty for root)
  session_hmac_key
)
```

This is the value emitted as `CRP-Provenance-HMAC` (CRP-SPEC-002 §6.1).

### 2.4 Fan-In HMAC Merge

See CRP-SPEC-004 §9.3 for the fan-in HMAC algorithm (sorted parent HMACs, joined and hashed).

---

## 3. Chain Verification Procedure

### 3.1 Full Chain Verification

To verify a session's complete audit chain:

```
function verify_chain(events, session_hmac_key):
    previous_hmac = ""  // empty for first event
    
    for event in events (ordered by timestamp):
        expected = HMAC-SHA256(
            event.type || event.timestamp || SHA256(event.data) 
            || event.window_id || previous_hmac,
            session_hmac_key
        )
        if expected != event.hmac:
            return BROKEN at event.index
        previous_hmac = event.hmac
    
    return VALID
```

### 3.2 Partial Verification

For auditors verifying a specific window without the full session:
1. The auditor receives the window's events and the parent window's HMAC
2. Verification starts from the parent HMAC and chains through the window's events
3. If all verify: `PARTIAL` (this window is valid but the full chain was not checked)

### 3.3 Verification Output

The verification result is emitted as `CRP-Provenance-Chain-Integrity`:

| Value | Meaning |
|-------|---------|
| `VALID` | Full chain verified from root to current window |
| `BROKEN` | Verification failed — possible tampering |
| `PARTIAL` | Window-level verification passed; full chain not checked |
| `UNVERIFIED` | First window of session (no previous to chain from) |

---

## 4. Export Formats

### 4.1 NDJSON (Primary Format)

Each audit event is exported as a single line of JSON (Newline-Delimited JSON):

```json
{"event_type":"DISPATCH_COMPLETED","timestamp":"2026-05-25T10:00:01Z","session_id":"crp_sess_7f3a","window_id":"crp_win_a7f3","data":{"response_hash":"sha256:abc...","tokens_used":105816,"latency_ms":2341},"hmac":"sha256:def..."}
{"event_type":"DPE_COMPLETED","timestamp":"2026-05-25T10:00:02Z","session_id":"crp_sess_7f3a","window_id":"crp_win_a7f3","data":{"composite_score":0.14,"risk_level":"LOW","claim_count":47},"hmac":"sha256:ghi..."}
```

### 4.2 OCSF (Open Cybersecurity Schema Framework)

For SIEM integration, events can be exported in OCSF format. The mapping:

| OCSF Field | CRP Source |
|-----------|-----------|
| `class_uid` | 6003 (API Activity) |
| `activity_id` | Mapped from event_type |
| `severity_id` | Mapped from event severity |
| `time` | event.timestamp |
| `src_endpoint.uid` | session_id |
| `dst_endpoint.uid` | provider + model |
| `metadata.product.name` | "CRP Gateway" |
| `metadata.product.vendor_name` | "AutoCyber AI" |
| `unmapped.crp_hmac` | event.hmac |
| `unmapped.crp_risk_level` | risk_level |

### 4.3 SARIF (GitHub Integration)

For CRP Scan (GitHub Action), audit events are exported as SARIF findings. See CRP-SPEC-013.

---

## 5. CRP Comply Integration

### 5.1 Real-Time Streaming

When CRP Comply is connected, audit events are streamed in real-time via webhook:

```
POST https://comply.crprotocol.io/ingest/{org_id}
Content-Type: application/json
Authorization: Bearer <comply_api_key>

{
  "events": [<batch of NDJSON events>],
  "session_id": "crp_sess_7f3a",
  "chain_tip_hmac": "sha256:xyz..."
}
```

### 5.2 Evidence Chain Construction

CRP Comply receives the events and:
1. Verifies the HMAC chain on import (any BROKEN chain raises an incident)
2. Maps events to regulatory controls (per CRP-SPEC-010)
3. Aggregates events into per-AI-system risk registers
4. Generates FRIA, DPIA, and Technical Documentation on demand
5. Makes evidence accessible via `CRP-Compliance-Audit-Trail-URI`

### 5.3 Retention

| Tier | Retention | Comply Plan |
|------|-----------|-------------|
| Free | 30 days | Free |
| Pro | 1 year | Pro ($149/mo) |
| Business | 5 years | Business ($499/mo) |
| Enterprise | Custom (up to 10 years, EU AI Act Art. 12 requires 10 years) | Enterprise |

---

## 6. Security Considerations

- Audit events MUST be written to append-only storage. In-place modification is architecturally prohibited.
- The session HMAC key MUST NOT be included in audit event exports. It is held separately and provided to verifiers via a secure key exchange.
- Audit events containing `DEBUG`-level events (e.g., `FACT_RETRIEVED`) MAY be excluded from exports to reduce volume. WARN and CRITICAL events MUST always be included.

---

## 7. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-015 — Security & Privacy
- RFC 2104 — HMAC
- OCSF v1.1.0 — Open Cybersecurity Schema Framework

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

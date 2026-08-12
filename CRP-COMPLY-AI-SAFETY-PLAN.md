# CRP Comply — AI Safety Hardening Plan
## (Prepared for next focused run)

**Date:** 2026-06-05  
**Priority:** P1 — Must complete before production scale  

---

## 1. Audit Trail Integrity

### 1.1 Cache Hits Bypass Audit
**File:** `src/crp_comply/agent/loop_runtime.py`  
**Gap:** When a tool call is deduplicated/cached (duplicate call detection), no audit record is written.  
**Fix:** Add `_crp_trail.record()` call in the cache-hit branch before returning the cached payload.

### 1.2 HMAC Chain Per-Session Persistence
**File:** `src/crp_comply/agent/orchestrator.py`  
**Gap:** `_crp_trail` is created per `run()` call but should persist across `run`/`resume`/`continue` on the same session_id.  
**Fix:** Store the trail object in `self._session_trails: dict[str, ComplianceAuditTrail]` and reuse.

### 1.3 CRP Dispatch Path — Full Audit Coverage ✅ (Done this run)
**File:** `src/crp_comply/agent/orchestrator.py`  
**Status:** Added `_dispatch_pr.record_output()` and PII redaction count to dispatch-end audit.  
**Remaining:** Add `_lineage` tracker usage for data provenance in dispatch path.

---

## 2. Injection Defense Depth

### 2.1 Tool-Result Injection Scan
**File:** `src/crp_comply/agent/orchestrator.py`  
**Gap:** `scan_for_injection()` only scans user task, not tool results or assistant messages.  
**Fix:** Add `scan_for_injection()` call on every message before appending to the LLM context. Gate with `CRP_COMPLY_SCAN_ALL_MESSAGES=1` env var.

### 2.2 Structural Input Validation (Layer 1)
**File:** `src/crp_comply/agent/crp_integration.py`  
**Gap:** No size limits, Unicode normalization, or MIME validation on agent input.  
**Fix:** Add `validate_input_structure()` function: size cap (64KB), NFC normalization, control char stripping, metadata key count limits.

### 2.3 Injection Scan Exception Handling
**File:** `src/crp_comply/agent/crp_integration.py`  
**Gap:** `scan_for_injection()` swallows ALL exceptions silently.  
**Fix:** Log at WARNING level when the detector itself fails (not when no flags found).

---

## 3. Safety Control Plane Integration

### 3.1 Safety Policy Directives
**File:** New module `src/crp_comply/agent/safety_policy.py`  
**Gap:** No CSP-style safety policy support.  
**Fix:** Parse `CRP-Safety-Policy` header / env var into directives: `halt-on`, `require-grounding`, `block-pii`, etc. Wire into agent loop.

### 3.2 Safety Budget (Multi-Agent Circuit Breaker)
**File:** `src/crp_comply/agent/orchestrator.py`  
**Gap:** No cumulative risk tracking across agent chains.  
**Fix:** Add `SafetyBudget` class: starts at 1.0, depleted by HIGH/MEDIUM/CRITICAL events. When <= 0.1, halt with HTTP 451 equivalent.

### 3.3 Checkpoint Primitive UI
**File:** `src/crp_comply/api/checkpoint_routes.py` + frontend  
**Gap:** `checkpoint_inbox.py` exists but no UI for human resolution.  
**Fix:** Add Inbox notification type for checkpoints. Add approve/reject/edit buttons in frontend.

---

## 4. DPE Integration (when crp v4 available)

### 4.1 Post-Generation DPE Pipeline
**Gap:** No 13-stage DPE analysis after LLM output.  
**Fix:** After `dispatch_via_crp()` or each tool-loop iteration, run DPE on the output. Store DPE report in audit trail.

### 4.2 Grounding Verification
**Gap:** No `require-grounding` enforcement.  
**Fix:** Compute grounding_pct from tool citations vs. claims. Reject if below threshold.

### 4.3 Halt-on-Critical
**Gap:** No HTTP 451 equivalent for unsafe output.  
**Fix:** When DPE risk_level == CRITICAL, return error state instead of final_text.

---

## 5. Data Lineage

### 5.1 Lineage Tracking for Agent Inputs
**File:** `src/crp_comply/agent/orchestrator.py`  
**Gap:** `_lineage` tracker is created but never used.  
**Fix:** Record lineage for: user task, tool results, RAG hits, CKF facts, web search results. Track transformations (PII redaction, surrogate substitution, envelope packing).

### 5.2 Lineage Export for Compliance Reports
**Gap:** No way to export lineage for GDPR Art. 30 or EU AI Act Art. 11.  
**Fix:** Add `/api/v1/lineage/{session_id}` endpoint returning NDJSON lineage.

---

## Implementation Order (Recommended)

1. **Week 1:** Audit trail fixes (1.1, 1.2, 1.3 remainder)
2. **Week 1:** Injection defense (2.1, 2.2, 2.3)
3. **Week 2:** Safety policy + budget (3.1, 3.2)
4. **Week 2:** Checkpoint UI (3.3)
5. **Week 3:** DPE integration (4.1–4.3) — blocked on crp v4 publish
6. **Week 3:** Data lineage (5.1, 5.2)

---

*This plan is derived from the CRPv4 SPEC-005, SPEC-006, SPEC-011, SPEC-033, and SPEC-034 specifications.*

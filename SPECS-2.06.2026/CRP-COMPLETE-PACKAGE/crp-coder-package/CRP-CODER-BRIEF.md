# CRP — Coder Implementation Brief

**For:** Lead Developer  
**From:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**Purpose:** Exactly what to build, in what order, reading which specs

---

## What CRP Is (One Paragraph)

CRP is an HTTP-header governance layer that sits between your app
and any LLM. One endpoint change. Every AI call gets safety signals,
tamper-evident provenance, compliance classification, and now —
with CDR — quality that holds constant regardless of how much output
is requested. The protocol adds < 50ms overhead. Zero extra inference
passes in the core path. Any model, any provider.

---

## The Three Unsolved Gaps (Fix These First in Any Implementation)

Before reading any other spec, know these three things that need
tight implementation attention:

### Gap 1 — N-gram blacklist is normative (SPEC-003 amendment)

The v3.1.1 n-gram blacklist works and is already in the codebase.
Formalise it as a required Phase 2 ranking step:

```python
# In Phase 2 envelope packing (SPEC-003 §6):
# After CDR novelty scoring, apply output-level guard:
forbidden_ngrams = session.ngram_blacklist  # built from prior window outputs
if any(ngram in candidate_text for ngram in forbidden_ngrams):
    candidate_score *= 0.1  # demote, don't eliminate
```

Update the blacklist after each window: extract all 6-grams from
the window output, add to session.ngram_blacklist.

### Gap 2 — CKF exhaustion handling (SPEC-024 amendment)

When CDR's mean novelty score across retrieved facts drops below
0.15 (configurable), the CKF is exhausted for this session.
Gateway MUST:

```
CRP-Context-Coverage-Score: 0.08
CRP-Context-Mode: ckf-exhausted
CRP-Onboarding-Hint: ingest-more-documents-for-continued-quality
```

And MUST NOT continue generating windows — further output will
degrade. Return the completeness score so the caller decides
whether to stop or continue with degraded quality.

### Gap 3 — Formal loop exit rule (SPEC-004 amendment)

Window loop terminates when ANY of these are true:

```python
def should_terminate(session, dpe_report):
    return (
        dpe_report.completeness_score >= 0.92      # task complete
        or session.window_count >= session.max_windows  # hard limit
        or session.coverage_score < 0.15            # CKF exhausted
        or session.safety_budget <= 0.10            # budget depleted
    )
```

---

## What to Build — Prioritised

### TIER 1 — Core Protocol (Build This)

These are the protocol. Everything else depends on them.
Read these specs, implement in this order:

| Spec | What to implement |
|------|------------------|
| **SPEC-009** | CKF: HNSW index, fact schema, ingestion pipeline, Coverage Set on the session object |
| **SPEC-003** | Envelope packing — Phase 1 (HNSW retrieval), Phase 2 (**CDR formula**), Phase 3 (primacy-recency sandwich). This is the most important algorithm. |
| **SPEC-024** | CDR: the novelty formula, Coverage Set update hook, CKF exhaustion handling. **This is the new piece that solves quality-at-quantity.** |
| **SPEC-004** | Window continuation: DAG, session state, Residual Task Anchor (forward-looking, not backward), loop exit rule from Gap 3 above |
| **SPEC-005** | DPE: all 13 stages. Stages 1-5 and 7-8 are the critical path. Stage 6 (cross-window coherence) requires session history. |
| **SPEC-006** | Safety Policy parser and enforcer. `halt-on CRITICAL` → HTTP 451. |
| **SPEC-007** | Session token: HKDF key derivation, signed JWT-style token carrying Coverage Set reference |
| **SPEC-002** | Header emission: all 58 headers. Emit from the DPE report. |
| **SPEC-011** | Audit trail: HMAC chain, 30+ event types, NDJSON export |

### TIER 2 — Products (Build for Revenue)

| Spec | What to implement |
|------|------------------|
| **SPEC-016** | Gateway service: `/v1/chat/completions` endpoint, provider routing, API key management, free/paid tier quotas |
| **SPEC-017** | Zero-CKF mode: `CRP-Context-Mode: zero-ckf` header, progressive activation cascade, onboarding hints |
| **SPEC-013** | CRP Scan GitHub Action: detection patterns for OpenAI/Anthropic/LangChain/etc., SARIF output, Comply signup link |

### TIER 3 — Read But Do Not Build Yet

| Spec | Why wait |
|------|---------|
| SPEC-018 (AIR) | Useful once Tier 1 is benchmarked. Feedback loop builds on proven CDR. |
| SPEC-019 (CQR) | Detection (C1-C6 flags) is part of DPE (Tier 1). Remediation passes are opt-in later. |
| SPEC-020 (CLD) | Opt-in only. For weak local models on async tasks. Not core. |
| SPEC-021 (ROS) | Opt-in only. Multi-pass consensus. Not core. |
| SPEC-022 (PEF) | The execution engine for 020/021. Not needed until those are built. |
| SPEC-023 | Architectural governance doc. Read it — it tells you what NOT to make default. |

---

## The CDR Algorithm — The Most Important New Thing

This is the single most important change in the entire spec suite.
It is also the simplest. Implement it exactly.

```python
def phase2_rank(facts, query_embedding, session):
    scored = []
    for fact in facts:
        # Standard relevance score (already computed in Phase 1)
        relevance = cosine_similarity(fact.embedding, query_embedding)
        
        # CDR novelty score — the new piece
        if session.coverage_set:
            coverage = max(
                cosine_similarity(fact.embedding, addressed)
                for addressed in session.coverage_set
            )
        else:
            coverage = 0.0  # Window 1: everything is novel
        
        novelty = 1.0 - coverage
        
        # Final CDR score
        score = fact.importance_weight * relevance * novelty
        scored.append((fact, score))
    
    # Sort descending, apply primacy-recency sandwich packing
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

def update_coverage_set(session, dpe_report):
    """Call this after every window completes."""
    for sub_query in dpe_report.addressed_sub_queries:
        embedding = embed(sub_query)  # reuse your existing embed function
        session.coverage_set.append(embedding)
```

**That is the complete CDR implementation.** Two functions. No new
dependencies. Reuses existing embeddings infrastructure.

---

## The Residual Task Anchor — Second Most Important Change

In SPEC-004, change what the continuation header carries:

```python
# BEFORE (backward-looking — grows every window, wastes context)
continuation_context = f"Previously covered: {summary_of_done_work}"

# AFTER (forward-looking — constant size, always useful)
remaining = [s for s in task_sections if s not in completed_sections]
continuation_context = f"Still to cover: {', '.join(remaining)}"
```

The model always knows exactly what's left. Context budget stays
constant. No unbounded summary growth.

---

## Key Invariants to Preserve

1. **< 50ms overhead on any single call** — CDR adds < 1ms. DPE is
   embeddings + NLI, not generation. Never add inference passes to
   the core path without an explicit `CRP-Amplification-Mode` header.

2. **Axiom 4 — strip before forwarding** — NO `CRP-*` header reaches
   the LLM provider. Strip all CRP headers from the outbound request.

3. **HMAC chain never breaks** — every window extends the chain.
   A BROKEN chain must surface as `CRP-Provenance-Chain-Integrity: BROKEN`.

4. **Zero-CKF degrades gracefully** — if coverage_set is empty,
   CDR novelty = 1.0 for all facts (correct). If CKF has 0 facts,
   emit `CRP-Context-Mode: zero-ckf` and continue (safety still works).

5. **Safety Policy enforcement is a hard gate** — `halt-on CRITICAL`
   means the response does NOT reach the caller. HTTP 451. Full stop.

---

## Files to Read (in this order)

```
1.  CRP-SPEC-024-coverage-differential-retrieval.md  ← START HERE
2.  CRP-SPEC-003-envelope.md                         ← core algorithm
3.  CRP-SPEC-009-ckf.md                              ← knowledge layer
4.  CRP-SPEC-004-continuation.md                     ← window loop
5.  CRP-SPEC-005-dpe.md                              ← analysis pipeline
6.  CRP-SPEC-002-headers.md                          ← wire format
7.  CRP-SPEC-006-safety-policy.md                    ← enforcement
8.  CRP-SPEC-007-session-token.md                    ← state relay
9.  CRP-SPEC-011-audit-trail.md                      ← provenance
10. CRP-SPEC-017-zero-ckf-mode.md                    ← day-one UX
11. CRP-SPEC-016-gateway-service.md                  ← product layer
12. CRP-SPEC-013-github-action.md                    ← funnel product
```

Do not read SPEC-018 through 022 until Tier 1 is benchmarked.
Do read SPEC-023 once — it tells you what must never become default.

---

## The Benchmark That Validates Everything

Run this after implementing CDR. This is the pass/fail test:

```
Task: "Write a comprehensive guide on [domain], 5 sections"
Model: any 7B or 8B local model (llama-3.1-8b recommended)
Windows: 5
Target: 2500 words

PASS criteria:
  Window 1 repetition: < 1.0%
  Window 5 repetition: < 1.0%   ← This is the new bar CDR enables
  Total words: > 2500
  Section count: exactly as requested
  CRP-Context-Coverage-Score window 1: > 0.95
  CRP-Context-Coverage-Score window 5: > 0.50
  
FAIL criteria (any one of):
  Window 5 repetition > 2.0%    ← CDR didn't work
  CRP-Context-Coverage-Score dropping to < 0.15 before task complete
    → CKF too small, need more documents
  Section count deviates from request by > 20%
    → Residual Task Anchor not working
```

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*

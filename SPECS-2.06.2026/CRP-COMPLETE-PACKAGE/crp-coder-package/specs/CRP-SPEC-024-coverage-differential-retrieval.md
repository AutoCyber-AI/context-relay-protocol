# CRP-SPEC-024: Coverage-Differential Retrieval (CDR)

**Document:** CRP-SPEC-024  
**Title:** Context Relay Protocol (CRP) — Coverage-Differential Retrieval: Guaranteeing Quality at Scale  
**Version:** 3.1.0 — Locked  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-003 §5–6, CRP-SPEC-004 §12, CRP-SPEC-009 §3  
**Prerequisites:** CRP-SPEC-003, CRP-SPEC-004, CRP-SPEC-009

---

## Abstract

This document specifies Coverage-Differential Retrieval (CDR) — the mechanism that guarantees output quality holds constant regardless of how much output is requested. The root cause of quality degradation in multi-window generation is precisely identified and resolved: CKF retrieval ranked by relevance alone returns the same high-relevance facts every window, because neither the query nor the CKF changes. The model reads familiar inputs and produces familiar outputs. CDR modifies the Phase 2 ranking formula to score facts by both relevance and session novelty, ensuring each window receives the most relevant material that has not yet been addressed. Quality at Window 5 matches quality at Window 1.

This document also formally specifies the Residual Task Anchor (amendment to SPEC-004), the window loop exit rules, and the n-gram output guard. Together these four mechanisms constitute the complete solution to the quality-quantity problem.

---

## 1. Root Cause Analysis

### 1.1 Why Quality Degrades Without CDR

The v3.1.1 benchmark established the trajectory precisely:

```
Window 1: 0.39% repetition   ← envelope is entirely fresh
Window 2: 1.08% repetition   ← familiar facts begin re-entering
Window 3: 0.69% repetition   ← n-gram blacklist partially compensates
Window 4: 0.52% repetition   ← compensation holds
Window 5: 2.08% repetition   ← envelope novelty exhausted
```

The cause: SPEC-003 Phase 1 retrieves top-K facts from the CKF by cosine similarity to the query. The query does not change between windows. The CKF does not change between windows. The same facts rank highest every time.

```
Query: "Kubernetes networking architecture" — all five windows

HNSW top-5 every window, unchanged:
  1. "Kubernetes uses a flat network model..."     sim=0.94  ← used W1
  2. "Pod-to-pod communication is direct..."       sim=0.91  ← used W1
  3. "kube-proxy manages Service routing..."       sim=0.89  ← used W2
  4. "Network policies control traffic flow..."    sim=0.87  ← used W2
  5. "CNI plugins implement the network layer..."  sim=0.85  ← used W3
```

Facts about eBPF dataplanes, BGP integration, service mesh internals, cross-cluster federation sit at similarity 0.65–0.75 — genuine, relevant, novel material — and never surface because relevance ranking is saturated by the Window 1 facts.

### 1.2 What the n-gram Blacklist Was Doing

The v3.1.1 n-gram blacklist attacked this at the output level — forbidding repeated phrases after the model produced them. It worked (56% repetition reduction) but treated the symptom. The model still received stale inputs; it was just prevented from repeating the most obvious phrases. CDR removes stale inputs before the model sees them. The blacklist becomes a thin secondary guard rather than the primary defence.

---

## 2. The CDR Formula

### 2.1 Definitions

**Coverage Set** — a session-scoped list of weighted embeddings representing sub-queries that prior windows have addressed:

```
CoverageEntry {
  embedding:     float[]    // same model as CKF facts (REQUIRED — see §2.5)
  depth_weight:  float      // 0.0–1.0: how thoroughly this was covered
  window_number: integer    // which window addressed it
}
```

**Residual Set** — the complementary set: sub-queries from the original task that have NOT yet been addressed. Derived by subtracting Coverage Set topics from the original task decomposition.

### 2.2 The Bidirectional Formula

The original formula had one signal: push away from what has been addressed. The correct formula has two signals: push away from what has been addressed AND pull toward what has not yet been addressed.

```
coverage_score(fact) =
    Σ( depth_weight_i × cosine_sim(fact, coverage_entry_i) )
    ────────────────────────────────────────────────────────
    Σ( depth_weight_i )
    
    for all entries in CoverageSet
    (weighted mean, not maximum — see §2.3)

residual_pull(fact) =
    max( cosine_sim(fact, residual_j)
         for residual_j in ResidualSet )
    
    (0.0 if ResidualSet is empty)

coverage_penalty = min(coverage_score(fact), 0.80)
                   ← capped at 0.80, never fully excluded (see §2.4)

novelty(fact) = max(
    1.0 - coverage_penalty,
    MIN_NOVELTY_FLOOR              ← 0.20 (see §2.4)
)

CDR_score(fact) = importance_weight
                × max(relevance(fact, query), residual_pull(fact))
                × novelty(fact)
```

This formula does three things simultaneously:
1. De-prioritises facts whose content has already been addressed
2. Boosts facts relevant to what still needs to be written
3. Guarantees no fact is completely excluded from consideration

### 2.3 Weighted Mean, Not Maximum

The original SPEC-024 used `max()` over all Coverage Set entries. This is wrong for a fact relevant to multiple sub-queries — one covered, one not. `max()` would heavily penalise it based on the covered sub-query even though it's still needed for the uncovered one.

The weighted mean distributes the coverage signal correctly:
- A fact relevant to one covered topic and one uncovered topic gets ~50% coverage penalty
- A fact relevant only to fully covered topics gets ~80%+ penalty (capped at 0.80)
- A fact relevant only to uncovered topics gets near-zero penalty

This is the correct behaviour.

### 2.4 The Minimum Novelty Floor

**CRITICAL implementation requirement.** `novelty` MUST NEVER go below `MIN_NOVELTY_FLOOR = 0.20`.

Without a floor, the formula can suppress facts that are essential for coherence. Example: Window 1 establishes "Kubernetes uses etcd as its distributed key-value store." Window 3 is writing about etcd performance characteristics — it needs that foundational fact again to write coherently. With a floor of 0.20, the fact is de-prioritised but not excluded. The packing algorithm can still include it if the envelope has room. Without a floor, it is effectively invisible and coherence breaks.

The floor of 0.20 means: even a completely addressed fact retains 20% of its base score. Highly relevant, fully covered facts remain competitive at 20% of full score. Low-relevance, fully covered facts are effectively excluded. This is the correct behaviour.

### 2.5 Embedding Model Consistency (Normative)

**Coverage Set embeddings MUST be computed using the same embedding model as the CKF fact embeddings.**

If the CKF was built with `text-embedding-3-large` (dim=3072), Coverage Set sub-query embeddings MUST also use `text-embedding-3-large`. Using a smaller or different model for runtime sub-query embedding silently corrupts all CDR scores because the similarity space is incommensurable. This is a hard requirement, not a recommendation.

The gateway MUST record the embedding model identifier in the session token (SPEC-007) and MUST reject Coverage Set updates that use a different model identifier.

### 2.6 Minimum Relevance Threshold

Before CDR scoring is applied, facts with `relevance(fact, query) < CDR_MIN_RELEVANCE` (default: 0.55) MUST be excluded from the candidate set entirely, regardless of their novelty score.

This prevents CDR from pulling genuinely off-topic material into the envelope at high window counts. At Window 8, many high-relevance facts are exhausted. CDR would otherwise surface facts with novelty=0.95 but relevance=0.40 — fresh but useless. The minimum relevance threshold ensures novelty can only promote within the relevance-qualified set.

The threshold is configurable per deployment. Narrower knowledge domains may increase it (0.65). Broader tasks may decrease it (0.50).

### 2.7 Window 1 Formal Behaviour

When the Coverage Set is empty (Window 1, or any window after session reset):

```
coverage_score(fact) = 0.0     (no entries to compute over)
residual_pull(fact)  = 0.0     (ResidualSet = full task, not specific)
novelty(fact)        = 1.0     (maximum novelty, all material fresh)
CDR_score(fact)      = importance_weight × relevance(fact, query)
```

**Window 1 CDR score equals the current SPEC-003 Phase 2 score.** CDR introduces no change to Window 1 behaviour. Its benefit is zero-cost on the first window and grows with each subsequent window.

---

## 3. Coverage Set Construction and Maintenance

### 3.1 Building Coverage Set Entries

After each window completes, DPE Stage 8 (Completeness Verification) produces a list of `addressed_sub_queries` — the sub-queries from the original task decomposition that the window's output covered. For each addressed sub-query:

```python
def update_coverage_set(session, dpe_report, window_output):
    for sub_query in dpe_report.addressed_sub_queries:
        
        # Depth weight: fraction of expected content produced
        # for this sub-query in this window
        depth = dpe_report.sub_query_depth.get(sub_query.id, 0.5)
        
        # Embed with the SAME model as the CKF
        embedding = ckf_embed_model.encode(sub_query.text)
        
        session.coverage_set.append(CoverageEntry(
            embedding=embedding,
            depth_weight=depth,
            window_number=session.window_count
        ))
    
    # Update Residual Set: remove addressed sub-queries
    session.residual_set = [
        sq for sq in session.task_sub_queries
        if sq.id not in {a.id for a in dpe_report.addressed_sub_queries}
    ]
```

### 3.2 Coverage Depth Weights

`depth_weight` ranges from 0.0 to 1.0:

| Coverage depth | Weight |
|---------------|--------|
| Thorough (dedicated section, multiple paragraphs) | 0.90 |
| Adequate (full paragraph) | 0.70 |
| Partial (single sentence or brief mention) | 0.40 |
| Marginal (passing reference only) | 0.15 |

DPE Stage 8 assigns depth based on word count ratio: actual words on this sub-query versus expected words. A sub-query expected to produce 300 words that received 280 words gets depth=0.90. One that received 60 words gets depth=0.20.

This means a sub-query that was partially addressed (depth=0.40) still shows up as partially relevant in CDR, allowing the model to complete it in a subsequent window rather than being blocked by a binary "covered/not covered" flag.

### 3.3 ResidualSet for Residual Task Anchor

The ResidualSet feeds the Residual Task Anchor (§4). It must be available at packing time. It is stored in the session token (SPEC-007 §2) as a compact list of remaining sub-query identifiers.

---

## 4. Residual Task Anchor (Amends SPEC-004 §12)

### 4.1 The Problem with Backward-Looking Continuation

Current SPEC-004 continuation summary grows with each window — it summarises what has been done. By Window 4 this summary is large, consumes context budget, and tells the model what it already knows. It is backward-looking.

### 4.2 The Fix: Forward-Looking Residual

Replace the continuation summary with a **Residual Task Anchor** — a compact statement of what remains to be done:

```python
# BEFORE: backward-looking, grows every window
continuation = f"Previously covered: {summary_of_all_prior_windows}"

# AFTER: forward-looking, constant size
remaining = session.residual_set  # already maintained by §3.1
anchor = f"Remaining sections to complete: {', '.join(r.label for r in remaining)}"
```

Properties of the Residual Task Anchor:
- **Constant size** — it shrinks as sections complete, never grows
- **Always actionable** — tells the model exactly what to do next
- **Structurally explicit** — prevents the model from re-addressing completed sections

### 4.3 Backward-Summary as Optional Addition

The full prior summary is NOT discarded — it is available in the session token if needed. For tasks where the model needs to reference what was said (e.g., "as established in section 2..."), the operator may include it at reduced weight. By default, only the Residual Task Anchor appears in the continuation context.

---

## 5. The N-Gram Output Guard (Formalises v3.1.1)

CDR solves quality degradation at the input level. The n-gram blacklist (implemented in v3.1.1) provides a secondary guard at the output level. This section formally specifies it as a normative SPEC-003 requirement.

### 5.1 Blacklist Construction

After each window, extract all 6-grams from the window output and add to the session's `ngram_blacklist`:

```python
def update_ngram_blacklist(session, window_output):
    tokens = tokenize(window_output)
    new_ngrams = {tuple(tokens[i:i+6]) for i in range(len(tokens)-5)}
    session.ngram_blacklist.update(new_ngrams)
```

### 5.2 Blacklist Application in Phase 2

During Phase 2 ranking, facts whose content matches blacklisted n-grams are de-prioritised:

```python
ngram_overlap = count_matching_ngrams(fact.content, session.ngram_blacklist)
ngram_penalty = min(0.80, ngram_overlap * 0.15)  # max 80% penalty
adjusted_score = CDR_score(fact) * (1.0 - ngram_penalty)
```

Note: this adjusts the **fact's score**, not the output. The blacklist filters what goes into the envelope. Combined with CDR, this means stale facts are doubly de-prioritised — by CDR for semantic coverage and by the blacklist for lexical overlap.

### 5.3 Diagnostic Value

If the n-gram blacklist triggers frequently (> 20% of retrieved facts receive a penalty), this signals that CDR's novelty scoring is not functioning correctly — likely because the CKF lacks sufficient depth. The gateway SHOULD emit:

```
CRP-Context-NGram-Guard-Activations: 8
```

High activation count → operator should ingest more documents.

---

## 6. Window Loop Exit Rules (Normative)

The multi-window generation loop MUST terminate when ANY of the following conditions is true. These are the four exit paths, in priority order:

### Exit 1 — Task Complete

```
dpe_report.completeness_score >= COMPLETION_THRESHOLD (default: 0.92)
AND session.residual_set is empty (or contains only marginal items)
```

The task is done. No further windows needed. Emit the final assembled output.

### Exit 2 — Hard Window Limit

```
session.window_count >= session.max_windows (default: 5, configurable to 20)
```

Hard ceiling regardless of completion status. The gateway returns the output assembled so far with:
```
CRP-Context-Continuation-Status: limit-reached
CRP-Quality-Completeness: 0.74   ← whatever was achieved
```

### Exit 3 — CKF Exhaustion

```
mean(CDR_score(fact) / relevance(fact, query) for fact in envelope) < 0.15
```

The mean novelty ratio has dropped below 0.15 — the CKF no longer has sufficiently novel material to maintain quality. Continuing would produce stale output. The gateway MUST stop and emit:

```
CRP-Context-Mode: ckf-exhausted
CRP-Context-Coverage-Score: 0.08
CRP-Onboarding-Hint: ingest-more-documents-for-continued-quality
```

**This is the most important exit condition.** It prevents the system from generating low-quality output when the knowledge base is exhausted. It also surfaces a clear, actionable signal to the operator: the protocol stopped because it ran out of novel material, not because of a bug.

### Exit 4 — Safety Budget Depleted

```
session.safety_budget <= 0.10
```

Per SPEC-012 §2.3. Not a content quality condition — a safety condition. Immediately triggers oversight escalation.

---

## 7. Complete Implementation Reference

### 7.1 Phase 2 Ranking — Complete Function

```python
CDR_MIN_RELEVANCE = 0.55
MIN_NOVELTY_FLOOR = 0.20
COVERAGE_PENALTY_CAP = 0.80

def cdr_rank(facts, query_embedding, session):
    """
    CDR-enhanced Phase 2 ranking.
    Replaces the relevance-only ranking in SPEC-003 §6.2.
    """
    candidates = []
    
    for fact in facts:
        relevance = cosine_similarity(fact.embedding, query_embedding)
        
        # Hard minimum relevance gate
        if relevance < CDR_MIN_RELEVANCE:
            continue
        
        # Weighted mean coverage score
        if session.coverage_set:
            weighted_sims = [
                entry.depth_weight * cosine_similarity(fact.embedding, entry.embedding)
                for entry in session.coverage_set
            ]
            total_weight = sum(e.depth_weight for e in session.coverage_set)
            coverage_score = sum(weighted_sims) / total_weight
        else:
            coverage_score = 0.0  # Window 1: no coverage history
        
        # Residual pull: how useful is this fact for what remains?
        if session.residual_set:
            residual_pull = max(
                cosine_similarity(fact.embedding, r.embedding)
                for r in session.residual_set
            )
        else:
            residual_pull = 0.0
        
        # Effective relevance: best of query relevance or residual pull
        effective_relevance = max(relevance, residual_pull)
        
        # Novelty with floor
        coverage_penalty = min(coverage_score, COVERAGE_PENALTY_CAP)
        novelty = max(1.0 - coverage_penalty, MIN_NOVELTY_FLOOR)
        
        # N-gram penalty (secondary guard)
        ngram_overlap = count_matching_ngrams(fact.content, session.ngram_blacklist)
        ngram_penalty = min(0.80, ngram_overlap * 0.15)
        
        # Final CDR score
        score = fact.importance_weight * effective_relevance * novelty * (1.0 - ngram_penalty)
        candidates.append((fact, score))
    
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates


def should_terminate_window_loop(session, dpe_report, envelope_stats):
    """
    Normative loop exit conditions. Returns (should_stop, reason).
    """
    if dpe_report.completeness_score >= 0.92 and not session.residual_set:
        return True, "task-complete"
    
    if session.window_count >= session.max_windows:
        return True, "limit-reached"
    
    if envelope_stats.mean_novelty_ratio < 0.15:
        return True, "ckf-exhausted"
    
    if session.safety_budget <= 0.10:
        return True, "safety-budget-depleted"
    
    return False, None
```

### 7.2 Coverage Set Update — Complete Function

```python
def update_session_after_window(session, dpe_report, window_output):
    """
    Called after every completed window.
    Updates Coverage Set, Residual Set, and N-gram blacklist.
    """
    # 1. Update Coverage Set
    for sub_query in dpe_report.addressed_sub_queries:
        depth = dpe_report.sub_query_depth.get(sub_query.id, 0.5)
        embedding = session.embed_model.encode(sub_query.text)  # MUST match CKF model
        session.coverage_set.append(CoverageEntry(
            embedding=embedding,
            depth_weight=depth,
            window_number=session.window_count
        ))
    
    # 2. Update Residual Set
    addressed_ids = {sq.id for sq in dpe_report.addressed_sub_queries}
    session.residual_set = [sq for sq in session.residual_set 
                            if sq.id not in addressed_ids]
    
    # 3. Update N-gram blacklist
    tokens = tokenize(window_output)
    new_ngrams = {tuple(tokens[i:i+6]) for i in range(len(tokens) - 5)}
    session.ngram_blacklist.update(new_ngrams)
    
    # 4. Update window count
    session.window_count += 1
```

---

## 8. Headers

### 8.1 CRP-Context-Coverage-Score

**Direction:** RES  
**Definition:** The **minimum** (worst-case) CDR novelty ratio across all facts included in this window's envelope. Reports the least-novel fact that was included. 1.0 = entirely fresh. 0.20 = minimum floor reached (facts hitting the floor included).

Using minimum rather than mean: mean can be inflated by a few very novel facts while most content is stale. Minimum reflects the actual worst-case freshness of what the model received.

```
CRP-Context-Coverage-Score: 0.74
```

**Interpretation:**
- > 0.70: Healthy — envelope is predominantly fresh
- 0.40–0.70: Moderate — mix of fresh and revisited material
- 0.20–0.40: Low — approaching CKF exhaustion
- < 0.20: Impossible (minimum floor prevents this)

### 8.2 CRP-Context-Coverage-Depth

**Direction:** RES  
**Definition:** Number of entries in the Coverage Set at packing time. Indicates accumulated session knowledge.

```
CRP-Context-Coverage-Depth: 18
```

### 8.3 CRP-Context-NGram-Guard-Activations

**Direction:** RES  
**Definition:** Number of candidate facts that received an n-gram penalty during Phase 2 ranking. High values signal CKF exhaustion.

```
CRP-Context-NGram-Guard-Activations: 3
```

### 8.4 CRP-Context-Continuation-Status

**Direction:** RES  
**Definition:** The loop exit reason when the window loop terminates.

```
CRP-Context-Continuation-Status: task-complete
CRP-Context-Continuation-Status: limit-reached
CRP-Context-Continuation-Status: ckf-exhausted
CRP-Context-Continuation-Status: safety-budget-depleted
CRP-Context-Continuation-Status: in-progress
```

---

## 9. The Quality-Quantity Guarantee

CDR formally enables the following guarantee:

> **Requesting more output does not reduce quality. Quality is held at Window 1 levels regardless of total output length, because each window receives maximally novel, relevant material from the CKF, pulled toward what remains to be covered and pushed away from what has been addressed.**

This guarantee holds under the following conditions:
1. The CKF contains sufficient facts to cover the full task (Coverage Score stays above 0.40 through task completion)
2. The minimum relevance threshold is met by the novel facts (the CKF is topically relevant to the task)

When condition 1 fails (CKF exhaustion), the guarantee is broken and the gateway signals this explicitly via `CRP-Context-Mode: ckf-exhausted` rather than silently degrading. The operator then knows to ingest more documents. The protocol is honest about its limits.

---

## 10. What CDR Does Not Solve

**Genuine knowledge gaps in the CKF.** If the CKF has no facts on a topic the task requires, CDR cannot surface them. CDR finds the best available novel material; it cannot conjure material that does not exist.

**Model capability limits.** CDR ensures the model receives the best possible inputs. It cannot ensure the model uses them well. A model that cannot reason about complex material receives that material correctly via CDR; producing good output from it is still the model's responsibility.

**Single-window tasks.** CDR provides no benefit on single-window generation. All CDR scores equal relevance scores when the Coverage Set is empty. The benefit is purely multi-window.

These limits are honest and expected. CDR solves the input-staleness problem completely. It does not solve problems that are not caused by input staleness.

---

## 11. References

- CRP-SPEC-003 — Context Envelope & Packing (amended by this document)
- CRP-SPEC-004 — Window Continuation & DAG (Residual Task Anchor amendment)
- CRP-SPEC-009 — Contextual Knowledge Fabric (Coverage Set hook)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

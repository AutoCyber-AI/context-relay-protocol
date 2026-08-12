# CRP-SPEC-003: Context Envelope & Packing Specification

**Document:** CRP-SPEC-003  
**Title:** Context Relay Protocol (CRP) — Context Envelope Construction & Packing Algorithm  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Repository:** https://github.com/crprotocol/spec  
**Date:** 2026-05-24  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-009 (CKF)

---

## Abstract

This document specifies the Context Envelope — the structured set of facts, knowledge fragments, and instructions assembled by the CRP gateway for injection into a large language model request. It defines the 3-phase packing algorithm (Select → Rank → Pack), the quality tier classification system, the saturation computation, the token budget model, and the conditional dispatch mechanism via ETag caching. The Context Envelope is the core mechanism by which CRP ensures that AI responses are grounded in verified, relevant, optimally-packed context rather than parametric memory.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Terminology](#2-terminology)
3. [Envelope Structure](#3-envelope-structure)
4. [The 3-Phase Packing Algorithm](#4-the-3-phase-packing-algorithm)
5. [Phase 1: Select](#5-phase-1-select)
6. [Phase 2: Rank](#6-phase-2-rank)
7. [Phase 3: Pack](#7-phase-3-pack)
8. [Quality Tier Classification](#8-quality-tier-classification)
9. [Saturation Model](#9-saturation-model)
10. [Token Budget Management](#10-token-budget-management)
11. [Conditional Dispatch (ETag Caching)](#11-conditional-dispatch-etag-caching)
12. [Envelope Preview](#12-envelope-preview)
13. [Grounding Mode Integration](#13-grounding-mode-integration)
14. [Multi-Window Envelope Evolution](#14-multi-window-envelope-evolution)
15. [Header Outputs](#15-header-outputs)
16. [Security Considerations](#16-security-considerations)
17. [Privacy Considerations](#17-privacy-considerations)
18. [References](#18-references)

---

## 1. Introduction

### 1.1 The Context Quality Problem

Large language models produce outputs whose accuracy is directly determined by the quality of context they receive. Research consistently demonstrates that models perform worse with larger context windows filled indiscriminately than with smaller, carefully curated context. The "lost in the middle" problem — where models fail to attend to information positioned in the middle of long contexts — persists across all frontier models as of 2026, with 11 out of 13 LLMs tested dropping below 50% of baseline scores at 32K tokens when surface-level pattern matching is removed.

The Context Envelope addresses this by treating context construction as a first-class engineering discipline: facts are selected for relevance, ranked by importance, and packed to maximise information density within a defined token budget — before the LLM ever sees them.

### 1.2 Scope

This document covers:
- The structure of a Context Envelope
- The 3-phase algorithm that constructs it
- The quality classification system for the result
- The caching mechanism that avoids redundant reconstruction
- The relationship between the envelope and CRP response headers

This document does NOT cover:
- The CKF graph structure from which facts are retrieved (see CRP-SPEC-009)
- The DPE analysis that runs after the LLM response (see CRP-SPEC-005)
- The dispatch strategies that consume the envelope (see CRP-SPEC-008)

---

## 2. Terminology

**Fact:** A discrete unit of knowledge stored in the CKF. A fact has: content (text), source_id (origin document reference), embedding (vector representation), relevance_score (computed per-query), importance_weight (intrinsic to the fact), and timestamp (ingestion time).

**Context Envelope:** The ordered collection of facts assembled for a single LLM call, together with metadata (quality tier, saturation, token count, ETag hash).

**Token Budget:** The maximum number of tokens available for the Context Envelope within the LLM's context window, after reserving space for the system prompt, user query, and expected response length.

**Saturation:** The ratio of token budget consumed by the envelope (0.0 – 1.0).

**Quality Tier:** The classification (S, A, B, C, D) reflecting the completeness and relevance of the assembled envelope.

**ETag:** A SHA-256 hash of the CKF fact-set state used to construct the envelope. Enables conditional dispatch.

---

## 3. Envelope Structure

A Context Envelope is a structured object containing the following fields:

```
ContextEnvelope {
  session_id:          string       // CRP session identifier
  window_number:       integer      // Position in continuation chain
  facts:               Fact[]       // Ordered list of selected facts
  total_facts_available: integer    // Candidate facts before filtering
  total_facts_included:  integer    // Facts in final envelope
  token_count:         integer      // Total tokens consumed
  token_budget:        integer      // Maximum tokens available
  saturation:          float        // token_count / token_budget
  quality_tier:        enum         // S | A | B | C | D
  etag:                string       // SHA-256 hash of fact-set
  strategy:            string       // Dispatch strategy selected
  grounding_mode:      string       // context-strict | context-preferred | open
  created_at:          ISO 8601     // Envelope creation timestamp
  ckf_communities:     string[]     // Leiden community labels accessed
  memory_tier_hit:     integer      // Highest memory tier accessed (0-3)
}
```

Each `Fact` in the `facts` array contains:

```
Fact {
  fact_id:             string       // Unique identifier
  content:             string       // The fact text
  source_id:           string       // Origin document / source reference
  relevance_score:     float        // 0.0 – 1.0, computed per-query
  importance_weight:   float        // 0.0 – 1.0, intrinsic to fact
  composite_score:     float        // Combined ranking score
  token_count:         integer      // Tokens consumed by this fact
  position:            integer      // Position in envelope (1-indexed)
  community:           string       // CKF Leiden community label
  ingested_at:         ISO 8601     // When fact was added to CKF
}
```

---

## 4. The 3-Phase Packing Algorithm

The packing algorithm operates in three sequential phases. Each phase narrows the candidate set and optimises the output. The algorithm is deterministic given the same input query and CKF state — producing the same envelope hash (ETag) and enabling conditional dispatch.

```
                    ┌─────────────────────────┐
                    │     User Query           │
                    │     CKF State            │
                    │     Token Budget         │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   PHASE 1: SELECT        │
                    │   Retrieval from CKF     │
                    │   Candidate generation   │
                    │   Output: N candidates   │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   PHASE 2: RANK          │
                    │   Relevance scoring      │
                    │   Importance weighting   │
                    │   Deduplication          │
                    │   Output: Ordered list   │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │   PHASE 3: PACK          │
                    │   Token budget fitting   │
                    │   Position optimisation  │
                    │   Quality assessment     │
                    │   Output: Envelope       │
                    └─────────────────────────┘
```

---

## 5. Phase 1: Select

### 5.1 Purpose

Phase 1 generates the candidate fact set from the CKF. It casts a wide net — retrieving more facts than will ultimately fit in the envelope, ensuring comprehensive coverage before ranking narrows the set.

### 5.2 Retrieval Process

**Step 1.1 — Query decomposition:** The user query is decomposed into constituent sub-queries when it contains multiple distinct information needs. A query "Compare the EU AI Act and GDPR approaches to automated decision-making" decomposes into: ["EU AI Act automated decision-making"], ["GDPR automated decision-making"], ["EU AI Act vs GDPR comparison"].

**Step 1.2 — Vector retrieval:** Each sub-query is embedded using the same embedding model as the CKF index. The HNSW index (see CRP-SPEC-009) retrieves the top-K nearest neighbours for each sub-query embedding. Default K = 50 per sub-query.

**Step 1.3 — Community expansion:** For each retrieved fact, the Leiden community label is checked. If a community is partially represented (fewer than 3 facts from a community that has 10+ facts within retrieval distance), the retrieval expands to include additional facts from that community. This prevents the "island" problem where semantically related facts are split across communities and only partially retrieved.

**Step 1.4 — Memory tier cascade:** Retrieval cascades through the memory hierarchy:
- Tier 0 (Active): Facts from the current context window — already present, no retrieval needed
- Tier 1 (Hot): Facts from the session cache — prior windows in this session
- Tier 2 (Warm): Recently accessed CKF subgraphs
- Tier 3 (Cold): Full CKF graph HNSW search

The highest tier accessed is recorded as `memory_tier_hit`.

**Step 1.5 — Candidate set output:** The union of all retrieved facts, deduplicated by `fact_id`, forms the candidate set. Typically 100–500 candidate facts for a complex query.

### 5.3 CKF Cache Check

Before executing Phase 1, the gateway checks whether the client sent `CRP-Context-If-Match`. If the presented ETag matches the current CKF state hash AND the query decomposition is identical to the previous call, the gateway MAY skip Phase 1 and reuse the prior candidate set. See Section 11.

---

## 6. Phase 2: Rank

### 6.1 Purpose

Phase 2 scores and orders the candidate facts, producing a ranked list where position 1 is the most valuable fact for the current query.

### 6.2 Scoring Model

Each candidate fact receives a composite score:

```
composite_score = (relevance_score × relevance_weight) +
                  (importance_weight × importance_factor) +
                  (freshness_score × freshness_weight) +
                  (diversity_bonus × diversity_weight)
```

**Default weights (configurable per CRP gateway deployment):**

| Component | Default Weight | Description |
|-----------|---------------|-------------|
| `relevance_weight` | 0.50 | Cosine similarity between query embedding and fact embedding |
| `importance_factor` | 0.25 | Intrinsic importance of the fact (source authority, citation count, manual annotation) |
| `freshness_weight` | 0.15 | Recency score — newer facts scored higher for time-sensitive queries |
| `diversity_weight` | 0.10 | Bonus for facts from underrepresented communities, preventing single-source dominance |

### 6.3 Relevance Score Computation

```
relevance_score = cosine_similarity(query_embedding, fact_embedding)
```

For decomposed queries, the relevance score is the maximum cosine similarity across all sub-query embeddings:

```
relevance_score = max(cosine_similarity(sub_query_i, fact_embedding) for i in sub_queries)
```

### 6.4 Freshness Score Computation

```
age_days = (current_time - fact.ingested_at).total_days()

freshness_score = max(0.0, 1.0 - (age_days / freshness_horizon))
```

Default `freshness_horizon` = 365 days. Facts older than the horizon receive freshness_score = 0.0 (but are NOT excluded — importance and relevance may still justify inclusion).

For queries containing temporal indicators ("current", "latest", "2026", "this year"), `freshness_horizon` is reduced to 90 days and `freshness_weight` is increased to 0.25 (with `relevance_weight` reduced to 0.40).

### 6.5 Diversity Bonus Computation

The diversity bonus prevents the envelope from being dominated by a single CKF community:

```
community_count = count of facts from this fact's community already selected
community_total = total candidate facts available from this community

if community_count / community_total > 0.40:
    diversity_bonus = 0.0  // community already well-represented
else:
    diversity_bonus = 1.0 - (community_count / community_total)
```

### 6.6 Deduplication

After scoring, semantically duplicate facts are detected using embedding similarity:

```
if cosine_similarity(fact_a.embedding, fact_b.embedding) > 0.95:
    retain the fact with higher composite_score
    discard the other
```

### 6.7 Output

Phase 2 outputs an ordered list of candidate facts, highest composite_score first, with duplicates removed.

---

## 7. Phase 3: Pack

### 7.1 Purpose

Phase 3 fits the ranked facts into the available token budget, determines the ordering within the envelope, and computes the quality tier.

### 7.2 Token Budget Calculation

```
token_budget = model_context_window
             - system_prompt_tokens
             - user_query_tokens
             - expected_response_tokens
             - safety_margin_tokens
```

**Default values:**

| Parameter | Default | Notes |
|-----------|---------|-------|
| `system_prompt_tokens` | Measured per-call | Includes grounding instruction |
| `expected_response_tokens` | 2048 | Configurable via `max_tokens` |
| `safety_margin_tokens` | 512 | Buffer for tokenizer estimation variance |

The remaining tokens form the `token_budget` for the envelope.

### 7.3 Greedy Packing

Facts are inserted in rank order until the token budget is consumed:

```
envelope = []
tokens_used = 0

for fact in ranked_facts:
    if tokens_used + fact.token_count <= token_budget:
        envelope.append(fact)
        tokens_used += fact.token_count
    else:
        // Try next fact (smaller facts may still fit)
        continue
```

This greedy approach maximises the composite_score of included facts within the token budget. Because facts vary in size, smaller high-value facts may be included even after a larger fact is skipped.

### 7.4 Position Optimisation (Anti-"Lost in the Middle")

After greedy packing, facts are reordered within the envelope to mitigate the "lost in the middle" attention degradation:

**Strategy: Primacy-Recency Sandwich**

```
critical_facts = facts with composite_score >= 0.80
important_facts = facts with 0.50 <= composite_score < 0.80
supporting_facts = facts with composite_score < 0.50

final_order = [
    critical_facts[0],         // Position 1: highest-value fact (primacy)
    critical_facts[-1],        // Position 2: second-highest (near primacy)
    supporting_facts,          // Middle positions: supporting context
    important_facts,           // Later positions: important but not critical
    critical_facts[1:-1],      // Final positions: remaining critical (recency)
]
```

This ensures the most important facts occupy positions with the strongest attention (beginning and end of context window), while supporting facts fill the middle where attention is weakest.

### 7.5 ETag Computation

After packing, the envelope ETag is computed:

```
fact_ids_sorted = sorted([f.fact_id for f in envelope])
etag_input = "|".join(fact_ids_sorted) + "|" + str(len(envelope))
etag = "sha256:" + SHA256(etag_input).hexdigest()
```

The ETag is deterministic: the same set of facts (regardless of order) produces the same ETag. This enables conditional dispatch — if the CKF hasn't changed and the query decomposition is identical, the ETag will match.

---

## 8. Quality Tier Classification

### 8.1 Classification Algorithm

The quality tier is computed from three signals:

```
coverage_score = total_facts_included / total_facts_available
saturation = tokens_used / token_budget
relevance_mean = mean([f.relevance_score for f in envelope])

quality_score = (coverage_score × 0.35) +
                (saturation × 0.30) +
                (relevance_mean × 0.35)
```

### 8.2 Tier Thresholds

| Tier | Quality Score | Saturation Range | Meaning |
|------|-------------|------------------|---------|
| `S` | ≥ 0.95 | ≥ 0.99 | Superior — all critical facts included, optimal relevance |
| `A` | ≥ 0.85 | ≥ 0.95 | High — comprehensive coverage with minor gaps |
| `B` | ≥ 0.70 | ≥ 0.85 | Adequate — majority of relevant facts included |
| `C` | ≥ 0.50 | ≥ 0.70 | Marginal — significant gaps in relevant coverage |
| `D` | < 0.50 | < 0.70 | Deficient — critical facts missing or insufficient context |

### 8.3 Tier Override Rules

The following conditions override the computed tier downward:

| Condition | Maximum Tier |
|-----------|-------------|
| Any critical fact (importance_weight ≥ 0.90) excluded due to budget | B |
| Coverage score < 0.30 | D |
| Zero facts from the primary Leiden community | C |
| Freshness check failed (query is time-sensitive but newest fact > 90 days) | C |

### 8.4 Client Quality Gating

If the client set `CRP-Accept-Quality: S, A` and the computed tier is B or lower, the gateway MUST:

1. Attempt strategy upgrade (if `upgrade-on-risk reflexive` is in Safety Policy)
2. If upgrade fails to improve tier: return HTTP 503 with `CRP-Context-Quality-Tier: B` indicating the best achievable tier
3. The 503 body MUST include a JSON object explaining the quality gap

---

## 9. Saturation Model

### 9.1 Definition

Saturation measures how fully the token budget was utilised:

```
saturation = tokens_used / token_budget
```

### 9.2 Saturation Semantics

| Saturation | Interpretation |
|-----------|---------------|
| 0.99 – 1.00 | Fully saturated — envelope used maximum available context |
| 0.95 – 0.98 | Near-saturated — minor space remaining |
| 0.85 – 0.94 | Well-packed — good utilisation with headroom |
| 0.70 – 0.84 | Moderate — significant unused budget (may indicate limited CKF coverage) |
| < 0.70 | Sparse — CKF has limited relevant content for this query |

### 9.3 Saturation-Driven Behaviour

When saturation is **high** (≥ 0.95):
- Gateway SHOULD set `CRP-Context-Cache: reuse-ckf` to avoid re-packing on continuation windows
- Gateway SHOULD consider dispatching a continuation window if the query requires more context than a single window can hold

When saturation is **low** (< 0.70):
- Quality tier is capped at C (see §8.3)
- If `CRP-LLM-Grounding-Mode: context-strict` is set, the gateway SHOULD warn the client that strict grounding may produce incomplete answers
- Gateway SHOULD emit `CRP-Context-Cache-Status: PARTIAL; reason=limited-ckf-coverage`

---

## 10. Token Budget Management

### 10.1 Multi-Model Token Counting

Different LLM providers use different tokenizers. The CRP gateway MUST:
- Detect the target provider from the dispatch routing configuration
- Use the correct tokenizer for the target model (tiktoken for OpenAI, sentencepiece for others)
- Count tokens using the target model's tokenizer, not a generic estimate
- Include a safety margin (default: 512 tokens) to account for tokenizer estimation variance

### 10.2 Budget Reporting

The token budget and usage are reported via response headers:

```
CRP-Context-Tokens-Used: 105816
CRP-Context-Saturation: 0.994
CRP-Context-Facts-Used: 47/312
```

### 10.3 Budget Pressure Signals

When the token budget is under pressure (saturation ≥ 0.98 and additional relevant facts remain unpacked), the gateway SHOULD:

1. Set `CRP-Context-Continuation-Id` to signal that a continuation window is available
2. Record the unpacked but relevant facts as "deferred" for the next window
3. Emit `CRP-Context-Window: 1/5` to indicate the continuation chain has capacity

---

## 11. Conditional Dispatch (ETag Caching)

### 11.1 Purpose

Conditional dispatch allows the gateway to skip envelope reconstruction when the underlying knowledge hasn't changed. This is the AI equivalent of HTTP conditional GET with ETags.

### 11.2 Flow

```
Client                          Gateway                         CKF
  │                                │                              │
  │── GET /dispatch ──────────────►│                              │
  │   CRP-Context-If-Match: sha256:abc...                        │
  │                                │                              │
  │                                │── Check ETag ───────────────►│
  │                                │◄── Match / No Match ─────────│
  │                                │                              │
  │   [If Match]                   │                              │
  │◄── 304 Not Modified ──────────│                              │
  │    CRP-Context-ETag: sha256:abc...                           │
  │    CRP-Context-Cache-Status: HIT                             │
  │                                │                              │
  │   [If No Match]                │                              │
  │                                │── Run 3-Phase Pack ─────────►│
  │◄── 200 OK ────────────────────│                              │
  │    CRP-Context-ETag: sha256:NEW...                           │
  │    CRP-Context-Cache-Status: MISS; reason=facts-updated      │
```

### 11.3 ETag Validity

An ETag remains valid as long as:
- No new facts have been ingested into the relevant CKF communities
- No facts have been deleted or modified
- The CKF community structure has not been recomputed (Leiden reclustering)

ETag validity is checked by comparing the presented hash against the current `CKF_state_hash` — a rolling hash of all fact IDs and their modification timestamps within the relevant communities.

### 11.4 Interaction with Cache-Control

| Client sends | ETag matches? | Behaviour |
|-------------|---------------|-----------|
| `CRP-Context-If-Match` only | Yes | 304 — skip reconstruction |
| `CRP-Context-If-Match` only | No | Full reconstruction, new ETag |
| `CRP-Context-Cache: no-cache` + `If-Match` | N/A | `no-cache` overrides — full reconstruction regardless |
| `CRP-Context-Cache: reuse-ckf` | N/A | Read CKF but do not re-ingest sources |
| `CRP-Context-Cache: only-if-ckf` | N/A | Return 424 if CKF has no relevant facts |

---

## 12. Envelope Preview

### 12.1 Purpose

Before full dispatch, the gateway generates an Envelope Preview — a lightweight assessment of what the envelope will contain, without running the LLM call. This is exposed in headers on the full response and also available as a standalone API call for cost estimation.

### 12.2 Preview Fields

```
EnvelopePreview {
  facts_available:     integer      // Total candidate facts
  facts_included:      integer      // Facts that fit in budget
  estimated_tokens:    integer      // Estimated envelope tokens
  quality_tier:        enum         // Predicted tier
  saturation:          float        // Predicted saturation
  etag:                string       // CKF fact-set hash
  communities:         string[]     // CKF communities accessed
  memory_tier_hit:     integer      // Highest tier accessed
}
```

### 12.3 Header Mapping

Every preview field maps to a response header:

| Preview Field | Response Header |
|--------------|----------------|
| `facts_available` / `facts_included` | `CRP-Context-Facts-Used: 47/312` |
| `estimated_tokens` | `CRP-Context-Tokens-Used: 105816` |
| `quality_tier` | `CRP-Context-Quality-Tier: A` |
| `saturation` | `CRP-Context-Saturation: 0.994` |
| `etag` | `CRP-Context-ETag: sha256:...` |
| `communities[0]` | `CRP-Memory-CKF-Community: eu-ai-act-compliance` |
| `memory_tier_hit` | `CRP-Memory-Tier-Hit: 2` |

---

## 13. Grounding Mode Integration

### 13.1 How Grounding Mode Affects Packing

The `CRP-LLM-Grounding-Mode` header (see CRP-SPEC-002 §11.2) affects the system prompt injected alongside the envelope:

| Mode | System Prompt Addition | Packing Impact |
|------|----------------------|----------------|
| `context-strict` | "Answer using ONLY the provided context. If the context does not contain sufficient information, state that clearly." | `importance_factor` increased to 0.35 (from 0.25); gateway caps quality tier at C if saturation < 0.80 |
| `context-preferred` | "Prefer the provided context when answering. If you use general knowledge, indicate this clearly." | Default weights apply |
| `open` | No grounding instruction | `relevance_weight` reduced to 0.35; `importance_factor` reduced to 0.15 |

### 13.2 DPE Interaction

The grounding mode is passed to the DPE (CRP-SPEC-005) to calibrate attribution analysis. In `context-strict` mode, any `PARAMETRIC` attribution is treated as a DPE finding (raising the hallucination risk score). In `open` mode, `PARAMETRIC` attribution is expected and does not raise the score.

---

## 14. Multi-Window Envelope Evolution

### 14.1 Context Enlargement Across Windows

When a single window cannot hold sufficient context, the gateway initiates a continuation chain (see CRP-SPEC-004 for the full Window DAG specification). The envelope evolves across windows as follows:

**Window 1:** Full 3-phase packing from CKF. Primary facts selected. Continuation-Id issued.

**Window 2+:** Client presents `CRP-Context-Continuation-Id`. Gateway:
1. Loads the Window 1 envelope metadata (which facts were included)
2. Retrieves ADDITIONAL facts not included in Window 1 (deferred facts)
3. Includes a condensed summary of Window 1's response as a fact in Window 2's envelope
4. Packs Window 2's envelope with the deferred facts + summary + any new query-specific facts

### 14.2 Cross-Window Fact Deduplication

Facts included in Window N MUST NOT be re-included in Window N+1 unless their content was updated in the CKF between windows. The gateway maintains a `facts_seen` set per session to prevent duplication.

### 14.3 Envelope State in Session Token

The `CRP-Set-Session` token carries `QualityHistory` — the quality tier of each window in the session. This enables the client and the gateway to track quality degradation across a continuation chain:

```
CRP-Set-Session: ...; QualityHistory=A,A,B
```

If quality is degrading (A → B → C), the gateway SHOULD:
- Recommend switching to `dispatch_hierarchical()` (aggregation strategy)
- Emit a warning in the audit trail
- Consider that the CKF may lack depth for this knowledge domain

---

## 15. Header Outputs

The following CRP response headers are populated by the envelope packing algorithm:

| Header | Source |
|--------|--------|
| `CRP-Context-Quality-Tier` | §8 Quality Tier Classification |
| `CRP-Context-Saturation` | §9 Saturation Model |
| `CRP-Context-Facts-Used` | Phase 3 output (included/available) |
| `CRP-Context-Tokens-Used` | Phase 3 token counting |
| `CRP-Context-ETag` | §7.5 ETag Computation |
| `CRP-Context-Cache-Status` | §11 Conditional Dispatch |
| `CRP-Context-Strategy` | Strategy selection |
| `CRP-Context-Window` | Window position in continuation chain |
| `CRP-Context-Continuation-Id` | §14 Multi-Window continuation |
| `CRP-Memory-Tier-Hit` | Phase 1 memory tier cascade |
| `CRP-Memory-CKF-Hits` | Phase 1 CKF retrieval count |
| `CRP-Memory-CKF-Community` | Phase 1 community expansion |
| `CRP-Memory-Knowledge-Age` | Freshness of newest included fact |

---

## 16. Security Considerations

### 16.1 Envelope Content Isolation

The Context Envelope contains customer data (facts from the CKF). This data:
- MUST be isolated per tenant in multi-tenant gateway deployments
- MUST NOT be logged in full in gateway access logs (only `fact_id` references logged)
- MUST NOT be included in CRP response headers (headers carry metadata, not content)
- MUST be subject to `CRP-Context-Cache: no-store` when containing PII

### 16.2 ETag as Information Disclosure

The ETag hash reveals whether the CKF state has changed between calls. In adversarial settings, an attacker observing ETag values could infer when a customer's knowledge base was updated. Mitigation: ETag values SHOULD include a per-session salt to prevent cross-session correlation.

### 16.3 Fact Source Leakage

`CRP-Memory-CKF-Community` reveals the knowledge domain of the query. In settings where the knowledge domain itself is sensitive, this header SHOULD be suppressed using gateway configuration.

---

## 17. Privacy Considerations

### 17.1 PII in the Envelope

The CKF may contain facts derived from documents containing personal data. The packing algorithm does not filter PII — it packs by relevance and importance regardless of content type. PII detection is handled by the DPE (CRP-SPEC-005) after the LLM response, not during packing.

If `CRP-Context-Cache: no-store` is set, facts from this session MUST NOT be persisted to the CKF, preventing PII from entering the long-term knowledge graph.

### 17.2 Right to Erasure

When a customer exercises GDPR Art. 17 (right to erasure), all facts derived from the deleted source documents MUST be removed from the CKF. The packing algorithm MUST NOT retrieve facts marked for deletion, even if they remain in the HNSW index pending physical deletion.

---

## 18. References

### Normative References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-009 — Contextual Knowledge Fabric

### Informative References

- "Lost in the Middle: How Language Models Use Long Contexts" — Liu et al., 2023
- "NoLiMa: Long-context Evaluation Beyond Literal Matching" — LMU Munich / Adobe, ICML 2025
- "Chroma Research: Effective Context Window Evaluation" — 2025

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*

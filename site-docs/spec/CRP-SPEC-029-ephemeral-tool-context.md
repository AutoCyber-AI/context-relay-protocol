# CRP-SPEC-029: Ephemeral & Tool Context (Tier E)

**Document:** CRP-SPEC-029  
**Title:** Context Relay Protocol (CRP) - Ephemeral & Tool Context: Managing Tool Outputs, Working Memory, and Instant-Decay Context  
**Version:** 1.0.0  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Completes:** CRP-SPEC-028 (Tier E)  
**Prerequisites:** CRP-SPEC-005, CRP-SPEC-008, CRP-SPEC-028

---

## Abstract

This document completes the Multi-Horizon Context Model (SPEC-028) by fully specifying Tier E - ephemeral context, dominated by tool-call outputs. Tool outputs are a context type unlike any other CRP handles: high-volume (a database query can return thousands of rows), structured (JSON, tables, not prose facts), instantly stale (a "current status" result is worthless minutes later), provenance-critical (the model's claims must be attributable to the tool result, not hallucinated), and token-explosive (raw output can exceed the entire context window). They also have bimodal persistence: most tool output is intermediate noise that should evaporate immediately, but some is a durable result the user explicitly cares about ("save that calculation").

CRP currently has no model for this. Tool outputs either get dumped raw into the prompt (blowing the window and degrading attention) or discarded entirely (losing context the next turn needs). This document specifies the Scratch Buffer - a structured, freshness-gated, reference-addressable store for ephemeral context - along with the summarisation, provenance, and promotion mechanisms that make tool output usable without poisoning the context.

---

## 1. Why Tool Output Breaks Every Existing Context Model

### 1.1 The Five Properties That Make Tool Output Different

| Property | CKF fact | Conversational turn | Tool output |
|----------|---------|--------------------|-------------| 
| Volume | small (1–2K tokens) | small (one turn) | **huge (unbounded)** |
| Structure | prose | prose | **structured (JSON/table)** |
| Staleness | slow (months) | session | **instant (seconds–minutes)** |
| Persistence | permanent | session | **bimodal (mostly evaporate)** |
| Provenance role | grounding source | dialogue | **critical grounding source** |

No existing CRP tier handles these. The CKF assumes small, prose, slow-decay facts. The Turn Log assumes prose dialogue. Tool output is none of these.

### 1.2 The Two Failure Modes Today

**Dump-everything:** Raw tool output is concatenated into the prompt. A SQL query returning 5,000 rows consumes the entire window, evicts everything else, and degrades the model's attention across the noise. The model drowns.

**Discard-everything:** Tool output is used once and dropped. The next turn - "now filter those results to last month" - has nothing to work with. The model fabricates or fails.

Both are wrong. Tool output needs structured, selective, freshness-aware management.

---

## 2. The Scratch Buffer (Tier E Store)

### 2.1 Structure

```
ScratchBuffer {
  session_id:    string
  entries: [
    {
      scratch_id:     string          // addressable ID, e.g. "scratch_sql_001"
      tool_name:      string          // which tool produced this
      tool_call_args: map             // the inputs (for provenance)
      raw_output:     string          // full output, stored but rarely injected
      raw_token_count: integer
      summary:        string          // compressed representation (§3)
      structured:     object | null   // parsed structure if applicable
      created_at:     ISO 8601
      freshness_ttl:  ISO 8601 dur     // how long this stays valid (§4)
      persistence:    enum            // EPHEMERAL | PINNED (§5)
      referenced_by:  integer[]       // turn_ids that used this
      provenance_hash: string         // hash of raw_output for attribution (§6)
    }
  ]
}
```

### 2.2 What Goes In the Buffer vs the Envelope

The critical distinction: the Scratch Buffer **stores** the full raw output, but the **envelope** receives only the summary (§3) unless the raw output is explicitly referenced and fresh. This is how a 5,000-row query result is managed: the rows live in the buffer, a compact summary ("Query returned 5,000 rows; columns: id, name, created_at; date range: 2024-01 to 2026-05; sample: [first 3 rows]") goes into the envelope. If the user then asks something requiring specific rows, those rows are retrieved from the buffer on demand.

---

## 3. Tool Output Summarisation

### 3.1 Structure-Aware Summarisation

Tool output is summarised according to its structure, not as prose:

| Output type | Summarisation strategy |
|------------|----------------------|
| Tabular (rows) | Schema + row count + value ranges + N sample rows |
| JSON object | Key structure + value types + key values extracted |
| List | Count + type + first/last N items |
| Scalar | The value directly (no summarisation needed) |
| Long text | Extractive summary (first sentence + key entities) |
| Error | Full error message (errors are always small and critical) |

### 3.2 The Summarisation Is Deterministic, Not Generative

Tool output summarisation MUST be deterministic (schema extraction, counting, sampling) - NOT a model call. This keeps it fast (sub-millisecond), free, and reliable. Using an LLM to summarise tool output would add latency, cost, and a hallucination surface to what should be a mechanical operation.

```python
def summarise_tool_output(raw, tool_name):
    parsed = try_parse(raw)  # JSON, CSV, etc.
    if is_tabular(parsed):
        return f"{tool_name} returned {len(parsed)} rows. " \
               f"Columns: {column_names(parsed)}. " \
               f"Ranges: {value_ranges(parsed)}. " \
               f"Sample: {parsed[:3]}"
    elif is_json_object(parsed):
        return f"{tool_name} returned object with keys {list(parsed.keys())}. " \
               f"Key values: {extract_scalar_values(parsed)}"
    elif is_scalar(parsed):
        return f"{tool_name} returned: {parsed}"
    # ... etc
```

### 3.3 Summary Token Budget

Each scratch summary has a hard token cap (default: 256 tokens). A summary exceeding the cap is further compressed (fewer sample rows, tighter ranges). This guarantees that no tool output, however large, can consume more than its budgeted share of the envelope.

---

## 4. Freshness Gating

### 4.1 Tool Output Stales Fast

Unlike CKF facts (TTL in months), tool output stales in seconds to minutes. A "current server load" reading is worthless 60 seconds later. A "today's exchange rate" is stale tomorrow. The Scratch Buffer assigns each entry a freshness TTL based on the tool's volatility class:

| Volatility class | Example tools | Default freshness TTL |
|-----------------|--------------|----------------------|
| `REALTIME` | live metrics, current status, stock price | 30 seconds |
| `VOLATILE` | search results, recent data queries | 5 minutes |
| `STABLE` | database records, document fetches | 1 hour |
| `STATIC` | computed constants, config reads | session |

The tool registry (SPEC-008 §6) declares each tool's volatility class.

### 4.2 Stale Output Is Not Silently Used

When an envelope would include a scratch entry past its freshness TTL, the assembler MUST NOT inject the stale value as if current. Instead it either:

1. **Re-invokes the tool** (if the dispatch strategy permits and the same call would be made) to refresh, OR
2. **Injects with a staleness warning:** "NOTE: This result is from 4 minutes ago and may be outdated: [summary]", OR
3. **Excludes it** and flags that fresh data is needed

The choice is governed by Safety Policy (§8). The default for REALTIME class is re-invoke; for others, warn.

### 4.3 Freshness Header

```
CRP-Context-Scratch-Freshness: fresh
CRP-Context-Scratch-Freshness: stale; age=240s; class=VOLATILE
```

---

## 5. Bimodal Persistence: Evaporate vs Pin

### 5.1 Most Tool Output Should Evaporate

Intermediate tool calls - a lookup to resolve an ID, an API call whose result is immediately consumed - are noise after their turn. They should evaporate to keep the buffer clean and the context uncluttered. The default persistence is `EPHEMERAL`: an entry is eligible for eviction once no longer referenced and past its freshness TTL.

### 5.2 Some Tool Output Must Persist

When the user explicitly cares about a result - "save that calculation," "remember this query," "use that value going forward" - it must persist beyond its natural freshness window. This is `PINNED` persistence. A pinned entry:
- Is not evicted regardless of freshness TTL
- Is promoted to a named reference the user can recall ("the calculation," "the budget figure")
- May be promoted into the CKF (Tier P) as a durable fact if it represents established knowledge

### 5.3 Pin Detection

Pinning is triggered by:
- Explicit user instruction ("save," "remember," "keep")
- The result being named and referenced across multiple turns (auto-pin after 2 references)
- Safety Policy requiring tool-output retention for audit (compliance contexts)

### 5.4 Promotion to CKF

A pinned scratch entry representing durable knowledge (not a volatile reading) can be promoted into the CKF:

```
"The Q3 revenue figure is $4.2M" (computed via tool, pinned, referenced 3×)
    → promoted to CKF as a fact with provenance: tool-derived
```

Promotion is the bridge from Tier E to Tier P. It is how a session's computed results become durable knowledge. Volatile readings (current status, live metrics) are never promoted - they have no durable truth value.

---

## 6. Provenance: Tool Output as a Grounding Source

### 6.1 The Attribution Requirement

When the model makes a claim based on tool output, the DPE (SPEC-005) MUST be able to attribute that claim to the specific tool result - not classify it as parametric or fabricated. Tool output is a first-class grounding source, equal to CKF facts.

### 6.2 Tool Output in DPE Attribution

SPEC-005 Stage 2 (Attribution Analysis) is extended: a claim can be attributed as:

| Attribution | Meaning |
|------------|---------|
| `CONTEXT_GROUNDED` | supported by a CKF fact (existing) |
| `TOOL_GROUNDED` | supported by a Scratch Buffer entry (new) |
| `CONVERSATION_GROUNDED` | supported by a prior turn (new) |
| `PARAMETRIC` | from model knowledge (existing) |
| `UNVERIFIABLE` | unsupported (existing) |

A claim like "the query returned 5,000 records" is checked against the scratch entry's structured data. If the entry says 5,000 rows, the claim is `TOOL_GROUNDED` and verified. If the model says 8,000, it is a distortion - caught by the DPE against the tool output exactly as it would be against a CKF fact.

### 6.3 Provenance Hash

Each scratch entry carries a `provenance_hash` of its raw output. When a claim is attributed to a scratch entry, the hash is recorded in the audit trail. An auditor can later verify that the model's claim matched the actual tool output at the time - tool-grounded provenance is as tamper-evident as the rest of CRP's chain (SPEC-011).

### 6.4 The Hallucination Guard for Tools

A specific, valuable consequence: the model cannot fabricate tool results. If the model claims "the API returned status 200" but the scratch entry shows status 500, the DPE flags a `TOOL_GROUNDED` distortion. The model is held to what the tool actually returned. This closes a major hallucination surface in agentic systems where models confabulate tool outcomes.

---

## 7. Reference Resolution for Tool Output

Tier E integrates with the reference resolution of SPEC-028 §4. Tool-output references are resolved against the Scratch Buffer:

```
"the query result"       → most recent tabular scratch entry
"that API response"      → most recent API-class scratch entry
"the calculation"        → most recent computation, or pinned named value
"those results"          → most recent multi-row entry
"the error"              → most recent error-class entry
```

When resolved, the referenced entry's summary (or raw output, if specifically required and fresh) is pulled into the envelope at full weight, with `TOOL_REFERENCE` intent (SPEC-028 §5.1) driving a high Tier E blend weight.

---

## 8. Safety Policy Integration

```
CRP-Safety-Policy: ...; tool-output-stale=warn; tool-output-retain=audit; tool-provenance=required
```

| Directive | Values | Meaning |
|-----------|--------|---------|
| `tool-output-stale` | `reinvoke`, `warn`, `exclude` | Behaviour when a referenced scratch entry is stale |
| `tool-output-retain` | `evaporate`, `audit`, `all` | Persistence policy: evaporate (default), audit (pin for compliance), all (never evict) |
| `tool-provenance` | `optional`, `required` | If required, claims attributable to tools MUST cite the scratch entry; uncited tool-derived claims are flagged |

In regulated contexts (`tool-output-retain=audit`), all tool outputs are pinned and written to the audit trail - necessary for EU AI Act traceability when an AI system's decision depended on a tool result.

---

## 9. Headers

### 9.1 CRP-Context-Scratch-Entries

**Direction:** RES  
**Definition:** Number of active entries in the Scratch Buffer, as `total/pinned`.

```
CRP-Context-Scratch-Entries: 7/2
```

### 9.2 CRP-Context-Scratch-Tokens-Saved

**Direction:** RES  
**Definition:** Tokens saved by injecting summaries instead of raw tool output this turn.

```
CRP-Context-Scratch-Tokens-Saved: 18400
```

### 9.3 CRP-Safety-Tool-Attribution

**Direction:** RES  
**Definition:** Count of claims attributed to tool output, as `tool-grounded/tool-distortions`.

```
CRP-Safety-Tool-Attribution: 5/0
```

A non-zero distortion count means the model misrepresented a tool result - a critical signal.

---

## 10. The Complete Three-Tier Envelope

With SPEC-028 and SPEC-029, an envelope for a turn in an agentic conversation is assembled from all three tiers:

```
Turn: "Filter those query results to last month and explain the trend"

Intent: TOOL_REFERENCE + analysis
Blend: P=0.25, C=0.25, E=0.50

Tier E (Scratch Buffer):
  - scratch_sql_001: "5000 rows, columns [id,name,created_at,amount]"
    (referenced by "those query results", fresh, TOOL_GROUNDED source)
Tier C (Turn Log):
  - Turn 4: user asked for the original query (context for "those")
  - Active thread: revenue-analysis
Tier P (CKF via CDR):
  - Fact: "month-over-month trend analysis compares..."
  - Fact: "seasonal adjustment accounts for..."

Assembled envelope: the query summary + the filtering context +
the analysis knowledge, blended, packed, governed.
Model produces: a trend explanation grounded in actual tool data,
attributable, non-fabricated.
```

This is the complete context solution: persistent knowledge, conversational history, and ephemeral tool output, unified, each under the correct retrieval policy, all governed by the DPE and provenance chain.

---

## 11. What This Does Not Cover

Streaming tool output (a tool that emits a continuous stream rather than a discrete result) is treated as a sequence of discrete scratch entries, one per chunk - full streaming semantics are deferred.

Tool output exceeding the buffer's total size budget triggers eviction of the oldest unreferenced ephemeral entries (LRU). If all entries are pinned and the budget is exceeded, the gateway signals `CRP-Context-Scratch-Full` and the operator must increase the budget or unpin entries.

---

## 12. References

- CRP-SPEC-005 - Decision Provenance Engine (attribution extension)
- CRP-SPEC-008 - Dispatch Strategy (tool registry, volatility classes)
- CRP-SPEC-011 - Audit Trail (tool provenance recording)
- CRP-SPEC-028 - Multi-Horizon Context Model (Tier E definition, reference resolution)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

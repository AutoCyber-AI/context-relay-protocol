# CRP-SPEC-039: Semantic Codebase Ingestion - CRP Scanning With CRP

**Document:** CRP-SPEC-039  
**Title:** Context Relay Protocol (CRP) - Semantic Codebase Ingestion: Using CRP's Own Knowledge Fabric to Understand Large Repositories With High Accuracy and Specificity  
**Version:** 1.0.0  
**Status:** Foundational - Scan Intelligence  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Extends:** CRP-SPEC-013 (Scan), CRP-SPEC-036 (Remediation)  
**Prerequisites:** CRP-SPEC-009, CRP-SPEC-013, CRP-SPEC-025, CRP-SPEC-036

---

## Abstract

CRP Scan (SPEC-013) and its Remediation Engine (SPEC-036) assume the codebase can be understood well enough to locate ungoverned AI calls and generate exact fixes. But neither specifies *how* - and pure pattern-matching (regex/AST grep) fails on real, large codebases: it misses calls hidden behind wrappers, factory functions, dependency injection, dynamic dispatch, and cross-file indirection. A grep for `OpenAI(` does not find a project that wraps the client in `our_llm_client()` three modules away. This document specifies how CRP Scan achieves *semantic* understanding of large repositories by **using CRP's own Contextual Knowledge Fabric to ingest the codebase as a knowledge graph** - dogfooding the protocol to power its own product. The repo is ingested into a code-aware CKF where files, functions, calls, and data flows become facts and graph edges; CDGR multi-hop retrieval (SPEC-025) then traces an AI call through wrappers and indirection to its true source and every site that needs governing. This gives Scan high accuracy (finds calls pattern-matching misses) and high specificity (the exact file, line, and call chain for each fix). CRP understands code the same way it understands any knowledge: as a semantic graph, not a flat text scan.

---

## 1. Why Pattern-Matching Fails on Real Codebases

### 1.1 The Naive Approach and Its Blind Spots

SPEC-013's detection rules (CRP001–005) match patterns like `OpenAI(`, `anthropic.`, `ChatOpenAI(`. On a toy example this works. On a real codebase it misses:

```python
# llm/client.py
def make_client():
    return OpenAI(api_key=cfg.key)        # the ONLY literal OpenAI() call

# services/support.py
from llm.client import make_client
client = make_client()                     # pattern-match sees nothing here
resp = client.chat.completions.create(...) # ← THE ungoverned call, invisible to grep

# services/billing.py
llm = get_llm("openai")                    # factory + DI - totally invisible
answer = llm.complete(prompt)              # ← also ungoverned, also invisible
```

A regex/AST scan for `OpenAI(` finds `make_client` and reports one finding in
`llm/client.py`. It misses the two *actual* ungoverned call sites in
`support.py` and `billing.py` - which is where governance must be applied.
On a large codebase, this blindness is the norm, not the exception.

### 1.2 What's Needed

Scan must understand that `make_client()` returns an OpenAI client, that
`support.py` calls it and then makes a completion, and that this completion
is the ungoverned site. That is *semantic, cross-file, multi-hop*
understanding - exactly what CRP's CKF + CDGR provide for knowledge. The
insight: treat the codebase as knowledge and ingest it with CRP itself.

---

## 2. The Codebase as a Knowledge Graph (CRP-on-CRP)

### 2.1 Ingesting Code Into a Code-Aware CKF

CRP Scan ingests the repository into a specialised CKF (SPEC-009) where the
"facts" are code entities and the graph edges are code relationships:

```
Code entity facts:
  - file:        services/support.py
  - function:    support.handle_ticket()
  - call:        client.chat.completions.create(...)  @ support.py:42
  - definition:  llm.client.make_client()
  - return_type: make_client() -> openai.OpenAI
  - import:      support.py imports make_client from llm.client

Graph edges (code relationships):
  - CALLS:        handle_ticket → make_client
  - RETURNS:      make_client → OpenAI instance
  - INVOKES_ON:   handle_ticket → .chat.completions.create on that instance
  - IMPORTS:      support.py → llm.client
  - DATA_FLOW:    cfg.key → OpenAI(api_key=)
```

This is built by combining a language-aware parser (tree-sitter / language
servers for accurate AST + symbol resolution) with CRP's embedding and graph
construction. The AST gives precise structure; CRP's CKF gives semantic
search and multi-hop traversal over that structure.

### 2.2 Why Use CRP's CKF Specifically

The CKF already does exactly what large-codebase understanding needs:
- **Embeddings** → semantically similar code (find all "LLM-calling" sites even with different syntax)
- **Graph edges** (SPEC-009) → call graphs, import graphs, data-flow
- **CDGR multi-hop** (SPEC-025) → trace a call through wrappers and indirection (the bridge-value scoring finds the *connector* functions between a definition and its true call site)
- **Communities** (Leiden) → module/subsystem clustering
- **Coverage** (SPEC-024) → scan systematically without re-examining the same code

Scan does not reimplement code intelligence - it *applies CRP's existing
knowledge intelligence to code*. This is the dogfooding: the protocol that
governs AI calls is the same protocol that understands the code containing
them.

---

## 3. Multi-Hop Detection - Tracing Calls Through Indirection

### 3.1 The CDGR Trace

To find true ungoverned call sites, Scan seeds with literal LLM-SDK
references and walks the code graph via CDGR (SPEC-025):

```
1. SEED: find literal LLM constructions (OpenAI(), anthropic.Client(), etc.)
   → make_client() in llm/client.py returns an OpenAI instance  [anchor]

2. EXPAND (CDGR graph walk): who calls make_client? what do they do with
   the return value?
   → support.py:handle_ticket calls make_client, invokes .create() on it
   → billing.py:get_llm("openai") factory → .complete() on result

3. BRIDGE-SCORE: the connector functions (make_client, get_llm) are the
   bridges between the SDK and the call sites - high bridge value (SPEC-025)

4. RESOLVE: the TRUE ungoverned call sites are support.py:42 and
   billing.py:N - NOT just the literal construction in client.py
```

The CDGR bridge-value scoring is precisely what surfaces the wrapper/factory
functions that connect an SDK import to its actual usage - the connectors a
flat scan misses. This is the same mechanism that finds connector facts in
knowledge retrieval, applied to code.

### 3.2 Data-Flow Awareness

The graph's DATA_FLOW edges let Scan determine whether a call is *already*
governed (routed through CRP) or not:

```
client = OpenAI(base_url="https://your-gateway.example/v1", ...)
   → DATA_FLOW: base_url = crp gateway → GOVERNED (no finding)

client = OpenAI(api_key=key)   # no crp base_url in the data flow
   → UNGOVERNED → finding + remediation (SPEC-036)
```

Semantic data-flow analysis distinguishes governed from ungoverned calls
accurately, even when the configuration is several assignments away from the
construction.

---

## 4. High Specificity - Exact Fix Locations

Because the code graph records precise locations, Scan produces fixes with
exact specificity (feeding SPEC-036's remediation PRs):

```
Finding: ungoverned OpenAI call
  True call site:   services/support.py:42
  Client source:    llm/client.py:8  (make_client)
  Construction:     llm/client.py:9  (OpenAI(api_key=cfg.key))
  Fix location:     llm/client.py:9  ← fix HERE governs ALL callers
  Call chain:       handle_ticket → make_client → OpenAI
  Remediation:      add base_url to the construction (one fix, all sites)
```

Critically, semantic understanding lets Scan recommend the *most efficient*
fix: governing the single `make_client` construction fixes every downstream
caller at once - something pattern-matching (which would try to fix each call
site) cannot reason about. CRP finds the *minimal set of fix locations* that
governs the *maximal set of calls*.

---

## 5. Scaling to Large Repositories

### 5.1 Incremental Ingestion

A large monorepo is ingested once into the code-CKF, then updated
incrementally per commit (only changed files re-ingested). The CKF persists
between scans (SPEC-009), so subsequent scans are fast - they query an
existing code knowledge graph rather than re-parsing the world.

### 5.2 Coverage-Driven Scanning

CDR's coverage model (SPEC-024) ensures large-repo scanning is systematic:
each module is examined, coverage is tracked, and the scan knows when it has
analysed the whole codebase versus when more remains - no missed
subsystems, no redundant re-analysis.

### 5.3 Community-Scoped Analysis

Leiden communities (SPEC-009) cluster the codebase into subsystems. Scan can
report findings per subsystem and prioritise (e.g. "the payments module has
3 ungoverned calls") - meaningful structure for a developer triaging a large
codebase, not a flat list of 200 findings.

---

## 6. The Dogfooding Narrative (Why This Matters Beyond Scan)

This specification is also CRP's strongest proof point: **CRP Scan works
because CRP works.** The same CKF + CDGR that lets CRP assemble high-quality
context for any task lets CRP Scan understand a large codebase with accuracy
pattern-matching cannot match. If CRP can ingest a sprawling monorepo and
trace an AI call through five layers of indirection to its true source, the
context-management claims are demonstrated on the hardest possible knowledge
domain - code. Scan is a live, public demonstration of the protocol's
semantic power.

This is a marketing and credibility asset: "CRP Scan uses CRP itself to
understand your codebase semantically - the same engine that governs your AI
calls reads your code." It turns the product into proof.

---

## 7. Headers / Reporting

| Field | Meaning |
|-------|---------|
| `scan.method` | `semantic` (CKF-based) vs `pattern` (fallback) |
| `scan.call_chains_traced` | Number of multi-hop call chains resolved |
| `scan.true_sites_found` | Ungoverned sites found semantically |
| `scan.pattern_only_would_miss` | How many of those a pattern scan would have missed (the value metric) |
| `scan.minimal_fix_set` | Number of fix locations that govern all findings |

`scan.pattern_only_would_miss` is the headline value metric - it quantifies
exactly how much more semantic scanning finds than regex, per scan.

---

## 8. Honest Status & Limits

The code-CKF requires a language-aware parser (tree-sitter / LSP) for
accurate AST and symbol resolution - CRP's embeddings and graph sit *on top*
of that structural layer. Without accurate parsing, the graph edges are
wrong. Supported languages are bounded by available parsers; Scan ships with
the major ones (Python, JS/TS, Java, Go) and degrades to pattern-matching for
unsupported languages, clearly flagged (`scan.method: pattern`).

Dynamic dispatch that is genuinely undecidable at static-analysis time (e.g.
a fully runtime-determined client type from external config) cannot be
resolved with certainty - Scan flags these as *possible* ungoverned sites for
human review rather than asserting them, avoiding false confidence.

Very large monorepos have a first-ingestion cost (parse + embed + graph the
whole repo). This is a one-time cost amortised by incremental updates;
subsequent scans are fast. The first scan of a huge repo is minutes, not
milliseconds - honestly stated.

Semantic scanning reduces but does not eliminate false positives/negatives.
It is substantially more accurate than pattern-matching (the
`pattern_only_would_miss` metric proves the gain) but is not perfect; findings
remain developer-reviewed proposals (SPEC-036 §9), never auto-applied.

---

## 9. References

- CRP-SPEC-009 - CKF (the code knowledge graph)
- CRP-SPEC-013 - GitHub Action / Scan (detection this powers)
- CRP-SPEC-024 - CDR (coverage-driven systematic scanning)
- CRP-SPEC-025 - CDGR (multi-hop call-chain tracing)
- CRP-SPEC-036 - Remediation Engine (consumes the exact fix locations)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

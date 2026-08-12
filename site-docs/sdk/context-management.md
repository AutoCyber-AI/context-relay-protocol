# Context Management SDK Reference

CRP solves the two hard problems every production AI system hits: **context
truncation** and **context degradation**. Instead of cramming everything into one
window and hoping, CRP gives each task its own optimised window, packs it with
the most relevant facts, and continues automatically when the model hits its
output limit.

!!! note "Progressive disclosure"
    You do not need to use these primitives directly. `client.ask()` orchestrates them automatically. This page shows how to see and control what is happening under the hood.

## What you get

| Problem | Without CRP | With CRP |
|---------|-------------|----------|
| Long tasks truncate mid-output | 8/30 sections, no conclusion | 25/30 sections, stitched conclusion |
| Context lost between calls | Each call starts from scratch | CKF carries facts across turns |
| Irrelevant context drowns the prompt | Raw text dump | Scored, ranked envelope |
| Multi-document reasoning fails | Flat chunks | Graph-walked CDGR bridging |
| No visibility into what the model saw | Black box | `a.sources` + `client.storage.overview()` |

## One-line continuation

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")

answer = client.ask(
    "Write a complete incident-response runbook",
    depth="exhaustive",
)

print(answer.text)        # full stitched output
print(answer.quality)     # S | A | B | C | D
print(answer.complete)    # True if task fully covered
print(answer.sources)     # facts that grounded the answer
```

---

## 1. Sessions and windows

A **session** is a long-running conversation. A **window** is a single turn or bounded sub-conversation within it. CRP maintains provenance, budgets, and HMAC chains per window.

```python
import crp

client = crp.SDKClient()

r1 = client.complete("What is the EU AI Act?")
r2 = client.ask("Which articles apply to high-risk systems?")

# Response metadata is available on every result
print(r1.crp.session_id)             # stable session handle
print(r1.crp.window_id)              # turn-scoped identifier
print(r1.crp.chain_valid)            # per-window HMAC chain integrity
print(r1.crp.safety_budget_remaining)

# Live session view
s = client.session()
print(s.id, s.fact_count, s.window_count)
print(s.status())                    # SessionStatus with tokens, cost, budget
```

### Visible outcomes

| What you see | Where it comes from |
|--------------|---------------------|
| `r.crp.session_id` | Stable session handle |
| `r.crp.window_id` | Turn-scoped identifier |
| `r.crp.chain_valid` | Per-window HMAC chain integrity |
| `r.crp.safety_budget_remaining` | Decrement tracked across windows |

---

## 2. Contextual Knowledge Fabric (CKF)

The CKF is CRP's semantic memory: facts extracted from ingested documents, conversations, and tool outputs, stored as a graph with similarity and structural edges.

```python
# Ingest knowledge
client.ingest("./docs/")

# Inspect the CKF
health = client.knowledge.health()
print(health)                       # CKF health snapshot

# Search what CRP knows
results = client.knowledge.search("TLS configuration")
for mf in results.facts:
    print(mf.fact.text)
    print(mf.fact.source_window_id)  # where this fact came from
    print(mf.fact.confidence)

# Pattern query on the fact graph
results = client.knowledge.query(entity_type="key_sentence")
```

### Zero-CKF mode

When no knowledge is available, CRP operates in `zero-ckf` mode. It still runs safety checks and provenance analysis, but retrieval is skipped.

!!! tip "Tip"
    Configure `context.mode: zero-ckf` in `crp.config.yaml` to force zero-CKF operation.

---

## 3. Context envelope construction

Before a prompt reaches a model, CRP builds an **envelope**: the optimal subset of context that fits the budget while maximising coverage and minimising redundancy.

### The six phases

1. **Decompose** the task into aspects.
2. **Score** facts for relevance.
3. **Rerank** using CDR coverage differentials.
4. **Pack** the selected facts into the token budget.
5. **Bookend** with system instructions.
6. **CKF-gate** the result.

### How to see it

The envelope is built inside the orchestrator. Its effects are reflected in:

* `r.crp.grounded` - whether the response was built from context.
* `a.quality` - how well the envelope covered available facts.
* `a.sources` - which source windows contributed facts.

```python
a = client.ask("How do we rotate TLS certificates?")
print(a.crp.grounded)
print(a.quality)
for src in a.sources:
    print(src.title, src.used_facts, src.relevance_score)
```

### Coverage differential retrieval (CDR)

CDR ranks facts by **novelty** relative to what the session already knows. It prevents repeating the same context every turn. The effect is visible as higher quality scores and fewer redundant sources across sequential `ask()` calls.

### Context differential graph retrieval (CDGR)

CDGR walks the CKF graph to bridge disconnected facts across documents. Source attributions in `a.sources` include facts reached via graph neighbours.

---

## 4. Continuation and stitching

When a task is too large for one model call, CRP **continues** across multiple windows and **stitches** the partial outputs into a coherent final result.

```python
# ask() with exhaustive depth triggers continuation automatically
a = client.ask("Write a full incident response runbook", depth="exhaustive")

# Inspect continuation metadata
print(a.complete)                    # whether the whole task was covered
print(a.finish_reason)               # stop | length | error
```

### Depth negotiation

`depth` controls how much compute CRP applies to a query:

| Depth | Behaviour |
|-------|-----------|
| `quick` | Short answer, low token cap |
| `standard` | Balanced coverage |
| `thorough` | Higher token cap, deeper envelope |
| `exhaustive` | Continuation loop with gap analysis and stitching |

```python
client.ask("Summarise this article", depth="quick")
client.ask("Write a deployment guide", depth="thorough")
client.ask("Generate a full runbook", depth="exhaustive")
```

### Cognitive State Object (CSO) relay

The CSO carries established facts, decisions, and dependencies across windows so continuation does not lose context. It is used automatically by `depth="exhaustive"`.

---

## 5. Tool-mediated context

Tools registered with `@client.tool` are invoked by the model during `complete()` and `ask()`. Their outputs are fed back to the model and also extracted into the CKF, so they become first-class context for the rest of the session.

```python
@client.tool
def list_services(env: str) -> list[str]:
    """Return services running in an environment."""
    return ["api", "worker", "db"]

r = client.ask("What services run in production?")
print(r.text)                        # model answer using tool result
print(client.storage.fact_count())   # tool output facts are now in warm store
```

---

## 6. Direct namespace access

### `client.ckf`

Inspect and query the Contextual Knowledge Fabric directly:

```python
print(client.ckf.health())
print(client.ckf.stats())
for fact in client.ckf.search("TLS configuration"):
    print(fact.text, fact.source_window_id)
```

### `client.cso`

Access the Cognitive State Object that carries facts and decisions across continuation windows:

```python
cso = client.cso.snapshot()
print(cso.facts)
print(cso.decisions)
```

### `client.provenance`

Run the Decision Provenance Engine on arbitrary text or the last response:

```python
report = client.provenance.analyze("The EU AI Act applies to high-risk AI systems.")
print(report.grounded)
print(report.fabrications)
```

---

## 7. Storage and extraction

CRP organises context in a warm-state store and the CKF. You can inspect both at any time.

```python
client.ingest("./docs/")

print(client.storage.overview())     # warm-store snapshot
print(client.storage.fact_count())   # total active facts
print(client.storage.windows())      # windows advanced this session
```

### Extraction pipeline

When you ingest a document, CRP runs a six-stage extraction pipeline:

1. Regex / heuristic extraction
2. Statistical NER
3. GLiNER named-entity recognition
4. UIE (universal information extraction) - when available
5. Discourse parsing
6. LLM-assisted refinement - when enabled

```python
client.ingest("contract.pdf")
print(client.storage.fact_count())   # number of facts extracted
print(client.knowledge.health())     # CKF state after ingestion
```

---

## 8. What is enforced and displayed

| Capability | Visible to user | Enforced |
|------------|-----------------|----------|
| Sessions / windows | `r.crp.session_id`, `r.crp.window_id` | HMAC chain verified per window |
| CKF | `client.knowledge.search()`, `client.storage.fact_count()` | Zero-CKF fallback; grounding checks |
| CDR | `a.quality`, `a.sources` | Budget-aware packing |
| CDGR | `a.sources` | Cross-document bridging |
| Continuation | `a.complete` | Exit rules inside `ContinuationManager` |
| CSO relay | `a.decisions`, `a.open_questions` | Decisions preserved across windows |
| Tool context | `@client.tool`, `client.storage.fact_count()` | Tool outputs extracted into CKF |
| Storage | `client.storage.overview()` | Backend-specific durability |
| Extraction | `client.storage.fact_count()` | Quality gate drops low-confidence facts |

!!! success "Not just scores"
    Every score above is coupled to an enforceable action: halting, redispatching, dropping facts, or routing to human review. Scores are transparent; actions are deterministic.

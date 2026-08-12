# CRP-SPEC-028: Multi-Horizon Context Model & Conversational Retrieval

**Document:** CRP-SPEC-028  
**Title:** Context Relay Protocol (CRP) - Multi-Horizon Context Model: Unifying Persistent, Conversational, and Ephemeral Context  
**Version:** 1.0.0  
**Status:** Final Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Amends:** CRP-SPEC-003 (Envelope), CRP-SPEC-024 (CDR scope)  
**Prerequisites:** CRP-SPEC-003, CRP-SPEC-009, CRP-SPEC-024, CRP-SPEC-025, CRP-SPEC-027

---

## Abstract

This document closes the largest scope gap in CRP: the entire context model assumes **document generation** - a finite task with enumerable sub-queries, where success means covering every sub-query exactly once and the goal is to maximise novelty. This assumption is correct for "write a 30-section guide" and wrong for the other half of LLM usage: **open-ended multi-turn conversation**, where there is no finite task, topics are revisited deliberately, the dialogue is never "done," and maximising novelty is often exactly the wrong behaviour (when a user asks "what did you mean about X," retrieving novel facts that aren't X is a failure).

The resolution is not a patch to CDR but a generalisation of CRP's entire context architecture. CRP currently models **one** context type - persistent knowledge (the CKF). This document introduces the **Multi-Horizon Context Model**: three context tiers with fundamentally different lifecycles and retrieval policies - Persistent (knowledge), Conversational (dialogue history), and Ephemeral (working/tool context, specified fully in SPEC-029) - unified by a single envelope assembler that blends them per-turn according to detected intent. CDR becomes one retrieval policy among three, applied where it fits (document tasks, novel exploration) and explicitly disabled where it does not (topic drill-down, reference resolution).

---

## 1. The Document Assumption and Why It Fails for Dialogue

### 1.1 What CDR Assumes

CDR (SPEC-024) and the continuation model (SPEC-004) assume:

| Assumption | Document task | Conversation |
|-----------|--------------|--------------|
| Finite, enumerable sub-queries | ✓ "30 sections" | ✗ open-ended |
| Coverage = progress | ✓ cover each once | ✗ revisiting is normal |
| Terminal state exists | ✓ completeness ≥ 0.92 | ✗ never "done" |
| Maximise novelty | ✓ don't repeat sections | ✗ often must repeat |
| Forward-only progression | ✓ section 1→30 | ✗ branches, returns, interleaves |

Every assumption holds for documents and breaks for dialogue. Applying CDR to a conversation would actively harm it: a user asking a follow-up about a topic discussed five turns ago needs that exact prior context retrieved - but CDR, designed to suppress already-covered topics, would deprioritise it as "low novelty." The novelty signal is inverted for drill-down turns.

### 1.2 What Conversation Actually Needs

Conversational context is governed by different forces:

- **Recency:** Recent turns matter more than distant ones (but not absolutely - see reference resolution)
- **Reference resolution:** "fix that bug," "what you said earlier," "the second option" - these require resolving anaphora to specific prior turns
- **Topic threading:** Conversations branch, digress, and return. The active thread must be tracked across interruptions
- **Intent-dependent retrieval:** Some turns explore new ground (novelty helps); some drill into prior ground (novelty hurts); the system must detect which

---

## 2. The Multi-Horizon Context Model

### 2.1 Three Context Tiers

CRP's context is reorganised into three tiers, each with its own store, lifecycle, and retrieval policy:

```
┌──────────────────────────────────────────────────────────────┐
│  TIER P - PERSISTENT (Knowledge)                              │
│  Store:    CKF (SPEC-009)                                     │
│  Lifecycle: slow decay (TTL months–years)                     │
│  Content:  facts, documents, domain knowledge                 │
│  Retrieval: CDR + CDGR (SPEC-024/025) - novelty-weighted      │
│  Use:      grounding, knowledge questions, document tasks     │
├──────────────────────────────────────────────────────────────┤
│  TIER C - CONVERSATIONAL (Dialogue)                           │
│  Store:    Turn Log (this document, §3)                       │
│  Lifecycle: session-scoped, recency-decayed                   │
│  Content:  user turns, assistant turns, topic threads         │
│  Retrieval: recency + reference resolution (this doc, §4)     │
│  Use:      follow-ups, clarifications, "what you said"        │
├──────────────────────────────────────────────────────────────┤
│  TIER E - EPHEMERAL (Working / Tool)                          │
│  Store:    Scratch Buffer (SPEC-029)                          │
│  Lifecycle: instant decay (turns–minutes)                     │
│  Content:  tool outputs, intermediate computations            │
│  Retrieval: explicit reference + freshness gate (SPEC-029)    │
│  Use:      "the query result," "that API response"            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 The Unified Envelope Assembler

A single envelope is assembled each turn by blending the three tiers. The blend ratio is determined by **per-turn intent classification** (§5):

```
envelope = blend(
    persistent_facts   × w_P,    ← from CKF via CDR/CDGR
    conversational_ctx × w_C,    ← from Turn Log via recency/reference
    ephemeral_ctx      × w_E,    ← from Scratch Buffer via reference/freshness
)
where w_P + w_C + w_E = 1.0, set per-turn by intent
```

The weights shift dramatically by turn type. A knowledge question is mostly Tier P. A "what did you mean" follow-up is mostly Tier C. A "summarise that query result" turn is mostly Tier E. The assembler computes the weights, retrieves from each tier under its own policy, and packs the blended result using the primacy-recency sandwich (SPEC-003).

---

## 3. The Turn Log (Tier C Store)

### 3.1 Structure

```
TurnLog {
  session_id:    string
  turns: [
    {
      turn_id:        integer
      role:           enum            // USER | ASSISTANT
      content:        string
      embedding:      float[]         // same model as CKF (SPEC-027 §2.5)
      timestamp:      ISO 8601
      topic_thread:   string          // thread identifier (§3.3)
      references:     integer[]       // turn_ids this turn refers to
      entities:       string[]        // named entities mentioned (for reference resolution)
      tool_calls:     string[]        // scratch buffer IDs produced this turn (Tier E link)
    }
  ]
  active_thread:   string             // currently active topic thread
}
```

### 3.2 Recency Decay

Unlike CKF facts (slow TTL decay) and unlike CDR (novelty, no recency preference), conversational turns decay by recency with a session-scoped half-life:

```
turn_recency(turn) = 0.5 ^ ((current_turn - turn.turn_id) / HALF_LIFE)
    where HALF_LIFE = 6 turns (default, configurable)
```

A turn 6 turns ago has half the recency weight of the current turn. This is the default conversational gravity: recent turns dominate. But recency is overridden by reference resolution (§4) - an explicitly referenced old turn is pulled back to full weight regardless of age.

### 3.3 Topic Threading

Conversations are not linear. Users digress and return. The Turn Log tracks **topic threads** - clusters of turns about the same subject, which may be non-contiguous:

```
Turn 1 (USER): "How do I configure etcd?"        → thread: etcd-config
Turn 2 (ASST): "..."                              → thread: etcd-config
Turn 3 (USER): "Actually, what's a good backup?"  → thread: backup
Turn 4 (ASST): "..."                              → thread: backup
Turn 5 (USER): "Back to etcd - what about TLS?"   → thread: etcd-config (RESUMED)
```

Thread assignment uses embedding similarity to prior threads: a new turn joins the most similar existing thread (if similarity > 0.70) or starts a new thread. When a thread resumes after interruption (Turn 5), the assembler pulls the dormant thread's turns back into context even though they are not recent - because the active thread, not raw recency, governs relevance.

---

## 4. Reference Resolution

### 4.1 The Anaphora Problem

Conversational turns contain references that must be resolved to prior turns or entities:

```
"fix that bug"              → which bug? (entity reference)
"what you said earlier"     → which turn? (turn reference)
"the second option"         → which enumeration? (ordinal reference)
"do it again but faster"    → what is "it"? (action reference)
"the query result"          → which tool output? (Tier E reference)
```

### 4.2 Resolution Procedure

Before envelope assembly, the current turn is scanned for referential expressions, and each is resolved against the Turn Log and entity set:

```python
def resolve_references(current_turn, turn_log, scratch_buffer):
    resolved = []
    for ref in detect_referential_expressions(current_turn):
        if ref.type == "entity":          # "that bug"
            target = most_recent_turn_mentioning(ref.entity, turn_log)
        elif ref.type == "turn":          # "what you said earlier"
            target = most_recent_assistant_turn(turn_log)
        elif ref.type == "ordinal":       # "the second option"
            target = turn_with_enumeration(ref.ordinal, turn_log)
        elif ref.type == "tool":          # "the query result"
            target = scratch_buffer.most_recent(ref.tool_type)
        resolved.append((ref, target))
    return resolved
```

Resolved targets are pulled into the envelope at full weight, overriding recency decay. This is the mechanism that makes "what did you mean about X five turns ago" work: the reference resolver identifies turn X and injects it at full priority, even though recency alone would have decayed it.

### 4.3 Reference Resolution Disables Novelty

**Critical interaction with CDR.** When the current turn contains a reference to prior content (a drill-down or clarification), CDR's novelty weighting is DISABLED for that turn. The user is explicitly asking to revisit covered ground; suppressing it as "low novelty" would be exactly wrong. The intent classifier (§5) detects this and sets the retrieval policy accordingly.

---

## 5. Per-Turn Intent Classification

### 5.1 The Five Conversational Intents

Each turn is classified into an intent that determines the tier blend and retrieval policy:

| Intent | Signal | Tier Blend | CDR Novelty |
|--------|--------|-----------|-------------|
| `EXPLORE` | New topic, no references | High Tier P | ON (novel facts help) |
| `DRILL_DOWN` | Reference to prior content | High Tier C | OFF (revisiting is the point) |
| `CLARIFY` | "what do you mean," "explain again" | High Tier C | OFF |
| `CONTINUE` | "go on," "and then," "more" | Tier C + Tier P | PARTIAL (extend, not repeat) |
| `TOOL_REFERENCE` | "the result," "that output" | High Tier E | N/A |

### 5.2 Classification Method

Intent is classified by a fast heuristic + embedding check (sub-millisecond, no model call):

```python
def classify_intent(current_turn, turn_log, scratch_buffer):
    refs = detect_referential_expressions(current_turn)
    
    if any(r.type == "tool" for r in refs):
        return "TOOL_REFERENCE"
    if any(phrase in current_turn for phrase in CLARIFY_MARKERS):
        return "CLARIFY"          # "what do you mean", "explain", "again"
    if refs:                       # any reference to prior content
        return "DRILL_DOWN"
    if any(phrase in current_turn for phrase in CONTINUE_MARKERS):
        return "CONTINUE"          # "go on", "more", "and then"
    # No references, no continuation markers → new exploration
    topic_sim = max_similarity(current_turn, turn_log.active_thread_turns)
    if topic_sim < 0.50:
        return "EXPLORE"           # genuinely new topic
    return "CONTINUE"              # same thread, extend it
```

This runs in microseconds - pattern matching plus one similarity computation. No inference. Core-tier.

### 5.3 Intent Drives the Blend

```python
INTENT_BLENDS = {
    "EXPLORE":        {"P": 0.70, "C": 0.25, "E": 0.05, "cdr_novelty": True},
    "DRILL_DOWN":     {"P": 0.30, "C": 0.65, "E": 0.05, "cdr_novelty": False},
    "CLARIFY":        {"P": 0.20, "C": 0.75, "E": 0.05, "cdr_novelty": False},
    "CONTINUE":       {"P": 0.50, "C": 0.40, "E": 0.10, "cdr_novelty": "partial"},
    "TOOL_REFERENCE": {"P": 0.20, "C": 0.30, "E": 0.50, "cdr_novelty": False},
}
```

---

## 6. Conversational Continuation vs Document Continuation

### 6.1 No Residual Task Anchor for Dialogue

The Residual Task Anchor (SPEC-024 §4) carries "remaining sections" forward. Conversation has no remaining sections. For Tier C, the anchor is replaced by the **Active Thread Summary** - a compact representation of the current topic thread's state:

```
Document continuation: "Remaining: service mesh, eBPF, federation"
Conversational anchor:  "Active thread: etcd configuration. 
                         Established: user runs v3.5, 3-node cluster.
                         Open: TLS setup approach not yet decided."
```

The Active Thread Summary tracks established facts and open questions within the current thread, not task completion. It is what lets a conversation maintain coherence across turns without a finite task structure.

### 6.2 Thread State

```
ThreadState {
  thread_id:         string
  established:       string[]    // facts settled in this thread
  open_questions:    string[]    // unresolved items in this thread
  user_constraints:  string[]    // constraints the user stated
  last_active_turn:  integer
}
```

When a thread resumes (§3.3), its ThreadState is restored to context, giving the model the full state of that topic even after a long digression.

---

## 7. Headers

### 7.1 CRP-Context-Tier-Blend

**Direction:** RES  
**Definition:** The tier weights used for this turn's envelope, as `P/C/E` percentages.

```
CRP-Context-Tier-Blend: 30/65/5
```

### 7.2 CRP-Context-Turn-Intent

**Direction:** RES  
**Definition:** The classified intent of the current turn.

```
CRP-Context-Turn-Intent: DRILL_DOWN
```

### 7.3 CRP-Context-References-Resolved

**Direction:** RES  
**Definition:** Number of referential expressions resolved to prior turns/entities this turn.

```
CRP-Context-References-Resolved: 2
```

### 7.4 CRP-Context-Active-Thread

**Direction:** RES  
**Definition:** Identifier of the currently active topic thread.

```
CRP-Context-Active-Thread: etcd-config
```

### 7.5 CRP-Context-Mode (extended)

The existing `CRP-Context-Mode` header (SPEC-017) gains conversational values:

```
CRP-Context-Mode: document      ← finite task, CDR active
CRP-Context-Mode: conversation  ← dialogue, multi-horizon blend active
CRP-Context-Mode: hybrid        ← document task within a conversation
```

---

## 8. The Hybrid Case

Real usage mixes modes: a conversation that includes a document-generation request ("write me a guide about what we just discussed"). The model is in conversation mode but the request is a document task.

The assembler handles this as `CRP-Context-Mode: hybrid`:
- Tier C provides the conversational context ("what we just discussed")
- That context seeds the document task's sub-query decomposition
- CDR/CDGR then run normally for the document generation
- The generated document is logged back as an assistant turn in Tier C

This composition is why the three tiers share one assembler rather than being separate systems. A turn can draw conversational context to define a document task, then switch to document retrieval policy for the generation, then log the result conversationally.

---

## 9. What This Does Not Yet Cover

Tier E (ephemeral/tool context) is introduced here as part of the model but specified in full in SPEC-029. This document establishes the three-tier architecture and fully specifies Tiers P (via existing CDR/CDGR) and C (conversational). SPEC-029 completes Tier E.

Cross-session conversational memory (remembering a conversation from last week) is out of scope here - the Turn Log is session-scoped. Persisting conversational context across sessions would promote selected turns into the CKF (Tier P) as facts, which is a CKF ingestion concern, not a retrieval one.

---

## 10. References

- CRP-SPEC-003 - Context Envelope & Packing (assembler, packing)
- CRP-SPEC-004 - Window Continuation (document continuation contrast)
- CRP-SPEC-009 - Contextual Knowledge Fabric (Tier P)
- CRP-SPEC-024 - Coverage-Differential Retrieval (Tier P policy)
- CRP-SPEC-025 - Graph Retrieval (Tier P policy)
- CRP-SPEC-029 - Ephemeral & Tool Context (Tier E)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

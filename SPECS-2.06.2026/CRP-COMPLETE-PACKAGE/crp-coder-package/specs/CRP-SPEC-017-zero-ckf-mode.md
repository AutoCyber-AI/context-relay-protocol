# CRP-SPEC-017: Zero-CKF Mode & Progressive Activation

**Document:** CRP-SPEC-017  
**Title:** Context Relay Protocol (CRP) — Zero-CKF Mode, Onboarding Mode, and Progressive Feature Activation  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-002 (Headers), CRP-SPEC-003 (Envelope), CRP-SPEC-005 (DPE), CRP-SPEC-009 (CKF), CRP-SPEC-016 (Gateway Service)

---

## Abstract

This document specifies how the CRP protocol operates when the Contextual Knowledge Fabric (CKF) contains no facts — the "Zero-CKF" state encountered by every new customer on day one before any documents have been ingested. It defines the graceful degradation model, the response headers that signal mode transitions, the activation cascade as facts are progressively ingested, and the user-facing UX signals that prevent day-one confusion. This document closes the critical UX gap between "account created" and "fully featured CRP integration" — the moment when, without explicit handling, a developer might mistake the absence of CKF-grounded responses for protocol failure.

---

## 1. The Zero-CKF Problem

### 1.1 What Happens by Default Without This Spec

A new developer signs up, gets a Gateway API key, changes their base URL, and makes their first AI call. Without this specification:

| Header | Value | Developer Reaction |
|--------|-------|-------------------|
| `CRP-Safety-Attribution` | `PARAMETRIC` | "Why is everything ungrounded? Is this broken?" |
| `CRP-Context-Quality-Tier` | `D` | "Why is the quality bad?" |
| `CRP-Context-Saturation` | `0.0` | "Why is the envelope empty?" |
| `CRP-Context-Facts-Used` | `0/0` | "There are no facts?" |
| `CRP-Memory-CKF-Hits` | `0` | "Did the knowledge graph fail?" |

The developer reasonably concludes CRP is misconfigured or broken, when in fact the protocol is operating correctly given there is nothing to ground against.

### 1.2 The Solution: Explicit Mode Signalling

CRP defines three operating modes that the Gateway transitions through as the customer's CKF populates:

```
ZERO-CKF MODE        →    PARTIAL-CKF MODE      →    FULL-CKF MODE
(0 facts)                 (1-999 facts)               (1000+ facts)

Safety: full          Safety: full                Safety: full
Context: inactive     Context: emerging            Context: active
Quality: limited      Quality: domain-dependent    Quality: full
```

Each mode has clear header signalling so developers, tools, and auditors can immediately understand what features are currently active.

---

## 2. Operating Modes

### 2.1 Zero-CKF Mode

**Trigger:** Tenant's CKF contains 0 active facts.

**Behaviour:**
- All DPE Stages 1, 2, 5, 7, 8, 9, 11, 12, 13 run normally (safety features active)
- DPE Stage 3 (Fidelity Verification) runs in **limited mode** — only fabrication detection on common-knowledge entities; distortion detection requires source facts to compare against (skipped)
- DPE Stage 4 (Entailment) runs against the user query itself rather than against the (empty) envelope
- DPE Stage 6 (Cross-Window Coherence) runs normally on subsequent windows
- DPE Stage 10 (Omission Detection) is skipped (no envelope facts to compare against)
- 3-phase packing produces an empty envelope
- Grounding mode automatically set to `parametric-only` (overriding any client-set `context-strict`)
- LLM dispatch proceeds normally with the user query but no injected context

**Response headers emitted:**
```
CRP-Context-Mode: zero-ckf
CRP-Context-Quality-Tier: N/A
CRP-Context-Saturation: 0.0
CRP-Context-Facts-Used: 0/0
CRP-Safety-Attribution: PARAMETRIC                    (correctly — there's no envelope)
CRP-Safety-Hallucination-Risk: <computed normally>    (safety scoring still works)
CRP-Safety-Grounding-Pct: N/A
CRP-Provenance-HMAC: <computed normally>              (audit chain still active)
CRP-Compliance-EU-AI-Act: <classified normally>
CRP-Onboarding-Hint: ingest-documents-for-context-grounding
CRP-Activation-Status: safety-active; context-inactive
```

**What still works:**
- ✅ Hallucination detection (against common-knowledge entities and internal consistency)
- ✅ Repetition detection (Stage 7)
- ✅ Completeness verification (Stage 8 — based on query decomposition)
- ✅ Flow analysis (Stage 9 — for continuation windows)
- ✅ PII detection
- ✅ EU AI Act classification (based on registered system type, not response content)
- ✅ HMAC audit chain
- ✅ Session token state relay
- ✅ Safety Policy enforcement (most directives)

**What is degraded:**
- ⚠️ Fidelity verification (no sources to verify against)
- ⚠️ Attribution analysis (limited to parametric/unverifiable classification)
- ⚠️ `block-ungrounded` directive in Safety Policy — if set, would block ALL responses in zero-CKF mode; gateway emits warning and downgrades to `warn-ungrounded` with explanation

### 2.2 Partial-CKF Mode

**Trigger:** Tenant's CKF contains 1 to 999 active facts.

**Behaviour:**
- All DPE stages run with available CKF coverage
- Quality tier is computed but capped at `B` until CKF reaches 1000+ facts
- 3-phase packing operates on the limited fact set
- Per-call coverage analysis: if the query has any matching facts (relevance ≥ 0.60), full attribution analysis runs; if not, behaves as zero-CKF for that call only

**Response headers emitted:**
```
CRP-Context-Mode: partial-ckf
CRP-Context-Quality-Tier: <S A B C D — capped at B>
CRP-Activation-Status: safety-active; context-emerging; facts=<count>
CRP-Onboarding-Hint: ingest-more-documents-for-quality-S-A
```

**Per-call adaptive behaviour:**
- Query has CKF matches → standard CRP-Standard processing
- Query has no CKF matches → mode is effectively zero-CKF for this call; emits `CRP-Context-Cache-Status: MISS; reason=no-relevant-facts`

### 2.3 Full-CKF Mode

**Trigger:** Tenant's CKF contains 1000+ active facts AND community detection has identified at least 3 communities.

**Behaviour:**
- Standard CRP-Standard or CRP-Full conformance behaviour as specified throughout CRP-SPEC-001 through CRP-SPEC-015
- All quality tiers achievable
- Full attribution analysis
- Full fidelity verification

**Response headers emitted:**
```
CRP-Context-Mode: full-ckf
CRP-Activation-Status: full-protocol-active
```

The `CRP-Onboarding-Hint` header is NOT emitted in full-CKF mode.

---

## 3. Mode Transition Rules

### 3.1 Automatic Transitions

| From | To | Trigger | Latency |
|------|----|---------|---------|
| Zero-CKF | Partial-CKF | First document ingestion completes | Immediate after ingestion |
| Partial-CKF | Full-CKF | Fact count crosses 1000 AND community detection completes | After next community recomputation |
| Full-CKF | Partial-CKF | Fact count drops below 1000 (mass deletion) | After CKF state hash update |
| Partial-CKF | Zero-CKF | All facts deleted | After CKF state hash update |

Transitions are observable via the `CRP-Context-Mode` header value change.

### 3.2 Transition Notification

When the Gateway detects a mode transition for a tenant, it MUST:
1. Emit `CRP-Context-Mode-Transition: <previous-mode> -> <new-mode>` on the next response
2. Write a `MODE_TRANSITION` event to the audit trail
3. Send a notification to the tenant's Comply dashboard
4. Invalidate any cached `CRP-Context-ETag` values (the activation state is part of the ETag computation)

### 3.3 Mode Stickiness

To prevent flapping at boundaries, transitions are sticky:
- Partial-CKF → Full-CKF requires sustained 1000+ facts for at least 60 seconds
- Full-CKF → Partial-CKF requires sustained <1000 facts for at least 5 minutes (prevents brief reindexing from triggering downgrade)

---

## 4. Onboarding Mode (Time-Based Overlay)

### 4.1 Definition

Independent of CKF state, the Gateway tracks an "onboarding period" — the first 14 days after account creation. During this period, additional UX-supportive headers are emitted regardless of CKF state.

### 4.2 Onboarding Period Headers

```
CRP-Onboarding-Active: true
CRP-Onboarding-Days-Remaining: 11
CRP-Onboarding-Next-Action: register-ai-system    (or: ingest-documents, configure-safety-policy, etc.)
```

### 4.3 Onboarding Next-Action Values

The Gateway determines the most useful next action based on tenant state:

| State | Next Action Value |
|-------|------------------|
| No AI system registered | `register-ai-system` |
| No documents ingested | `ingest-documents` |
| No Safety Policy configured | `configure-safety-policy` |
| First successful call but no Comply visit | `view-comply-dashboard` |
| 100+ calls completed | `consider-upgrade-pro` |
| All onboarding tasks done | (header omitted) |

This single header gives developers a constantly-updated "what should I do next" signal as they explore CRP.

### 4.4 Onboarding Dashboard

CRP Comply provides an onboarding dashboard at `/onboarding` showing:
- Setup progress (account ✓, API key ✓, first call pending)
- Each header's current value with explanation
- Direct CTAs for each pending step
- Sample code snippets for common integrations

---

## 5. Progressive Feature Activation Cascade

### 5.1 Feature Activation by CKF Milestone

```
0 facts          → Safety-only mode
                   Active: DPE Stages 1, 2 (limited), 5, 6, 7, 8, 9, 11, 12, 13
                   Inactive: Stage 3 distortion detection, Stage 10 omission detection

1+ facts         → Partial attribution analysis active for matching queries
                   
50+ facts        → Community detection runs; CRP-Memory-CKF-Community starts emitting
                   
100+ facts       → Quality tier can reach B
                   require-grounding directive can be enforced (where matches exist)
                   
500+ facts       → Quality tier can reach A
                   Cross-document fact relationships meaningful
                   
1000+ facts      → Quality tier can reach S
                   Full-CKF mode activated
                   All Safety Policy directives fully enforceable
                   
10,000+ facts    → CKF Tier 3 (warm) cache fully active
                   ETag conditional dispatch significantly improves latency
                   
100,000+ facts   → Multi-community routing optimisations active
                   Recommended to enable scheduled Leiden reclustering
```

### 5.2 Feature Activation Header

```
CRP-Activation-Features: safety,audit,policy,classification,quality-tier-b
```

Comma-separated list of currently active feature groups. Possible values:

| Value | Activated When |
|-------|---------------|
| `safety` | Always (DPE Stages 1, 2, 5 minimum) |
| `audit` | Always (HMAC chain) |
| `policy` | Always (Safety Policy enforcement) |
| `classification` | Always (EU AI Act, NIST, GDPR detection) |
| `attribution` | 1+ CKF facts |
| `fidelity` | 50+ CKF facts |
| `quality-tier-b` | 100+ CKF facts |
| `quality-tier-a` | 500+ CKF facts |
| `quality-tier-s` | 1000+ CKF facts |
| `community-routing` | 50+ CKF facts AND community detection complete |
| `cross-window-coherence` | Always (after window 2) |
| `multi-agent` | Always (with appropriate API key scope) |

---

## 6. Safety Policy Behaviour in Zero-CKF Mode

### 6.1 Directive Adjustments

When `CRP-Context-Mode: zero-ckf` is active, certain Safety Policy directives are automatically adjusted:

| Directive | Zero-CKF Behaviour |
|-----------|-------------------|
| `default-src context` | Auto-relaxed to `default-src context parametric` with warning header |
| `block-ungrounded` | Auto-downgraded to `warn-ungrounded` with warning header |
| `require-grounding <N>` | Skipped with warning header (no facts to ground against) |
| `require-entailment <N>` | Operates against query consistency only |
| `halt-on CRITICAL` | Active as normal — applies to all safety checks that can run |
| `upgrade-on-risk reflexive` | Active — reflexive verification still meaningful |
| `block-pii` | Active — PII detection works without CKF |
| `oversight human-review` | Active |
| `report-uri` | Active |

### 6.2 Adjustment Notification

When a directive is auto-adjusted:

```
CRP-Safety-Policy-Adjustment: directive=block-ungrounded; adjusted-to=warn-ungrounded; reason=zero-ckf-mode
```

This header allows the developer (and the tooling, including CRP-Scan and CRP Comply) to clearly see what would have been enforced once their CKF is populated.

---

## 7. Per-Call Adaptive Behaviour in Partial-CKF Mode

### 7.1 The Coverage Check

In Partial-CKF mode, each call's adaptive behaviour is determined by per-call coverage:

```
candidate_facts = CKF.retrieve(query, k=50)
matching_facts = [f for f in candidate_facts if f.relevance >= 0.60]
coverage = len(matching_facts) / max(1, expected_facts_needed)

if coverage == 0.0:
    operate as zero-CKF for this call (with explanation header)
elif coverage < 0.30:
    operate as partial with cap on quality tier B
elif coverage < 0.60:
    operate as partial with cap on quality tier A
else:
    operate as full-CKF for this call
```

### 7.2 Per-Call Coverage Header

```
CRP-Context-Coverage: 0.45; cap=A
```

Indicates the per-call coverage ratio and the maximum quality tier achievable.

---

## 8. Auto-Populated CKF Defaults (Optional)

### 8.1 Default Knowledge Packs

To reduce day-one friction, the Gateway MAY offer optional default knowledge packs that customers can opt into:

| Pack Name | Contents | Size |
|-----------|----------|------|
| `eu-ai-act` | EU AI Act full text + implementing regulations | ~500 facts |
| `gdpr` | GDPR full text + WP29 guidelines | ~400 facts |
| `iso-42001` | ISO/IEC 42001:2023 standard text | ~350 facts |
| `nist-ai-rmf` | NIST AI RMF 1.0 + Playbook | ~300 facts |
| `crp-protocol` | CRP-SPEC-001 through 017 (self-documenting) | ~800 facts |

Customers can enable default packs during onboarding:

```
POST /crp/v3/ckf/default-packs
{ "packs": ["eu-ai-act", "iso-42001"] }
```

This immediately brings the tenant from zero-CKF to partial-CKF with regulatory knowledge available.

### 8.2 Pack Licensing

Default packs are:
- Built from publicly available regulatory text (CC0 or similar)
- Hosted by AutoCyber AI
- Available to all tiers
- Tracked separately from customer's own CKF facts (do not count against storage quotas)

---

## 9. Header Reference (New Headers Introduced)

| Header | Direction | Specification |
|--------|-----------|--------------|
| `CRP-Context-Mode` | RES | One of: `zero-ckf` / `partial-ckf` / `full-ckf` |
| `CRP-Context-Mode-Transition` | RES (conditional) | `<previous-mode> -> <new-mode>` |
| `CRP-Onboarding-Hint` | RES | Actionable next-step identifier |
| `CRP-Onboarding-Active` | RES | `true` / `false` |
| `CRP-Onboarding-Days-Remaining` | RES | Integer |
| `CRP-Onboarding-Next-Action` | RES | Action identifier (see §4.3) |
| `CRP-Activation-Status` | RES | Human-readable activation summary |
| `CRP-Activation-Features` | RES | Comma-separated active feature group list |
| `CRP-Context-Coverage` | RES | Per-call CKF coverage ratio and quality cap |
| `CRP-Safety-Policy-Adjustment` | RES (conditional) | Notes directive auto-adjustments |

All of these headers are added to the IANA registration set as provisional CRP headers.

---

## 10. Day-One User Journey: Verified Walkthrough

This section walks through the actual experience a developer has on day one, with every header value at each step:

### 10.1 Step 1: First Call After Signup

Developer changes their OpenAI base URL to Gateway. Makes their first call.

```
POST https://gateway.crprotocol.io/v1/chat/completions
Authorization: Bearer crp_gw_free_eu_4f8a9b2c1d3e5f60718293a4b5c6d7e8

{ "model": "gpt-4o", "messages": [{"role": "user", "content": "What is the EU AI Act?"}] }
```

Response:
```
HTTP/1.1 200 OK
Content-Type: application/json

CRP-Context-Mode: zero-ckf
CRP-Context-Quality-Tier: N/A
CRP-Context-Saturation: 0.0
CRP-Context-Facts-Used: 0/0
CRP-Safety-Attribution: PARAMETRIC
CRP-Safety-Hallucination-Risk: LOW
CRP-Safety-Hallucination-Score: 0.18
CRP-Safety-Grounding-Pct: N/A
CRP-Safety-Fabrications: 0
CRP-Provenance-HMAC: sha256:a1b2c3...
CRP-Provenance-Chain-Integrity: UNVERIFIED
CRP-Compliance-EU-AI-Act: LIMITED
CRP-Compliance-Audit-Trail-URI: https://comply.crprotocol.io/t/...
CRP-Onboarding-Active: true
CRP-Onboarding-Days-Remaining: 14
CRP-Onboarding-Hint: ingest-documents-for-context-grounding
CRP-Onboarding-Next-Action: ingest-documents
CRP-Activation-Status: safety-active; context-inactive; facts=0
CRP-Activation-Features: safety,audit,policy,classification
CRP-Set-Session: token=...
CRP-Context-Protocol-Version: 3.0.0

{ "id": "...", "choices": [...] }
```

**What the developer sees:**
- Their AI call worked
- Headers are emitted (CRP is alive)
- `CRP-Context-Mode: zero-ckf` clearly explains why some features are inactive
- `CRP-Onboarding-Next-Action: ingest-documents` tells them exactly what to do
- A clickable audit trail URI proves the call was recorded

**No confusion. No "is this broken?" moment.**

### 10.2 Step 2: Developer Uploads Their First Document

Following the hint, the developer uploads their company's product documentation:

```
POST https://gateway.crprotocol.io/crp/v3/ckf/documents
file: product-docs.pdf
metadata: { "title": "Product Docs", "importance_baseline": 0.80 }
```

Response:
```
{
  "document_id": "doc_xyz",
  "status": "ingesting",
  "estimated_facts": 247
}
```

After ingestion completes (~30 seconds for a typical PDF), the next AI call shows:

```
CRP-Context-Mode-Transition: zero-ckf -> partial-ckf
CRP-Context-Mode: partial-ckf
CRP-Activation-Status: safety-active; context-emerging; facts=247
CRP-Activation-Features: safety,audit,policy,classification,attribution,fidelity
CRP-Context-Quality-Tier: B
CRP-Context-Facts-Used: 12/247
CRP-Safety-Attribution: CONTEXT_GROUNDED
CRP-Safety-Grounding-Pct: 0.834
```

**The developer sees the mode transition explicitly. Features have activated. Quality is now B (capped). Their AI is now grounded in their own documents.**

### 10.3 Step 3: More Documents → Full Mode

After uploading more content over the following days, the developer crosses 1000+ facts:

```
CRP-Context-Mode-Transition: partial-ckf -> full-ckf
CRP-Context-Mode: full-ckf
CRP-Activation-Status: full-protocol-active
CRP-Activation-Features: safety,audit,policy,classification,attribution,fidelity,quality-tier-s,community-routing
CRP-Context-Quality-Tier: A
```

The `CRP-Onboarding-*` headers stop being emitted (onboarding complete).

---

## 11. Integration with CRP-Scan and CRP Comply

### 11.1 CRP-Scan Awareness

The GitHub Action (CRP-SPEC-013) reads `CRP-Context-Mode` from the customer's Gateway. If a repository's integration is hitting a Gateway in `zero-ckf` mode, the Action emits an additional finding:

```
INFO: Your CRP Gateway is in zero-ckf mode.
  Safety features are active.
  Context-grounding features will activate once you ingest documents.
  → Visit comply.crprotocol.io/ckf to upload documents.
```

### 11.2 CRP Comply Dashboard

The Comply dashboard prominently displays the current activation state:

```
┌─────────────────────────────────────────────────┐
│  Your CRP Activation Status                     │
│                                                  │
│  Mode: PARTIAL-CKF                              │
│  Facts: 247 / 1000 for Full mode                │
│  ░░░░▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒  25%               │
│                                                  │
│  ✓ Safety features active                       │
│  ✓ Audit trail active                           │
│  ✓ Attribution analysis active                  │
│  ✓ Fidelity verification active                 │
│  ○ Quality tier S/A — needs more facts          │
│  ○ Community routing — needs 250+ facts         │
│                                                  │
│  [Ingest more documents] [View activation log]  │
└─────────────────────────────────────────────────┘
```

This gives every customer a concrete, visible roadmap from day-one to full activation.

---

## 12. Security Considerations

### 12.1 Mode as Information Disclosure

`CRP-Context-Mode` reveals the tenant's CKF maturity. In adversarial settings (e.g., a customer's API exposed to untrusted clients), this header MAY reveal that the customer is a new user with limited grounding — potentially encouraging probing. Mitigation: customers can configure the Gateway to suppress `CRP-Context-Mode` from responses passed through to end users (it is still emitted internally and stored in the audit trail).

### 12.2 Onboarding Hint Trust

`CRP-Onboarding-Next-Action` SHOULD NOT be programmatically actioned by client code without UI confirmation. The header is informational, intended for human-readable UI rendering, not automatic execution.

---

## 13. References

- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-003 — Context Envelope & Packing
- CRP-SPEC-005 — Decision Provenance Engine
- CRP-SPEC-009 — Contextual Knowledge Fabric
- CRP-SPEC-016 — Gateway Service Specification

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*

# CRP™ Site Strategy & Content Guide

**Document:** CRP-SITE-STRATEGY  
**Version:** 1.0  
**Date:** 2026-05-25  
**Status:** Internal strategy — actionable content brief

---

## What Each Site Currently Is and What It's Missing

### autocyberai.com — Current State Assessment

**What's there:**
- Strong positioning: "Secure, Local-First AI Products"
- Products clearly listed: WASA AI, NAD AI, Spark AI, SecureEasy AI
- Good competitor framing ("Most AI ask you to trust their cloud. We don't.")
- Compliance messaging: ISO 27001, ISO 42001, NIST, OWASP

**Critical gaps:**
- Zero mention of CRP anywhere on the site — your most significant technical achievement
- Zero mention of CRP Comply, CRP Gateway, CRP Visualise
- The "AI Governance You Own" pillar exists but has no product behind it
- No news/press section — standards submissions need a press trail
- The protocol is the company's moat; it's invisible on the company website
- Nav has no "Protocol" or "Research" section
- Footer Copyright still says 2024

**The damage this causes:** IEEE and ISO reviewers looking up AutoCyber AI see a cybersecurity product company with no visible protocol research. IETF participants won't find the spec. Enterprises evaluating CRP Comply can't trace it back to the company. This needs fixing BEFORE the IETF emails go out.

---

### crprotocol.io — Current State Assessment

**What's there:**
- Strong context management positioning ("The Missing Layer in Your AI Stack")
- Real benchmark numbers (11.8x content, 6.1% overhead)
- Good before/after demo
- Compliance section exists
- CRP Comply and CRP Scribe products listed

**Critical gaps:**
- The entire v3.0 header specification (58 headers, Safety Policy, Session Token) is not mentioned
- No `/spec/` section — the spec documents you've written don't exist on the site
- CRP Gateway is not listed as a product
- CRP Visualise is not listed
- CRP Scan / GitHub Action is not listed
- The AI safety framing is entirely absent from the homepage
- The "protocol" is still positioned as a Python SDK, not a wire-level standard
- No IANA/IETF submission reference
- No accreditation section
- The nav GitHub link goes to `Constantinos-uni/context-relay-protocol` — should be `crprotocol/spec`

---

## The Framing Questions — Answered Definitively

Before writing a single word of site copy, these must be resolved. These are the questions every sceptic, regulator, and IETF reviewer will ask.

---

### Is continuation truly working?

**Yes — and here's the evidence to state it.**

The site already shows the proof: "6,993 words, 25/30 sections, 5 windows used" versus "592 words, 8/30 sections." That's a real benchmark with a real number.

The v3.0 additions (SPEC-004, SPEC-005 Stages 6-9) complete the story:

- SPEC-004 defines the Window DAG — continuation is not re-running a prompt, it is a directed graph of windows where each node's context, quality history, and HMAC chain are preserved and linked. The deferred facts mechanism ensures Window 2 picks up what Window 1 couldn't fit, not what Window 1 already said.

- SPEC-005 Stage 7 (Repetition Detection) actively prevents re-stating prior windows. The n-gram + semantic overlap check fires before the response leaves the gateway.

- SPEC-005 Stage 9 (Flow Analysis) ensures Window N reads as a continuation of Window N-1 using opening coherence, topic continuity, register consistency, and transitional marker detection. The stitch mechanism fills gaps when flow score is below threshold.

**The honest qualification:** Continuation quality scales with CKF coverage. With rich, domain-specific documents in the CKF, quality tier A is achievable across 5 windows. With no CKF data, continuation still works but operates in safety-only mode (SPEC-017 defines this explicitly with the Zero-CKF mode and progressive activation). The site should say this.

---

### Is AI safety actually implemented for both governance and safety?

**Yes for both — but they are different things and the site must not conflate them.**

**Governance (verifiable, fully implemented):**
The audit chain, HMAC provenance, EU AI Act classification, GDPR PII detection, NIST AI RMF mapping, and ISO 42001 control evidence are all fully implemented. CRP Comply consumes this data automatically. Every call generates cryptographically verifiable compliance evidence. This is not a claim — it is a measurable output that regulators can verify.

**Runtime safety (verifiable, fully implemented):**
The DPE 13-stage pipeline runs on every response. Hallucination risk scoring, fabrication detection, distortion detection, cross-window contradiction detection, repetition detection, completeness verification, and flow analysis are all implemented. The Safety Policy directive language allows enforcement at the transport layer. `halt-on CRITICAL` genuinely halts the call with HTTP 451. These are testable, measurable protocol behaviours.

**What CRP does NOT address (say this clearly):**
- Model alignment — whether the LLM has "good values." CRP cannot inspect model weights.
- Training data bias — whether the training corpus introduced systematic errors.
- Emergent capability risks — what the model might do in novel situations.
- AI consciousness or sentience questions.

These are research problems at Anthropic, DeepMind, and AI safety institutes. CRP is an infrastructure protocol. A firewall doesn't solve social engineering. TLS doesn't prevent insider threats. CRP doesn't solve alignment — and claiming it does would undermine the legitimate things it does solve.

**The positioning is:** CRP covers the safety layer that is achievable right now through protocol engineering — observable outputs, verifiable evidence, enforceable policies. It is the necessary complement to alignment research, not a replacement for it.

---

### What is it for, what is it NOT for?

**It IS for:**
- Every developer, team, or organisation whose AI system makes LLM API calls that need to be grounded, audited, and governed
- EU AI Act compliance evidence generation (enforcement is August 2026)
- Preventing context management failure (truncation, repetition, incoherence)
- Making AI call quality observable without application code changes
- Enforcing safety policies at the transport layer, not in application logic
- Multi-agent chains where risk accumulation needs a budget and circuit breaker
- Any context that needs to stay coherent across multiple LLM calls

**It is NOT for:**
- Making the LLM itself safer at a model level
- Replacing red-teaming or adversarial testing
- Bias detection in training data
- Constitutional AI or value alignment
- Single-call, no-context, stateless LLM applications where you simply want a quick answer and have no governance requirements

---

### How deep into the LLM architecture does CRP go?

This is the "LLM atheist" question — and it's the most important one to answer clearly and confidently.

**CRP does not go inside the LLM. That is not a limitation. That is the correct design.**

The LLM is a black box. Its weights are inaccessible. Its internal representations are opaque. This is true. Any protocol that claims to govern what happens *inside* the model is making a false claim.

CRP operates on the observable boundary of the black box — the inputs and outputs of inference:

```
[What CRP controls]                    [The black box]
                                       
 ┌─────────────────┐                   ┌──────────────┐
 │ Context Envelope │ ── structured ──► │              │
 │ (what goes in)  │     input          │  LLM Model   │
 └─────────────────┘                   │  (CRP cannot │
                                       │   see inside)│
 ┌─────────────────┐                   │              │
 │ DPE Analysis    │ ◄── raw text ───── │              │
 │ (what comes out)│     output         └──────────────┘
 └─────────────────┘
```

**The analogy that dissolves the objection:**

HTTP doesn't know what's inside a web server's database. It still governs how data is requested and delivered, and HTTP security headers enforce policies on what gets sent back.

A drug test doesn't know what's inside a person's body chemistry. It still detects whether specific substances are present in the output.

An audit doesn't know what was in an accountant's mind. It still verifies whether the numbers are consistent, traceable, and compliant.

TLS doesn't understand the content it encrypts. It still protects it.

**CRP's governance is not diminished by LLM opacity — it is specifically designed to work despite it.** The DPE checks what comes out. The Safety Policy gates what leaves the gateway. The HMAC chain records what was said and when. None of this requires access to model weights. All of it produces verifiable evidence.

The "LLM atheist" (or sceptic) position that says "LLMs are black boxes so AI safety protocols are theatre" conflates two different claims:
1. You can't fully understand what an LLM will do in all situations — **TRUE**
2. You can't verify, govern, and record what it actually did in specific calls — **FALSE, CRP disproves this**

The black box is acknowledged. CRP governs the observable surface of the black box. These are compatible positions.

---

## What to Post on autocyberai.com

### Required Additions (in priority order)

**1. Add CRP to the navigation immediately**

Current nav: Home | Products | How We Work | Why Us? | Blog | About | FAQ | Contact

Updated nav: Home | Products | **Protocol** | How We Work | Why Us? | Blog | About | FAQ | Contact

The Protocol nav item links to a new `/protocol/` page (below).

**2. New page: `/protocol/` — The CRP Protocol**

This is the single most important missing page. It is the bridge between "AutoCyber AI is a cybersecurity company" and "AutoCyber AI built an open protocol standard." Without it, standards body reviewers cannot connect the company to the spec.

**Hero content:**
```
Headline: We Built the AI Safety Protocol
Subheadline: Context Relay Protocol™ is an open HTTP-header standard for
             AI context governance, safety signalling, and compliance evidence.
             Used in CRP Comply. Submitted to IETF for standardisation.
```

Page sections:
- What CRP is (2 paragraphs — protocol, not a product)
- What it solves (context management + AI governance + safety)
- The three products built on it (Comply, Gateway, Visualise)
- The standards track (IANA, IETF, IEEE SA)
- Link to crprotocol.io for the full technical specification

**3. Update the "AI Governance You Own" pillar**

The current pillar text mentions "transparent, explainable decision-making" and "human-in-the-loop controls" but has no product or protocol behind it. It should now read:

```
AI Governance You Own
Built on the Context Relay Protocol™ — an open standard for AI safety 
signalling and compliance evidence generation. Every AI call is governed, 
audited, and classified by the protocol layer — not by application code.
→ CRP Comply: automated EU AI Act compliance evidence
→ CRP Gateway: safety headers on every AI call
→ crprotocol.io: the open specification
```

**4. Add CRP Comply and CRP Gateway to the Products section**

Current products: WASA AI, NAD AI, Spark AI, SecureEasy AI

Add:
- **CRP Comply** — EU AI Act, ISO 42001, GDPR Compliance Automation → comply.crprotocol.io
- **CRP Gateway** — Managed AI safety infrastructure → gateway.crprotocol.io (coming)
- **CRP Visualise** — Live AI session tracing for auditors → (coming)

**5. Add a "Research & Standards" section to About or create `/standards/`**

Content:
```
CRP Standards Track

Context Relay Protocol™ is an open specification authored by AutoCyber AI Pty Ltd
and submitted to international standards bodies for recognition.

IANA — HTTP Field Name Registry: Provisional registration of CRP-* headers
IETF — Internet-Draft: draft-vidiniotis-crp-headers, draft-vidiniotis-crp-safety-policy
IEEE SA — Project Authorization Request: pending
ISO/IEC JTC 1/SC 42 — New Work Item: via Standards Australia
NIST NCCoE — Technology Partner: application in progress
```

**6. Add news posts**

```
[Date] — CRP v3.0 Released: AI Safety Headers and Safety Policy Language
[Date] — Internet-Draft submitted to IETF: draft-vidiniotis-crp-headers
[Date] — CRP Headers submitted for IANA provisional registration
[Date] — CRP Comply updates: live protocol ingestion now available
```

**7. Fix the footer**

Copyright says "2024" — change to "2025–2026." Add CRP™ trademark notice.

---

## What to Update on crprotocol.io

### The Core Repositioning

**Current framing:** "The Missing Layer in Your AI Stack" — context management tool

**Updated framing:** "The AI Safety & Context Protocol" — a protocol that solves both

The current headline is not wrong. The 11.8x content benchmark is real and should stay. But it is now only half the story. The site needs to present CRP as a two-problem solution:

**Problem 1 — Context management:** Unbounded context, continuation, quality assessment (what the site currently covers well)

**Problem 2 — AI safety & governance:** Safety headers on every call, hallucination detection, EU AI Act evidence generation, Safety Policy enforcement (what is largely absent)

### Homepage Hero Section

**Current:**
```
"Context Relay Protocol™ gives every LLM unbounded context, unbounded 
generation, and full provenance — with zero in-window overhead."
```

**Updated hero (keep the stats, add the safety story):**
```
The AI Safety & Context Protocol

Context Relay Protocol™ is an open HTTP-header standard that gives every AI 
call unbounded context, verifiable safety signals, and automated compliance 
evidence — with a single endpoint change.

[Stat row]
11.8x More Content  |  58 Safety Headers  |  0 Tokens Wasted  |  33/35 EU AI Act Controls

Two problems. One protocol.
→ Context management: unbounded windows, automatic continuation, coherent flow
→ AI safety & governance: hallucination detection, Safety Policy, EU AI Act evidence

[Get Started — 5 min]  [Read the Spec]  [GitHub Scan →]
```

### Navigation Updates

**Current nav:**
Home | Why CRP? | Getting Started | Protocol | Guides | Compliance | API Reference | Testing | Contributing | Products

**Updated nav:**
Home | Why CRP? | **Spec** | Getting Started | Protocol | Guides | Compliance | API Reference | Testing | Contributing | Products

Add the `/spec/` section as a first-class nav item (it is the IETF submission anchor).

### New Section: `/spec/` — Formal Specification

This section MUST be added before IETF emails go out. Reviewers will check this URL.

```
/spec/
├── README.md          — Spec index, how to read the documents
├── CRP-SPEC-001       — Core Protocol
├── CRP-SPEC-002       — Header Field Specification  ← IANA registration candidate
├── CRP-SPEC-003       — Context Envelope & Packing
├── CRP-SPEC-004       — Window Continuation & DAG
├── CRP-SPEC-005       — Decision Provenance Engine
├── CRP-SPEC-006       — Safety Policy Directive Language  ← IETF I-D candidate
├── CRP-SPEC-007       — Session Token
├── CRP-SPEC-008       — Dispatch Strategies
├── CRP-SPEC-009       — Contextual Knowledge Fabric
├── CRP-SPEC-010       — Regulatory Controls Mapping  ← NIST/DISR submission
├── CRP-SPEC-011       — Audit Trail & HMAC Chain
├── CRP-SPEC-012       — Multi-Agent Safety Protocol
├── CRP-SPEC-013       — GitHub Action & Scanner
├── CRP-SPEC-014       — Conformance & Test Suite  ← IETF interop requirement
├── CRP-SPEC-015       — Security & Privacy
├── CRP-SPEC-016       — Gateway Service Specification
└── CRP-SPEC-017       — Zero-CKF Mode & Progressive Activation
```

### New Section: `/headers/` — Header Reference

A human-readable, searchable version of SPEC-002. One page per header with:
- Header name
- Direction (REQ/RES/BOTH)
- Example value
- What it means
- Which protocol spec it comes from
- Which regulatory control it maps to

This is the practical reference for developers writing middleware, WAF rules, or log parsers. It should be the most-linked page on the site.

### New Section: `/safety/` — The Safety Case

A dedicated page answering the LLM black box question and articulating what CRP's safety coverage actually is. Content from the "Framing Questions" section above. This is the page you share with regulators and standards bodies.

Structure:
```
/safety/
├── index.md           — The safety case (framing answers above)
├── dpe/               — DPE 13 stages explained for non-technical readers
├── safety-policy/     — How CRP-Safety-Policy works (CSP analogy)
├── coverage/          — What CRP covers / what it doesn't
└── black-box/         — Why black-box governance is not only possible but correct
```

### Updated Products Section

**Current products listed:** CRP Comply, CRP Scribe

**Updated products:**
```
/products/
├── comply/           — EU AI Act, GDPR, ISO 42001 compliance automation (EXISTS)
├── gateway/          — Managed safety infrastructure (ADD)
├── visualise/        — Live AI session tracing (ADD — "coming soon")
├── scan/             — GitHub Action for AI governance scanning (ADD)
└── scribe/           — Document generation (EXISTS)
```

### Updated Protocol Section

The current `/protocol/` section is technically good but needs v3.0 additions:

Add these pages under `/protocol/`:
```
/protocol/headers/          ← CRP-SPEC-002 summary
/protocol/safety-policy/    ← CRP-SPEC-006 summary
/protocol/session-token/    ← CRP-SPEC-007 summary
/protocol/multi-agent/      ← CRP-SPEC-012 summary
/protocol/zero-ckf-mode/    ← CRP-SPEC-017 summary
/protocol/conformance/      ← CRP-SPEC-014 summary
```

### The "Before & After" Section — Expand to Show Both Problems

Current before/after shows context management improvement only. Add a safety/governance before/after:

```
Context Problem — Before CRP:
Task: "Write a 30-section K8s guide"
→ Output: 592 words, 8/30 sections, truncated mid-sentence

Context Problem — With CRP:
→ Output: 6,993 words, 25/30 sections, quality tier A, full DAG

Safety Problem — Without CRP:
AI call made → raw LLM response returned
→ No hallucination risk score
→ No provenance record
→ No compliance evidence
→ No Safety Policy enforcement
→ EU AI Act audit impossible

Safety Problem — With CRP:
AI call made → DPE runs (< 50ms overhead) → response delivered
CRP-Safety-Hallucination-Risk: LOW
CRP-Provenance-HMAC: sha256:4fa8e921...
CRP-Compliance-EU-AI-Act: LIMITED
CRP-Compliance-Audit-Trail-URI: https://comply.crprotocol.io/t/...
→ Fully governed. Zero application code changes.
```

---

## The Spec Documents That Support Each Page

| Site Page | Primary Spec Documents |
|-----------|----------------------|
| autocyberai.com/protocol/ | SPEC-001 (architecture), SPEC-016 (Gateway), SPEC-010 (regulatory) |
| crprotocol.io homepage | SPEC-001, SPEC-002, SPEC-005 (DPE), SPEC-017 (Zero-CKF) |
| crprotocol.io/spec/ | All 17 spec documents |
| crprotocol.io/headers/ | SPEC-002 exclusively |
| crprotocol.io/safety/ | SPEC-005, SPEC-006, SPEC-012, SPEC-015 |
| crprotocol.io/protocol/continuation/ | SPEC-003, SPEC-004, SPEC-005 (Stages 6-9) |
| crprotocol.io/compliance/ | SPEC-010, SPEC-011, SPEC-015 |
| crprotocol.io/products/gateway/ | SPEC-016, SPEC-017 |
| crprotocol.io/products/scan/ | SPEC-013 |
| crprotocol.io/conformance/ | SPEC-014 |
| Standards submission page | SPEC-001, SPEC-002, SPEC-006, SPEC-014 |

---

## The Exact Page Structure for crprotocol.io (MkDocs nav.yml update)

```yaml
nav:
  - Home: index.md
  - Why CRP?: why-crp.md
  - Spec:
    - Overview: spec/index.md
    - CRP-SPEC-001 Core Protocol: spec/CRP-SPEC-001-core-protocol.md
    - CRP-SPEC-002 Headers: spec/CRP-SPEC-002-headers.md
    - CRP-SPEC-003 Envelope: spec/CRP-SPEC-003-envelope.md
    - CRP-SPEC-004 Continuation: spec/CRP-SPEC-004-continuation.md
    - CRP-SPEC-005 Decision Provenance Engine: spec/CRP-SPEC-005-dpe.md
    - CRP-SPEC-006 Safety Policy: spec/CRP-SPEC-006-safety-policy.md
    - CRP-SPEC-007 Session Token: spec/CRP-SPEC-007-session-token.md
    - CRP-SPEC-008 Dispatch Strategies: spec/CRP-SPEC-008-dispatch.md
    - CRP-SPEC-009 CKF: spec/CRP-SPEC-009-ckf.md
    - CRP-SPEC-010 Regulatory Mapping: spec/CRP-SPEC-010-regulatory-mapping.md
    - CRP-SPEC-011 Audit Trail: spec/CRP-SPEC-011-audit-trail.md
    - CRP-SPEC-012 Multi-Agent Safety: spec/CRP-SPEC-012-multi-agent-safety.md
    - CRP-SPEC-013 GitHub Action: spec/CRP-SPEC-013-github-action.md
    - CRP-SPEC-014 Conformance: spec/CRP-SPEC-014-conformance.md
    - CRP-SPEC-015 Security & Privacy: spec/CRP-SPEC-015-security-privacy.md
    - CRP-SPEC-016 Gateway Service: spec/CRP-SPEC-016-gateway-service.md
    - CRP-SPEC-017 Zero-CKF Mode: spec/CRP-SPEC-017-zero-ckf-mode.md
  - Safety:
    - The Safety Case: safety/index.md
    - DPE Pipeline: safety/dpe.md
    - Safety Policy Language: safety/safety-policy.md
    - Coverage & Limits: safety/coverage.md
    - The Black Box Question: safety/black-box.md
  - Getting Started:
    - Installation: getting-started/installation.md
    - Quick Start: getting-started/quickstart.md
    - Providers: getting-started/providers.md
    - Local Models: getting-started/local-models.md
    - CLI Reference: getting-started/cli.md
    - Licensing: getting-started/licensing.md
  - Protocol:
    - Core Protocol: protocol/core.md
    - Context Envelope: protocol/envelope.md
    - Headers Reference: protocol/headers.md        # NEW
    - Safety Policy: protocol/safety-policy.md      # NEW
    - Session Token: protocol/session-token.md      # NEW
    - Dispatch Strategies: protocol/dispatch-strategies.md
    - Continuation & Stitching: protocol/continuation.md
    - Extraction Pipeline: protocol/extraction.md
    - Contextual Knowledge Fabric: protocol/ckf.md
    - Quality Tiers: protocol/quality-tiers.md
    - Provenance & Hallucination Detection: protocol/provenance.md
    - Multi-Agent Safety: protocol/multi-agent.md   # NEW
    - Zero-CKF Mode: protocol/zero-ckf-mode.md      # NEW
    - Conformance Levels: protocol/conformance.md   # NEW
    - Meta-Learning: protocol/meta-learning.md
    - Research Foundations: protocol/research.md
  - Guides:
    - Demo App: guides/demo-app.md
    - Streaming: guides/streaming.md
    - Multi-Turn Conversations: guides/multi-turn.md
    - Data Ingestion: guides/ingestion.md
    - Session Persistence: guides/session-persistence.md
    - HTTP Sidecar: guides/sidecar.md
  - Compliance:
    - EU AI Act: compliance/eu-ai-act.md
    - ISO 42001: compliance/iso-42001.md
    - GDPR: compliance/gdpr.md
    - NIST AI RMF: compliance/nist-ai-rmf.md
    - Security: compliance/security.md
  - API Reference:
    - Client: api/client.md
    - Dispatch Methods: api/dispatch.md
    - Compliance API: api/compliance.md
    - JSON Schemas: api/schemas.md
  - Testing & Benchmarks:
    - Running Tests: testing/running-tests.md
    - Benchmarks: testing/benchmarks.md
    - Reproduce Benchmarks: testing/reproduce.md
  - Contributing: contributing.md
  - Standards Track: standards.md    # NEW
  - Products:
    - Overview: products/index.md
    - CRP Comply: products/comply.md
    - CRP Gateway: products/gateway.md     # NEW
    - CRP Visualise: products/visualise.md # NEW
    - CRP Scan: products/scan.md           # NEW
    - CRP Scribe: products/scribe.md
  - Terms of Service: terms-of-service.md
```

---

## The "Black Box" Answer: Site-Ready Language

This is the copy to use on the /safety/black-box page and in any FAQ:

---

**"If LLMs are black boxes, how can CRP make any guarantees about what they produce?"**

CRP makes no claims about what happens inside the model. It governs what goes in and what is done with what comes out.

The LLM is given a precisely constructed Context Envelope (the input layer). What it produces is then subjected to 13 stages of analysis: claim detection, attribution analysis, fabrication detection, distortion detection, entailment scoring, contradiction detection, repetition checking, completeness verification, and flow analysis (the output layer). Based on those analyses, CRP decides whether to deliver, flag, halt, or re-dispatch the response.

This is not fundamentally different from how every other form of governance works:

- A financial auditor does not know what was in an accountant's mind. They verify whether the numbers are consistent and traceable.
- A breathalyser does not know what is happening inside someone's liver. It measures what is present in the output.
- HTTP security headers do not know what is inside a web server's database. They enforce policies on what gets delivered.

CRP is designed to work with LLM opacity, not despite it. The protocol's value is not predicated on understanding model internals — it is predicated on the verifiable, measurable properties of model outputs.

What CRP cannot do: prevent a model from having biased training data, alter model weights, or predict behaviour in all future scenarios. These are research problems being worked on by alignment researchers at Anthropic, Google DeepMind, and others.

What CRP does do: govern, record, and analyse every observable output from every inference call, in a cryptographically verifiable, regulation-aligned, language-agnostic way — and enforce policies on those outputs before they reach application code or end users.

The black box is real. The governance of its observable surface is also real. CRP is that governance layer.

---

*© 2025–2026 AutoCyber AI Pty Ltd. Internal strategy document.*

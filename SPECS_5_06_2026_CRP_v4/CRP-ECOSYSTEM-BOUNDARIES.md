# CRP Ecosystem — What Each Product Is, and the Boundaries Between Them

**Purpose:** the single clear answer to "what is the Gateway, what is Comply,
what is Scan, and how do they fit" — so nothing overlaps or reimplements.

---

## THE ONE-LINE DEFINITIONS

| Product | One line | Question it answers |
|---------|----------|---------------------|
| **CRP Protocol** | the open standard + reference implementation | *(the engine — not sold)* |
| **CRP Scan** | finds ungoverned AI in your code | "where is my AI ungoverned?" — FIND |
| **CRP Gateway** | the managed runtime that governs every call | "how do I run governed AI?" — RUN |
| **CRP Comply** | turns runtime evidence into audit-ready proof | "how do I prove it to an auditor?" — PROVE |
| **Authoritative Domain Agent** | a provably-grounded expert agent on an official corpus | "can I trust this expert answer?" — TRUST |

---

## THE PIPELINE (how they connect)

```
   FIND                RUN                      PROVE
┌────────┐        ┌──────────────┐        ┌──────────────┐
│  SCAN  │───────▶│   GATEWAY    │───────▶│   COMPLY     │
│        │ finds  │              │ runtime│              │
│ ungovern│ →fix  │ governs every│ evidence│ packages as │
│ -ed AI │ is:    │ call; full   │ streams │ audit-ready │
│        │ "route │ context suite│ to──────│ evidence +  │
│        │ through│ + visual     │        │ expert agent │
│        │ Gateway"│ console      │        │ guidance     │
└────────┘        └──────────────┘        └──────────────┘
                         │
                         │ can host
                         ▼
                  ┌──────────────┐
                  │ DOMAIN AGENT │  provably-grounded expert agents
                  │ (ADA)        │  bound to an official corpus
                  └──────────────┘

The remediation Scan recommends = "route through the Gateway."
The Gateway's runtime output = the evidence Comply packages.
Comply's expert agent = the first Authoritative Domain Agent.
One config (SPEC-037) shared across all of them.
```

---

## CRP GATEWAY — the RUNTIME product (SPEC-016, 043)

**What it is:** a managed, hosted, subscription service. Point your app at
it; every LLM call is governed (safety, provenance, compliance signals) and
you get the full context-management suite (CDR, CDGR, CSO, STL, knowledge,
sessions, tools) — via API AND a low-code/no-code visual console.

**Purpose:** run governed, context-managed AI in production without building
any of it. The Cloudflare-for-AI-governance.

**Customer:** developers and companies running AI in production; teams with
weak/local models who want the quality lift; non-technical builders who use
the visual console.

**Model:** rolling subscription, usage-based (Free / Developer / Team /
Business / Enterprise).

**The key upgrade (SPEC-043):** the visual console — drag capability blocks
(knowledge, depth, safety, checkpoints, tools, model) into a governed
pipeline, test in a playground, deploy as a live endpoint, export as code.
No-code, low-code, and code, all on one shared config.

**What it is NOT:** a compliance platform. It produces evidence; it does not
package it for auditors. That's Comply.

---

## CRP COMPLY — the COMPLIANCE product (SPEC-040, 042)

**What it is:** the compliance and audit-readiness platform. Three layers —
Programme (policy), Artefacts (your evidence), Evidence (runtime audit). An
expert agent guides you through EU AI Act / ISO 42001 / GDPR / NIS2. Produces
audit-ready deliverables and signed, article-mapped evidence packs.

**Purpose:** become audit-ready with REAL auditable evidence of operations,
guided by an expert agent. The destination after Scan for paid remediation.

**Customer:** compliance officers, companies facing audits/regulation, teams
in funding due-diligence or procurement.

**Model:** paid tiers (the Scan→Comply remediation funnel lands here);
audited-call quota + prepaid credits.

**The key upgrade (SPEC-042):** stop reimplementing CRP badly. Retire the
weak bespoke proxy; consume the GATEWAY's runtime evidence instead. Add the
safety layer it lacks. Connect to Scan via a "Connect Repo" page. Upgrade the
agent to CRP v4 retrieval.

**What it is NOT:** a runtime. It does not govern calls itself — it consumes
the Gateway's governance output and proves it. (The current bespoke proxy is
the mistake SPEC-042 fixes.)

---

## CRP SCAN — the DISCOVERY product (SPEC-013, 036, 039)

**What it is:** a GitHub Action + semantic codebase scanner. Uses CRP's own
CKF to ingest a repo as a knowledge graph and trace AI calls through wrappers
and indirection (SPEC-039). Finds every ungoverned AI call.

**Purpose:** find where AI is ungoverned, and route to the fix.

**Customer:** developers; the top of the funnel.

**Model:** free detection (creates awareness) → paid remediation (SPEC-036) →
lands in Comply.

**The connection:** findings → Comply's Connect Repo / Inbox. The remediation
is "route through the Gateway." Scan is the front door of the ecosystem.

---

## AUTHORITATIVE DOMAIN AGENT — the TRUST product (SPEC-044)

**What it is:** a CRP-governed agent bound to an authoritative official corpus,
guaranteed to speak only from it, citing every claim, refusing to fabricate.

**Purpose:** trustworthy domain-expert answers whose authority is provable —
the gap in agentic AI the user identified.

**Customer:** any high-stakes domain — compliance (the first instance, in
Comply), legal, medical, standards, internal policy, financial.

**Model:** a Gateway capability (bind-your-corpus pipeline) and/or standalone
vertical products.

**The connection:** Comply's expert agent is the first ADA. The pattern
generalises to any domain with an official body of truth. CRP's per-claim
grounding + provenance make it possible.

---

## WHY THE BOUNDARY MATTERS

The blur to avoid: **Comply running its own runtime.** Comply's current
bespoke proxy is a weak parallel to the Gateway. The clean architecture:
- ONE runtime (the Gateway) governs calls and provides context capability.
- ONE compliance layer (Comply) consumes that runtime's evidence and proves it.
- ONE scanner (Scan) finds what isn't yet governed.
- ONE config (SPEC-037) shared across all.

Each product does one job. They compose into a pipeline. None reimplements
another. That is the ecosystem operating at its maximum intention.

---

*AutoCyber AI Pty Ltd · contact@crprotocol.io · crprotocol.io*

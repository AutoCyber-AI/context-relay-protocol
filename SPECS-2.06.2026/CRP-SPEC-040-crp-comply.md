# CRP-SPEC-040: CRP Comply — The AI Safety & Compliance Control Centre

**Document:** CRP-SPEC-040  
**Title:** Context Relay Protocol (CRP) — CRP Comply: The Product Specification for the AI Safety Control Centre and Compliance Evidence Platform  
**Version:** 1.0.0  
**Status:** Foundational — The Revenue Product  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Consumes:** the governance/safety/audit output of the entire protocol  
**Prerequisites:** CRP-SPEC-010, 011, 033, 034, 036

---

## Abstract

CRP Comply is referenced throughout the specification suite as the destination product — the place safety is controlled, checkpoints are resolved, remediations are applied, and compliance evidence is generated — yet it has had no product specification of its own. It is the primary revenue engine (the protocol is open; Comply is monetised) and, per SPEC-034 §14, the AI Safety Control Centre. This document specifies CRP Comply as a product: what it is, who uses it, its core surfaces (the safety control plane UI, the human-in-the-loop checkpoint inbox, the compliance evidence engine, multi-tenant organisation management, the observability dashboard), how it generates regulatory artifacts (EU AI Act Art. 11 Technical Documentation, FRIA, DPIA) from live protocol data rather than questionnaires, the Scan-to-Comply remediation flow, and the pricing model. CRP Comply is where CRP's runtime governance becomes an auditable, manageable, human-overseen, regulator-ready operation — the bridge from "the protocol governs your AI" to "you can prove it, control it, and act on it from one place."

---

## 1. What CRP Comply Is

CRP Comply is a SaaS platform that turns the CRP protocol's runtime governance output into a managed, visible, actionable control centre. The protocol produces governance signals, audit events, risk scores, and checkpoint requests on every AI call. Comply is where those land, are managed, and become regulatory evidence.

```
CRP PROTOCOL (runtime)              CRP COMPLY (management + evidence)
  every AI call produces:    ───►     - sees every call's governance
   - risk/grounding signals             - controls safety settings (control plane)
   - audit chain events                 - resolves checkpoints (HITL inbox)
   - checkpoint requests                - generates compliance evidence
   - compliance classification          - applies Scan remediations
   - tool/decision provenance           - multi-tenant org management
```

### 1.1 The Positioning

CRP Comply is the **AI Safety Control Centre** — not merely a compliance tool. It is where an organisation:
- **Sees** the safety posture of all its AI systems
- **Controls** safety settings without touching code
- **Resolves** the human-in-the-loop decisions CRP routes to people
- **Proves** compliance with auditable evidence generated from live data
- **Acts** on the ungoverned-AI findings CRP Scan surfaces

### 1.2 Who Uses It

| Role | Uses Comply for |
|------|----------------|
| Developer | connecting systems, seeing AI call quality/risk, applying Scan remediations |
| AI Safety / ML lead | tuning safety settings, defining checkpoints, monitoring risk trends |
| Compliance officer | generating EU AI Act / GDPR evidence, audit review |
| Reviewer (domain expert) | the checkpoint inbox — approving/rejecting flagged decisions |
| Executive | the posture dashboard — overall AI risk and compliance status |

---

## 2. Core Surface 1 — The Safety Control Plane UI

The visual rendering of SPEC-033's Safety Control Plane and SPEC-037's unified config.

```
┌─ AI SAFETY CONTROL CENTRE ────────────────────────────────────┐
│  Systems: 4 connected     Risk posture: ●LOW    Findings: 2    │
│                                                                │
│  ┌─ SETTINGS ──────────────┐  ┌─ CHECKPOINTS ───────────────┐ │
│  │ Grounding   [███████░] 85│  │ ● >$1M txns → risk-team     │ │
│  │ Halt on     [ HIGH ▾]    │  │ ● trades → desk (2 approve) │ │
│  │ PII         [Redact ▾]   │  │ + add checkpoint            │ │
│  │ Jailbreak   [●ON]        │  └──────────────────────────────┘ │
│  │ Toxicity    [●ON]        │  ┌─ CUSTOM RULES ──────────────┐ │
│  │ Secrets     [Block ▾]    │  │ ● no_competitor_mentions    │ │
│  └──────────────────────────┘  │ + add rule                  │ │
│                                 └──────────────────────────────┘ │
│  Coverage: EU AI Act ✓ Art 9,13,14  GDPR ✓  ISO 42001 ✓        │
└────────────────────────────────────────────────────────────────┘
```

Every change is a governed, audited event (changing safety config is itself
logged). Edits here write to the unified config store (SPEC-037 §5) and take
effect on the next call — a compliance officer tightens grounding without a
code deploy.

---

## 3. Core Surface 2 — The Checkpoint Inbox (Human-in-the-Loop)

The home for SPEC-033/034's inline checkpoints. When a checkpoint fires
anywhere in any connected system, it lands here for a human to resolve.

```
┌─ CHECKPOINT INBOX ──────────────── 3 pending ─────────────────┐
│  ⏳ Loan approval — $2.1M             [from: loan-service]     │
│     "Recommend approval, DTI 0.3..."  risk: MEDIUM            │
│     Reasoning: [view CSO]  Evidence: [3 sources]             │
│     ┌──────────┬──────────┬─────────────────┐                │
│     │ APPROVE  │  REJECT  │ APPROVE W/ EDIT  │  ⏱ 1h 40m left │
│     └──────────┴──────────┴─────────────────┘                │
│  ─────────────────────────────────────────────────────────── │
│  ⏳ External email draft               [from: support-bot]    │
│  ⏳ Trade execution: SELL 5000 AAPL    [needs 2 approvers]    │
└────────────────────────────────────────────────────────────────┘
```

Each resolution runs the SPEC-034 lifecycle (approve/reject/edit/timeout),
re-verifies edits through the DPE, feeds rejections back as constraints, and
records a signed `CHECKPOINT_RESOLVED` event — the EU AI Act Art. 14 human-
oversight evidence. Reviewers can be routed by role, and the inbox supports
email/Slack/webhook delivery so reviewers act where they already work.

---

## 4. Core Surface 3 — The Compliance Evidence Engine

The feature that justifies the price: generating regulatory artifacts from
live protocol data, not questionnaires.

### 4.1 What It Generates

| Artifact | Regulation | Generated from |
|----------|-----------|----------------|
| Technical Documentation | EU AI Act Art. 11 | system registry + audit chain + safety config |
| FRIA (Fundamental Rights Impact Assessment) | EU AI Act Art. 27 | risk classification + checkpoint records |
| DPIA (Data Protection Impact Assessment) | GDPR Art. 35 | PII detection log + data-flow records |
| Conformity declaration support | EU AI Act Art. 47 | conformance results + control coverage |
| Audit reports | SOC 2 / ISO 42001 | the HMAC audit chain (SPEC-011) |
| Risk-management records | EU AI Act Art. 9 | continuous risk scoring over time |

### 4.2 Why This Is Different From Every Other Compliance Tool

Traditional compliance tools ask humans to fill in questionnaires describing
what their AI *supposedly* does. CRP Comply generates evidence from what the
AI *actually did* — every call's real risk score, real grounding, real PII
handling, real human oversight, cryptographically chained. The evidence is
not a description; it is a tamper-evident record. This is the moat:
**questionnaire compliance is claimed; CRP compliance is proven.**

### 4.3 Continuous, Not Point-in-Time

Because the protocol governs every call continuously, the evidence is always
current. A regulator asking "show me your risk management for the last
quarter" gets a generated report from the actual audit chain, not a stale
document written once. Continuous compliance is a structural property of
running on CRP.

---

## 5. Core Surface 4 — Observability Dashboard

For developers and ML leads (distinct from compliance): see your AI
operation's health.

```
┌─ AI OPERATIONS ───────────────────────────────────────────────┐
│  Calls today: 48,201   Avg quality: A   Avg risk: LOW          │
│  Halts: 12    Checkpoints: 3    Fabrications caught: 47         │
│                                                                │
│  Quality trend  ▁▂▃▅▆▇▇▇  ↑ improving                          │
│  Risk by system: loan-svc ●LOW  support ●LOW  research ●MED    │
│  Top grounding gaps: [research-bot: 0.68 avg] → ingest more    │
│  Cost: $1,240 this month  (CRP saved est. 38% via positioning) │
└────────────────────────────────────────────────────────────────┘
```

This makes CRP's value visible: fabrications caught, quality trending up,
token savings from positioning (SPEC-031), grounding gaps that signal where
to ingest more knowledge. It turns governance from invisible plumbing into a
dashboard a team checks daily.

---

## 6. Core Surface 5 — Scan Remediation Inbox

Where CRP Scan findings (SPEC-036) land for action.

```
┌─ UNGOVERNED AI — REMEDIATIONS ────────────── 2 findings ──────┐
│  ⚠ services/support.py:42  ungoverned OpenAI call             │
│     Fix: govern make_client() (llm/client.py:9) → fixes 3 sites│
│     [ Open PR ]  [ View diff ]  [ Dismiss ]                    │
│  ⚠ research-bot  no safety policy configured                  │
│     Recommended: require_grounding=0.75, halt=CRITICAL         │
│     [ Apply in Control Plane ]  [ Customise ]                  │
└────────────────────────────────────────────────────────────────┘
```

Code fixes open PRs (SPEC-036 §3); config fixes apply to the Control Plane
(SPEC-036 §4). This closes the Scan→signup→remediate→verify loop inside
Comply.

---

## 7. Multi-Tenant Organisation Management

| Capability | Detail |
|-----------|--------|
| Organisations | top-level tenant; data isolated (SPEC-016 §4) |
| AI systems | each registered system has its own classification, policy, audit |
| Teams & roles | developer / safety-lead / compliance / reviewer / admin / viewer |
| Data residency | per-org region (EU/AU/US/UK) for EU AI Act residency |
| SSO / SCIM | enterprise identity integration |
| Approver routing | checkpoints routed to roles/people/teams |

---

## 8. Pricing (the monetisation model)

| Tier | Price | For | Includes |
|------|-------|-----|----------|
| Free | $0 | individuals, trials | 1 system, basic governance dashboard, audit retention 7d, community support |
| Pro | ~$49/seat/mo | small teams | unlimited systems, checkpoint inbox, evidence generation, 90d retention, Scan remediations |
| Business | ~$499/mo + usage | scale-ups | SSO, multi-team, custom rules, 1y retention, priority support, data residency |
| Enterprise | custom | regulated orgs | on-prem/private, unlimited retention, dedicated support, custom compliance frameworks, SLAs |

The open protocol drives adoption; Comply captures revenue where the value
is managed and proven. The funnel: CRP Scan (free, finds problems) → Comply
signup (free) → Pro (resolve + prove) → Business/Enterprise (scale + govern).

---

## 9. The Relationship to the Protocol and Other Products

```
CRP PROTOCOL (open)  ──── governs every call, emits signals
        │
        ├─ CRP GATEWAY (SPEC-016)  ── hosted execution; streams to Comply
        ├─ CRP SCAN (SPEC-013/036/039) ── finds ungoverned AI → Comply remediations
        └─ CRP COMPLY (this spec)  ── control, oversight, evidence, observability
                                        THE management + revenue layer
```

Comply is the surface where all the protocol's governance becomes a product.
The Gateway runs CRP; Scan finds where CRP is missing; Comply is where humans
control it and regulators are satisfied.

---

## 10. Honest Status & Limits

CRP Comply is a substantial product build — five major surfaces, multi-tenant
infrastructure, evidence generation, integrations. It is the largest single
engineering effort in the ecosystem and should be built incrementally: the
safety control plane + observability + audit first (immediate value on top of
the Gateway), then the checkpoint inbox, then the evidence engine, then Scan
remediation integration.

The compliance evidence engine generates artifacts from protocol data, but
regulatory artifacts often require human-authored context (intended purpose,
deployment context) that the protocol does not capture — Comply generates the
evidence-backed sections and prompts humans for the narrative sections. It
accelerates and grounds compliance; it does not fully automate legal judgment.

Evidence generation asserts what the protocol recorded; it cannot attest to
AI behaviour outside CRP's governance (ungoverned calls produce no evidence —
which is exactly why CRP Scan exists, to find them).

---

## 11. References

- CRP-SPEC-010 — Regulatory Mapping (what evidence maps to which control)
- CRP-SPEC-011 — Audit Trail (the evidence source)
- CRP-SPEC-016 — Gateway (streams governance to Comply)
- CRP-SPEC-033/034 — Safety Control Plane & Checkpoints (the control + inbox)
- CRP-SPEC-036/039 — Scan Remediation (the remediation inbox)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

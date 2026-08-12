# CRP-SPEC-036: CRP Scan Remediation Engine

**Document:** CRP-SPEC-036  
**Title:** Context Relay Protocol (CRP) — CRP Scan Remediation Engine: From Detection to Fix  
**Version:** 1.0.0  
**Status:** Foundational — Product-Completing  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Extends:** CRP-SPEC-013 (GitHub Action / Scan)  
**Prerequisites:** CRP-SPEC-013, CRP-SPEC-016, CRP-SPEC-032, CRP-SPEC-033

---

## Abstract

CRP Scan (SPEC-013) detects ungoverned AI calls in a codebase and directs the developer to sign up — and then the specification stops. What the remediation actually *is*, where it comes from, how it reaches the developer, and what happens after signup were never defined. The funnel terminated in a void. This document defines the **Remediation Engine**: the complete path from a detected finding to a working fix. Remediations are concrete and code-level — CRP Scan does not merely say "this call is ungoverned," it produces the exact diff that governs it, opens it as a pull request, and (where the issue is configuration rather than code) wires it to the developer's CRP Comply control plane. The engine has three remediation classes — **code fixes** (governed-client diffs applied as PRs), **configuration fixes** (safety/policy settings applied in CRP Comply), and **guided fixes** (where human judgment is needed, a checkpoint-style task) — each with a defined source, delivery mechanism, and post-application verification. This turns CRP Scan from a detector that creates anxiety into a tool that resolves it.

---

## 1. The Void This Closes

SPEC-013 specified detection (find OpenAI/Anthropic/LangChain calls lacking governance), SARIF output, and the signup funnel. The unanswered questions:

1. **What is a remediation?** A code change? A setting? Advice?
2. **Where does it come from?** Generated how, from what knowledge?
3. **How is it delivered?** Inline? PR? Dashboard?
4. **What happens after signup?** The funnel's payoff was undefined.
5. **How does CRP Comply fit?** Stated as "utilised" but not how.

Without these answers, CRP Scan is a tool that tells you something is wrong and then abandons you. The Remediation Engine is the answer.

---

## 2. The Three Remediation Classes

Every finding maps to one of three remediation classes, determined by what kind of fix it needs:

```
FINDING
   │
   ├─ Fixable by changing code?         → CODE FIX (§3)
   │    e.g. ungoverned OpenAI call      → PR with governed-client diff
   │
   ├─ Fixable by changing configuration? → CONFIG FIX (§4)
   │    e.g. no safety policy set         → applied in CRP Comply control plane
   │
   └─ Needs human judgment?              → GUIDED FIX (§5)
        e.g. should this be HITL?          → a guided task / checkpoint
```

---

## 3. Code Fixes — The Governed-Client Diff (PR)

### 3.1 What It Is

The most common finding is an ungoverned AI call. The remediation is the exact code change that routes it through CRP, delivered as a pull request the developer reviews and merges.

**Detected:**
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
response = client.chat.completions.create(model="gpt-4o", messages=msgs)
```

**Remediation PR (the diff CRP Scan generates):**
```diff
  from openai import OpenAI
- client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
+ client = OpenAI(
+     api_key=os.environ["CRP_GATEWAY_KEY"],
+     base_url="https://gateway.crprotocol.io/v1",   # CRP governance
+ )
  response = client.chat.completions.create(model="gpt-4o", messages=msgs)
```

With a PR description explaining: what was ungoverned, what the change does, the env var to set, and a link to the finding. The developer reviews a normal PR — no new workflow.

### 3.2 Where the Fix Comes From

Code fixes are generated from a **remediation template library** keyed by detection pattern. Each detection rule (SPEC-013 has rules CRP001–005) has one or more paired remediation templates:

| Detection | Remediation template |
|-----------|---------------------|
| CRP001: ungoverned OpenAI call | base_url + key swap diff |
| CRP002: ungoverned Anthropic call | Anthropic-compatible gateway diff |
| CRP003: LangChain LLM without CRP | `CRPChatModel` wrapper diff |
| CRP004: missing safety policy | config fix (§4) + optional code annotation |
| CRP005: no audit/provenance | gateway routing (covers it automatically) + verification |

The templates are deterministic transformations (AST-level edits, not LLM-generated) for the common cases — reliable, reviewable, reproducible. For non-standard integrations, an optional CRP-powered code-fix generator (using CRP itself, governed) proposes a diff, clearly marked as AI-generated-needs-review.

### 3.3 How It's Delivered

```
Scan runs in CI (SPEC-013) → findings produced
   │
   ├─ free tier: SARIF annotations on the PR showing findings +
   │   the remediation diff inline in the annotation (read-only preview)
   │
   └─ paid tier (post-signup): CRP Scan opens a REMEDIATION PR
        - one PR per finding, or one batched PR (configurable)
        - each diff applies the governed-client change
        - PR includes the env var setup + finding link + verification
```

The free tier *shows* the fix (creating the desire); the paid tier *applies* it as a PR (delivering the value). This is the funnel's concrete payoff: signup turns read-only remediation previews into auto-generated PRs.

### 3.4 Post-Application Verification

After a remediation PR is merged, the next scan verifies the finding is resolved: the call now routes through CRP, the finding clears, and the conformance score (SPEC-013) rises. The developer sees measurable progress — findings going from N to zero — not just a one-time fix.

---

## 4. Configuration Fixes — Applied in CRP Comply

### 4.1 What It Is

Some findings are not missing code but missing *governance configuration* — the call is routed through CRP, but no safety policy is set, grounding isn't required, no human oversight exists for a high-risk path. These are fixed in the **CRP Comply control plane** (SPEC-033), not in code.

### 4.2 Where the Fix Comes From and How It's Delivered

```
Finding: "AI call governed but no safety policy configured"
   │
   ▼
CRP Scan → links the finding to the developer's CRP Comply account
   │
   ▼
In CRP Comply: a pre-filled remediation appears in the Safety Control Plane —
   "Recommended: set require_grounding=0.75, halt_on=CRITICAL for this system"
   with a one-click APPLY (writes it to the Safety Manifest, SPEC-033 §5)
```

The remediation is a proposed Safety Manifest change. The developer reviews it in the Comply dashboard and applies it — no code change, just a governance setting. This is precisely how CRP Comply is "utilised": **CRP Scan finds the governance gap; CRP Comply is where the gap is closed.** Scan is the detector, Comply is the control plane, and the remediation flows from one to the other.

### 4.3 The Scan → Comply Handoff

```
crp-scan finding (config class)
   → carries: system identity, detected gap, recommended setting
   → posted to CRP Comply via the Scan→Comply API
   → appears as a pending remediation in the Comply Safety Control Plane
   → developer applies (or modifies) → Safety Manifest updated
   → next scan confirms the gap closed
```

This handoff is the structural link between the two products: they share the finding and its remediation, so a developer moves from "Scan told me X is ungoverned" to "I fixed it in Comply" in one continuous flow.

---

## 5. Guided Fixes — Where Human Judgment Is Needed

### 5.1 What It Is

Some findings cannot be auto-fixed because the right answer depends on the developer's intent. Example: CRP Scan detects an AI call that makes a financial decision. Whether that needs a human-in-the-loop checkpoint (SPEC-033) is a judgment only the developer can make.

### 5.2 How It's Delivered

The remediation is a **guided task** — a structured prompt in the Comply dashboard (or the PR) that explains the situation, presents the options, and applies the chosen one:

```
GUIDED REMEDIATION
  Finding:  This AI call appears to make loan-approval decisions.
  Question: Should approvals require human sign-off?
  Options:
    [ Add a checkpoint ]  → inserts crp.checkpoint() (SPEC-033) at this call,
                            routes to an approver you choose
    [ Set a risk threshold ] → auto-checkpoint only above $X
    [ No oversight needed ]  → records the decision + rationale (audited)
```

Choosing "Add a checkpoint" generates the code diff (a code fix, §3) that inserts the checkpoint. Guided fixes thus *resolve into* code or config fixes once the human judgment is made — they are the bridge for findings that need a decision before a fix can be generated.

---

## 6. The Complete Remediation Flow

```
1. DETECT (SPEC-013) — scan finds ungoverned/under-governed AI usage in CI
2. CLASSIFY — each finding → code fix / config fix / guided fix
3. PREVIEW (free) — findings + remediation previews shown as PR annotations
4. SIGNUP — developer signs up (the funnel; SPEC-016 §3.3 pre-fills from scan)
5. REMEDIATE (paid):
     code fixes   → auto-generated PRs (governed-client diffs)
     config fixes → pre-filled remediations in CRP Comply control plane
     guided fixes → structured tasks that resolve into code/config fixes
6. APPLY — developer merges PRs / clicks apply in Comply
7. VERIFY — next scan confirms findings cleared; conformance score rises
8. MONITOR — ongoing scans keep the codebase governed as it changes
```

The funnel now has a defined payoff at every step: detection creates awareness, previews create desire, signup unlocks application, and verification proves value — closing the loop SPEC-013 left open.

---

## 7. Where Remediations Come From (Summary)

| Class | Source | Generation | Reliability |
|-------|--------|-----------|-------------|
| Code fix (common) | Remediation template library | Deterministic AST edits | High — reviewable diffs |
| Code fix (non-standard) | CRP-powered generator | AI-generated, governed by CRP itself, marked for review | Medium — flagged as needs-review |
| Config fix | Safety Manifest recommendations | Rule-based from the finding type | High — proposed settings |
| Guided fix | Decision templates | Human chooses; resolves to code/config | High — human-confirmed |

The common cases are deterministic and reliable. The novel cases use CRP to remediate CRP gaps (CRP generating its own governance code, itself governed) — a fitting dogfooding, always developer-reviewed.

---

## 8. Pricing Alignment (with SPEC-013)

| Tier | Remediation capability |
|------|----------------------|
| Free | Detection + SARIF findings + remediation *previews* (read-only) |
| Pro ($29/repo/mo, SPEC-013) | Auto-generated remediation PRs + Comply config remediations |
| Business | + batched remediation, custom remediation templates, guided-fix workflows |
| Enterprise | + policy-as-code remediation, org-wide remediation campaigns |

The free tier shows the fix; paying applies it. This is the conversion mechanism — the value of seeing exactly what's wrong, then paying to have it fixed automatically.

---

## 9. Honest Status & Limits

The deterministic code-fix templates cover the common integration patterns (OpenAI, Anthropic, LangChain, LlamaIndex). Long-tail or heavily-customised integrations fall to the AI-generated remediation path, which is less reliable and always marked needs-review — CRP Scan does not silently apply AI-generated code changes.

Remediation PRs change a developer's code; they are always proposals (PRs), never direct commits to protected branches. The developer reviews and merges. This is non-negotiable — an automated tool must not modify code without review.

Config remediations propose Safety Manifest changes; they do not auto-apply (the developer/compliance officer confirms in Comply). Auto-applying safety settings would itself be a safety risk.

The engine detects and remediates *governance gaps* (ungoverned calls, missing policy). It does not remediate general code bugs or non-CRP issues — it is scoped to AI-governance remediation, not a general code-fixing tool.

---

## 10. References

- CRP-SPEC-013 — GitHub Action / Scan (detection this completes)
- CRP-SPEC-016 — Gateway (the base_url remediations target; signup funnel)
- CRP-SPEC-032 — Developer Experience (the governed-client patterns used in fixes)
- CRP-SPEC-033 — Safety Control Plane (where config remediations apply)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

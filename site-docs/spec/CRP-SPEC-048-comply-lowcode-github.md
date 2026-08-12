# CRP-SPEC-048: No-Code Governance via Scan, GitHub Connection & Result-Preserving Signup

**Document:** CRP-SPEC-048  
**Title:** Context Relay Protocol (CRP) - Truly No-Code Governance Through Scan-Driven Remediation, Secure GitHub Connection, and Result-Preserving Post-Detection Signup  
**Version:** 2.0.0  
**Status:** Foundational - UX & Integration  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Extends:** CRP-SPEC-033, 036, 039, 040, 042  
**Prerequisites:** CRP-SPEC-033, 036, 039, 040, 042, 047

---

## Abstract

This document specifies how CRP Comply becomes *truly* no-code by closing the loop between CRP Scan and AI governance: Scan semantically identifies the exact code locations needing governance (SPEC-039), Comply presents the user with what governance is available and applicable at each location, the user expresses what they want in plain language and clicks, and CRP **translates that intent back into the exact protocol configuration and code** to implement it - because CRP knows its own specifications. It also specifies the secure GitHub connection (public/private repos) Comply needs, and - critically - a **result-preserving signup flow** so that a user who runs a Scan *before* signing up does not lose their findings: results are held against an anonymous token and claimed on signup, at the user's choice. The design principle: the user never writes governance code and never loses work; Scan finds the where, the user expresses the what in plain language, and CRP supplies the how.

---

## PART A - TRULY NO-CODE GOVERNANCE (Scan → intent → code)

## 1. Why "Set a Slider" Isn't Yet Truly No-Code

SPEC-048 v1 specified the visual control panel (sliders, toggles). That makes *configuration* no-code, but it still assumes the user knows *what to configure and where*. Truly no-code means the user doesn't even need to know that - the system tells them what's ungoverned, what governance applies, and implements their plain-language choice. The missing link is using **Scan's semantic findings** to drive the governance setup automatically. The user shouldn't hunt for what to govern; CRP should find it and offer the fix.

## 2. The Closed Loop: Find → Offer → Express → Translate → Apply

```
1. FIND (Scan, SPEC-039)
   Semantic scan identifies the EXACT locations needing governance:
   "services/support.py:42 - ungoverned OpenAI call making user-facing
    responses; no grounding, no safety policy, handles customer PII"

2. OFFER (Comply)
   For each finding, Comply presents what governance is AVAILABLE and
   APPLICABLE, in plain language:
   "This call answers customers directly. You can:
     ☐ Require it to stay grounded in your docs (no made-up answers)
     ☐ Redact personal data from responses
     ☐ Halt if the answer looks high-risk
     ☐ Send risky answers to a human first"
   (each option maps to a real CRP capability - SPEC-033/006/005)

3. EXPRESS (user, plain language + clicks)
   The user ticks options and/or types intent:
   "Yes, keep it grounded, redact PII, and a human should approve
    anything mentioning refunds."

4. TRANSLATE (CRP - the key step)
   CRP translates the intent into exact protocol configuration + code,
   because it knows its own specifications:
     - "grounded" → require_grounding: 0.80 (SPEC-006)
     - "redact PII" → pii_handling: redact (SPEC-005 §11)
     - "human approve refunds" → checkpoint_when(
           condition="output contains 'refund'", route_to=<chosen>)
           (SPEC-033 §3)
     - the SafetyManifest entry for support.py:42
     - the one-line base_url change to route the call through CRP

5. APPLY
   - config → written to the SafetyManifest / unified config (SPEC-037)
   - code → offered as a PR (the base_url swap + any checkpoint decorator)
     via the GitHub connection (Part B), reviewable, never auto-committed
```

## 3. The Intent-to-Configuration Translator (the new component)

### 3.1 What It Does

The Translator is the component that converts captured user intent into precise CRP protocol configuration. It is *grounded in CRP's own specifications* - it is, in fact, an Authoritative Domain Agent (SPEC-044) whose authoritative corpus is the CRP specification suite itself. It cannot invent governance that doesn't exist; it maps intent only to real CRP capabilities, citing the spec for each.

```
User intent (plain language + clicks)
   │
   ▼
TRANSLATOR (ADA grounded in the CRP spec corpus, SPEC-044)
   - classify the intent into governance capabilities
   - map each to the exact CRP setting/primitive (with spec citation)
   - generate the SafetyManifest config (SPEC-037)
   - generate any required code (base_url swap, checkpoint decorator)
   - REFUSE / flag if the user asks for something CRP can't do
     (honest - don't fake a capability)
   │
   ▼
Proposed governance: config diff + code diff + plain-language summary
   "Here's what this will do: [plain summary]. Apply?"
```

### 3.2 Capturing Intent in the Best Possible Way

To translate well, intent must be captured well. Comply captures it through a hybrid surface, not free text alone:
- **Structured options first** (checkboxes mapped to capabilities) - unambiguous, directly mappable, the primary path.
- **Plain-language refinement** (a text box) - for nuance the checkboxes miss ("only for enterprise customers", "except internal tools"). The Translator parses this against the capability set.
- **Confirmation in plain language** - the Translator always echoes back what it will do in plain language before applying, so the user verifies intent was captured correctly. This round-trip (intent → config → plain-language echo) is how capture accuracy is ensured.
- **The applied result is editable** - every translated setting lands in the visual control panel (SPEC-048 v1 §2) where the user can see and adjust it. Translation is a starting point, not a black box.

### 3.3 Why This Is Reliable, Not Magic

The Translator maps to a *finite, known set* of CRP capabilities (the specs), not to arbitrary code. It is constrained: it can only produce configurations that are valid CRP settings, validated against the schema (SPEC-037 §6). It cites the spec for each mapping. And it refuses to claim capabilities CRP lacks (honest, per SPEC-044). This bounded translation - plain intent to a known capability set, with confirmation - is reliable in a way that open-ended code generation is not.

## 4. The Per-Finding Governance Card (the UI)

```
┌─ UNGOVERNED AI FOUND ─────────────────────────────────────────┐
│  services/support.py:42                                        │
│  This AI call answers customers directly. It has no grounding, │
│  no safety policy, and may expose personal data.               │
│                                                                │
│  RECOMMENDED GOVERNANCE (tick what you want):                  │
│   ☑ Keep answers grounded in your documents                   │
│   ☑ Redact personal data from responses                       │
│   ☐ Halt high-risk answers automatically                      │
│   ☑ Send answers mentioning "refund" to a human               │
│       → route to: [ support-lead@company.com        ]         │
│                                                                │
│   Anything else?  [ "...only during business hours"        ]  │
│                                                                │
│   ┌─ What this will do ─────────────────────────────────────┐ │
│   │ Require 80% grounding · redact PII · checkpoint on       │ │
│   │ "refund" → support-lead. One-line code change to apply.  │ │
│   └──────────────────────────────────────────────────────────┘ │
│   [ Apply: open PR + save config ]   [ Adjust ]               │
└────────────────────────────────────────────────────────────────┘
```

The user ticked boxes and typed one phrase. CRP found the location, knew the applicable governance, translated the choice into real configuration + code, and showed it back in plain language. That is truly no-code: the user expressed intent; CRP supplied the protocol knowledge and the implementation.

---

## PART B - SECURE GITHUB CONNECTION

## 5. The Connection (GitHub App, public + private)

Comply runs in the cloud, so unlike Scan-in-the-IDE it needs its own secure repo access. The mechanism is a **GitHub App** (least-privilege, per-repo, short-lived tokens):

```
1. User clicks "Connect GitHub" on the Connect Repo page
2. Installs the "CRP Comply" GitHub App, selects repos (public OR private)
3. Grants read-only (code + metadata); optional dedicated-branch write for auto-PRs
4. Comply stores ONLY the installation id (a reference, not a secret)
5. Per scan, Comply mints a short-lived (~1h) installation token, uses it, discards it
```

### 5.1 Security Requirements (unchanged, restated)

- Never store long-lived repo credentials - only the installation id + tenant mapping.
- The GitHub App private key lives in a secrets manager (KMS/vault), AES-256 at rest, never in code.
- Per-tenant isolation of the connection and the derived code-CKF (SPEC-016 §4).
- Code fetched transiently for scanning; the CKF holds the derived graph (findings, call sites), not a repo copy, unless the user opts into persistent code evidence.
- Honour local-vs-hosted storage choice (SPEC-038/040 §6.2).
- Read-only default; auto-PR write is explicit opt-in, dedicated branch only, never protected branches (SPEC-036 §9).
- Instant revocation (from Comply or GitHub); every scan logged to the audit chain (SPEC-011).

### 5.2 The No-Grant Alternative

Users who won't grant repo access upload the `crp-scan` Action's SARIF output (SPEC-042 §5.2). Comply ingests findings without touching the repo - the zero-trust path. Either way, the governance loop (Part A) is identical once findings are in.

---

## PART C - RESULT-PRESERVING POST-DETECTION SIGNUP

## 6. The Problem: Don't Lose the User's Results

A user may run a Scan (e.g. the free GitHub Action, or a public-repo quick scan) *before* signing up or connecting an account. Their findings - the value that motivates signup - must not be lost when they do sign up. But it's their choice whether to keep them. The flow must preserve results and let the user claim them, without forcing an account before they see value.

## 7. The Anonymous-Token → Claim-on-Signup Flow

```
1. ANONYMOUS SCAN
   User runs a scan without an account (public repo, or SARIF upload, or
   the free Action posting results). Comply generates an ANONYMOUS RESULT
   TOKEN (a random, unguessable id) and stores the findings against it,
   with a short TTL (e.g. 30 days) and a clear "unclaimed" status.
   → the user sees their results immediately, tied to result_token=xyz

2. VALUE SHOWN, SIGNUP OFFERED (not forced)
   "We found 7 ungoverned AI calls. Sign up free to save these results,
    get your fixes, and track your compliance - or they'll expire in 30 days."
   The user has already seen the value (the findings). Signup is to KEEP
   and ACT on them, not to see them.

3. SIGNUP / SIGN-IN (identity provider)
   The result_token is carried through the managed sign-up flow (as a query
   param / stored client-side). On account+org creation, the token travels
   with it.

4. CLAIM (the user's choice)
   After auth, Comply asks: "Add these 7 findings to your account?"
   [ Yes, claim them ]  [ No, start fresh ]
   - Claim → the findings are migrated from the anonymous token to the
     user's org (tenant), status flips to "claimed", TTL removed. They
     now feed the Programme, Inbox, and compliance score.
   - Decline → the anonymous results expire naturally; the user starts clean.

5. LINKED
   Claimed findings are now first-class in the user's account - the
   governance loop (Part A) runs on them, remediations appear in the Inbox.
```

### 7.1 Why a Token, Not Forced Signup

Forcing signup before showing results adds friction at the exact moment of curiosity and loses users. Showing results first (against an anonymous token) delivers value immediately; signup is then motivated by *keeping* that value. This is a higher-converting, more honest funnel - and the token mechanism means no result is lost in the gap between "ran a scan" and "made an account."

### 7.2 Security & Privacy of Anonymous Results

- The result token is unguessable (cryptographically random) and the only way to access those results - no enumeration.
- Anonymous results are stored minimally and isolated; they expire by TTL if unclaimed.
- For a scan of a **private** repo, anonymous/pre-auth scanning is NOT offered - private-repo scanning requires the authenticated GitHub App connection (Part B). Anonymous scanning is limited to public repos or user-uploaded SARIF the user already possesses. This prevents pre-auth access to private code.
- On claim, results move into the user's tenant-isolated store; on decline or expiry, they are deleted.

### 7.3 The Choice Is the User's

The spec is explicit: claiming is opt-in. The user decides whether pre-signup results are linked to their new account. Default-offered, never automatic - respecting that some users want a clean start and some want continuity.

---

## 8. The Complete Convenience Flow (all parts together)

```
Run a scan (no account needed, public repo / SARIF)
   → see findings instantly (anonymous token)
   → sign up to keep them (org account created)
   → claim findings (your choice)
   → connect GitHub for live private-repo scanning (GitHub App, secure)
   → for each finding: tick what governance you want, type any nuance
   → CRP translates intent → exact config + code (grounded in its own specs)
   → confirm the plain-language summary
   → Apply: PR opened (one-line governance) + config saved
   → your AI is now governed, with evidence, and you wrote no code
```

This is the maximally convenient, truly-no-code path from "I have ungoverned AI somewhere" to "it's governed, proven, and I never wrote governance code or lost my results."

---

## 9. Honest Status & Limits

The intent-to-configuration Translator (Part A §3) is real NLP/agent engineering - it is an ADA (SPEC-044) over the CRP spec corpus, and its quality depends on that grounding being accurate and its capability-mapping being complete. The structured-options-first design (§3.2) deliberately reduces reliance on free-text parsing; the plain-language box is refinement, not the primary channel, precisely because free-text intent capture is imperfect. The plain-language confirmation echo is the safeguard.

The Translator must refuse to fabricate capabilities (SPEC-044 honesty). If a user asks for governance CRP doesn't have, it must say so, not approximate silently - otherwise the no-code promise becomes a no-code lie.

The GitHub App is standard but high-trust engineering (it touches source); the security model must be implemented exactly and ideally audited.

The result-preserving token flow must enforce the public-repo/SARIF-only limit for anonymous scans (§7.2) - pre-auth scanning of private repos would be a security hole. This boundary is non-negotiable.

Claimed-result migration must be atomic and idempotent (a user might click claim twice); dedupe on the result token.

---

## 10. References

- CRP-SPEC-033 - Safety Control Plane (capabilities the Translator maps to)
- CRP-SPEC-036 - Scan Remediation (the PR mechanism)
- CRP-SPEC-039 - Semantic Code Ingestion (finds the exact locations)
- CRP-SPEC-040/042 - Comply + Connect Repo surface
- CRP-SPEC-044 - Authoritative Domain Agent (the Translator IS one, over CRP's specs)
- CRP-SPEC-047 - Monetisation & account linkage (internal)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

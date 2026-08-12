# Comprehensive Standards & Product Roadmap

_Last updated: 2026-05-29_

## Current Confirmed State

| Item | Status | Notes |
|------|--------|-------|
| IETF I-D `draft-vidiniotis-crp-core` | ✅ Submitted to Datatracker | https://datatracker.ietf.org/doc/draft-vidiniotis-crp-core/ — confirmed live in IANA email from David Dong (ticket #1453152) |
| IETF I-D `draft-vidiniotis-crp-headers-00` | ✅ Submitted to Datatracker | https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/ |
| IETF I-D `draft-vidiniotis-crp-safety-policy-00` | ✅ Submitted to Datatracker | https://datatracker.ietf.org/doc/draft-vidiniotis-crp-spec-006-safety-policy/ — confirmed live 2026-05-29 |
| Emails to IETF mailing lists | ✅ Sent | Email 1 (HTTP WG), Email 2 (AIPREF), Email 3 (Rosenberg), Email 5 (dispatch) — all sent. Email 4 (BoF) pending. |
| Public GitHub spec repo | ✅ Live | https://github.com/AutoCyber-AI/crprotocol-specs |
| CC BY 4.0 LICENSE file in repo | ✅ Done | Added 2026-05-29 |
| SPDX copyright headers on all specs | ✅ Done | Added to all 14 public specs 2026-05-29 |
| Correct repo URLs in spec files | ✅ Done | Fixed all `crprotocol/spec` → `AutoCyber-AI/crprotocol-specs` |
| CONTRIBUTING.md in repo | ✅ Done | Added 2026-05-29 |
| SECURITY.md in repo | ✅ Done | Added 2026-05-29 |
| CRP v3 implemented in reference codebase | ❌ Not done | Phase 5 |
| GitHub Actions (crp-scan) | ❌ Not built | Phase 4 |
| CRP Comply live integration with CRP headers | ❌ Not done | Phase 6 |
| IANA header registration | ⏳ Pending | Ticket #1453152 submitted 2026-05-29. Expect 1–4 weeks. |
| Trademark applications | ✅ Filed | "Context Relay Protocol" filed. Confirm exact mark names and jurisdictions with attorney. |
| Provisional patents | ❌ Not filed | Cannot afford — skipped. Do NOT publish SPEC-012 internals or Stop-Inject mechanism. |
| IETF IPR disclosure | ✅ Submitted | Submitted 2026-05-29 — "IPR disclosure has been submitted, IETF Secretariat notified." May take 1 business day to post. |
| HTTP WG subscription | ✅ Done | Subscribed to ietf-http-wg@w3.org |
| Dispatch WG subscription | ✅ Done | Subscribed to dispatch@ietf.org |


---

## PHASE 0 — Before anything else ✅ LARGELY COMPLETE

### 0.1 — Trademark applications ✅ FILED

"Context Relay Protocol" trademark filed. Confirm with your attorney the exact scope of marks filed (AU/US/EU) and whether CRP Comply™, CRP Gateway™, CRP Scan™ are covered.

### 0.2 — Provisional patents ⛔ SKIPPED (cannot afford)

**Do NOT publish under any circumstances:**
- The Stop-Inject mechanism (CRP-SPEC-006 internal detail — not in the public spec, confirm this)
- CRP-SPEC-012 (multi-agent safety internals) — keep private indefinitely
- Exact DPE weight/multiplier values — public spec uses symbolic `w₁,w₂,w₃,w₄` ✅

### 0.3 — IETF IPR disclosure ✅ DONE

Submitted 2026-05-29. Confirmation: _"Your IPR disclosure has been submitted, and the IETF Secretariat has been notified. It may take one business day to be posted on the IETF Page of Intellectual Property Rights Notices."_

---

## PHASE 1 — Public GitHub spec repo ✅ COMPLETE

**Repo:** https://github.com/AutoCyber-AI/crprotocol-specs

### What is published (all done ✅):

| File | Status |
|------|--------|
| CRP-SPEC-001-core-protocol.md | ✅ Published |
| CRP-SPEC-002-headers.md | ✅ Published |
| CRP-SPEC-003-envelope.md | ✅ Published |
| CRP-SPEC-004-continuation.md | ✅ Published |
| CRP-SPEC-005-dpe.md (scrubbed) | ✅ Published — weights are symbolic only |
| CRP-SPEC-006-safety-policy.md | ✅ Published — Stop-Inject internals NOT included |
| CRP-SPEC-008-dispatch.md | ✅ Published |
| CRP-SPEC-009-ckf.md | ✅ Published |
| CRP-SPEC-010-regulatory-mapping.md | ✅ Published |
| CRP-SPEC-011-audit-trail.md | ✅ Published |
| CRP-SPEC-013-github-action.md | ✅ Published |
| CRP-SPEC-014-conformance.md | ✅ Published |
| CRP-SPEC-015-security-privacy.md | ✅ Published |
| CRP-SPEC-017-zero-ckf-mode.md | ✅ Published |
| README.md | ✅ Complete with standards track table, IANA ticket, badges |
| LICENSE (CC BY 4.0) | ✅ Added 2026-05-29 |
| CONTRIBUTING.md | ✅ Added 2026-05-29 |
| SECURITY.md (security@crprotocol.io) | ✅ Added 2026-05-29 |
| SPDX copyright headers on every spec | ✅ Added 2026-05-29 |

### Keep private (do NOT publish):
- CRP-SPEC-007 — session token signing internals
- CRP-SPEC-012 — multi-agent safety internals
- CRP-SPEC-016 — gateway service internals
- Exact DPE weights/multipliers

### Licence decision: CC BY 4.0 for specs (open); reference implementation stays proprietary/ELv2

The GitHub UI only shows OSI-approved SPDX licences. CC BY 4.0 is NOT in that list. The correct approach:
1. Add a `LICENSE` file with full CC BY 4.0 text ✅ (done)
2. The repo will show "Other" in the GitHub UI — that is fine and correct.
3. The reference implementation (`crp` Python package) remains separately licensed under Elastic License 2.0.

### Can the protocol code be closed source?

The **specification** is CC BY 4.0 (anyone can implement it). The **reference implementation** is Elastic License 2.0 — anyone can use it non-commercially, no competing SaaS. This is the right model: open spec, commercial implementation. Code is currently closed-source and that is fine. Open-sourcing the reference implementation is optional and not required for IETF adoption.

### Repository boilerplate:

All boilerplate items (README, CONTRIBUTING, SECURITY, LICENSE, SPDX headers) are done ✅ as of 2026-05-29.

---

## PHASE 2 — IANA header registration ⏳ SUBMITTED

Submitted 2026-05-29. **IANA ticket #1453152.**

The 10 provisional headers submitted:

| Header | Status |
|--------|--------|
| CRP-Context-Quality-Tier | ⏳ Pending |
| CRP-Safety-Hallucination-Risk | ⏳ Pending |
| CRP-Provenance-HMAC | ⏳ Pending |
| CRP-Compliance-EU-AI-Act | ⏳ Pending |
| CRP-Safety-Policy | ⏳ Pending |
| CRP-Agent-Safety-Budget | ⏳ Pending |
| CRP-Set-Session | ⏳ Pending |
| CRP-Context-ETag | ⏳ Pending |
| CRP-Compliance-Audit-Trail-URI | ⏳ Pending |
| CRP-Safety-Oversight-Mode | ⏳ Pending |

Referenced both I-Ds in submission. Expect reply within 1–2 business days; completion 1–4 weeks.

---

## PHASE 3 — IETF emails ✅ SENT

All four emails sent. Order and status:

| Email | Destination | Status |
|-------|-------------|--------|
| Email 1 — HTTP WG | ietf-http-wg@w3.org | ✅ Sent (subscribed first) |
| Email 2 — AIPREF WG | ai-control@ietf.org | ✅ Sent verbatim with corrected repo URL |
| Email 3 — Jonathan Rosenberg | Author of draft-rosenberg-aiproto-framework | ✅ Sent with corrected repo URL, no meeting offer |
| Email 4 — BoF proposal | iesg@ietf.org | ❌ Pending — needs 10+ supporters first (Phase 9) |
| Email 5 — Dispatch | dispatch@ietf.org | ✅ Sent — **needs update**: re-send or follow up referencing all 3 I-Ds now confirmed |

**⚠️ Important:** Three I-Ds are now confirmed:
- `draft-vidiniotis-crp-core` ✅ — confirmed live (referenced in IANA ticket #1453152 from David Dong)
- `draft-vidiniotis-crp-headers` ✅ — confirmed live
- `draft-vidiniotis-crp-safety-policy` ✅ — referenced in IANA submission; verify on Datatracker

The dispatch email (Email 5) was sent referencing only `draft-vidiniotis-crp-headers`. **Send a follow-up to dispatch@ietf.org** referencing all three I-Ds now confirmed. See updated Email 5b in CRP-IETF-EMAIL-TEMPLATES.md.

**Next actions for IETF:**
- File IPR disclosure at https://datatracker.ietf.org/ipr/add/ covering all 3 drafts
- Send Email 5b (dispatch follow-up with all 3 I-Ds)
- Reply to any IETF mailing list responses within 48 hours
- Track feedback in `FEEDBACK.md` in the spec repo

---

## PHASE 4 — Build the GitHub Action ❌ NOT STARTED
This is the single most important item for the GitHub technology partnership.

What CRP-SPEC-013 defines:

A GitHub Action called crp-scan that detects ungoverned AI calls (OpenAI, Anthropic, LangChain, CrewAI, etc.) in any repo
Outputs SARIF format → appears in GitHub Security tab (Code Scanning Alerts)
Links each finding to comply.crprotocol.io for remediation
Free tier: detect + report. Paid tier: auto-remediation + full header gap analysis
Build steps:

Create repo crp-scan under crprotocol org (or Constantinos-uni/crp-scan)
Add action.yml at the root:
name: CRP AI Governance Scanner
description: Detects ungoverned AI API calls and reports via SARIF to GitHub Security tab
inputs:
  severity-threshold:
    description: Minimum severity to report (LOW/MEDIUM/HIGH/CRITICAL)
    default: MEDIUM
runs:
  using: docker
  image: Dockerfile


Implement the Python detection engine from CRP-SPEC-013 §1 (pattern matching against LLM providers, agent frameworks, prompt definitions)
Implement SARIF output per §3 of the spec
Test on 5+ real repos (especially ones with LangChain/OpenAI usage)
Publish to GitHub Actions marketplace — this is free, just submit from the repo settings
Write a README with a 2-line install example

- uses: crprotocol/crp-scan@v1
  with:
    severity-threshold: HIGH


Why this is the GitHub partnership hook: GitHub Advanced Security integrates with SARIF natively. A CRP scan action that populates Code Scanning Alerts — for free — creates viral adoption. Every repo that adds it generates awareness of CRP.

PHASE 5 — CRP v3 implementation (Months 1–3)
Minimal viable v3 for standards credibility:

IETF Proposed Standard requires two independent implementations. You need yours to be demonstrably compliant with CRP-SPEC-014 (Conformance). The minimum viable v3 adds:

58 safety headers (CRP-SPEC-002) — add all remaining headers to crp/ Python package. Priority order:

CRP-Safety-Hallucination-Risk (already in some form)
CRP-Provenance-HMAC (tamper-evident chain)
CRP-Compliance-EU-AI-Act (EU AI Act classification)
CRP-Safety-Policy directive grammar (CRP-SPEC-006)
CRP-Agent-Safety-Budget (once provisional patents filed)
Safety Policy enforcement (CRP-SPEC-006) — the directive grammar:

CRP-Safety-Policy: max-risk=HIGH; require-grounding=1; 
                   stop-on=CRITICAL; oversight-mode=NOTIFY

Conformance test suite (CRP-SPEC-014) — all 1,537 tests passing is already claimed on the homepage. Make sure the v3 headers are covered.

Release as v3.0.0 — pyproject.toml version bump, PyPI publish, GitHub release tag. Update the homepage stats.

PHASE 6 — CRP Comply live integration (Months 2–3)
CRP Comply at comply.crprotocol.io currently generates compliance evidence from CRP headers. To "finish" it:

Connect live CRP header data from CRP Gateway (CRP-SPEC-016) into Comply's evidence pipeline
Implement EU AI Act Article 9 (risk management system) auto-reporting from CRP-Compliance-EU-AI-Act header
Implement ISO 42001 Clause 9.1 (monitoring) reports from audit trail headers
Add DPIA generation from CRP-Compliance-GDPR-PII header
Add the "Free tier" onboarding flow from CRP-SPEC-016 §3: account → region selection → API key → first governed call → Comply dashboard in under 5 minutes


PHASE 7 — GitHub Technology Partnership (Month 2–3, after Phase 4)
The partnership path requires a working Action on the marketplace first.

Publish crp-scan action to marketplace (Phase 4 must be done)
Apply to GitHub Technology Partner Program at partner.github.com — free to apply, requires review
Email partnerships@github.com with this pitch (after marketplace listing exists):
Subject: CRP AI Governance Action — GitHub Advanced Security integration proposal

The CRP Scan GitHub Action (crprotocol/crp-scan) detects ungoverned AI API calls in any repository and reports findings as SARIF Code Scanning Alerts via GitHub's Security tab. It's the top-of-funnel for the Context Relay Protocol (CRP) ecosystem — the open HTTP header standard for AI governance (two IETF Internet-Drafts submitted).

We'd like to discuss: (1) a Featured listing in the GitHub Actions marketplace, (2) co-marketing around EU AI Act compliance (August 2026 enforcement deadline is a natural hook), and (3) GitHub Advanced Security integration for enterprise customers.

crp-scan marketplace: github.com/marketplace/actions/crp-scan
Spec repo: github.com/crprotocol/spec
Standards: crprotocol.io/standards/

Secondary hook — GitHub Copilot extension: CRP Comply's governance evidence could integrate with GitHub Copilot's AI policy features. Mention this as a roadmap item.

PHASE 8 — Government & standards body engagement (Months 3–6)
Australia DISR — Submit CRP-SPEC-010 (regulatory mapping) to DISR's AI Safety Standard consultation at industry.gov.au/AI-safety-standard. Reference both IETF I-Ds.

NIST NCCoE — Apply to Technology Partner Program at nccoe.nist.gov/partner-with-nccoe. CRP maps to NIST AI RMF GOVERN 1.1/1.2/1.3 and MANAGE 1.0/2.0. Reference CRP-SPEC-010.

Standards Australia — Contact ISO/IEC JTC 1/SC 42 mirror committee (Standards Australia via standards.org.au) to introduce CRP as input to AI governance standards work.

IEEE SA (months 6–12) — Join as Corporate Member (~USD $7,500/yr). Contact AIS/SSIT to introduce CRP as a candidate IEEE P-standard.

PHASE 9 — IETF BoF (Months 6–9)
After getting substantive IETF mailing list responses (Phase 3) and collecting 10+ supporters:

Submit BoF request to iesg@ietf.org CC wgchairs@ietf.org using EMAIL 4 template from CRP-IETF-EMAIL-TEMPLATES.md
Target: IETF 127 (San Francisco, November 2026) — submit BoF request by July 2026
Recruit two BoF co-chairs: one from HTTP WG, one with AI/regulatory background
Prepare slides answering RFC 5434 BoF question checklist


Priority order summary (what to do first)
Priority	Action	Blocks
1	Trademark applications (AU, US, EU)	Sending emails
2	Provisional patents (Stop-Inject, Safety-Budget, DPE weights)	Publishing SPEC-006/012 internals
3	IETF IPR disclosure on Datatracker	WG adoption
4	Create public spec GitHub repo	Sending emails, GitHub Action
5	IANA provisional header registration	Standards credibility
| Priority | Action | Blocks | Status |
|----------|--------|--------|--------|
| 1 | Trademark applications (AU, US, EU) | Sending emails | ✅ Filed |
| 2 | Provisional patents | Publishing SPEC-006/012 internals | ⛔ Skipped — cannot afford |
| 3 | IETF IPR disclosure on Datatracker | WG adoption | ✅ Submitted 2026-05-29 — Secretariat notified, posts within 1 business day |
| 4 | Create public spec GitHub repo | Sending emails | ✅ Done — AutoCyber-AI/crprotocol-specs |
| 5 | IANA provisional header registration | Standards credibility | ⏳ Submitted — ticket #1453152 |
| 6 | Send IETF mailing list emails | BoF | ✅ Done (Emails 1, 2, 3, 5 sent) |
| 6b | Submit core protocol I-D | Standards credibility | ✅ Already submitted — `draft-vidiniotis-crp-core` confirmed live |
| 7 | Build + publish crp-scan GitHub Action | GitHub partnership | ❌ Not started |
| 8 | CRP v3 (58 headers + Safety Policy in Python package) | Second implementation | ❌ Not started |
| 9 | CRP Comply live header integration | Commercial viability | ❌ Not started |
| 10 | GitHub partnership email | Partnership | ❌ Not started (blocked on #7) |
| 11 | BoF request (IETF 127, deadline July 2026) | WG formation | ❌ Not started (needs 10+ supporters) |

**EU AI Act full enforcement: August 2026.** The GitHub Action and CRP Comply live integration must ship before that date.

---

## IANA Submission Record

**Ticket:** IANA #1453152  
**Submitted:** 2026-05-29  
**Email response from:** IANA General Enquiries via RT <iana-questions@iana.org>  
**Auto-reply ref:** RT ticket 1453152  
**Reply-to for future correspondence:** Include `[IANA #1453152]` in subject line

---

## Notes & Decisions Made

- **Licence:** CC BY 4.0 for specs (open); reference implementation stays Elastic License 2.0 (closed commercial SaaS). The GitHub UI will show "Other" — that is correct and fine.
- **Open source?** No. Open spec + closed implementation is the right model. No PR contributions accepted at this time.
- **Patents:** Skipped — unaffordable. Consequence: Do NOT publish Stop-Inject mechanism or SPEC-012 under any circumstances.
- **Repo name:** `AutoCyber-AI/crprotocol-specs` (not `crprotocol/spec` as originally planned — all references updated 2026-05-29)
- **draft-vidiniotis-crp-safety-policy:** Verify it is actually live on Datatracker — user says it may not be. If not, re-submit.
- **Core protocol I-D:** CRP-SPEC-001 has no corresponding IETF I-D yet. This is a gap that should be filled.

---

_Original detailed phase descriptions preserved below for reference._

---



# My response to all of that...

for the crprotocol.io site...the nav bar isnt shown in the main page, the opening page...it has to be visible there too!!

But it's better structure!

Let's properly get crprotocol.io site indexed and searchable Add the attached .xml file Upload the file to root directory of your site https://crprotocol.io/


Regarding the phase completion/progress so far:
The trademarks have been filed for context relay protocol!

I cannot afford patents!

0.3 is unclear

Phase 1:
- I have a github organisation AutoCyber AI. Made a repo called crprotocol-specs...CREATE THE README TO INCLUDE!
- Uploaded all spec documents except 7, 12, 16.....curious whether trully the current dpe and 6 are truly redacted....

- These seem to be the only licence available: Apache License 2.0, GNU General Public License v3.0,  MIT License, BSD 2-Clause "Simplified" License, BSD 3-Clause "New" or "Revised" License, Boost Software License 1.0, Creative Commons Zero v1.0 Universal, Eclipse Public License 2.0, GNU Affero General Public License v3.0, GNU General Public License v2.0, GNU Lesser General Public License v2.1, Mozilla Public License 2.0, The Unlicense 

- Should we make a CC BY. 

- Add the copyright...Also note...is this possible...can the code for the protocol actually be private/closed source?! Or open-source better?! Open source and no contributors welcome?! Whatt's besT?

Phase 2:
Response of submitting exactly what you gave me:

Thank you for your request.
Your application has been submitted and added to the processing queue. The ticket number assigned to your request and a copy of your application have been sent to your email account for your records.

You should hear from a staff member within 1-2 business days.

Requests to add entries to "First Come First Served" registries are typically completed within one week, if no additional information or outside consultation is required. Requests to add entries to "Expert Review" and "Specification Required" registries are forwarded to IESG-designated registry experts (volunteers not employed by IANA) for review. Reviews may be completed within a few days or several weeks, depending on variables that can include request complexity and reviewer availability.

For more information on registration procedures, please see Section 4 of RFC 8126.

And in specific these per form inoput:
Requesting provisional registration of HTTP header field names for the Context Relay Protocol (CRP) specification suite.

The registration request is for provisional HTTP header field assignments in the IANA "Hypertext Transfer Protocol (HTTP) Field Name Registry" for interoperability, implementation consistency, and standards-track evaluation associated with the CRP Internet-Drafts submitted to the IETF.

The requested headers are intended for AI safety, provenance verification, compliance signaling, context continuity, and auditability across AI-agent and LLM systems communicating over HTTP-based infrastructures.

Requested provisional header registrations include:

* CRP-Context-Quality-Tier
* CRP-Safety-Hallucination-Risk
* CRP-Provenance-HMAC
* CRP-Compliance-EU-AI-Act
* CRP-Safety-Policy
* CRP-Agent-Safety-Budget
* CRP-Set-Session
* CRP-Context-ETag
* CRP-Compliance-Audit-Trail-URI
* CRP-Safety-Oversight-Mode

Reference specifications:

* draft-vidiniotis-crp-headers-00
* draft-vidiniotis-crp-safety-policy-00

The CRP specifications define standardized safety, compliance, provenance, and context-management semantics for AI systems and multi-agent orchestration environments over HTTP transports.


This is the email...keep a record of it!


IANA General Enquiries via RT <iana-questions@iana.org>
17:02 (1 minute ago)
to me

To whom it may concern:

This is an automatically generated message to notify you that we have
received your request, and it has been recorded in our ticketing
system with a reference number of 1453152.

There is no need to reply to this message right now. IANA staff will review
your message and reply to your inquiry within three (3) business days.

If this message is in reply to a previously submitted ticket, it is
possible that the previous ticket has been marked as closed. As we
review this ticket, we will also review previous correspondence and
take appropriate action.

To expedite processing, and ensure our staff can view the full history
of this request, please make sure you include the following exact text in
the subject line of all future correspondence on this issue:

         [IANA #1453152]

You can also simply reply to this message, as this tag is already in
the subject line.

Thank you,

IANA Services
iana-questions@iana.org
PTI

Phase 3:
I visisted what you gave me and see these actions:
ietf-http-wg@w3.org Mail Archives
This is the public mailing list of the IETF HTTP-WG.

Note that https://www.ietf.org/about/note-well/ applies to all contributions to this mailing list.

About this list: indices by date latest messages messages in mailbox format Feed
Mail actions: mail a new topic subscribe to this list unsubscribe from this list
Help: how to use the archives search the Public archives

I pressed the subscribe to this list an a new email opened up with subject subscribe  and recipient (s ?) "ietf-http-wg-request@w3.org" <ietf-http-wg-request@w3.org>

this is the repo name:
https://github.com/AutoCyber-AI/crprotocol-specs  you should be able to MAKE ADDITIONS HERE! Clone it locally in desktop and add what is necesssary and missing!

Email 1 sent...excluding the happy to set the meeting...cause im not and cannot!

Email 2 sent verbatim with updated repo


Email 3 sent with updated repo and removed meeting. 

Note right now the only drafts are these 2..of which I havent seen the core actually been mentioned...IT'S THE MAIN PROTOCOL ITSELF!

https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/
https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/

Hence, modify email 5!
There's no draft-vidiniotis-crp-safety-policy ....



KEEP TRACK OF EVERYTHING DONE. UPDATE THE .MD DOCUMENT FOR EMAIL TEMPALTES AND STEPS TO DO...

DOCUMENT WHAT ELSE IS LEFT IN ANOTEHR .MD!


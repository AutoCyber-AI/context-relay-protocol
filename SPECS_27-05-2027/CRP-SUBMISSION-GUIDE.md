# CRP™ Protocol Accreditation & Submission Guide

**Document:** CRP-SUBMISSION-GUIDE  
**Version:** 1.0  
**Author:** AutoCyber AI Pty Ltd  
**Date:** 2026-05-24  
**Status:** Internal Strategy Document — CONFIDENTIAL

---

## Overview: What We Are Achieving

The goal is **multi-body accreditation** of the Context Relay Protocol as a recognised international standard for AI context governance, safety signalling, and compliance evidence. This makes CRP:

1. A normative reference in EU AI Act implementing regulations
2. A cited implementation in NIST AI RMF Playbook
3. An IETF RFC — the same status as HTTP headers, OAuth, and TLS
4. An IEEE standard — same body that standardised AI ethics (7000-series)
5. Referenced by ISO/IEC JTC 1/SC 42 as a companion to ISO 42001

**How many bodies accredit us: 4 primary + 2 government reference bodies = 6 total**

| Body | What They Give You | Timeline |
|------|-------------------|----------|
| **IETF** | RFC for CRP headers — developer/industry gold standard | 18–36 months |
| **IANA** | Official HTTP header prefix registration | 3–6 months (do first) |
| **IEEE SA** | IEEE standard for AI governance protocol | 24–48 months |
| **ISO/IEC JTC 1/SC 42** | ISO standard, companion to ISO 42001 | 36–60 months |
| **NIST NCCoE** | US government reference implementation | 12–18 months |
| **Standards Australia / DISR** | Australian government reference | 12–18 months |

---

## IP Protection: Do This BEFORE Going Public

> ⚠️ **Critical: Establish IP protection before any public submission.**

### Step 1: Trademark (Do immediately)
- File TM for **CRP™**, **Context Relay Protocol™**, **CRP Comply™**, **CRP Visualise™**, **CRP Gateway™** in:
  - Australia: IP Australia — [ipaustralia.gov.au](https://www.ipaustralia.gov.au) — Class 42 (software/technology services)
  - US: USPTO — [uspto.gov](https://www.uspto.gov) — Class 42
  - EU: EUIPO — [euipo.europa.eu](https://www.euipo.europa.eu) — Class 42
  - Cost: ~AUD $3,000–5,000 total with a IP attorney
  - **File before IETF submission — public I-D disclosure is prior art**

### Step 2: Copyright notices on all spec documents
All `.md` spec files must carry: `© 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (spec text).`  
The CC BY 4.0 licence lets anyone read and implement the spec — but the trademark means they cannot call it "CRP" or "Context Relay Protocol" without a licence.

### Step 3: What to patent vs what to open
**Consider provisional patent (AU/US) for:**
- `CRP-Safety-Stop-Inject` — real-time hallucination interruption via stop sequence injection mid-stream
- `CRP-Agent-Safety-Budget` — session-scoped risk budget mechanism for multi-agent chains
- The composite DPE risk scoring formula with regulatory amplifiers

**Leave open (standard spec):**
- Header names and values
- Safety Policy directive grammar
- Session token format

**Provisional patent cost:** ~AUD $3,000–5,000 per application via a patent attorney. File provisionals first (12-month priority window), then decide on full applications.

### Step 4: IETF IPR declaration
When submitting I-D, you MUST disclose any patents covering the spec per BCP 79. File an IPR disclosure at [datatracker.ietf.org/ipr/new/](https://datatracker.ietf.org/ipr/new/) stating which claims are licensed under RAND (Reasonable And Non-Discriminatory) terms.

---

## What to Make Public and Where

### Currently public (you have):
- [crprotocol.io](https://crprotocol.io) — protocol site (MkDocs from repo) ✓
- [comply.crprotocol.io](https://comply.crprotocol.io) — compliance platform ✓
- GitHub repo (protocol) — confirm it's public ✓

### What to add to your GitHub repo RIGHT NOW:

```
crprotocol/
├── spec/                          ← ADD THIS
│   ├── CRP-SPEC-001-core.md
│   ├── CRP-SPEC-002-headers.md
│   ├── CRP-SPEC-003-envelope.md
│   ├── CRP-SPEC-004-continuation.md
│   ├── CRP-SPEC-005-dpe.md
│   ├── CRP-SPEC-006-safety-policy.md
│   └── CRP-SPEC-010-regulatory-mapping.md
├── CONTRIBUTING.md                ← ADD THIS (for IETF WG credibility)
├── SECURITY.md                    ← ADD THIS
├── LICENSE                        ← Ensure CC BY 4.0
├── CHANGELOG.md
└── docs/                          ← existing MkDocs
```

### What to publish on crprotocol.io:

Add a `/spec/` section to the MkDocs site linking each spec document. This is your reference implementation home — IETF reviewers will check it.

**Add these pages:**
- `/spec/` — spec document index
- `/spec/headers/` — full header reference (from CRP-SPEC-002)
- `/spec/safety-policy/` — directive grammar (from CRP-SPEC-006)
- `/spec/conformance/` — conformance levels
- `/changelog/` — version history
- `/accreditation/` — links to IETF I-D, IANA registration once live

### What to add to autocyberai.com:

**Add immediately:**
- Homepage: mention CRP as the core technology — "We built the AI safety protocol that makes AI systems auditable, governable, and compliant by default"
- `/crp/` page: overview of the protocol ecosystem with links to crprotocol.io
- `/products/` page: CRP Comply, CRP Gateway, CRP Visualise
- Press/news section: "CRP v3.0 released — introducing AI safety headers"
- Team/about: Constantinos Vidiniotis as author of the CRP specification

> AutoCyber AI's company site is the face for enterprise/government buyers. crprotocol.io is the face for developers. They serve different audiences and should cross-link.

### What NOT to make public yet:
- CRP-SPEC-007 (Session Token internals) — keep private until patent filed
- DPE scoring formula weights (competitive advantage) — reference the formula in the spec as normative but keep the exact calibration weights proprietary
- CRP Comply source code — this is your product, not the protocol

---

## TRACK 1: IANA Header Registration

**Goal:** Get `CRP-*` registered as provisional HTTP header fields in the IANA HTTP Field Name Registry.  
**Why first:** Cheapest, fastest, and immediately legitimises the header names before any competitor registers them.  
**Timeline:** 4–8 weeks  
**Cost:** Free

### Step-by-step:

**1. Review the registry**
- Go to: [https://www.iana.org/assignments/http-fields](https://www.iana.org/assignments/http-fields)
- Confirm no existing `CRP-*` registrations

**2. Prepare registration templates for each header**

For each header, you need:

```
Header Field Name: CRP-Safety-Hallucination-Risk
Applicable Protocol: http
Status: provisional
Author/Change Controller: AutoCyber AI Pty Ltd <contact@crprotocol.io>
Specification Document: https://crprotocol.io/spec/headers/
Related Information: Part of the Context Relay Protocol (CRP) header specification.
  Carries the hallucination risk classification (CRITICAL/HIGH/MEDIUM/LOW)
  for an AI response, computed by the CRP Decision Provenance Engine.
```

**3. Submit via IANA web form or mailing list**
- Web form: [https://www.iana.org/form/protocol-assignment](https://www.iana.org/form/protocol-assignment)
- Or email: iana@iana.org with subject "HTTP Field Name Registration Request"
- Per RFC 9110 Section 16.3: provisional registrations require only Expert Review (not full RFC)

**4. Respond to Designated Expert review**
- IANA will assign a Designated Expert (likely from the HTTP WG)
- Respond promptly to any questions — typically 2–4 weeks

**5. Publish the registrations on crprotocol.io/spec/headers/**
- Once registered, link to the IANA registry from your spec pages

> **Tip:** Register the 10 most important headers first (the "Core CRP Headers" set), not all 58 at once. Start with: `CRP-Context-Quality-Tier`, `CRP-Safety-Hallucination-Risk`, `CRP-Provenance-HMAC`, `CRP-Compliance-EU-AI-Act`, `CRP-Safety-Policy`, `CRP-Agent-Safety-Budget`, `CRP-Set-Session`, `CRP-Context-ETag`, `CRP-Compliance-Audit-Trail-URI`, `CRP-Safety-Oversight-Mode`.

---

## TRACK 2: IETF Internet-Draft

**Goal:** Submit CRP as an IETF Internet-Draft targeting eventual RFC status.  
**Timeline:** Submit I-D in 2–3 months; RFC in 18–36 months.  
**Cost:** Free to submit. Budget for IETF meeting attendance (~USD $3,000/meeting).

### What to submit

Submit two related I-Ds:

| I-D Name | Content | Target Spec |
|---|---|---|
| `draft-vidiniotis-crp-headers-00` | CRP header field vocabulary and semantics | CRP-SPEC-002 |
| `draft-vidiniotis-crp-safety-policy-00` | Safety Policy directive language | CRP-SPEC-006 |

### Step-by-step:

**1. Create an IETF Datatracker account**
- Go to: [https://datatracker.ietf.org/accounts/create/](https://datatracker.ietf.org/accounts/create/)
- Use your professional email (contact@crprotocol.io)

**2. Write the I-D in the correct format**

Two options (both accepted):
- **XML (preferred):** Use the `xml2rfc` toolchain — [https://authors.ietf.org/](https://authors.ietf.org/)
- **Markdown (easier):** Use `kramdown-rfc` — [https://github.com/cabo/kramdown-rfc](https://github.com/cabo/kramdown-rfc)
  - Write in Markdown, tool converts to RFC XML v3 automatically
  - Use the i-d-template: [https://github.com/martinthomson/i-d-template](https://github.com/martinthomson/i-d-template)

**3. Check your I-D with idnits**
- Tool: [https://author-tools.ietf.org/idnits](https://author-tools.ietf.org/idnits)
- Must pass before submission — fix all nits

**4. Submit to IETF Datatracker**
- Go to: [https://datatracker.ietf.org/submit/](https://datatracker.ietf.org/submit/)
- Upload XML file
- Authors receive email for verification — confirm within 24 hours
- I-D is published in the Datatracker and archived

**5. Email the relevant mailing list**

Post to the HTTP Working Group list announcing your I-D:
- List: `ietf-http-wg@w3.org`
- Subscribe: [https://lists.w3.org/Archives/Public/ietf-http-wg/](https://lists.w3.org/Archives/Public/ietf-http-wg/)
- Subject: `[ANNOUNCE] New I-D: draft-vidiniotis-crp-headers-00 — AI Context Safety Headers`
- Body: brief paragraph describing what problem you're solving, link to I-D

Also post to the IETF AI area list:
- List: Look for `dispatch@ietf.org` or the AIPREF (AI Preferences) WG list

**6. Attend an IETF meeting (within 6 months)**

IETF meets 3× per year. The next relevant opportunities:
- **IETF 123** — ~July 2026
- **IETF 124** — ~November 2026

At the meeting, request a BoF (Birds of a Feather) session:
- Email: `ietf-secretariat@ietf.org` subject "BoF Request: AI Context Governance Protocol"
- BoF brings together people interested in the topic to determine if a new WG is warranted
- You need ~10–20 people interested — solicit support from companies using CRP

**7. Build toward Working Group adoption**

After the I-D is published:
- Solicit co-authors from other organisations (legitimacy + WG support)
- Get 2 independent interoperable implementations — required for Proposed Standard
- Keep updating the I-D every 6 months (I-Ds expire if not updated)

**Key IETF resources:**
- Authors guide: [https://authors.ietf.org/](https://authors.ietf.org/)
- Datatracker: [https://datatracker.ietf.org/](https://datatracker.ietf.org/)
- Submission tool: [https://datatracker.ietf.org/submit/](https://datatracker.ietf.org/submit/)
- I-D template (GitHub): [https://github.com/martinthomson/i-d-template](https://github.com/martinthomson/i-d-template)
- kramdown-rfc: [https://github.com/cabo/kramdown-rfc](https://github.com/cabo/kramdown-rfc)
- idnits checker: [https://author-tools.ietf.org/idnits](https://author-tools.ietf.org/idnits)

---

## TRACK 3: IEEE Standards Association

**Goal:** IEEE standard for CRP as an AI governance protocol.  
**Timeline:** 24–48 months from PAR to publication.  
**Cost:** IEEE SA Corporate Membership ~USD $7,500/yr. Standards development ~USD $15,000–30,000 total.

### What to submit

A PAR (Project Authorization Request) targeting the **IEEE 7000-series** (Autonomous and Intelligent Systems) standards committee — the same committee that produced IEEE 7001 (Transparency), IEEE 7010 (Wellbeing), and IEEE 7014 (Empathy Ethics).

Proposed standard title: **"IEEE Standard for AI Context Relay and Safety Governance Protocol (CRP)"**

### Step-by-step:

**1. Join IEEE Standards Association**
- Go to: [https://standards.ieee.org/about/sasb/](https://standards.ieee.org/about/sasb/)
- Corporate membership: [https://standards.ieee.org/products-programs/corporate-program/](https://standards.ieee.org/products-programs/corporate-program/)
- Contact: `stds-contact@ieee.org`

**2. Contact the IEEE AIS (Autonomous and Intelligent Systems) standards committee**
- Committee page: [https://standards.ieee.org/initiatives/autonomous-intelligence-systems/](https://standards.ieee.org/initiatives/autonomous-intelligence-systems/)
- Email the SSIT/SC (Society for Social Implications of Technology Standards Committee) as it covers AI governance — email `m.zaman@ieee.org` (Program Manager) to discuss

**3. Prepare and submit a PAR**
- Log in to myProject: [https://development.standards.ieee.org/myproject/](https://development.standards.ieee.org/myproject/)
- Submit PAR for a New IEEE Standard
- The PAR requires: Title, Scope, Purpose, Stakeholders, Relationship to Existing Standards
- PAR is reviewed by NesCom (New Standards Committee) and approved by IEEE SA Standards Board

**PAR scope text (draft):**
> This standard defines the Context Relay Protocol (CRP), a layered protocol specification for managing AI context quality, safety governance, and compliance evidence in deployed large language model systems. The standard specifies: (a) a header vocabulary for AI request/response cycles; (b) a session state relay mechanism; (c) a safety policy directive language for transport-layer AI safety enforcement; (d) a provenance and audit chain for tamper-evident compliance evidence; and (e) regulatory alignment mappings to EU AI Act, NIST AI RMF, ISO/IEC 42001, and GDPR.

**4. Form a Working Group**

You need to recruit Working Group members from:
- Industry (companies using/building AI: AWS, Azure, Google, startups)
- Academia (AI safety researchers)
- Government (CSIRO, NIST, AI Safety Institute)
- Standards bodies (existing IEEE 7000-series participants)

Reach out via LinkedIn and the IEEE mailing lists for the AIS committee.

**Key IEEE resources:**
- IEEE SA: [https://standards.ieee.org/](https://standards.ieee.org/)
- myProject (PAR submission): [https://development.standards.ieee.org/myproject/](https://development.standards.ieee.org/myproject/)
- PAR submission guide: [https://standards-support.ieee.org/hc/en-us/sections/4412984803860](https://standards-support.ieee.org/hc/en-us/sections/4412984803860)
- AIS standards: [https://standards.ieee.org/initiatives/autonomous-intelligence-systems/standards/](https://standards.ieee.org/initiatives/autonomous-intelligence-systems/standards/)
- IEEE SA corporate program: [https://standards.ieee.org/products-programs/corporate-program/](https://standards.ieee.org/products-programs/corporate-program/)

---

## TRACK 4: ISO/IEC JTC 1/SC 42

**Goal:** ISO standard for CRP as a companion to ISO 42001 (AI Management Systems).  
**Timeline:** 36–60 months.  
**Entry point: Standards Australia (SAI Global).**

### Step-by-step:

**1. Contact Standards Australia**
- Website: [https://www.standards.org.au/](https://www.standards.org.au/)
- Email: `enquiries@standards.org.au`
- Phone: 1300 65 46 46
- Explain you want to propose a New Work Item (NWI) to ISO/IEC JTC 1/SC 42
- Standards Australia is Australia's ISO member body and can sponsor your NWI

**2. Join the relevant mirror committee**
- IT-043 — The Australian mirror committee for ISO/IEC JTC 1/SC 42 (AI)
- Membership gives you visibility into what SC 42 is working on and who the key people are
- Contact Standards Australia to join

**3. Prepare a New Work Item Proposal (NWIP)**
- The NWIP describes the proposed standard's scope, justification, and list of participating national bodies
- You need support from at least 5 participating member bodies (countries) — solicit through your IETF/IEEE network

**4. SC 42 Working Groups**
- WG 3: Trustworthiness — most relevant for CRP safety/provenance
- WG 5: AI systems — relevant for governance
- Contact SC 42 Secretariat: [jtc1sc42secretariat@csa.ca](mailto:jtc1sc42secretariat@csa.ca) (CSA Group, Canada)

**Key ISO/IEC resources:**
- Standards Australia: [https://www.standards.org.au/](https://www.standards.org.au/)
- ISO/IEC JTC 1/SC 42: [https://www.iso.org/committee/6794475.html](https://www.iso.org/committee/6794475.html)
- SC 42 Secretariat: [jtc1sc42secretariat@csa.ca](mailto:jtc1sc42secretariat@csa.ca)

---

## TRACK 5: NIST NCCoE Technology Partner (USA Government Reference)

**Goal:** CRP cited in the NIST AI RMF Playbook as a reference implementation.  
**Timeline:** 12–18 months.  
**Cost:** Free to apply. May require travel to NIST workshops.

### Step-by-step:

**1. Publish CRP-SPEC-010 (Regulatory Controls Mapping) as a public document**
- This maps every CRP feature to specific NIST AI RMF controls
- Publish at crprotocol.io/spec/nist-mapping/
- This is your credibility document for NIST

**2. Apply to NIST NCCoE Technology Partner Program**
- NCCoE (National Cybersecurity Center of Excellence) runs technology partner programs for security infrastructure
- Apply at: [https://www.nccoe.nist.gov/partner-with-nccoe](https://www.nccoe.nist.gov/partner-with-nccoe)
- Position CRP as AI security and governance infrastructure

**3. Submit comment to NIST AI RMF public comment process**
- NIST regularly runs public comment periods on AI RMF updates
- Check: [https://www.nist.gov/artificial-intelligence](https://www.nist.gov/artificial-intelligence)
- Submit CRP as a reference implementation for MAP, MEASURE, and MANAGE functions

**4. Engage NIST AI Safety Institute (AISI)**
- AISI runs workshops and calls for participation
- Website: [https://www.nist.gov/artificial-intelligence/executive-order-safe-secure-and-trustworthy-artificial-intelligence](https://www.nist.gov/artificial-intelligence/executive-order-safe-secure-and-trustworthy-artificial-intelligence)

---

## TRACK 6: Australian Government (DISR / AI Safety Standard)

**Goal:** CRP referenced in Australia's AI Safety Standard as a technical implementation mechanism.  
**Timeline:** 6–12 months (consultation is happening now).

### Step-by-step:

**1. Update autocyberai.com immediately**
- Add a page about CRP and its relationship to Australian AI governance
- You are an Australian company — this is a genuine first-mover advantage

**2. Submit to DISR AI Safety Standard consultation**
- DISR (Department of Industry, Science and Resources) is developing Australia's voluntary AI Safety Standard
- Website: [https://www.industry.gov.au/science-technology-and-innovation/technology/artificial-intelligence](https://www.industry.gov.au/science-technology-and-innovation/technology/artificial-intelligence)
- Submit CRP-SPEC-010 (regulatory mapping) as evidence of a technical implementation mechanism

**3. Engage CSIRO Data61**
- CSIRO Data61 is the technical partner for Australian AI governance
- Email: `contact@data61.csiro.au`
- Propose CRP as a technical reference for their AI ethics/safety work

**4. Submit to the Digital ID / Trusted AI working groups**
- DSB (Data Standards Body): [https://www.datastandards.net.au/](https://www.datastandards.net.au/)

---

## The Sequence: What to Do and When

### Now (next 60 days) — IP protection first, then visibility

| Week | Action |
|------|--------|
| 1 | Engage IP attorney: file TM applications (AU, US, EU) for CRP™, CRP Comply™, CRP Gateway™, CRP Visualise™ |
| 1–2 | File provisional patent applications for CRP-Safety-Stop-Inject and CRP-Agent-Safety-Budget |
| 2 | Add `/spec/` directory to GitHub repo with CRP-SPEC-001 through 006 and 010 |
| 2 | Update crprotocol.io MkDocs to include `/spec/` section |
| 3 | Update autocyberai.com with CRP protocol content and product ecosystem |
| 3–4 | Prepare IANA registration templates for top 10 CRP headers |
| 4 | Submit IANA registrations |
| 5–8 | Write IETF I-D (use i-d-template + kramdown-rfc) |

### Months 2–3 — IETF submission

| Action |
|--------|
| Submit `draft-vidiniotis-crp-headers-00` to IETF Datatracker |
| Submit `draft-vidiniotis-crp-safety-policy-00` to IETF Datatracker |
| Announce on ietf-http-wg@w3.org mailing list |
| IANA Expert Review response |

### Months 3–6 — Government reference tracks

| Action |
|--------|
| Publish CRP-SPEC-010 regulatory mapping publicly |
| Submit to DISR AI Safety Standard consultation |
| Apply to NIST NCCoE Technology Partner |
| Contact Standards Australia re: ISO/IEC JTC 1/SC 42 path |
| Contact CSIRO Data61 |

### Months 6–12 — IEEE and community building

| Action |
|--------|
| Join IEEE SA Corporate Member |
| Contact AIS committee / SSIT/SC |
| Submit IEEE PAR via myProject |
| Attend IETF 123 or 124, request BoF session |
| Build second independent CRP implementation (for IETF Proposed Standard requirement) |
| Recruit Working Group co-authors from industry |

### Year 2+ — Standards track progression

| Action |
|--------|
| IETF Working Group adoption (if BoF successful) |
| ISO/IEC JTC 1/SC 42 NWIP submission |
| IEEE Working Group draft ballot |
| IETF Last Call for RFC |

---

## The Goal: What Success Looks Like

In 3 years:

> "CRP-Safety-Hallucination-Risk is a registered IANA HTTP header field (RFC XXXX). CRP is an IEEE standard for AI governance protocols. CRP is referenced in the NIST AI RMF Playbook v1.1 as a reference implementation for the MEASURE and MANAGE functions. CRP Comply is the only compliance platform whose evidence is generated from a cryptographically verifiable, RFC-standardised protocol chain."

That is the position no competitor can replicate — because they don't own the protocol.

---

## Summary: Bodies, What They Accredit, Links

| Body | Accreditation Type | Key Link | Contact |
|------|-------------------|----------|---------|
| **IANA** | HTTP header registration | [iana.org/assignments/http-fields](https://www.iana.org/assignments/http-fields) | iana@iana.org |
| **IETF** | Internet-Draft → RFC | [datatracker.ietf.org/submit](https://datatracker.ietf.org/submit/) | ietf-http-wg@w3.org |
| **IEEE SA** | IEEE standard | [development.standards.ieee.org/myproject](https://development.standards.ieee.org/myproject/) | stds-contact@ieee.org |
| **ISO/IEC JTC 1/SC 42** | ISO standard | [iso.org/committee/6794475.html](https://www.iso.org/committee/6794475.html) | jtc1sc42secretariat@csa.ca |
| **NIST NCCoE** | US government reference | [nccoe.nist.gov/partner-with-nccoe](https://www.nccoe.nist.gov/partner-with-nccoe) | nccoe@nist.gov |
| **Standards Australia / DISR** | AU government reference | [standards.org.au](https://www.standards.org.au/) | enquiries@standards.org.au |

---

*© 2025–2026 AutoCyber AI Pty Ltd. CONFIDENTIAL — Internal use only.*

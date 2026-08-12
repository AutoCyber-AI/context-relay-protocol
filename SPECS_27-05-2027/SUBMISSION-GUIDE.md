# CRP™ Protocol — Standardisation Submission Guide
> **AutoCyber AI Pty Ltd** · Context Relay Protocol™  
> Prepared: May 2026 · Version 1.0  
> Confidential — Internal use until IP protection steps completed

---

## Our Goal

Get CRP™ recognised as a formal standard by **5 bodies**, in this priority order:

| # | Body | What We Get | Timeline |
|---|------|------------|----------|
| 1 | **IANA** | CRP-* header prefix registered in HTTP Field Name Registry | 1–3 months |
| 2 | **IETF** | RFC for CRP header spec — same body that standardised HTTP | 18–36 months |
| 3 | **NIST** | CRP cited as reference implementation in AI RMF Playbook | 6–18 months |
| 4 | **IEEE SA** | Published IEEE standard for AI context governance protocol | 24–48 months |
| 5 | **ISO/IEC JTC 1/SC 42** | International standard companion to ISO 42001 | 36–60 months |

**This is not sequential — pursue all five in parallel.** IANA and NIST are fastest and give immediate credibility. IETF runs concurrently. IEEE and ISO are long-game.

---

## CRITICAL: Do These First (Before Making Anything Public)

### 1. Trademark Protection

You already use `CRP™` — but you need formal registration.

**Action:** File trademark applications for:
- `CRP` (the abbreviation)
- `Context Relay Protocol` (full name)
- `CRP Comply`
- `CRP Gateway`
- `CRP Visualise`

**Where:**
- 🇦🇺 **IP Australia** (your home jurisdiction — do this first): https://www.ipaustralia.gov.au/trade-marks/apply-for-a-trade-mark
- 🇺🇸 **USPTO** (US market): https://www.uspto.gov/trademarks/apply
- 🇪🇺 **EUIPO** (EU market — critical given EU AI Act focus): https://euipo.europa.eu/ohimportal/en/apply-now

**Cost:** ~AUD $250/class in AU. ~USD $350/class in US. ~EUR $850 in EU.  
**Do this week. It takes 4–12 months to be approved but priority date is filing date.**

### 2. Patent Key Innovations

These specific innovations in CRP are novel and patentable:

| Innovation | Why Novel |
|---|---|
| `CRP-Safety-Stop-Inject` — mid-stream stop sequence injection on hallucination detection | No prior art for real-time hallucination interruption at protocol layer |
| `CRP-Agent-Safety-Budget` — session-scoped risk counter in multi-agent chains | No analogous circuit-breaker mechanism in any published AI protocol |
| `CRP-Set-Session` with HMAC chain tip embedded | Combining stateless session relay with provenance chain integrity is novel |
| `CRP-Context-ETag` + conditional dispatch on fact-graph hash | Conditional AI context dispatch pattern not in prior art |
| `CRP-Safety-Policy` directive language (CSP for AI) | AI-specific safety policy at transport layer — novel architecture |

**Where:** File provisional patents in AU first (cheapest, 12-month window to convert):
- IP Australia: https://www.ipaustralia.gov.au/patents/apply-patent/provisional-applications
- Cost: ~AUD $110 per provisional application

**Then convert to PCT (Patent Cooperation Treaty) for international coverage within 12 months.**

### 3. Copyright the Spec Documents

Your spec documents (CRP-SPEC-001 through CRP-SPEC-014) are automatically copyrighted under AU law, but add explicit notices.

Every spec document should carry:
```
© 2025–2026 AutoCyber AI Pty Ltd. All rights reserved.
Context Relay Protocol™ is a trademark of AutoCyber AI Pty Ltd.
This specification is made available under the CRP Community License v1.0.
See https://crprotocol.io/license for terms.
```

**Create a CRP Community License** — similar to how IETF handles this. Key terms:
- Free to read, implement, and use in products
- Cannot fork and rename as a competing standard
- Cannot remove attribution
- Commercial use of the protocol is permitted; commercial use of the name/mark requires permission

---

## What to Make Public vs Keep Private

### ✅ Make Public (goes in your GitHub repo + crprotocol.io)

These build credibility and are required for IETF submission:

```
/spec/
  CRP-SPEC-001-core-protocol.md          ← Required for IETF
  CRP-SPEC-002-header-specification.md   ← Required for IANA + IETF
  CRP-SPEC-003-context-envelope.md       ← Public
  CRP-SPEC-004-window-continuation.md    ← Public
  CRP-SPEC-006-safety-policy-language.md ← Required for IETF
  CRP-SPEC-010-regulatory-controls-map.md← Required for NIST
  CRP-SPEC-014-conformance-test-suite.md ← Required for all bodies
```

### ⚠️ Publish Abstract Only (reference in spec, full detail protected)

```
  CRP-SPEC-005-dpe-pipeline.md    ← Publish interface/outputs, NOT algorithm weights/implementation
  CRP-SPEC-009-ckf-fabric.md      ← Publish schema/API, NOT HNSW index parameters or CKF graph impl
```

### 🔒 Keep Private / Trade Secret

```
  DPE signal weighting formula and calibration data
  CKF Leiden community detection parameters  
  CRP Comply evidence generation implementation
  CRP Gateway routing algorithm and provider pricing
  CRP Visualise rendering engine
```

**The rule:** Publish the *interface* (what goes in, what comes out, what headers mean). Keep the *implementation* (how the DPE actually scores, how CKF actually graphs). Competitors can implement the protocol correctly using only the public spec — they cannot replicate your platform.

---

## Submission 1: IANA HTTP Field Name Registry

**Priority: Do this first. Fastest, zero cost, immediate legitimacy.**

### What it gives you
Your `CRP-*` header names appear in the official IANA HTTP Field Name Registry — the same registry as `Content-Type`, `Authorization`, `Cache-Control`. Any developer looking up CRP headers finds them at iana.org. This is permanent record of prior art.

### How to do it

**Step 1:** Read RFC 9110 Section 16.3 — the registration procedure:  
https://www.rfc-editor.org/rfc/rfc9110#section-16.3

**Step 2:** For now, register as **Provisional** (doesn't require a published RFC — just an in-progress spec):

Go to: https://www.iana.org/assignments/http-fields/http-fields.xhtml  
Click: **"Registry interface"** link at the top of the page  
OR email: iana@iana.org with subject: `HTTP Field Name Registration Request`

**Step 3:** Submit the following for each header you want registered:

```
Field Name: CRP-Context-Quality-Tier
Status: provisional
Specification document: https://crprotocol.io/spec/CRP-SPEC-002-header-specification
Contact: contact@crprotocol.io / AutoCyber AI Pty Ltd
Notes: Part of the Context Relay Protocol (CRP) header specification.
       See draft-vidiniotis-crp-headers (IETF I-D, forthcoming).
```

**Step 4:** Register these headers as your first batch (the most important ones):

| Header Name | Priority |
|---|---|
| `CRP-Context-Quality-Tier` | P1 |
| `CRP-Safety-Hallucination-Risk` | P1 |
| `CRP-Safety-Policy` | P1 |
| `CRP-Provenance-HMAC` | P1 |
| `CRP-Compliance-EU-AI-Act` | P1 |
| `CRP-Compliance-Audit-Trail-URI` | P1 |
| `CRP-Agent-Safety-Budget` | P1 |
| `CRP-Set-Session` | P2 |
| `CRP-Context-ETag` | P2 |
| `CRP-Context-Cache` | P2 |

**Timeline:** 2–4 weeks for provisional registration.  
**Cost:** Free.

---

## Submission 2: IETF Internet-Draft

**Priority: Submit within 3 months. This starts the standardisation clock.**

### What it gives you
Your spec is a publicly indexed document in the global internet standards process. It is cited in academic papers, referenced by other protocol designers, and establishes prior art for every CRP concept. Getting Working Group adoption → eventual RFC is the goal, but even the I-D stage has significant value.

### The naming convention

IETF Internet-Drafts follow the format: `draft-[author]-[topic]-[sequence]`

Your draft should be named: **`draft-vidiniotis-crp-headers-00`**

### Documents to prepare

You need **two Internet-Drafts** submitted together:

**Draft 1:** `draft-vidiniotis-crp-core-00`  
Contents of: CRP-SPEC-001 (Core Protocol) — the architecture overview  

**Draft 2:** `draft-vidiniotis-crp-headers-00`  
Contents of: CRP-SPEC-002 (Header Specification) — the full header registry  

### Format requirements

IETF prefers RFCXML (xml2rfc v3). The good news: **you can write in Markdown and convert.**

**The tool:** `kramdown-rfc` — converts Markdown to RFC XML  
GitHub: https://github.com/cabo/kramdown-rfc

**Template repository:** Use this to bootstrap your I-D:  
https://github.com/martinthomson/i-d-template

The template handles GitHub Actions that auto-build your I-D to RFCXML on every commit. Your spec `.md` files in the repo become your I-D source.

### Required sections in every I-D

```markdown
# Internet-Draft structure (all required)
1. Title, authors, date, status (Informational or Standards Track)
2. Abstract (150–200 words)
3. Introduction
4. Conventions (MUST/SHOULD/MAY language per RFC 2119)
5. Technical specification
6. Security Considerations (IETF requires this — use CRP security properties)
7. IANA Considerations (list your header registrations)
8. References (normative and informative)
9. Authors' Addresses
```

### Where to submit

**Submission tool:** https://datatracker.ietf.org/submit  
(Create an IETF Datatracker account first: https://datatracker.ietf.org/accounts/create/)

You do not need to be a member of any working group to submit an I-D. Anyone can submit.

### After submission: get Working Group adoption

The IETF has an active AI protocols discussion. Email these mailing lists introducing your I-D:

1. **HTTP Working Group** (for the header spec):  
   ietf-http-wg@w3.org  
   Archive: https://lists.w3.org/Archives/Public/ietf-http-wg/

2. **General AI protocols** (for the core protocol):  
   Watch https://datatracker.ietf.org/wg/ for any AI-related WG  
   The draft-rosenberg-aiproto-framework I-D is the closest existing work — email its authors to propose CRP as a complementary spec.

3. **Propose a BoF (Birds of a Feather)** session at the next IETF meeting:  
   IETF meetings are 3× per year. Next one: watch https://www.ietf.org/meeting/upcoming/  
   BoF proposal: email ietf@ietf.org with subject "BoF Proposal: AI Context Safety Protocol"

**Timeline:** 6 months to first I-D. 18–36 months to RFC if WG adopts it.  
**Cost:** Free for I-D submission. IETF meeting attendance ~USD $900/person if you want to present.

---

## Submission 3: NIST AI RMF Reference Implementation

**Priority: Submit within 6 months. Fastest path to government credibility.**

### What it gives you
NIST's AI RMF is the reference framework for US federal AI procurement and heavily influences Australian DISR policy. Getting CRP cited as a reference implementation in the NIST AI RMF Playbook means every AI Risk Management project in the US and Australia is a potential CRP customer.

### Step 1: NIST NCCoE Technology Partner Application

The National Cybersecurity Center of Excellence accepts technology partner applications:

**Apply at:** https://www.nccoe.nist.gov/get-involved/technology-partner  
**Contact:** nccoe-partner@nist.gov  

**What to include in your application:**
- CRP as an AI context safety protocol
- Mapping to NIST AI RMF: GOVERN-1.2, MAP-1.6, MEASURE-2.5, MANAGE-3.2
- Reference: CRP-SPEC-010 (Regulatory Controls Mapping) — publish this first

### Step 2: NIST AI RMF Comment Process

NIST periodically opens the AI RMF for public comment. Submit CRP-SPEC-010 as a formal comment:

**Check for open comment periods:** https://www.nist.gov/artificial-intelligence  
**Submit comments:** Via the Federal Register notice when open  
**Contact:** aiframework@nist.gov

### Step 3: NIST AI RMF Playbook Contribution

The NIST AI RMF Playbook is a community resource:  
https://airc.nist.gov/Docs/1

Email airc@nist.gov with:
- Subject: "CRP Protocol — Reference Implementation for AI RMF MEASURE and MANAGE functions"
- Attach: CRP-SPEC-010 (regulatory controls mapping)
- Request: Citation as an implementation resource in the Playbook

**Timeline:** 6–18 months to citation.  
**Cost:** Free.

---

## Submission 4: IEEE Standards Association PAR

**Priority: Submit within 12 months after IETF I-D is live.**

### What it gives you
An IEEE standard (like IEEE 7001, 7010, or the recently ratified IEEE 2874-2025) gives CRP the highest technical legitimacy — the same body that standardised Wi-Fi, Ethernet, and AI safety frameworks. Enterprise and government procurement teams look for IEEE standards.

### Become an IEEE SA member first

Corporate membership is required to sponsor a PAR (Project Authorisation Request):  
**Apply:** https://standards.ieee.org/about/get-involved/join/  
**Cost:** USD $1,500/year for corporate membership

### Submit a PAR (Project Authorisation Request)

A PAR describes the proposed standard's scope, purpose, and need.

**PAR submission portal:** https://development.standards.ieee.org/par  
**Guide:** https://standards.ieee.org/develop/project/

**Target committee:** IEEE SA Autonomous and Intelligent Systems (AIS) Standards Committee  
This committee produced the IEEE 7000-series and IEEE 2874-2025.  
Contact: ais-standards@ieee.org

**Your PAR should describe:**
```
Title: IEEE Standard for AI Context Relay and Safety Governance Protocol (CRP)

Scope: This standard defines a protocol for AI context management, safety 
signal propagation, and governance metadata in AI systems. It specifies 
header-based communication between AI clients, protocol gateways, and 
language model providers, including specifications for hallucination risk 
scoring, provenance chain integrity, regulatory compliance metadata 
emission, and multi-agent safety budget tracking.

Need: No existing protocol standard addresses AI context management, 
real-time safety signal propagation at the transport layer, or 
cryptographically verifiable AI audit trails. This standard fills the gap 
between AI application frameworks (MCP, A2A) and AI governance regulations 
(EU AI Act, NIST AI RMF, ISO 42001).

Stakeholders: AI developers, AI system operators, compliance officers, 
security teams, regulatory bodies, enterprise IT organisations.
```

### After PAR approval: form your Working Group

Recruit members from:
- Australian Government (DISR, ASD)
- EU AI Office (European Commission)
- CSIRO (Data61)
- Industry partners: companies using CRP
- Academic: ANU Cybernetics, UNSW, University of Melbourne

**Timeline:** PAR submission to approval: 6–12 months. Working Group to published standard: 18–36 months more.  
**Cost:** USD $1,500/yr membership + staff time for Working Group management.

---

## Submission 5: ISO/IEC JTC 1/SC 42 (via Standards Australia)

**Priority: Engage Standards Australia within 6 months. Long-game but highest global reach.**

### What it gives you
ISO/IEC standards are referenced in law in 167 countries. An ISO standard for CRP makes it a normative reference in ISO 42001 audits — meaning every ISO 42001 certified organisation worldwide has a reason to evaluate CRP. This is the ultimate long-game.

### Step 1: Contact Standards Australia

Standards Australia is the Australian member body of ISO and the path to JTC 1/SC 42:

**Contact:** https://www.standards.org.au/standards-development/how-to-contribute  
**Phone:** 1800 035 822  
**Email:** info@standards.org.au  

Ask to speak to the team managing **IT-042** (Standards Australia's mirror committee for ISO/IEC JTC 1/SC 42).

**Your pitch:** "We have developed a protocol specification for AI context management and safety governance. We would like to explore submitting a New Work Item Proposal (NWIP) to JTC 1/SC 42 for an international standard."

### Step 2: JTC 1/SC 42 NWIP

Once Standards Australia agrees to sponsor, they submit the NWIP on your behalf.

**SC 42 home page:** https://www.iso.org/committee/6794475.html  
**Current SC 42 work programme:** 45 published standards, gap in protocol-level AI governance

**The NWIP requires:**
- Scope statement
- Justification (what's missing from existing standards)
- Initial draft (your published spec docs)
- Support from 5 Participating member bodies (Standards Australia will help gather these)

### Step 3: Parallel fast-track

**ISO has a PAS (Publicly Available Specification) track** that is faster than the full standard process:  
- Requires a well-established specification (your crprotocol.io spec docs qualify)
- Organisation submits it to ISO for consideration as a PAS
- Can become an ISO standard if enough member bodies support it

**This is how IETF RFCs often become ISO standards** — IETF publishes the RFC, ISO adopts it as a PAS. So IETF → ISO is a natural pipeline once your RFC is published.

**Timeline:** NWIP to published ISO standard: 36–60 months.  
**Cost:** Standards Australia membership (~AUD $2,000/yr) + staff time.

---

## Your Existing Assets — What to Do With Each

### GitHub Repository (crprotocol.io source)

**Action items:**

1. **Create `/spec/` directory** at the root with all 14 spec `.md` documents  
   (CRP-SPEC-001 through CRP-SPEC-014 — see companion files in this output)

2. **Add `LICENSE`** — a custom CRP Community License (see above)

3. **Add `CONTRIBUTING.md`** — invite contributions but require CLA  
   This builds the "community" signal IETF looks for

4. **Add `SECURITY.md`** — responsible disclosure policy  
   Required for IETF credibility

5. **Add i-d-template** GitHub Action to auto-build IETF drafts from your spec `.md` files:  
   https://github.com/martinthomson/i-d-template

6. **Create `/implementations/`** directory — list all known implementations  
   IETF Proposed Standard requires **2 independent implementations**. The Python SDK is one. Build a second reference implementation in Node.js or Go and list it here.

7. **Add GitHub Topics:** `ai-safety`, `ai-governance`, `eu-ai-act`, `protocol`, `http-headers`, `ietf`  
   This makes your repo discoverable.

### crprotocol.io (MkDocs site)

**Action items:**

1. **Add a `/spec/` section** to the MkDocs nav — renders all 14 spec `.md` documents  
   Your visitors can read the full specification at crprotocol.io/spec/

2. **Add a `/standardisation/` page** — explains the IETF, IANA, IEEE, ISO processes and links to your active drafts once submitted

3. **Add a `/.well-known/crp-protocol`** endpoint — a JSON document describing the protocol version and spec location:
   ```json
   {
     "protocol": "crp",
     "version": "3.0.0",
     "spec": "https://crprotocol.io/spec/CRP-SPEC-001-core-protocol",
     "headers": "https://crprotocol.io/spec/CRP-SPEC-002-header-specification",
     "iana_status": "provisional",
     "ietf_draft": "draft-vidiniotis-crp-headers-00"
   }
   ```

4. **Add a changelog** — important for IETF. Every spec version change documented.

### comply.crprotocol.io

**Action items:**

1. Add **"Protocol Powered"** badge to the UI — "Powered by CRP™ Protocol" with link to crprotocol.io/spec  
   This creates brand awareness every time Comply is used.

2. Add a **Standards page** — "CRP Comply's evidence generation is built on the CRP™ protocol, currently in IETF standardisation process." With links to your IANA registrations.

3. **Every evidence pack** should include a footer: "Generated by CRP Comply using CRP™ Protocol v3.0. Specification: crprotocol.io/spec"

### autocyberai.com

**This site needs an update now — it is your company's professional face.**

**Minimum update required:**
1. **Homepage:** Add CRP™ Protocol as your flagship product, with a hero section  
   "Creators of the CRP™ Protocol — the AI safety and governance standard"

2. **Products page:** Cards for CRP Protocol, CRP Comply, CRP Gateway (coming soon), CRP Visualise (coming soon)

3. **Standards page:** "AutoCyber AI is the creator of the CRP™ Protocol, currently in submission to the IETF for standardisation. CRP is the first protocol to define HTTP-style headers for AI context, safety, and governance."

4. **Press/News section:** When your IETF I-D is submitted, issue a press release through AutoCyber AI, not just crprotocol.io. Journalists looking up the company behind the protocol will land here.

5. **Contact for standardisation enquiries:** Add a dedicated email like `standards@autocyberai.com`

---

## What Else Should You Make Public?

### 1. A Reference Implementation in a Second Language

**What:** A minimal CRP client in Node.js or Go that implements the header spec  
**Why:** IETF requires 2 independent implementations for Proposed Standard status. The Python SDK is one.  
**Where:** New GitHub repo — `crprotocol/crp-js` or `crprotocol/crp-go`  
**IP protection:** Open source under MIT/Apache, but the trademarks and platform remain proprietary.

### 2. The IANA Registration Document

**What:** A public document listing all 58 CRP headers with their registration fields  
**Why:** Required for IANA submission, and published at crprotocol.io/spec/iana-considerations  
**Template format follows RFC 9110 Section 16.3**

### 3. The Regulatory Controls Mapping (CRP-SPEC-010)

**What:** The complete mapping of CRP headers to EU AI Act, GDPR, ISO 42001, NIST AI RMF controls  
**Why:** This is the document you send to NIST, DISR, and Standards Australia. Making it public builds authority.  
**Where:** crprotocol.io/spec/CRP-SPEC-010-regulatory-controls-map + GitHub

### 4. Conformance Test Suite (CRP-SPEC-014)

**What:** Test vectors and pass/fail criteria for CRP implementations  
**Why:** Any standard needs a conformance suite. IETF reviewers will ask for it.  
**Where:** `crprotocol/crp-test-suite` GitHub repo

### 5. A CRP Community Discussion Forum

**What:** GitHub Discussions enabled on the main crprotocol repo, or a Discourse forum  
**Why:** IETF reviewers look for community engagement. A forum shows active use.  
**Where:** Enable GitHub Discussions on the repo immediately. Free.

---

## Submission Timeline Summary

| Month | Action |
|-------|--------|
| **Now** | File AU trademark applications for CRP™, Context Relay Protocol™ |
| **Month 1** | File provisional patents for the 5 novel innovations |
| **Month 1** | Submit IANA provisional header registrations (top 10 headers) |
| **Month 1** | Enable GitHub Discussions, add `/spec/` directory with CRP-SPEC-001 through 006 |
| **Month 1** | Update autocyberai.com with CRP protocol section |
| **Month 2** | Publish CRP-SPEC-010 (Regulatory Controls Mapping) on crprotocol.io |
| **Month 2** | Submit CRP-SPEC-010 to NIST (aiframework@nist.gov) |
| **Month 2** | Contact NIST NCCoE Technology Partner programme |
| **Month 3** | Prepare IETF Internet-Drafts (draft-vidiniotis-crp-core-00 and draft-vidiniotis-crp-headers-00) |
| **Month 3** | Submit both I-Ds to IETF Datatracker |
| **Month 3** | Email IETF HTTP WG mailing list introducing the I-D |
| **Month 3** | Contact Standards Australia IT-042 committee |
| **Month 4** | Publish Node.js reference implementation (second implementation for IETF) |
| **Month 6** | File IEEE SA PAR (after IETF I-D is live) |
| **Month 6** | Apply to DISR AI Safety Standard consultation |
| **Month 8** | Standards Australia NWIP preparation begins |
| **Month 12** | File PCT patents (converting from AU provisional) |
| **Month 18** | IETF Working Group adoption campaign (if not already adopted) |

---

## Key Contacts & Links

### IANA
- Registry: https://www.iana.org/assignments/http-fields/http-fields.xhtml
- Contact: iana@iana.org
- HTTP WG (for header review): ietf-http-wg@w3.org

### IETF
- Datatracker: https://datatracker.ietf.org
- Submit I-D: https://datatracker.ietf.org/submit
- Author tools: https://authors.ietf.org
- i-d-template (Markdown to RFC): https://github.com/martinthomson/i-d-template
- kramdown-rfc: https://github.com/cabo/kramdown-rfc
- idnits checker: https://tools.ietf.org/tools/idnits/
- Related I-D to cite: https://datatracker.ietf.org/doc/draft-rosenberg-aiproto-framework/

### NIST
- AI RMF: https://airc.nist.gov
- NCCoE Technology Partner: https://www.nccoe.nist.gov/get-involved/technology-partner
- AI Framework contact: aiframework@nist.gov
- AI Resource Centre contact: airc@nist.gov

### IEEE SA
- Standards development: https://standards.ieee.org/develop/project/
- Membership: https://standards.ieee.org/about/get-involved/join/
- AIS committee: https://standards.ieee.org/initiatives/autonomous-intelligence-systems/
- Contact: ais-standards@ieee.org

### Standards Australia / ISO
- Standards Australia: https://www.standards.org.au
- Contribute to standards: https://www.standards.org.au/standards-development/how-to-contribute
- ISO JTC 1/SC 42: https://www.iso.org/committee/6794475.html
- Contact: info@standards.org.au

### IP Australia
- Trademarks: https://www.ipaustralia.gov.au/trade-marks/apply-for-a-trade-mark
- Patents: https://www.ipaustralia.gov.au/patents/apply-patent/provisional-applications

### Australia AI Policy
- DISR AI Safety: https://www.industry.gov.au/science-technology-and-innovation/technology/artificial-intelligence
- AI Safety Standard consultation: https://consult.industry.gov.au

---

*© 2026 AutoCyber AI Pty Ltd. Context Relay Protocol™. Confidential.*

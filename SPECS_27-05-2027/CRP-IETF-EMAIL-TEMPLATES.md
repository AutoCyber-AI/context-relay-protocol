# CRP™ IETF Outreach Email Templates

**Document:** CRP-IETF-EMAILS  
**Version:** 1.0  
**Date:** 2026-05-25  
**Status:** Ready-to-send templates — fill in `[brackets]` before sending

---

## Critical Pre-Send Checklist

Before sending ANY of these emails, you must have done:

- [ ] Filed trademark applications (AU, US, EU) for CRP™, CRP Comply™, CRP Gateway™
- [ ] Filed provisional patents for CRP-Safety-Stop-Inject and CRP-Agent-Safety-Budget
- [ ] Published `/spec/` directory on the GitHub repo with at minimum SPEC-001, SPEC-002, SPEC-006
- [ ] Published `/spec/` section on crprotocol.io linking to the GitHub docs
- [ ] Submitted the Internet-Draft to IETF Datatracker (you need a draft URL to reference)
- [ ] Created an IETF Datatracker account using your professional email

Emails reference the Internet-Draft. **Submit it first.** Then send these emails to announce it.

---

## EMAIL 1: HTTP Working Group (PRIMARY — send first)

**Why this list:** The HTTP WG owns HTTP header field standards. CRP headers are HTTP header fields. This is the most directly relevant mailing list and the one with the most operational authority over what CRP is doing.

**Subscribe first:** Go to https://lists.w3.org/Archives/Public/ietf-http-wg/ — the subscribe link is at the bottom. You can read the archive without subscribing but you cannot post unless subscribed.

**Send to:** `ietf-http-wg@w3.org`

**Subject:** `[I-D] New: draft-vidiniotis-crp-headers-00 — HTTP Header Fields for AI Context Safety and Governance`

```
Hi all,

I have submitted an Internet-Draft proposing a vocabulary of HTTP header
fields for AI context governance, safety signalling, and compliance evidence
on AI inference request/response cycles.

Draft: https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/
Repository: https://github.com/AutoCyber-AI/crprotocol-specs
Website: https://crprotocol.io/spec/

# Motivation

AI inference calls (requests to large language models) currently carry no
standardised metadata about the quality, safety, or governance status of
their responses. Every operator instruments this separately, producing
non-interoperable signals.

This draft applies the HTTP header pattern — the same pattern that gave us
Cache-Control, ETag, and Content-Security-Policy — to AI request/response
cycles. The draft defines six header namespaces:

  CRP-Context-*     envelope state, quality tier, ETag for conditional dispatch
  CRP-Safety-*      hallucination risk, attribution, fidelity, oversight mode
  CRP-Provenance-*  HMAC chain integrity, audit trail URI
  CRP-Compliance-*  EU AI Act class, NIST tier, GDPR PII flag
  CRP-Agent-*       agentic dispatch state, safety budget across agent chains
  CRP-Memory-*      context cache layer signals

A separate draft (draft-vidiniotis-crp-safety-policy-00) defines a
declarative directive language for these headers, inspired by CSP.

# What this is NOT

This is not a new inference protocol. The headers ride on existing HTTP
requests to existing LLM providers (OpenAI, Anthropic, etc.). The draft
explicitly mandates that CRP headers MUST be stripped before forwarding
to providers — the model remains ignorant of the protocol layer.

This is not a replacement for MCP or A2A. Both are based on JSON-RPC over
HTTP. The CRP headers govern the AI calls made by MCP tools and propagate
across A2A hops. CRP sits at a different layer.

# What I'm asking

I'd appreciate feedback on:

  1. Header naming and namespace structure
  2. The interaction model between CRP-Safety-Policy and Content-Security-Policy
     (which inspired it)
  3. Whether IANA provisional registration of the priority 10 headers
     (listed in §16.1 of the draft) is the right starting point
  4. Whether this work should pursue a new WG, individual submission,
     or seek adoption by an existing WG

If there's interest in a side meeting at IETF 126 (Vienna, July 2026) or
IETF 127 (San Francisco, November 2026), I'd be glad to organise one.

Two independent implementations are in development to meet Proposed
Standard interoperability requirements.

Thank you for reading. Comments and critique welcome — both on-list and
to the issue tracker on the GitHub repository.

Best,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

**After sending:**
- Expect 5–15 replies over the next 7–14 days
- Reply to every substantive comment within 48 hours
- Track open critique in a `FEEDBACK.md` in your spec repo
- Update the I-D within 60 days incorporating feedback (`-01` revision)

---

## EMAIL 2: AIPREF Working Group (AI Preferences)

**Why this list:** IETF's AIPREF WG was chartered in January 2025 to standardise mechanisms for expressing AI-related preferences in HTTP. CRP-Safety-Policy is directly in their charter scope as a preference-expression mechanism.

**Find the list:** Check the WG page at https://datatracker.ietf.org/wg/aipref/ for the current mailing list address. As of writing, it is `ai-control@ietf.org` — but verify before sending.

**Send to:** `ai-control@ietf.org` (verify on the WG page)

**Subject:** `[I-D] CRP — Header-based AI safety policy expression (complementary to AIPREF)`

```
Hi AIPREF,

I have submitted two Internet-Drafts proposing HTTP header mechanisms
for AI governance that may complement the work this WG is doing on
AI preferences:

  draft-vidiniotis-crp-headers — header field vocabulary
  draft-vidiniotis-crp-safety-policy — directive language for the headers

Repository: https://github.com/crprotocol/spec
Website: https://crprotocol.io/spec/

# Relationship to AIPREF's scope

AIPREF (as I understand it) focuses on how content publishers and
consumers express preferences about AI training and use. CRP focuses
on the run-time governance of AI inference calls — what risk levels
are tolerated, what grounding sources are trusted, when human oversight
is required.

The two are complementary:

  - AIPREF: "this content may not be used for AI training"
  - CRP:    "this AI call must halt if hallucination risk reaches CRITICAL"

Both express preferences via HTTP headers. CRP could potentially extend
AIPREF's vocabulary into the inference-time governance domain.

# What I'm proposing

I'd value feedback on whether CRP should:

  (a) be progressed as a separate work item in this WG
  (b) be progressed in HTTP WG (where I've also posted)
  (c) seek a new WG via BoF at IETF 126 or 127
  (d) remain individual submissions until WG interest develops

Happy to present the relevant subset of CRP at an interim meeting or
at IETF 126 in Vienna if there is interest.

Best,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

---

## EMAIL 3: AI Protocol Framework Author (Jonathan Rosenberg)

**Why:** `draft-rosenberg-aiproto-framework` is the most directly adjacent active I-D — it surveys MCP, A2A, and identifies gaps in AI agent protocol standardisation. The author is the right person to introduce CRP to as a complementary specification.

**Find the email:** Look up the author email in the I-D itself at https://datatracker.ietf.org/doc/draft-rosenberg-aiproto-framework/ — author emails are always in the document header.

**Send to:** `[author email from the I-D]`

**Subject:** `CRP draft — complementary to your AI agent protocol framework I-D`

```
Hi Jonathan,

I've been following your AI agent protocol framework I-D
(draft-rosenberg-aiproto-framework). The survey of MCP, A2A, and the
gaps you identify in the AI agent protocol space is exactly the
context I want to position my own work within.

I've submitted two related I-Ds focused on a layer your framework
doesn't address: governance, safety signalling, and provenance for the
underlying LLM calls that any agent protocol ultimately makes.

  draft-vidiniotis-crp-headers
  draft-vidiniotis-crp-safety-policy
  Repository: https://github.com/crprotocol/spec

# Where I see the relationship

Your framework operates at the agent-to-agent and agent-to-tool layer
(JSON-RPC payloads). CRP operates at the HTTP header layer of every
underlying LLM call. The two layers don't compete — CRP can carry
safety state across A2A hops and MCP tool calls without modifying
either protocol.

Specifically, the CRP-Agent-Safety-Budget header propagates risk
budget across agent boundaries in a way that's currently impossible
without a transport-layer mechanism. This addresses one of the
multi-agent gaps your draft mentions.

# What I'm hoping for

  1. Your reading of where CRP fits — useful gap-filler, redundant, or
     orthogonal to your direction?
  2. Whether you'd be open to a citation reference (in either direction)
     in revised drafts
  3. Whether a joint side meeting at IETF 126 (Vienna) or IETF 127
     (San Francisco) might be worth organising

No expectation of a long reply — even a single line on whether this
is in scope for your interests would be valuable.

Thanks for your time and for the work you've done documenting the
landscape.

Best,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

---

## EMAIL 4: BoF Proposal — Birds of a Feather Session

**Why a BoF:** A BoF gathers people interested in a topic to determine if a new WG should be chartered. For CRP to become a WG (rather than individual submissions indefinitely), you need a BoF at an IETF meeting demonstrating sufficient community interest.

**Required preparation before sending:**

1. Have the I-D published and reviewed by at least 5 people
2. Have 10+ supporters who will attend the BoF (solicit through Email 1, 2, 3 responses)
3. Have draft answers to all the BoF questions in RFC 5434 — the BoF coordination document

**Send to:** `iesg@ietf.org` (the Internet Engineering Steering Group) AND CC `wgchairs@ietf.org`

**Subject:** `BoF Proposal — AI Context Governance Protocol (IETF 127)`

```
Dear IESG,

I would like to request a Birds-of-a-Feather (BoF) session at IETF 127
(San Francisco, 14-20 November 2026) on the topic of HTTP header
mechanisms for AI context governance, safety signalling, and provenance.

# Proposed BoF Name

AICG (AI Context Governance) — working title

# Proposed Chairs

[To be confirmed — recruit two co-chairs, ideally one from HTTP WG
and one with AI/regulatory background]

# Background

The IETF has chartered AIPREF (AI Preferences) to address training-time
preferences. Active individual submissions (draft-rosenberg-aiproto-framework,
draft-vidiniotis-crp-headers, draft-vidiniotis-crp-safety-policy) address
agent protocols and runtime safety governance but lack a coordinating WG.

# Problem Statement

AI inference calls between clients and LLM providers carry no
standardised metadata about response quality, safety risk, or
regulatory classification. Each operator implements bespoke
instrumentation, producing non-interoperable safety signals.

This is the same problem HTTP solved with Cache-Control, ETag, and
Content-Security-Policy — but for AI inference rather than content
delivery.

The EU AI Act enters major enforcement phases in August 2026, creating
immediate operational demand for interoperable AI safety signalling.
A specification developed through IETF's open process is the right
venue to ensure global interoperability rather than vendor lock-in.

# Goals of the BoF

  1. Determine whether sufficient interest exists for a new WG
  2. Refine the problem statement and proposed scope
  3. Identify whether existing WGs (HTTPBIS, AIPREF) could absorb the
     work or whether a new WG is justified
  4. Establish initial milestones and deliverables

# Why Now

  - EU AI Act August 2026 enforcement creates concrete demand
  - draft-rosenberg-aiproto-framework demonstrates IETF interest in
    AI protocol space
  - AIPREF's chartering establishes precedent for AI-related work
  - Two existing I-Ds (draft-vidiniotis-crp-headers, draft-vidiniotis-
    crp-safety-policy) provide concrete starting documents
  - Multiple implementations already exist or are in development

# Supporters (to be confirmed)

[List of 10+ people who have expressed interest — populate from Email 1
responses before submitting]

# Documents

  draft-vidiniotis-crp-headers
  draft-vidiniotis-crp-safety-policy
  draft-rosenberg-aiproto-framework (related, by different author)

Background material: https://crprotocol.io/spec/

# Logistics

I am willing to organise the BoF, prepare slides, and coordinate
the agenda. Requesting a 60-minute slot during IETF 127.

Thank you for considering this proposal.

Best regards,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

**After sending the BoF request:**
- IESG reviews BoF requests typically 3–4 months before the meeting
- For IETF 127 (Nov 2026): submit BoF request by July 2026
- For IETF 128 (March 2027): submit by November 2026
- Expect questions back — be ready with answers to all RFC 5434 BoF questions

---

## EMAIL 5: Generic Outreach to Other AI/Standards Mailing Lists

**Where to also post:**

| List | Subscribe | Best for |
|------|-----------|----------|
| `dispatch@ietf.org` | https://www.ietf.org/mailman/listinfo/dispatch | When you're unsure which WG fits |
| W3C AI WG | Check https://www.w3.org/groups/ for current AI groups | Browser/web-context AI standards |
| OWASP AI Security | Check OWASP AI security project mailing lists | AI security community awareness |

**Send to:** `dispatch@ietf.org`

**Subject:** `[I-D] Request for guidance — CRP AI safety headers, where does this belong?`

> **Note:** Email 5 was sent referencing only `draft-vidiniotis-crp-headers`. Send **Email 5b** below as a follow-up to add the two additional confirmed drafts.

```
Hi dispatch,

Looking for guidance on the right home for three I-Ds I've submitted:

  draft-vidiniotis-crp-core-00 — core protocol specification
    https://datatracker.ietf.org/doc/draft-vidiniotis-crp-core/

  draft-vidiniotis-crp-headers-00 — HTTP header field vocabulary
    https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/

  draft-vidiniotis-crp-safety-policy-00 — CSP-inspired directive language
    https://datatracker.ietf.org/doc/draft-vidiniotis-crp-safety-policy/

I've also posted to ietf-http-wg@ and AIPREF. Both are plausible homes,
but neither is an obvious fit:

  - HTTPBIS: the headers are HTTP headers, but they encode AI-specific
    semantics that may be outside the WG's core scope
  - AIPREF: focuses on training-time preferences; CRP focuses on
    runtime governance signals

I'm considering proposing a BoF at IETF 127 (San Francisco, Nov 2026).
Before doing that, I'd value any guidance the dispatch WG can offer:

  - Is this work that should be developed in HTTPBIS as a profile?
  - Is this enough new ground to warrant a new WG?
  - Are there other adjacent WGs I should engage first?

Repository: https://github.com/AutoCyber-AI/crprotocol-specs

Best,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

---

## EMAIL 5b: Dispatch Follow-Up ⚠️ SEND NOW (adds the two missing drafts)

> **When to use:** Email 5 was already sent referencing only `draft-vidiniotis-crp-headers`.
> Send this short follow-up to add the other two confirmed drafts to the record.

**Send to:** `dispatch@ietf.org`

**Subject:** `[I-D] Follow-up: two additional drafts related to CRP headers submission`

```
Hi dispatch,

Following up on my earlier post about draft-vidiniotis-crp-headers.
Two companion drafts have also been submitted that I should have
included in the original message:

  draft-vidiniotis-crp-core-00 — core protocol and request/response model
    https://datatracker.ietf.org/doc/draft-vidiniotis-crp-core/

  draft-vidiniotis-crp-safety-policy-00 — CSP-inspired directive language
    https://datatracker.ietf.org/doc/draft-vidiniotis-crp-safety-policy/

The three drafts together form a coherent specification suite. My
question about WG home applies to all three.

Best,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

---

## After Submission: Working Group Adoption Timeline

Here is what to expect, week by week, after sending the emails above:

### Weeks 1–2: Initial responses
- 5–15 substantive replies on the HTTP WG list
- 2–5 replies on AIPREF
- Reply within 48 hours to every substantive comment
- Most replies will be critiques — that's good

### Weeks 3–4: First substantive feedback
- File issues on the GitHub spec repo for every actionable critique
- Group similar feedback into themed discussions on the list
- Identify 3–5 active participants who consistently engage

### Months 2–3: Draft revision
- Publish `-01` revision incorporating feedback
- Announce the new revision on the same lists
- Begin organising informal side meeting for IETF 126 (Vienna, July 2026)

### Months 4–6: Side meetings and BoF prep
- Side meeting at IETF 126 — informal, no IESG approval needed
- Use it to validate BoF readiness
- If positive, submit BoF request for IETF 127 (San Francisco, Nov 2026)

### Months 6–12: BoF (if approved)
- BoF held at IETF 127
- Demonstrates interest level
- IESG decides whether to charter a new WG
- Alternative: existing WG adopts the work

### Months 12–18: WG adoption
- If WG forms or existing WG adopts: documents become `draft-ietf-*`
- Document review continues with WG Last Call
- Multiple I-D revisions (`-02`, `-03`, etc.)

### Months 18–36: Proposed Standard
- Two independent implementations required (CRP Gateway + at least one third-party)
- Conformance test results published per CRP-SPEC-014
- IETF Last Call → IESG review → RFC publication

### Cost summary

  - I-D submission: $0
  - Mailing list participation: $0
  - IETF meeting (remote attendance): $0 for some sessions, ~USD $250 for full remote
  - IETF meeting (in-person): ~USD $900 per person for full registration
  - Travel to IETF 126 (Vienna) or IETF 127 (San Francisco): variable, plan ~USD $2,500
    including flights and hotel
  - Total realistic year-1 budget for IETF track: USD $5,000–$10,000

---

## Tone Guidance for IETF Communication

The IETF has a specific culture. Get this right:

  - Direct, not promotional. Don't say "revolutionary" — say what the
    spec does and let reviewers judge.
  - Acknowledge prior art and adjacent work. Cite MCP, A2A, CSP, Cache-Control
    as inspirations or related work.
  - Welcome critique. The first reply to your post will be a critique.
    Thank the person, address the substance, file the issue.
  - Avoid commercial framing. Mention AutoCyber AI Pty Ltd as the author/
    employer but do not pitch CRP Comply or Gateway. IETF cares about the
    open spec, not your business.
  - Use lowercase for namespaces in casual prose. "the crp-safety-policy
    directive" reads more naturally than "the CRP-SAFETY-POLICY directive."
  - Reply on-list, not off-list. Conversations on the list are part of the
    standards record. Off-list deals make IETF participants suspicious.

---

*© 2025–2026 AutoCyber AI Pty Ltd. Internal use template — fill in [brackets] before sending.*

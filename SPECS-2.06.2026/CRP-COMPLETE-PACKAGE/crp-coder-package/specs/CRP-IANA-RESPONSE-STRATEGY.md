# CRP™ IANA Response Strategy

**Date:** 2026-05-29
**Status:** Urgent — reply needed

---

## 1. The Email Thread: Facts Only

### What happened (chronologically):

1. **You submitted** a provisional HTTP header registration request via the IANA web form on May 28, 2026
2. **You requested** registration of 10 CRP-* headers
3. **You referenced** two Internet-Drafts:
   - `draft-vidiniotis-crp-core`
   - `draft-vidiniotis-crp-headers`
4. **David Dong (IANA)** confirmed receipt and forwarded to designated experts
5. **You replied** confirming the I-D references and offering additional info
6. **The designated experts rejected** with: *"This draft hasn't been adopted on any stream, and is only a first proposal now; deferring until it gets some traction in the community."*

### What you have (your 3 Internet-Drafts):

1. `draft-vidiniotis-crp-core-00` — Core protocol
2. `draft-vidiniotis-crp-headers-00` — Header field vocabulary
3. (Third I-D — confirm: is this `draft-vidiniotis-crp-safety-policy-00`?)

---

## 2. What the Expert's Response Actually Means

**They are NOT saying CRP doesn't exist or isn't real.**

They are saying: "We receive many header registration requests from brand-new individual I-Ds that never go anywhere. We defer registration until the I-D has demonstrated it is going to progress."

Breaking down the exact words:

- **"hasn't been adopted on any stream"** — Your I-Ds are currently individual submissions (`draft-vidiniotis-*`). They haven't been adopted by a Working Group (`draft-ietf-*`), the Independent Stream, the IRTF stream, or the IAB stream. This is a factual statement about the I-D's current status, not a judgment of quality.

- **"only a first proposal now"** — The I-Ds are at version `-00` (first submission). No revisions, no community feedback incorporated, no evidence of iterative development through the IETF process.

- **"deferring until it gets some traction in the community"** — This is the key phrase. "Traction" means one or more of:
  - Mailing list discussion (substantive replies on ietf-http-wg@ or another WG list)
  - Working Group interest or adoption call
  - Independent Stream Editor acceptance
  - Multiple implementations referenced in the I-D
  - A revision (-01) incorporating community feedback
  - A side meeting or BoF at an IETF meeting

**The expert is giving you a roadmap, not a rejection.**

---

## 3. Questions You Should Ask IANA to Clarify

Send these questions in your reply. They are legitimate clarification requests that show you understand the process and are seeking actionable guidance:

**Question 1:** "What specific evidence of community traction would satisfy the expert review criteria for provisional registration? For example, would mailing list discussion on ietf-http-wg@w3.org, a published -01 revision, or evidence of multiple implementations be sufficient?"

**Question 2:** "Would acceptance by the Independent Submission Stream (via the ISE) satisfy the 'adopted on any stream' criterion, or does the expert require IETF Working Group adoption specifically?"

**Question 3:** "Is there a minimum number of I-D revisions or a minimum time period the expert expects before reconsidering? I want to ensure I meet the criteria before resubmitting."

**Question 4:** "The specification references a working implementation (pip install crprotocol, CRP v3 on PyPI). Does the expert consider implementation evidence relevant to the traction assessment?"

---

## 4. The Reply Email to Send

**To:** iana@iana.org (reply to the existing thread)
**CC:** (nobody — keep it in the same thread)
**Subject:** RE: [existing thread subject]

```
Dear David and the designated expert,

Thank you for the clear feedback. I understand the deferral and 
appreciate the guidance.

To help me meet the criteria for a future resubmission, I have 
a few clarifying questions:

1. What specific evidence of community traction would satisfy 
   the expert review criteria for provisional registration? 
   Would substantive mailing list discussion, a revised (-01) 
   draft incorporating community feedback, or evidence of 
   multiple implementations be sufficient?

2. Would acceptance by the Independent Submission Stream 
   satisfy the "adopted on any stream" criterion, or is IETF 
   Working Group adoption specifically required?

3. Is there a minimum period or number of draft revisions the 
   expert expects before reconsidering?

4. The specifications reference a working, published 
   implementation (crprotocol on PyPI, CRP v3). Does 
   implementation evidence factor into the traction assessment?

For context on current progress:
- The I-Ds have been announced on the ietf-http-wg@w3.org 
  mailing list
- A reference implementation is published and verified 
  (pip install crprotocol)
- We are engaging with the AIPREF Working Group on potential 
  stream adoption
- A side meeting at IETF 126 (Vienna, July 2026) is being 
  explored

I will re-submit this request once the criteria are met. Thank 
you for the guidance.

Best regards,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

---

## 5. Where Else to Submit — And Exactly What

You have 3 Internet-Drafts. Here is where each one should go next:

### 5.1 Independent Submission Stream (ISE) — FASTEST PATH TO IANA

**What:** Submit all 3 I-Ds (or just the headers I-D) to the Independent 
Submission Editor (ISE) for consideration as an Independent Stream RFC.

**Why:** An Independent Stream RFC satisfies IANA's "adopted on any stream" 
criterion without needing WG adoption. It is published as an Informational 
RFC — a real RFC with a real number.

**Who:** Eliot Lear, Independent Submission Editor
**Email:** rfc-ise@rfc-editor.org
**Submit what:** `draft-vidiniotis-crp-headers` (the most self-contained 
and directly registrable of the three)

**Email to send:**
```
Subject: Independent Stream Submission Inquiry — CRP Header Fields

Dear Eliot,

I would like to inquire about submitting an Internet-Draft for 
consideration on the Independent Submission Stream:

  draft-vidiniotis-crp-headers-00
  https://datatracker.ietf.org/doc/draft-vidiniotis-crp-headers/

The draft defines HTTP header field vocabulary for AI context 
governance and safety signalling. It specifies 58 header fields 
across six namespaces (CRP-Context-*, CRP-Safety-*, 
CRP-Provenance-*, CRP-Compliance-*, CRP-Agent-*, CRP-Memory-*) 
carried on standard HTTP request/response cycles between AI 
applications and LLM providers.

The draft has a published reference implementation 
(pip install crprotocol, verified against local and hosted LLMs) 
and has been announced on ietf-http-wg@w3.org.

I submitted a provisional HTTP Field Name registration to IANA 
which was deferred by the designated expert pending stream 
adoption. I am pursuing the Independent Stream as a path to 
satisfy that criterion.

Related I-Ds:
  draft-vidiniotis-crp-core-00
  [third I-D name]

Could you advise whether this work is suitable for the 
Independent Submission Stream?

Best regards,
Constantinos Vidiniotis
AutoCyber AI Pty Ltd
contact@crprotocol.io
```

### 5.2 HTTP Working Group — ALREADY DONE, FOLLOW UP

**What:** You've already emailed ietf-http-wg@w3.org. Now you need to:

1. Check if you received replies — substantive discussion on the list IS 
   the "traction" the IANA expert wants to see
2. If no replies yet, post a follow-up in 2-3 weeks with a specific 
   technical question (not just a re-announcement) — e.g., "I'd value 
   feedback on whether the CRP-Safety-Policy directive grammar is 
   compatible with CSP's parsing model"
3. If you got replies, engage them substantively and track the discussion

### 5.3 AIPREF Working Group — ALREADY DONE, FOLLOW UP

**What:** Same as above — check for replies, engage if received.

### 5.4 IETF 126 Side Meeting (Vienna, July 18-24, 2026)

**What:** Book an informal side meeting at IETF 126. No approval needed — 
you just need a room and attendees.

**How:** See https://wiki.ietf.org/meeting/126/sidemeetings
Sign up for a slot. Title it: "AI Context Safety Headers — CRP Protocol"

**Why this matters for IANA:** A side meeting at an IETF meeting with 
10+ attendees is strong evidence of "community traction." Mention it 
in your IANA resubmission.

### 5.5 Publish a -01 Revision

**What:** Update each I-D to version -01. Include:
- A "Changes from -00" section
- Any feedback received from mailing lists
- An "Implementation Status" section (RFC 7942 format) referencing 
  `crprotocol` on PyPI

**Why:** The expert noted the I-Ds are "only a first proposal." A -01 
revision shows iterative development and community engagement. This 
is one of the easiest "traction" signals to produce.

### 5.6 Where NOT to submit yet

- **IEEE SA:** Not relevant to IANA registration. Pursue separately 
  for the broader standard.
- **ISO/IEC JTC 1:** Same — separate track, doesn't help IANA.
- **NIST:** Same — different audience.

**The IANA unblock path is specifically: ISE acceptance OR WG adoption 
OR demonstrable community traction (mailing list + -01 revision + 
side meeting).**

---

## 6. The Realistic Timeline

| When | Action | Traction Signal |
|------|--------|----------------|
| This week | Reply to IANA with clarifying questions | Shows process awareness |
| This week | Email ISE (rfc-ise@rfc-editor.org) | Opens Independent Stream path |
| Next 2 weeks | Follow up on HTTP WG / AIPREF mailing lists | Generates discussion |
| June 2026 | Publish -01 revisions of all 3 I-Ds | Shows iteration |
| June 2026 | Book IETF 126 side meeting (Vienna) | Demonstrates community interest |
| July 2026 | Attend IETF 126 side meeting | In-person traction |
| August 2026 | Resubmit IANA registration with evidence | Should succeed this time |

---

*© 2025–2026 AutoCyber AI Pty Ltd.*

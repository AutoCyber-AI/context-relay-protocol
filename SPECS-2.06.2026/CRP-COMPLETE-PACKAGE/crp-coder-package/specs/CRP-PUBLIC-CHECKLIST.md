# CRP™ Public Presence Checklist

**Document:** CRP-PUBLIC-CHECKLIST  
**Status:** Action items — prioritised  
**Date:** 2026-05-24

---

## What You Have (Current State)

| Asset | URL | Status | Gap |
|-------|-----|--------|-----|
| Protocol site | crprotocol.io | ✅ Live (MkDocs) | Missing /spec/ section |
| Compliance platform | comply.crprotocol.io | ✅ Live | Needs live protocol integration |
| GitHub repo | github.com/crprotocol/? | ✅ Live | Missing /spec/ directory with .md docs |
| Company site | autocyberai.com | ⚠️ Stale | No mention of CRP protocol |

---

## What to Add, In Priority Order

### Priority 1 — Do before any public standards submission

**GitHub repo (`github.com/crprotocol/spec` or add to existing repo):**
```
spec/
├── README.md              ← "CRP Specification — Index of Documents"
├── CRP-SPEC-001-core.md
├── CRP-SPEC-002-headers.md
├── CRP-SPEC-003-envelope.md
├── CRP-SPEC-004-continuation.md
├── CRP-SPEC-005-dpe.md
├── CRP-SPEC-006-safety-policy.md
└── CRP-SPEC-010-regulatory-mapping.md

CONTRIBUTING.md            ← Required for IETF credibility
SECURITY.md
LICENSE (CC BY 4.0)
CHANGELOG.md
```

**crprotocol.io (MkDocs additions):**
- `/spec/` — document index, links to GitHub
- `/spec/headers/` — complete header reference
- `/spec/safety-policy/` — CSP-style directive grammar
- `/spec/conformance/` — Basic/Standard/Full levels
- `/changelog/` — version history
- `/accreditation/` — IANA registration status (once live)

### Priority 2 — autocyberai.com update

**Homepage:** Add CRP as the core technology product.  
Suggested headline: *"We built the AI safety protocol making AI systems auditable by default."*

**Add pages:**
- `/protocol/` — what CRP is, link to crprotocol.io
- `/products/` — CRP Comply, CRP Gateway (coming), CRP Visualise (coming)
- `/news/` — "CRP v3.0 — AI Safety Headers" announcement post

**Why this matters for accreditation:** IEEE and ISO reviewers will look up AutoCyber AI. A stale company site undermines credibility.

### Priority 3 — Community presence

| Platform | Action | Why |
|----------|--------|-----|
| **IETF Datatracker** | Create account, bookmark AI-related WGs | Required for I-D submission |
| **GitHub Discussions** | Enable on spec repo | Shows community engagement |
| **LinkedIn (company page)** | Post about CRP v3 headers | Enterprise audience |
| **Hacker News** | Post "Show HN: CRP — AI Safety Headers" | Developer audience, IETF participants |
| **Dev.to / Medium** | Technical blog post on CRP headers vs HTTP analogy | Developer adoption |

---

## What NOT to Make Public (IP Risk)

| Item | Keep Private | Reason |
|------|-------------|--------|
| DPE exact scoring weights | ✅ Private | Competitive advantage, possible patent |
| CRP-Safety-Stop-Inject implementation | ⚠️ Patent first | File provisional before publishing internals |
| CRP-Agent-Safety-Budget algorithm | ⚠️ Patent first | Novel, patentable mechanism |
| CRP Comply source code | ✅ Private | Commercial product |
| CRP Gateway source code | ✅ Private | Commercial product |
| Session token signing key derivation | ✅ Private | Security-critical |
| Customer audit trail data | ✅ Private | GDPR, confidentiality |

---

## Spec Document Open/Closed Status

| Document | Make Public? | Format | Timing |
|----------|-------------|--------|--------|
| CRP-SPEC-001 Core Protocol | ✅ Yes | .md → GitHub + site | Now |
| CRP-SPEC-002 Headers | ✅ Yes | .md → GitHub + site + IANA | Now |
| CRP-SPEC-003 Envelope | ✅ Yes | .md → GitHub | Now |
| CRP-SPEC-004 Continuation | ✅ Yes | .md → GitHub | Now |
| CRP-SPEC-005 DPE | ⚠️ Partial | Public: structure and outputs. Private: scoring weights | After patent provisional |
| CRP-SPEC-006 Safety Policy | ✅ Yes | .md → GitHub + IETF I-D | Now |
| CRP-SPEC-007 Session Token | ⚠️ Partial | Public: header format. Private: signing algorithm | After patent provisional |
| CRP-SPEC-008 Dispatch Strategies | ✅ Yes | .md → GitHub | Now |
| CRP-SPEC-009 CKF | ⚠️ Partial | Public: interface. Private: HNSW config | Now (partial) |
| CRP-SPEC-010 Regulatory Mapping | ✅ Yes — critical | .md → GitHub + NIST submission | Now |
| CRP-SPEC-011 Audit Chain | ✅ Yes | .md → GitHub | Now |
| CRP-SPEC-012 Multi-Agent Safety | ⚠️ Partial | Public after patent provisional | After patent |
| CRP-SPEC-013 GitHub Action | ✅ Yes | .md + GitHub Action code | With GitHub Action launch |
| CRP-SPEC-014 Conformance Suite | ✅ Yes | .md → GitHub | Now |

---

*© 2025–2026 AutoCyber AI Pty Ltd.*

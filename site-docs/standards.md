---
seo_title: CRP Standards Track — IETF, IANA, IEEE SA & ISO/IEC Submissions
description: CRP is submitted to IETF, IANA, IEEE SA, and ISO/IEC JTC 1/SC 42 as an open standard for AI context governance.
---

# Standards Track

The Context Relay Protocol™ is an open specification authored by
**Constantinos Vidiniotis** at **AutoCyber AI Pty Ltd** (ABN 22 697 087 166)
and submitted to international standards bodies for recognition.

The v4 specification suite consists of **48 specifications** covering core
protocol, safety, quality, storage, configuration, and product interfaces.

## Active Submissions

| Body | Track | Status |
|------|-------|--------|
| **IANA** | HTTP Field Name Registry - provisional registration of `CRP-*` headers | Submitted |
| **IETF** | Internet-Draft `draft-vidiniotis-crp-headers` | Submitted |
| **IETF** | Internet-Draft `draft-vidiniotis-crp-safety-policy` | Submitted |
| **IEEE SA** | Project Authorization Request (PAR) | In preparation |
| **ISO/IEC JTC 1/SC 42** | New Work Item via Standards Australia (DISR) | In preparation |
| **NIST NCCoE** | Technology Partner application | In progress |

## Spec Documents Backing Each Submission

| Submission | Primary Spec |
|------------|--------------|
| IANA HTTP Field Names | [SPEC-002](spec/CRP-SPEC-002-headers.md) |
| IETF - CRP Headers I-D | [SPEC-001](spec/CRP-SPEC-001-core-protocol.md), [SPEC-002](spec/CRP-SPEC-002-headers.md), [SPEC-014](spec/CRP-SPEC-014-conformance.md) |
| IETF - CRP Safety Policy I-D | [SPEC-006](spec/CRP-SPEC-006-safety-policy.md), [SPEC-014](spec/CRP-SPEC-014-conformance.md) |
| ISO/IEC JTC 1/SC 42 NWI | [SPEC-001](spec/CRP-SPEC-001-core-protocol.md), [SPEC-010](spec/CRP-SPEC-010-regulatory-mapping.md), [SPEC-011](spec/CRP-SPEC-011-audit-trail.md) |
| NIST AI RMF mapping | [SPEC-010](spec/CRP-SPEC-010-regulatory-mapping.md) |

## Reference Implementation

The reference implementation in this repository is **conformant with
SPEC-014 Level 2** (full interoperability). See the
[conformance test suite](testing/running-tests.md) for verification.

## Independent Implementations

CRP is designed to be implemented in any language. Header names, ABNF, and
semantics are specified normatively in SPEC-001 / SPEC-002 / SPEC-006 and
require no Python, no SDK, and no licence to implement.

If you are implementing CRP independently, please open an issue in the
[spec repository](https://github.com/AutoCyber-AI/context-relay-protocol)
so we can list your project and run interop tests.

## Contact for Standards Reviewers

- IETF / IANA correspondence: <standards@crprotocol.io>
- IEEE SA / ISO correspondence: <standards@crprotocol.io>
- Editorial errata: <spec@crprotocol.io>

---

*"Context Relay Protocol" and "CRP" are trademarks of Constantinos Vidiniotis
(application pending). The protocol itself is open and free to implement.*

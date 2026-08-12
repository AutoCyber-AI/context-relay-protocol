# CRP Visualise

!!! warning "Coming soon"
    CRP Visualise is **not yet generally available**. It is in private alpha
    with a small number of enterprise pilot customers. The managed service at
    `visualise.crprotocol.io` and the self-hosted container are on the roadmap.
    [Join the waitlist →](mailto:visualise@crprotocol.io)

**See every decision, claim, and risk in a CRP session - live in the browser.**

CRP Visualise turns opaque AI calls into inspectable evidence for auditors,
regulators, and incident responders. It renders the Window DAG, DPE verdicts,
claim provenance, hallucination heat-maps, and Safety Policy evaluations for
any CRP session, in real time.

## What You See

- The Window DAG (every continuation node, every stitch, every re-extraction).
- DPE verdict timeline per call - risk score, flow score, completeness ratio.
- Claim-to-fact provenance: click any sentence in any output to see the source.
- Safety Policy evaluation trail - which directive matched, what verdict it produced.
- HMAC chain integrity status across the session.
- Regulatory-control coverage for the session (EU AI Act, ISO 42001, GDPR).

## Who It Is For

| Audience | Why it matters |
|----------|----------------|
| Internal auditors | Walk through a session like a flight recorder. |
| External auditors / regulators | Read-only sealed view; cryptographic chain verification. |
| Incident responders | Reconstruct exactly what the AI said, when, with what evidence. |
| Engineers | Debug context packing, continuation, and policy decisions visually. |

## Architecture

Visualise consumes the same audit chain emitted by [SPEC-011](../spec/CRP-SPEC-011-audit-trail.md).
It is **read-only** and **stateless** - no LLM calls, no data mutation, no
PII storage beyond the existing audit retention policy.

## Deployment

- Managed service at `visualise.crprotocol.io` *(coming soon)*.
- Self-hosted container for air-gapped / sovereign deployments *(coming soon)*.
- Optional regulator-portal mode (sealed read-only access by case number).

[:octicons-arrow-right-24: Join the waitlist](mailto:visualise@crprotocol.io)

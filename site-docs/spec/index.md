---
seo_title: CRP Specifications — 50 Open Specs for AI Context, Safety & Compliance
description: Index of the 50 CRP specifications covering core protocol, headers, envelope, safety, provenance, compliance, agentic positioning, and product interfaces.
---

# CRP™ Formal Specification

The Context Relay Protocol™ is defined by a family of **50 normative specifications**
that collectively describe the wire-level behaviour of CRP v5.1: the headers,
envelope packing, continuation graph, Decision Provenance Engine, safety-policy
directive language, multi-agent safety, audit trail, conformance levels,
retrieval-integrity layer, cognitive state object, semantic task layer, and
security / privacy properties.

This section is the authoritative reference and the anchor for international
standards submissions (IANA, IETF, IEEE SA, ISO/IEC JTC 1/SC 42).

## Why These Specifications Matter

**For implementers**, the specs provide an unambiguous contract: every
`CRP-*` header, envelope phase, continuation edge, and audit field is defined
with normative language, ABNF syntax, and conformance tests. Two independent
implementations that follow the same spec should interoperate without guesswork.

**For customers and auditors**, the specs are the evidence base. They map
every CRP control to ISO/IEC 42001, the EU AI Act, GDPR, NIST AI RMF, and
ISO/IEC 27001, so a deployment can be assessed against published criteria rather
than opaque marketing claims.

**For standards bodies**, the specs are submission-ready modules: header fields
for IANA, architecture and conformance for IETF, and quality / safety arguments
for IEEE SA and ISO/IEC JTC 1/SC 42.

## How to Read These Documents

Each specification follows IETF RFC conventions:

- **Normative keywords** ("MUST", "SHOULD", "MAY") follow [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) / [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).
- Header-field syntax is expressed in [ABNF](https://www.rfc-editor.org/rfc/rfc5234).
- Cryptographic primitives (HMAC-SHA256, SHA-256) follow [FIPS 198-1](https://csrc.nist.gov/pubs/fips/198-1/final) and [FIPS 180-4](https://csrc.nist.gov/pubs/fips/180-4/upd1/final).
- Interoperability is governed by SPEC-014 (Conformance & Test Suite).

## Document Index

| Spec | Title | Status | Standards-Track Anchor |
|------|-------|--------|------------------------|
| [SPEC-001](CRP-SPEC-001-core-protocol.md) | CRP-SPEC-001: Core Protocol Specification | Draft | Architecture |
| [SPEC-002](CRP-SPEC-002-headers.md) | CRP-SPEC-002: Header Field Specification | Draft | IANA HTTP Field Name Registry |
| [SPEC-003](CRP-SPEC-003-envelope.md) | CRP-SPEC-003: Context Envelope & Packing Specification | Draft | - |
| [SPEC-004](CRP-SPEC-004-continuation.md) | CRP-SPEC-004: Window Continuation & DAG Specification | Draft | - |
| [SPEC-005](CRP-SPEC-005-dpe.md) | CRP-SPEC-005: Decision Provenance Engine (DPE) Specification | Draft | - |
| [SPEC-006](CRP-SPEC-006-safety-policy.md) | CRP-SPEC-006: Safety Policy Directive Language | Draft | IETF Internet-Draft |
| [SPEC-007](CRP-SPEC-007-session-token.md) | CRP-SPEC-007: Session Token & State Relay | Draft | - |
| [SPEC-008](CRP-SPEC-008-dispatch.md) | CRP-SPEC-008: Dispatch Strategy Specification | Draft | - |
| [SPEC-009](CRP-SPEC-009-ckf.md) | CRP-SPEC-009: Contextual Knowledge Fabric (CKF) Specification | Draft | - |
| [SPEC-010](CRP-SPEC-010-regulatory-mapping.md) | CRP-SPEC-010: Regulatory Controls Mapping | Draft | NIST AI RMF / ISO 42001 / EU AI Act |
| [SPEC-011](CRP-SPEC-011-audit-trail.md) | CRP-SPEC-011: Audit Trail & HMAC Chain Specification | Draft | - |
| [SPEC-012](CRP-SPEC-012-multi-agent-safety.md) | CRP-SPEC-012: Multi-Agent Safety Protocol | Draft | - |
| [SPEC-013](CRP-SPEC-013-github-action.md) | CRP-SPEC-013: GitHub Action & Scanner Specification | Draft | - |
| [SPEC-014](CRP-SPEC-014-conformance.md) | CRP-SPEC-014: Conformance & Test Suite Specification | Draft | IETF interop requirement |
| [SPEC-015](CRP-SPEC-015-security-privacy.md) | CRP-SPEC-015: Security & Privacy Specification | Draft | - |
| [SPEC-016](CRP-SPEC-016-gateway-service.md) | CRP-SPEC-016: Gateway Service Specification | Public draft | - |
| [SPEC-017](CRP-SPEC-017-zero-ckf-mode.md) | CRP-SPEC-017: Zero-CKF Mode & Progressive Activation | Draft | - |
| [SPEC-018](CRP-SPEC-018-air.md) | CRP-SPEC-018: Adaptive Intelligence Relay (AIR) | Public draft | - |
| [SPEC-019](CRP-SPEC-019-cognitive-quality.md) | CRP-SPEC-019: Cognitive Quality Relay (CQR) & Reasoning Scaffold Protocol | Public draft | - |
| [SPEC-020](CRP-SPEC-020-cognitive-load-distribution.md) | CRP-SPEC-020: Cognitive Load Distribution (CLD) | Public draft | - |
| [SPEC-021](CRP-SPEC-021-reasoning-orchestration.md) | CRP-SPEC-021: Reasoning Orchestration & Self-Consistency (ROS) | Public draft | - |
| [SPEC-022](CRP-SPEC-022-execution-fabric.md) | CRP-SPEC-022: Parallel Execution Fabric (PEF) & Amplification Economics | Public draft | - |
| [SPEC-023](CRP-SPEC-023-amplification-boundary.md) | CRP-SPEC-023: The Amplification Boundary - Protocol Layering & Opt-In Capability Model | Public draft | - |
| [SPEC-024](CRP-SPEC-024-coverage-differential-retrieval.md) | CRP-SPEC-024: Coverage-Differential Retrieval (CDR) | Public draft | - |
| [SPEC-025](CRP-SPEC-025-graph-retrieval.md) | CRP-SPEC-025: Coverage-Differential Graph Retrieval (CDGR) | Public draft | - |
| [SPEC-026](CRP-SPEC-026-semantic-quality-benchmark.md) | CRP-SPEC-026: Semantic Quality Benchmark (SQB) | Public draft | - |
| [SPEC-027](CRP-SPEC-027-retrieval-integrity.md) | CRP-SPEC-027: Retrieval Integrity - Concurrency, Conflict Resolution & Recency | Public draft | - |
| [SPEC-028](CRP-SPEC-028-conversational-context.md) | CRP-SPEC-028: Multi-Horizon Context Model & Conversational Retrieval | Public draft | - |
| [SPEC-029](CRP-SPEC-029-ephemeral-tool-context.md) | CRP-SPEC-029: Ephemeral & Tool Context (Tier E) | Public draft | - |
| [SPEC-030](CRP-SPEC-030-cognitive-state-relay.md) | CRP-SPEC-030: The Cognitive State Object & State Relay Protocol | Public draft | - |
| [SPEC-031](CRP-SPEC-031-semantic-task-layer.md) | CRP-SPEC-031: The Semantic Task Layer (STL) - Positioning, Not Injection | Public draft | - |
| [SPEC-032](CRP-SPEC-032-developer-experience.md) | CRP-SPEC-032: Developer Experience & The Progressive Disclosure SDK | Public draft | - |
| [SPEC-033](CRP-SPEC-033-safety-control-plane.md) | CRP-SPEC-033: The Safety Control Plane & Inline Human-in-the-Loop | Public draft | - |
| [SPEC-034](CRP-SPEC-034-safety-coverage.md) | CRP-SPEC-034: AI Safety Coverage Map & Checkpoint Lifecycle | Public draft | - |
| [SPEC-035](CRP-SPEC-035-context-lifecycle.md) | CRP-SPEC-035: Context Lifecycle & Access Tiering - The Storage Engine | Public draft | - |
| [SPEC-036](CRP-SPEC-036-scan-remediation.md) | CRP-SPEC-036: CRP Scan Remediation Engine | Public draft | - |
| [SPEC-037](CRP-SPEC-037-unified-config.md) | CRP-SPEC-037: The Unified Configuration - One File Governs Everything | Public draft | - |
| [SPEC-038](CRP-SPEC-038-storage-backends.md) | CRP-SPEC-038: Pluggable Storage Backends - Bring Your Own Store | Public draft | - |
| [SPEC-039](CRP-SPEC-039-semantic-code-ingestion.md) | CRP-SPEC-039: Semantic Codebase Ingestion - CRP Scanning With CRP | Public draft | - |
| [SPEC-040](CRP-SPEC-040-crp-comply.md) | CRP-SPEC-040: CRP Comply - The Three-Layer AI Compliance & Governance Platform | Public draft | - |
| [SPEC-041](CRP-SPEC-041-adoption-ecosystem.md) | CRP-SPEC-041: Adoption & Ecosystem - Time-to-Value, Integrations, and Growth | Public draft | - |
| [SPEC-042](CRP-SPEC-042-comply-upgrade-integration.md) | CRP-SPEC-042: CRP Comply v2→v4 Upgrade & Ecosystem Integration | Public draft | - |
| [SPEC-043](CRP-SPEC-043-gateway-runtime-product.md) | CRP-SPEC-043: The Gateway as Runtime Product & The Visual Console | Public draft | - |
| [SPEC-044](CRP-SPEC-044-authoritative-domain-agent.md) | CRP-SPEC-044: The Authoritative Domain Agent | Public draft | - |
| [SPEC-045](CRP-SPEC-045-knowledge-learning.md) | CRP-SPEC-045: Session & Persistent Knowledge Learning | Public draft | - |
| [SPEC-046](CRP-SPEC-046-user-defined-cognition.md) | CRP-SPEC-046: User-Defined Cognition - The Thinking Process Compiler | Public draft | - |
| [SPEC-047](CRP-SPEC-047-monetisation-payments.md) | CRP-SPEC-047: Monetisation, Payments & Account Linkage | Internal - withheld | - |
| [SPEC-048](CRP-SPEC-048-comply-lowcode-github.md) | CRP-SPEC-048: No-Code Governance via Scan, GitHub Connection & Result-Preserving Signup | Public draft | - |
| [SPEC-HOSTING](CRP-SPEC-HOSTING-CONTROL.md) | CRP™ Hosting, Control & Data Architecture | Internal - withheld | - |

## Reading Order for Reviewers

- **IETF reviewers** - read in order: SPEC-001, SPEC-002, SPEC-006, SPEC-014, SPEC-015.
- **IANA reviewers** - SPEC-002 contains all provisional CRP-* header registrations.
- **IEEE SA / ISO reviewers** - SPEC-001, SPEC-005, SPEC-010, SPEC-011.
- **Implementers** - SPEC-001, SPEC-003, SPEC-004, SPEC-008, SPEC-014.
- **Auditors and regulators** - SPEC-010, SPEC-011, SPEC-015.

## Stability and Versioning

CRP follows semantic versioning. Breaking changes require a new major version
and a new IETF Internet-Draft revision. The current version is **v4.0**.

Errata and editorial changes are tracked in [CHANGELOG.md](https://github.com/AutoCyber-AI/context-relay-protocol/blob/main/CHANGELOG.md)
in the canonical repository.

## Licensing

The specification text is published under CC BY-SA 4.0. The reference implementation code remains under Elastic License 2.0. The protocol itself - header names, ABNF, semantics - is open and free to implement. "Context Relay Protocol" and "CRP" are
trademarks of Constantinos Vidiniotis (application pending).

---

**Questions?** Contact [info@crprotocol.io](mailto:info@crprotocol.io) or open an
issue in the [canonical repository](https://github.com/AutoCyber-AI/context-relay-protocol).
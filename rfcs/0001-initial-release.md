<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# RFC-0001: CRP v2.0 Initial Release

- **RFC Number**: 0001
- **Title**: Context Relay Protocol v2.0 — Initial Specification Release
- **Author(s)**: Constantinos Vidiniotis (@Constantinos-uni)
- **Status**: Accepted
- **Created**: 2026-04-06

## Summary

This RFC documents the rationale for the CRP v2.0 initial specification release. CRP v2.0 is the first public version of the Context Relay Protocol — an open protocol for structured context management across LLM invocations.

## Motivation

Every agentic AI system forces its LLM to work inside a single, shared context window. This creates context contamination, attention collapse, and hard ceilings on output length. No existing protocol addresses context management as a first-class concern:

- **MCP** addresses tool access, not context management
- **A2A** addresses inter-agent communication, not intra-agent context
- **RAG** provides retrieval but no output management, no continuation, no graph-structured knowledge

CRP fills this gap with a formally specified, LLM-agnostic, embedded-library protocol.

## Design Decisions

### Embedded Library (Not a Server)

CRP runs in-process with the application. No Docker, no sidecar, no network hop. This eliminates deployment friction — the primary adoption barrier for protocols.

### CKF Is Free and Normative

The Contextual Knowledge Fabric is not a premium add-on. CKF IS the protocol's intelligence. Following the PostgreSQL model, the full capability ships free with every SDK. Monetization targets operations at scale, not capability.

### 6-Stage Graduated Extraction

Rather than a monolithic extraction system, CRP uses a graduated pipeline where later stages activate only when earlier stages have insufficient yield. This keeps typical overhead at ~10-15ms while supporting complex content when needed.

### Quality Tiers (Not Magic Claims)

CRP reports quality honestly with S/A/B/C/D tiers and a formal degradation model. The protocol acknowledges extraction is lossy and provides the math for when and how quality degrades.

### Language-Neutral Specification

All types defined in JSON Schema (Draft 2020-12). All algorithms in pseudocode. Reference implementations planned for Python, TypeScript, and Rust.

## Specification Structure

| Document | Purpose |
|----------|---------|
| 01_RESEARCH_FOUNDATIONS | Academic backing |
| 02_CORE_PROTOCOL | Full protocol spec (29 sections) |
| 03_CONTEXT_ENVELOPE | Envelope architecture |
| 04_TOKEN_GENERATION_PROTOCOL | Continuation and stitching |
| 05_SYSTEM_WIDE_INTEGRATION | Integration patterns |
| 06_IMPLEMENTATION_PLAN | SDK implementation roadmap |
| 07_SECURITY | Security architecture |
| 08_MONETIZATION | Business model |
| 09_DEPLOYMENT | Deployment architecture |

## Open Questions

None — this RFC documents the initial release. Future changes will go through their own RFC process.

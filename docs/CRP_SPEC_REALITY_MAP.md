---
seo_title: CRP Spec Reality Map — What is Implemented vs Public Draft
description: Maps the 48 CRP specifications to implementation status, hosting, security, and product surface so teams know what is real today and what remains draft.
---

# CRP Spec Reality Map

CRP has **48 normative specifications**. Most are published as **Draft** or **Public draft** for standards-body and implementer review. This document maps them to what is actually running in the codebase today, what is partially implemented, and what is still design-stage.

## Legend

| Tag | Meaning |
|---|---|
| **Live** | Shipping in the open-source repo or managed cloud today |
| **Partial** | Core pieces implemented; some advanced features still draft |
| **Draft** | Spec is published but no production implementation yet |
| **Internal** | Withheld from public publication (hosting / control / monetisation details) |

---

## Hosting, control, and data architecture

| Spec | Title | Status | Reality |
|---|---|---|---|
| **SPEC-HOSTING** | CRP™ Hosting, Control & Data Architecture | **Internal** | Operational trust boundaries and infrastructure choices are intentionally withheld from the public site. Contact `security@crprotocol.io` for deployment architecture. |
| **SPEC-016** | Gateway Service Specification | Public draft | Gateway HTTP sidecar exists (`crp serve`); managed-cloud runtime is internal. |
| **SPEC-043** | Gateway as Runtime Product & Visual Console | Public draft | Console UX is draft; Gateway API surface is live. |
| **SPEC-038** | Pluggable Storage Backends | Public draft | Storage abstraction exists; not all backends are wired. |

---

## Security, audit, and privacy

| Spec | Title | Status | Reality |
|---|---|---|---|
| **SPEC-015** | Security & Privacy Specification | Draft | HMAC audit signing, Clerk JWT auth, RBAC, secret redaction, and header-injection defence are implemented in the MCP server and backend clients. mTLS / cert-pinning are deployment-level options. |
| **SPEC-011** | Audit Trail & HMAC Chain Specification | Draft | HMAC-SHA256 signatures on checkpoint records and audit events are live in `crp_mcp`. Full session HMAC chain is implemented in Gateway sessions. |
| **SPEC-007** | Session Token & State Relay | Draft | Session tokens are implemented in `crp_shared`. |
| **SPEC-006** | Safety Policy Directive Language | Draft | Policy compiler exists (`crp_mcp/checkpoint_policy.py`); full directive parser is partial. |

---

## Core protocol (headers, envelope, continuation)

| Spec | Title | Status | Reality |
|---|---|---|---|
| **SPEC-001** | Core Protocol Specification | Draft | Core SDK structure and header registry are live; some advanced cognitive layers are draft. |
| **SPEC-002** | Header Field Specification | Draft | Header registry and lint tools are live; IANA registration is in progress. |
| **SPEC-003** | Context Envelope & Packing | Draft | Envelope packing and preview tools are live. |
| **SPEC-004** | Window Continuation & DAG | Draft | Continuation planning tools exist; DAG state relay is partial. |
| **SPEC-008** | Dispatch Strategy Specification | Draft | Dispatch strategies are implemented in the Gateway. |
| **SPEC-009** | Contextual Knowledge Fabric (CKF) | Draft | CKF ingestion and retrieval are live; graph layers are partial. |

---

## Safety, checkpoints, and human-in-the-loop

| Spec | Title | Status | Reality |
|---|---|---|---|
| **SPEC-033** | Safety Control Plane & Inline Human-in-the-Loop | Public draft | **Live.** Checkpoints, multi-approver, escalation, timeout auto-reject, and HMAC signatures are implemented in `crp_mcp/checkpoint_service.py`. |
| **SPEC-034** | AI Safety Coverage Map & Checkpoint Lifecycle | Public draft | Coverage map is documented; lifecycle automation is live for MCP checkpoints. |
| **SPEC-005** | Decision Provenance Engine (DPE) | Draft | DPE scoring and risk levels are implemented; some research-grade signals are draft. |

---

## Products

| Spec | Title | Status | Reality |
|---|---|---|---|
| **SPEC-040** | CRP Comply — Compliance & Governance Platform | Public draft | Comply backend client, repo analysis, and diff tools are live in the MCP server. Full dashboard is partial. |
| **SPEC-042** | Comply v2→v4 Upgrade & Ecosystem Integration | Public draft | Migration tooling exists; some low-code flows are draft. |
| **SPEC-048** | No-Code Governance via Scan & GitHub Connection | Public draft | GitHub App linking and repo scanning are implemented in the MCP server (`crp_connect_repo_link`, `crp_scan_repo`). |
| **SPEC-013** | GitHub Action & Scanner Specification | Draft | **Live.** The `CRP Scan` GitHub Action is published. |
| **SPEC-036** | Scan Remediation Engine | Draft | SARIF output and remediation planning are live; auto-remediation PRs are planned. |

---

## Implementation status summary

| Layer | Live | Partial | Draft / Internal |
|---|---|---|---|
| **MCP server** | Auth, billing, backends, checkpoints, audit, connectors | — | — |
| **Gateway runtime** | HTTP sidecar, header handling, session store | Managed-cloud console | SPEC-HOSTING internals |
| **Comply** | Repo analysis, diff, policy checks | Dashboard UI | — |
| **Scan** | GitHub Action, SARIF, local preview | Auto-remediation PRs | — |
| **SDK** | Levels 0–2 core methods | Streaming, amplification, agent dispatch | Levels 3 advanced features |

---

## What this means for deployment

- **Today:** You can deploy the MCP server in hosted mode with Clerk auth, Stripe billing, live backend calls, and real checkpoint connectors.
- **Soon:** Managed-cloud Gateway/Comply console will expose the remaining SPEC-043/040 dashboard features.
- **Still design-stage:** SPEC-HOSTING internal architecture, SPEC-047 monetisation internals, and some research specs (AIR, CQR, CLD, ROS, PEF, UDC) are public drafts and not yet implemented.

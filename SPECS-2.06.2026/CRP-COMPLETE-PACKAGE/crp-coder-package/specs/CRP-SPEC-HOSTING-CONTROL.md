# CRP™ Hosting, Control & Data Architecture

**Document:** CRP-HOSTING-CONTROL  
**Version:** 1.0  
**Date:** 2026-05-24  
**Status:** Internal Architecture — CONFIDENTIAL

---

## Overview: Three Domains of Control

```
┌─────────────────────────────────────────────────────────────────┐
│  AUTOCYBER AI PTY LTD (crprotocol.io)                          │
│  Controls: Gateway infrastructure, CKF platform, Comply         │
│  platform, IANA header namespace, HMAC chain verification API   │
└─────────────────────────────────────────────────────────────────┘
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
┌──────────────────┐  ┌─────────────┐  ┌─────────────────┐
│ CRP GATEWAY      │  │ CRP COMPLY  │  │ CRP VISUALISE   │
│ (hosted service) │  │ (SaaS)      │  │ (SaaS)          │
└──────────────────┘  └─────────────┘  └─────────────────┘
               │              │              │
               └──────────────┼──────────────┘
                              │ (streams audit events, headers)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  CUSTOMER CONTROL BOUNDARY                                       │
│  Controls: Their data, their AI call content, their application  │
│  code, their BYOK LLM keys, their audit trail exports            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. What AutoCyber AI Hosts and Controls

### 1.1 CRP Gateway Infrastructure

**What it is:** The managed HTTP reverse proxy that processes all AI calls, injects headers, runs DPE, maintains HMAC chains.

**AutoCyber AI owns and operates:**
- Gateway instances (multi-region: AU, EU, US)
- LLM provider credential vault (encrypted, tenant-isolated)
- CKF graph storage per tenant
- HMAC chain verification service
- DPE pipeline infrastructure
- Header injection engine

**What AutoCyber AI sees:** All AI request/response content that passes through the Gateway. This is the critical trust point — customers are routing their AI traffic through the Gateway.

**Privacy implication:** This is equivalent to a customer routing traffic through Cloudflare or a WAF. The Gateway operator sees the traffic. This MUST be addressed in:
- Terms of Service: explicit statement that AutoCyber AI does not train on, sell, or use customer AI content
- DPA (Data Processing Agreement) for GDPR customers
- SOC 2 Type II audit of the Gateway (required for enterprise customers)
- `no-store` Cache directive support for sensitive calls

### 1.2 CRP Comply Platform

**What AutoCyber AI hosts:**
- The Comply SaaS application
- Per-customer evidence databases (HMAC chains, DPE reports, regulatory classifications)
- Document generation infrastructure (FRIA, DPIA, Technical Documentation)
- Customer account management and billing

**What AutoCyber AI does NOT see:**
- In BYOK mode: the raw AI call content (only headers and metadata stream to Comply)
- In Gateway mode: audit events (structured metadata) stream to Comply — not full message content unless explicitly configured

### 1.3 CRP Visualise Platform

**What AutoCyber AI hosts:**
- The Visualise SaaS application
- Session graph rendering engine
- Historical session replay storage (tiered retention)

### 1.4 The Open Protocol (crprotocol.io)

**What AutoCyber AI publishes:**
- Protocol specification documents (crprotocol.io/spec/)
- Open-source reference implementation (github.com/crprotocol)
- MkDocs documentation site

**What customers can run themselves:**
- The self-hosted CRP sidecar (open-source SDK)
- Their own CKF instance
- Their own DPE pipeline (if they implement the spec)

---

## 2. What the Customer Controls

### 2.1 In Self-Hosted Mode (BYOK SDK)

The customer controls everything:
- Their application code
- Their LLM provider keys (never leave their environment)
- The CRP sidecar instance (runs in their infrastructure)
- Their CKF data (stored in their vector database)
- Their HMAC chain (generated locally, not transmitted to AutoCyber AI unless Comply is connected)
- Their audit logs (local filesystem or their SIEM)

AutoCyber AI sees: Nothing (unless customer connects Comply or Visualise).

### 2.2 In Gateway Mode (Managed Service)

The customer controls:
- Their application code
- Their CRP Gateway API key (rotatable)
- Their Safety Policy configuration
- Their compliance evidence in Comply
- Audit trail export (customer can export full HMAC chain at any time)
- Data deletion rights (GDPR Art. 17 — customer can delete their entire audit trail)

The customer does NOT control:
- Gateway infrastructure (AutoCyber AI operates it)
- CKF graph hosting (AutoCyber AI operates it, customer owns the data)
- HMAC chain storage (AutoCyber AI stores it, customer can export it)

### 2.3 Data Portability Commitments (Required for Trust)

AutoCyber AI MUST commit to:
1. **Full audit trail export:** Customer can download their complete HMAC chain as NDJSON at any time
2. **CKF data export:** Customer can export their full knowledge graph in standard formats
3. **Comply evidence export:** All FRIA, DPIA, Technical Documentation exportable as PDF/JSON
4. **30-day data deletion:** Upon contract termination, all customer data deleted within 30 days
5. **No-lock-in guarantee:** Customers can self-host after cancelling Gateway subscription using exported data

---

## 3. Control Matrix

| Data Type | AutoCyber AI | Customer | Shared |
|-----------|-------------|----------|--------|
| AI call content (prompts/responses) | ✗ No | ✅ Full | — |
| CRP headers metadata | ✅ Processes | ✅ Reads | Both |
| HMAC chain | ✅ Stores | ✅ Exports | Both |
| LLM provider API keys (BYOK) | ✗ Never | ✅ Full | — |
| LLM provider API keys (Gateway) | ✅ Vaulted | ✗ No direct | — |
| CKF knowledge graph | ✅ Hosts | ✅ Data owner | Both |
| Comply evidence pack | ✅ Hosts | ✅ Downloads | Both |
| DPE risk scores | ✅ Computes | ✅ Reads | Both |
| Session tokens | ✅ Signs | ✅ Holds | Both |
| Protocol specification | ✅ Publishes | ✅ Implements | Both |

---

## 4. Monetisation Dependency Map (Clean Version)

```
OPEN (AutoCyber AI publishes, anyone implements)
├── CRP Protocol Specification
├── Header vocabulary (IANA registered)
├── Safety Policy grammar
└── Self-hosted sidecar SDK

PAID — MANAGED INFRASTRUCTURE (AutoCyber AI hosts)
├── CRP Gateway
│   ├── LLM key vault (customer doesn't touch provider keys)
│   ├── Multi-region routing
│   ├── DPE pipeline at scale
│   └── Automatic Comply feed
├── CRP Comply
│   ├── Evidence chain storage
│   ├── Document generation
│   ├── Regulatory classification
│   └── Auditor sharing
├── CRP Visualise
│   ├── Session graph rendering
│   ├── Risk timeline
│   ├── Compliance map view
│   └── Session replay
└── CRP Scan Pro (GitHub)
    ├── Full header gap analysis
    ├── Auto-remediation PRs
    └── Comply sync

PROTOCOL SERVICES (AutoCyber AI certifies)
├── CRP Certification (CRP-Compliant product badge)
├── Conform test suite access
└── HMAC chain verification API (for third-party auditors)
```

The dependency is structural: the open protocol creates the need for the managed services. You cannot use Gateway without a CRP key. You cannot use Comply's live ingestion without Gateway or the SDK. You cannot share a verifiable Visualise session without Comply. Each product creates the next need.

*© 2025–2026 AutoCyber AI Pty Ltd. CONFIDENTIAL.*

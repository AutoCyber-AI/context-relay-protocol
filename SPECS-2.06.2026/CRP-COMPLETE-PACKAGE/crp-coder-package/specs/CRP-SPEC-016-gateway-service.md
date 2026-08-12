# CRP-SPEC-016: Gateway Service Specification

**Document:** CRP-SPEC-016  
**Title:** Context Relay Protocol (CRP) — Gateway as a Managed Service  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 through CRP-SPEC-015

---

## Abstract

This document specifies CRP Gateway as a managed service offering — the hosted reverse proxy operated by AutoCyber AI Pty Ltd that implements the full CRP protocol stack. While CRP-SPEC-001 through CRP-SPEC-015 define the protocol, this document defines the **product**: the public API surface, onboarding flow, free-tier and paid-tier quotas, document ingestion API, AI system registration, tenant provisioning, and the day-one user experience from account creation to first governed AI call.

This is the document that closes the gap between "protocol is specified" and "developers can actually use it without manual integration work."

---

## Table of Contents

1. [Service Architecture](#1-service-architecture)
2. [Public API Endpoints](#2-public-api-endpoints)
3. [Onboarding Flow](#3-onboarding-flow)
4. [Tenant Provisioning](#4-tenant-provisioning)
5. [AI System Registration](#5-ai-system-registration)
6. [API Key Management](#6-api-key-management)
7. [Free Tier Quotas](#7-free-tier-quotas)
8. [Paid Tier Quotas](#8-paid-tier-quotas)
9. [Document Ingestion API](#9-document-ingestion-api)
10. [Provider Routing Configuration](#10-provider-routing-configuration)
11. [Default Safety Policies](#11-default-safety-policies)
12. [Service Discovery](#12-service-discovery)
13. [Rate Limiting](#13-rate-limiting)
14. [SLA Tiers](#14-sla-tiers)
15. [Security Posture](#15-security-posture)
16. [References](#16-references)

---

## 1. Service Architecture

### 1.1 Hosted Endpoint Topology

CRP Gateway is operated as a multi-region managed service with the following endpoint structure:

```
gateway.crprotocol.io           ← Primary entrypoint (DNS-routed to nearest region)
├── eu.gateway.crprotocol.io    ← EU region (Frankfurt + Dublin)
├── au.gateway.crprotocol.io    ← Australia region (Sydney + Melbourne)
├── us.gateway.crprotocol.io    ← US region (Virginia + Oregon)
└── uk.gateway.crprotocol.io    ← UK region (London)
```

Customers MUST select a region during account provisioning. The `CRP-Compliance-Data-Residency` header enforces region-locked processing.

### 1.2 Service Components

```
┌────────────────────────────────────────────────────────────────┐
│                     CRP Gateway Service                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ API Frontend │  │ DPE Workers  │  │ CKF Storage Layer  │   │
│  │ (TLS, auth)  │  │ (DPE + RQA)  │  │ (vector + graph)   │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │ Provider     │  │ Audit Stream │  │ Comply Webhook     │   │
│  │ Key Vault    │  │ (HMAC chain) │  │ Dispatcher        │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│                                                                  │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Public API Endpoints

### 2.1 Inference Endpoints (OpenAI-compatible)

The Gateway exposes OpenAI-compatible endpoints so existing client SDKs work with a single base URL change:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/chat/completions` | POST | Standard chat completion — OpenAI-compatible |
| `/v1/completions` | POST | Legacy completion — OpenAI-compatible |
| `/v1/embeddings` | POST | Embedding generation — passes through with audit logging only |
| `/v1/models` | GET | Lists available models (provider-mapped) |

### 2.2 CRP-Native Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/crp/v3/dispatch` | POST | Direct CRP dispatch with full strategy control |
| `/crp/v3/session/{id}` | GET | Retrieve session state (requires session token) |
| `/crp/v3/session/{id}` | DELETE | Terminate session, finalise audit chain |
| `/crp/v3/sessions/{id}/dag` | GET | Retrieve Window DAG for the session |
| `/crp/v3/verify-chain` | POST | Verify HMAC chain integrity for an audit trail |

### 2.3 Knowledge Management Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/crp/v3/ckf/documents` | POST | Upload document for ingestion into CKF |
| `/crp/v3/ckf/documents` | GET | List ingested documents |
| `/crp/v3/ckf/documents/{id}` | DELETE | Remove document (GDPR Art. 17 erasure) |
| `/crp/v3/ckf/facts` | GET | Query CKF facts (admin/audit only) |
| `/crp/v3/ckf/state` | GET | Get current CKF ETag and statistics |

### 2.4 Admin Endpoints (account holder only)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/crp/v3/admin/systems` | POST | Register an AI system |
| `/crp/v3/admin/systems/{id}` | PATCH | Update system registration |
| `/crp/v3/admin/keys` | POST | Provision a new API key |
| `/crp/v3/admin/keys/{id}` | DELETE | Revoke an API key |
| `/crp/v3/admin/policies` | PUT | Set default Safety Policy for an AI system |
| `/crp/v3/admin/quotas` | GET | Get current quota usage |

### 2.5 Well-Known URIs

| URI | Purpose |
|-----|---------|
| `/.well-known/crp-gateway.json` | Gateway capability advertisement (per RFC 8615) |
| `/.well-known/security.txt` | Security disclosure contact (RFC 9116) |

The `crp-gateway.json` document SHALL contain:

```json
{
  "crp_version": "3.0.0",
  "conformance_level": "full",
  "endpoints": {
    "inference": "https://gateway.crprotocol.io/v1",
    "crp_native": "https://gateway.crprotocol.io/crp/v3"
  },
  "providers_supported": ["openai", "anthropic", "gemini", "azure-openai", "bedrock", "ollama"],
  "regions": ["eu", "au", "us", "uk"],
  "max_loop_depth": 5,
  "max_fan_out": 10,
  "max_dag_nodes": 50
}
```

---

## 3. Onboarding Flow

### 3.1 The Critical Day-One Experience

The onboarding flow is designed to take a developer from "found by GitHub scan" to "first governed AI call working" in under 5 minutes.

```
┌────────────────────────────────────────────────────────────┐
│  Step 1: Account creation (< 60 seconds)                    │
│  - Email + password OR OAuth (GitHub, Google, Microsoft)    │
│  - Region selection                                         │
│  - Implicit free-tier provisioning                          │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Step 2: Provider key configuration (< 60 seconds)          │
│  - Paste OpenAI/Anthropic/etc. key into vault               │
│  - OR select "BYOK in code" (provider key in client app)    │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Step 3: System registration (< 60 seconds)                 │
│  - Name your AI system ("my-chatbot")                        │
│  - Select domain (general, medical, financial, etc.)         │
│  - Auto-classifies EU AI Act risk level                      │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Step 4: API key issuance (instant)                          │
│  - crp_gw_free_<32 chars>                                    │
│  - Code snippet generated showing one-line integration       │
└────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────────┐
│  Step 5: First call (< 60 seconds)                           │
│  - Developer changes base_url in their app                   │
│  - First call goes through Gateway                           │
│  - Headers emitted, audit event recorded                     │
│  - Visible in Comply dashboard immediately                   │
└────────────────────────────────────────────────────────────┘
```

### 3.2 Onboarding Banner: Zero-CKF Notification

On every Gateway response during the first 24 hours OR before any CKF facts have been ingested, the Gateway MUST emit:

```
CRP-Context-Mode: safety-only
CRP-Onboarding-Hint: ingest-documents-for-context-grounding
```

This tells the developer (and any inspecting tooling) that the gateway is operating in safety-only mode and full context-grounding features will activate once documents are ingested.

This is the critical UX signal that prevents day-one confusion when `CRP-Safety-Attribution: PARAMETRIC` appears on responses (correctly, since there's nothing to ground against yet).

### 3.3 Pre-Populated Signup from GitHub Scan

When the signup URL contains `?source=github-scan` query parameters, the onboarding flow is pre-populated:

```
https://comply.crprotocol.io/signup?source=github-scan&provider=openai&framework=langchain&finding_count=3
```

Pre-populates:
- Provider selection (Step 2)
- Suggested domain based on framework (Step 3)
- Suggested system name from repository name
- Shows scan findings in the welcome dashboard

This converts the GitHub Action funnel from "create account from scratch" to "confirm what we already know."

---

## 4. Tenant Provisioning

### 4.1 Tenant Isolation Model

Every account is provisioned as an isolated tenant with:

| Resource | Isolation Mechanism |
|----------|-------------------|
| CKF storage | Per-tenant namespace; separate HNSW indexes |
| Audit chain | Per-tenant HMAC master key; separate session HMAC keys |
| API keys | Per-tenant key prefix; scope-bound |
| Provider credentials | Encrypted in per-tenant vault; never shared |
| Comply evidence | Per-tenant evidence database |
| Quota counters | Per-tenant; never aggregated across tenants |

### 4.2 Tenant Provisioning Steps

1. Account record created in identity store
2. Tenant HMAC master key generated via HSM/KMS
3. CKF namespace created with empty HNSW index
4. Default AI system registered (placeholder, replaced in Step 3 of onboarding)
5. Free-tier API key issued
6. Comply evidence database initialised
7. Welcome event written to audit chain

All steps MUST complete atomically. Failed provisioning rolls back all resources.

---

## 5. AI System Registration

### 5.1 Why Registration Matters

The EU AI Act classifies risk based on the deployment domain, not the LLM response content. A medical diagnosis assistant and a recipe suggestion bot may produce similar text, but they have radically different risk classifications. The Gateway MUST know which type of AI system is making the call to assign the correct `CRP-Compliance-EU-AI-Act` value.

### 5.2 System Registration Schema

```json
{
  "system_id": "sys_chatbot_prod_v1",
  "name": "Customer Support Chatbot",
  "description": "Public-facing customer support assistant",
  "domain": "general_information",
  "intended_purpose": "Answer customer questions about our products",
  "deployment_context": "public",
  "high_risk_indicators": {
    "involves_employment_decisions": false,
    "involves_credit_decisions": false,
    "involves_medical_decisions": false,
    "involves_law_enforcement": false,
    "involves_critical_infrastructure": false,
    "involves_biometric_id": false,
    "involves_education_access": false
  },
  "users_classification": "general_public",
  "personal_data_processing": false,
  "automated_decision_making": false,
  "default_safety_policy": "profile=public-facing",
  "data_residency": "EU"
}
```

### 5.3 Automatic EU AI Act Classification

From the registration, the Gateway computes the EU AI Act risk class:

```
if any high_risk_indicator == true:
    eu_ai_act_class = "HIGH"
elif domain in ["biometric_id", "social_scoring"]:
    eu_ai_act_class = "UNACCEPTABLE"
elif personal_data_processing == true OR automated_decision_making == true:
    eu_ai_act_class = "LIMITED"
else:
    eu_ai_act_class = "MINIMAL"
```

This value is emitted as `CRP-Compliance-EU-AI-Act` on every call from this system.

### 5.4 Domain Catalog

The Gateway maintains a catalog of supported domains:

| Domain | Default Risk | Default Safety Policy Profile |
|--------|--------------|------------------------------|
| `general_information` | LIMITED | `public-facing` |
| `customer_support` | LIMITED | `public-facing` |
| `developer_tooling` | MINIMAL | `developer` |
| `creative_writing` | MINIMAL | `developer` |
| `medical` | HIGH | `medical` |
| `financial` | HIGH | `financial` |
| `legal` | HIGH | `medical` (strict equivalent) |
| `employment` | HIGH | `medical` (strict equivalent) |
| `education` | HIGH | `medical` (strict equivalent) |
| `government_services` | HIGH | `medical` (strict equivalent) |
| `critical_infrastructure` | HIGH | `medical` (strict equivalent) |
| `biometric_id` | UNACCEPTABLE | — (blocked) |
| `social_scoring` | UNACCEPTABLE | — (blocked) |

---

## 6. API Key Management

### 6.1 Key Format

```
crp_gw_<tier>_<region>_<random>
```

Examples:
```
crp_gw_free_eu_4f8a9b2c1d3e5f60718293a4b5c6d7e8
crp_gw_pro_au_9b1c2d3e4f5061728394a5b6c7d8e9f0
crp_gw_business_us_a1b2c3d4e5f60718293a4b5c6d7e8f9
crp_gw_ent_eu_<custom>
```

The tier prefix is informational only — actual quota enforcement uses the billing record, not the key prefix.

### 6.2 Key Scoping

Each key can be scoped to:

| Scope | Description |
|-------|-------------|
| `system_id` | Key only works for calls from this AI system |
| `ip_allowlist` | Key only accepted from specific IPs (CIDR) |
| `referer_allowlist` | Key only accepted with matching Origin/Referer headers |
| `policy_tier` | Key can only set Safety Policy at or below this tier |
| `max_loop_depth` | Key cannot use loop depths above this value |

### 6.3 Key Rotation

Keys can be rotated without service interruption:

1. Create new key via `/crp/v3/admin/keys`
2. Both keys active simultaneously
3. Update client applications to new key
4. Revoke old key once traffic has migrated
5. Audit trail records both key usages — full traceability of which key made which calls

---

## 7. Free Tier Quotas

### 7.1 Free Tier Limits

The free tier is designed to be **genuinely useful, not a teaser** — sufficient for production small-scale use and full feature evaluation.

| Resource | Free Tier Limit |
|----------|----------------|
| AI calls per day | 100 |
| AI calls per month | 2,000 |
| Concurrent sessions | 5 |
| Maximum window depth (continuation) | 3 |
| Maximum fan-out width | 3 |
| Maximum loop depth (agentic) | 2 |
| CKF document storage | 50 MB |
| CKF facts (total) | 5,000 |
| Audit history retention | 30 days |
| Comply evidence retention | 30 days |
| Team seats | 1 |
| Provider keys in vault | 2 |
| Registered AI systems | 1 |
| Safety Policy: profile=medical | Disabled (requires Pro) |
| CRP Visualise sessions | 5 per month |
| Auditor sharing | Disabled (requires Business) |
| Webhook reports (CRP-Safety-Report-URI) | 100/day |
| SLA | None (best effort) |

### 7.2 What Works Fully on Free Tier

Every safety and provenance feature is fully enabled on the free tier:

| Feature | Free Tier |
|---------|----------|
| Full DPE pipeline (all 13 stages) | ✓ Full |
| All 58 CRP headers | ✓ Full |
| HMAC audit chain | ✓ Full |
| Safety Policy enforcement | ✓ Full |
| EU AI Act classification | ✓ Full |
| GDPR PII detection | ✓ Full |
| ISO 42001 control mapping | ✓ Full |
| Reflexive dispatch | ✓ Full |
| Agentic dispatch | ✓ Up to loop_depth=2 |
| Cross-window coherence (Stage 6) | ✓ Full |
| Repetition detection (Stage 7) | ✓ Full |
| Completeness verification (Stage 8) | ✓ Full |
| Flow & continuity (Stage 9) | ✓ Full |
| CRP-Safety-Stop-Inject | ✓ Full |
| Comply audit evidence pack | ✓ Full |

The free tier is a complete CRP implementation, simply quota-limited.

### 7.3 What's Restricted on Free Tier

| Restriction | Reason |
|------------|--------|
| Volume (calls/day, /month) | Cost control |
| Continuation depth (3 vs 5) | Server resource control |
| Audit retention (30 days) | Storage cost |
| Industry profiles (medical, financial) | These are regulated industries with higher liability — Pro+ required |
| Auditor sharing | Enterprise feature |
| Multi-region deployment | Single region only |

---

## 8. Paid Tier Quotas

### 8.1 Pro Tier ($149/month)

| Resource | Pro Limit |
|----------|----------|
| AI calls per month | Included: 50,000 / Then: $0.003 per call |
| Concurrent sessions | 50 |
| Maximum window depth | 5 |
| CKF storage | 5 GB |
| CKF facts | 500,000 |
| Audit retention | 1 year |
| Team seats | 5 |
| Registered systems | Unlimited |
| Industry profiles | All available |
| SLA | 99.5% uptime |

### 8.2 Business Tier ($499/month)

| Resource | Business Limit |
|----------|----------------|
| AI calls per month | Included: 250,000 / Then: $0.002 per call |
| Concurrent sessions | 250 |
| Maximum window depth | Unlimited (within max_dag_nodes=50) |
| CKF storage | 50 GB |
| CKF facts | 5,000,000 |
| Audit retention | 5 years |
| Team seats | 20 |
| Auditor seats | 5 |
| CRP Visualise | Included |
| Multi-region | Available |
| SLA | 99.9% uptime |

### 8.3 Enterprise Tier (Custom)

- Dedicated Gateway instance (single-tenant infrastructure)
- On-premises or private cloud deployment
- Custom regulatory mapping
- Unlimited everything
- 99.99% uptime SLA
- 24/7 support
- Quarterly compliance review
- EU AI Act authority submission support
- CRP Certification program access

---

## 9. Document Ingestion API

### 9.1 Document Upload

```
POST /crp/v3/ckf/documents
Authorization: Bearer crp_gw_<key>
Content-Type: multipart/form-data

file: <binary>
metadata: {
  "title": "EU AI Act Final Text",
  "source_uri": "https://eur-lex.europa.eu/...",
  "importance_baseline": 0.90,
  "tags": ["regulation", "eu-ai-act"],
  "ttl": "P5Y"
}
```

Response:
```json
{
  "document_id": "doc_a7f3b2c1d4e5",
  "status": "ingesting",
  "estimated_facts": 412,
  "ckf_etag_will_change": true
}
```

### 9.2 Supported Formats

| Format | Notes |
|--------|-------|
| PDF | Including OCR for scanned PDFs |
| DOCX | Word documents |
| MD | Markdown |
| HTML | Web content (sanitised) |
| TXT | Plain text |
| JSON | Structured data — keys treated as fact identifiers |
| CSV | Tabular data — rows treated as fact candidates |

### 9.3 Ingestion Pipeline (Asynchronous)

1. Document uploaded → stored in tenant's document store
2. Async job triggered: chunking, fact extraction, embedding
3. Facts added to HNSW index (immediate but unreflected in ETag until step 5)
4. Leiden community detection triggered if batch ≥ 50 new facts
5. CKF state hash updated → `CRP-Context-ETag` invalidated for all clients

Progress is queryable via `GET /crp/v3/ckf/documents/{id}`.

### 9.4 Source Authority Levels

Documents can be tagged with authority levels that affect importance weighting:

| Authority | Default Importance Boost |
|-----------|------------------------|
| `regulatory` | +0.10 |
| `peer-reviewed` | +0.05 |
| `official-documentation` | 0.00 (baseline) |
| `community` | -0.05 |
| `unverified` | -0.10 |

---

## 10. Provider Routing Configuration

### 10.1 Provider Selection per Call

The Gateway selects the LLM provider via three mechanisms (in priority order):

1. **Model name routing:** `model: "gpt-4o"` → OpenAI; `model: "claude-sonnet-4"` → Anthropic; `model: "gemini-2.0-pro"` → Google
2. **Default provider:** If no model specified, uses the tenant's configured default
3. **Failover provider:** If primary provider fails (5xx, timeout), automatically fails over to configured backup

### 10.2 Provider Vault

Each tenant's provider credentials are stored in an encrypted vault:

```json
{
  "providers": [
    {
      "id": "openai_primary",
      "type": "openai",
      "key_encrypted": "<AES-256-GCM ciphertext>",
      "models_allowed": ["gpt-4o", "gpt-4o-mini"],
      "rate_limit_override": null,
      "is_default": true
    },
    {
      "id": "anthropic_primary",
      "type": "anthropic",
      "key_encrypted": "<AES-256-GCM ciphertext>",
      "models_allowed": ["claude-sonnet-4", "claude-haiku-4-5"],
      "is_default": false
    }
  ],
  "default_provider_id": "openai_primary",
  "failover_provider_id": "anthropic_primary"
}
```

### 10.3 BYOK Mode

Customers MAY choose "BYOK in client" — provider keys stay in their application; the Gateway forwards calls using the customer-provided key on each request:

```
POST /v1/chat/completions
Authorization: Bearer crp_gw_<key>
CRP-Provider-Key: <customer-provided OpenAI key>
```

In BYOK mode, the Gateway does not vault the provider key but still applies all CRP features (DPE, headers, audit, Comply integration).

---

## 11. Default Safety Policies

### 11.1 Per-System Default Policy

Each registered AI system has a default Safety Policy. If a request from this system does not include `CRP-Safety-Policy`, the default applies.

### 11.2 Tier-Based Default Profiles

| System Domain | Free Tier Default | Pro+ Default |
|--------------|------------------|--------------|
| general_information | `warn-on CRITICAL; warn-on HIGH` | `profile=public-facing` |
| developer_tooling | `warn-on CRITICAL; require-quality S A B` | `profile=developer` |
| medical | (not available on Free) | `profile=medical` |
| financial | (not available on Free) | `profile=financial` |

### 11.3 Policy Override Hierarchy

```
1. CRP-Safety-Policy in request header (highest priority)
2. Per-API-key configured policy
3. Per-AI-system default policy
4. Tenant-wide default policy
5. Gateway-wide default for the tier
```

---

## 12. Service Discovery

### 12.1 Well-Known Endpoint

```
GET https://gateway.crprotocol.io/.well-known/crp-gateway.json
```

Returns service capabilities (see §2.5).

### 12.2 Health Check

```
GET https://gateway.crprotocol.io/health
```

Returns service health status (200 OK if healthy, 503 if degraded). Includes:
- Region status
- Provider availability (OpenAI, Anthropic, etc.)
- DPE pipeline status
- CKF index status

### 12.3 Status Page

`https://status.crprotocol.io` provides public service status. Subscribers can receive incident notifications via webhook, email, or RSS.

---

## 13. Rate Limiting

### 13.1 Per-Key Rate Limits

| Tier | RPS (Requests Per Second) | Burst |
|------|--------------------------|-------|
| Free | 2 | 5 |
| Pro | 20 | 50 |
| Business | 100 | 250 |
| Enterprise | Custom | Custom |

### 13.2 Rate Limit Response

When rate limited, the Gateway returns HTTP 429 with:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 5
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1748160300
CRP-Context-Protocol-Version: 3.0.0
```

### 13.3 Quota Exhaustion

When monthly quota is exhausted:
- Free tier: HTTP 402 (Payment Required) with upgrade link
- Pro+: Continues on overage pricing per the tier's per-call rate

---

## 14. SLA Tiers

| Tier | Uptime | Response Time SLA | Support Response |
|------|--------|------------------|------------------|
| Free | None (best effort) | None | Community forum |
| Pro | 99.5% | p95 < 2s gateway overhead | Email, 48hr |
| Business | 99.9% | p95 < 1s gateway overhead | Email + chat, 4hr |
| Enterprise | 99.99% | p95 < 500ms gateway overhead | Phone + Slack, 24/7 |

Note: "Gateway overhead" excludes LLM provider latency. SLA covers only the time spent inside CRP Gateway processing.

---

## 15. Security Posture

### 15.1 Required Certifications (AutoCyber AI)

For Pro+ tier customers, AutoCyber AI Pty Ltd MUST maintain:

- SOC 2 Type II (US/AU customer requirement)
- ISO/IEC 27001 (EU customer requirement)
- ISO/IEC 42001 (CRP self-compliance — we build AI compliance, we are AI compliance)

### 15.2 Pen Testing

Annual third-party penetration testing of the Gateway service. Results summary available to Business+ customers under NDA.

### 15.3 Bug Bounty

Public bug bounty program at `https://crprotocol.io/security/bounty` covering:
- Token forgery
- HMAC chain bypass
- Cross-tenant data access
- Provider credential exposure
- DPE evasion attacks

Critical vulnerabilities: $5,000 – $25,000. High: $1,000 – $5,000. Medium: $250 – $1,000.

---

## 16. References

- All CRP-SPEC-001 through CRP-SPEC-015
- RFC 8615 — Well-Known Uniform Resource Identifiers
- RFC 9116 — A File Format to Aid in Security Vulnerability Disclosure

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*

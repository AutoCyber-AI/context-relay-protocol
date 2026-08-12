# CRP-SPEC-015: Security & Privacy Specification

**Document:** CRP-SPEC-015  
**Title:** Context Relay Protocol — Security & Privacy  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-05-24  
**License:** CC BY 4.0 (specification text)

---

## Abstract

This document specifies the security and privacy architecture of the Context Relay Protocol (CRP). It covers native security mechanisms built into the protocol, existing standards leveraged (TLS, HMAC-SHA256, JWT, HTTP security headers), threat model, attack surface analysis, and platform-level security requirements for CRP Gateway deployments. This document is both a protocol specification and a technical due diligence reference for enterprise security reviews.

---

## 1. Security Architecture Overview

CRP security operates at four distinct layers:

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 4: Platform Security                                     │
│  (Gateway infrastructure, tenant isolation, key vault, SOC 2)  │
├────────────────────────────────────────────────────────────────┤
│  Layer 3: Protocol Security                                     │
│  (HMAC chain, session token, nonce, header injection defence)   │
├────────────────────────────────────────────────────────────────┤
│  Layer 2: Transport Security                                    │
│  (TLS 1.3, certificate pinning, mTLS for enterprise)           │
├────────────────────────────────────────────────────────────────┤
│  Layer 1: Data Security                                         │
│  (envelope content isolation, PII detection, no-store policy)  │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Threat Model

### 2.1 Assets Being Protected

| Asset | Classification | Owner |
|-------|---------------|-------|
| AI call content (prompts + responses) | Confidential | Customer |
| LLM provider API keys | Secret | Customer (BYOK) / Gateway vault |
| HMAC session keys | Secret | CRP Gateway (generated per session) |
| CKF knowledge graph content | Confidential | Customer |
| Audit trail / HMAC chain | Confidential | Customer (stored by AutoCyber AI) |
| CRP Gateway API keys | Secret | Customer holds, Gateway validates |
| Safety Policy configuration | Internal | Customer |

### 2.2 Threat Actors

| Actor | Capability | Primary Concern |
|-------|-----------|----------------|
| External attacker | Network-level, credential theft | LLM key theft, session hijacking |
| Malicious LLM output | Prompt injection in response | Header injection (Axiom 4 prevents) |
| Malicious AI input | Prompt injection in request | Policy bypass, HMAC chain poisoning |
| Compromised client app | Holds CRP API key | Key rotation, scope limits |
| Rogue insider (AutoCyber AI) | Platform access | Tenant isolation, key separation |
| Compliance auditor | Read-only access | Evidence tampering (HMAC prevents) |

### 2.3 Out of Scope

- LLM provider security (OpenAI, Anthropic infrastructure)
- Client application security beyond the CRP integration surface
- Physical security of data centres

---

## 3. Native CRP Security Mechanisms

These are security mechanisms defined by the CRP protocol itself — not external dependencies.

### 3.1 HMAC-SHA256 Audit Chain (Tamper Evidence)

**What it is:** Every AI call produces an HMAC-SHA256 hash chained to the previous call in the session. Any modification to any audit record breaks the chain.

**Algorithm:**
```
HMAC_n = HMAC-SHA256(
  session_id
  || window_number
  || timestamp_iso8601
  || content_hash (SHA256 of LLM response)
  || dpe_report_hash (SHA256 of DPE output)
  || previous_HMAC,   ← chaining
  session_hmac_key    ← per-session, generated at session init
)
```

**Properties:**
- Forward integrity: modifying any past record invalidates all subsequent records
- Verifiable by any party holding the session HMAC key
- `CRP-Provenance-Chain-Integrity: BROKEN` emitted if verification fails
- Session HMAC key is derived using HKDF from the session ID and a Gateway master key — customers can export their session HMAC key for independent verification

**Regulatory mapping:** GDPR Art. 5(1)(f) (integrity), EU AI Act Art. 64 (logging), ISO 42001 A.9.4

### 3.2 Session Token (Signed State Relay)

**What it is:** A JWT-like signed token issued by the Gateway carrying session state — the CRP equivalent of a signed HTTP cookie.

**Format:**
```
CRP-Set-Session: token=<base64url(payload)>.<base64url(signature)>;
                 Path=/; Max-Age=3600; Signed; SameSite=Strict
```

**Payload fields:**
```json
{
  "session_id": "crp_sess_7f3a9bc2...",
  "window_number": 3,
  "quality_history": ["A", "A", "B"],
  "safety_budget_remaining": 0.78,
  "hmac_chain_tip": "sha256:9bce472f...",
  "issued_at": "2026-05-24T09:00:00Z",
  "expires_at": "2026-05-24T10:00:00Z",
  "scope": "crp_gw_key_abc123",
  "version": "3.0.0"
}
```

**Signature:** `HMAC-SHA256(base64url(header) || "." || base64url(payload), session_signing_key)`

**Security properties:**
- Signed with per-session key: Gateway-issued tokens cannot be forged by clients
- `expires_at` enforced: expired tokens rejected with HTTP 401
- `scope` field: token is only valid for the CRP API key that created the session
- `hmac_chain_tip` allows Gateway to detect replay attacks (presented token must match chain tip)
- `SameSite=Strict` when used in browser contexts

### 3.3 Axiom 4: LLM Provider Transparency Boundary

**What it is:** CRP headers MUST be stripped before forwarding to LLM providers. This is a security boundary, not just an architectural choice.

**Why it's a security mechanism:**
1. Prevents LLM prompt injection via headers — a malicious LLM cannot read or manipulate CRP headers
2. Prevents LLM output from appearing to set CRP headers — response headers are injected by the Gateway AFTER the LLM response is received and validated by DPE
3. Prevents information leakage of safety policy to the model (the model cannot "know" it's being monitored and adjust behaviour accordingly)

**Implementation requirement:** Gateway MUST use a header allowlist for LLM provider requests, not a CRP-prefix denylist. Only explicitly permitted headers (Content-Type, Authorization, etc.) are forwarded.

### 3.4 CRP-Safety-Nonce (Policy Replay Prevention)

**What it is:** A per-session nonce bound to the Safety Policy. Prevents an attacker from replaying an older, more permissive Safety Policy on a new session.

**Header:** `CRP-Safety-Nonce: base64:nZ8fXw==`

**Mechanism:** Gateway generates a nonce at session init, binds it to the Safety Policy hash. Requests presenting a Safety Policy with a nonce mismatch are rejected with HTTP 400.

### 3.5 Header Injection Defence

**What it is:** Prevention of CRP header injection by malicious clients or LLM outputs.

**Rules:**
1. Gateway MUST reject any request where the client has pre-set `CRP-Safety-*` response headers (these are response-only headers)
2. Gateway MUST strip any `CRP-Provenance-*` headers from client requests (these are generated internally)
3. Gateway MUST validate `CRP-Safety-Policy` syntax before accepting a session — malformed directives rejected with HTTP 400
4. Gateway MUST NOT copy any content from LLM response bodies into CRP header values

### 3.6 CRP-Context-Cache: no-store (Data Minimisation)

**What it is:** A directive preventing the CKF from persisting sensitive session content.

**Usage:** `CRP-Context-Cache: no-store`

**Effect:**
- Facts from this session are NOT written to the persistent CKF graph
- Session context is held in Tier 1 (session cache) only and purged on session end
- Comply audit event records metadata headers only — not message content
- GDPR Art. 5(1)(c) data minimisation compliance

### 3.7 PII Detection and Flagging

**What it is:** The DPE includes a PII detection module that scans both request content and LLM responses for personal data indicators.

**Output header:** `CRP-Compliance-GDPR-PII: true`

**Actions configurable via Safety Policy:**
- `block-pii` directive: Gateway blocks the request/response if PII is detected
- `warn-pii` directive (default): passes with header flag, fires report-uri webhook
- PII detection does NOT redact content — it flags for application-layer handling

---

## 4. Leveraged Security Standards

### 4.1 TLS 1.3 (Transport Security)

**Requirement:** All CRP Gateway endpoints MUST be served over HTTPS with TLS 1.3 minimum. TLS 1.2 MAY be supported for backward compatibility but SHOULD be deprecated by 2027.

**Certificate requirements:**
- Minimum RSA-2048 or ECDSA P-256 
- OCSP stapling REQUIRED
- HSTS header REQUIRED: `Strict-Transport-Security: max-age=31536000; includeSubDomains`

**mTLS for enterprise:** Enterprise CRP Gateway deployments SHOULD support mutual TLS (mTLS) for client authentication, eliminating API key dependency in high-security environments.

### 4.2 HMAC-SHA256 (Integrity)

Used for: HMAC chain, session token signing, envelope content integrity. See Section 3.1 and 3.2.

Standard: RFC 2104, FIPS PUB 198-1.

### 4.3 HKDF (Key Derivation)

Session HMAC keys are derived using HKDF (RFC 5869):
```
session_hmac_key = HKDF-SHA256(
  IKM = gateway_master_key,
  salt = session_id,
  info = "crp-session-hmac-v3",
  L = 32 bytes
)
```

This means: the master key never leaves the Gateway; each session has a unique HMAC key; session keys can be revoked individually by rotating the master key.

### 4.4 AES-256-GCM (Encryption at Rest)

LLM provider credentials in the Gateway key vault MUST be encrypted at rest using AES-256-GCM. Key encryption keys (KEKs) MUST be stored in a HSM or cloud KMS (AWS KMS, Azure Key Vault, GCP Cloud KMS).

### 4.5 JWT-compatible Session Tokens

Session tokens use JWT-compatible structure (base64url header.payload.signature) but use HMAC-SHA256 rather than RS256/ES256. This is intentional — asymmetric signatures are unnecessary for Gateway-issued tokens validated by the same Gateway. The structure is JWT-like for tooling compatibility.

### 4.6 OAuth 2.0 / API Key Authentication

**CRP Gateway API keys:**
- Format: `crp_gw_[env]_[32-char random]` — prefix allows programmatic detection
- Scoped: keys can be scoped to specific Safety Policy levels, CKF namespaces, or IP ranges
- Rotatable: customers can rotate keys without service interruption
- Never logged: API keys MUST NOT appear in access logs (only key prefix logged)

**Enterprise SSO:** CRP Comply and CRP Visualise MUST support SAML 2.0 and OIDC for enterprise SSO. See RFC 6749, RFC 8414.

---

## 5. Platform Security (Gateway Deployment)

Requirements for production CRP Gateway deployments:

### 5.1 Tenant Isolation

- All customer data (CKF graphs, audit chains, session state) MUST be stored in isolated namespaces
- Namespace isolation MUST be enforced at the database query layer, not just the application layer
- Cross-tenant data access MUST be architecturally impossible (separate encryption keys per tenant)

### 5.2 LLM Provider Credential Vault

- Provider credentials (OpenAI API keys, Anthropic API keys, etc.) MUST be stored encrypted in an HSM-backed key vault
- Credentials MUST NOT be logged or included in error messages
- Credential access MUST be audited — every LLM provider call logs which credential was used
- Credential rotation MUST NOT require application restart

### 5.3 Audit and Observability

- All Gateway API key authentication attempts (success and failure) MUST be logged
- All Safety Policy violations (`halt-on CRITICAL` events) MUST be logged and alertable
- All chain integrity failures MUST trigger immediate incident creation
- Logs MUST be append-only and tamper-evident (separate HMAC chain for infrastructure logs)

### 5.4 Compliance Certifications Required (AutoCyber AI)

For enterprise customer trust, AutoCyber AI MUST obtain:

| Certification | Priority | Timeline |
|--------------|----------|----------|
| SOC 2 Type II | P1 — required for enterprise sales | 6–12 months |
| ISO 27001 | P1 — required for EU customers | 12–18 months |
| ISO 42001 (AI) | P1 — required (we build compliance tools) | 12–18 months |
| Cyber Essentials Plus (UK/AU) | P2 | 6 months |
| PCI DSS (if handling payment data) | P3 | Only if applicable |

---

## 6. Privacy Architecture

### 6.1 Data Categories and Processing Basis

| Data Category | GDPR Basis | Retention | Customer Control |
|--------------|-----------|-----------|-----------------|
| AI call metadata (headers, risk scores) | Legitimate interest / Contract | Configurable (30d–5yr) | Export + delete |
| AI call content (prompts/responses) | Contract | Not stored by default (no-store) | Not applicable |
| CKF knowledge graph content | Contract | Persistent until deleted | Full export + delete |
| Audit trail (HMAC chain) | Legal obligation | Minimum 2yr (EU AI Act Art.64) | Export, delete after retention |
| Account data (email, billing) | Contract | Duration of contract + 30d | GDPR Art. 17 |

### 6.2 Data Residency

`CRP-Compliance-Data-Residency` header declares jurisdiction:
- `EU` — data processed and stored in EU regions only (Frankfurt, Dublin)
- `AU` — data processed and stored in Australia only (Sydney, Melbourne)
- `US` — data processed and stored in US regions only (Virginia, Oregon)

AutoCyber AI MUST provide region-specific Gateway deployments to honour this header.

### 6.3 AI Content Processing Commitment

AutoCyber AI MUST publish and contractually commit:

> "AutoCyber AI does not use, train on, sell, or share customer AI call content processed through the CRP Gateway for any purpose other than performing the CRP protocol services contracted by the customer. AI call content is not retained by default. Audit metadata (headers, risk scores, provenance hashes) is retained per the customer's configured retention policy."

This commitment MUST appear in:
- Terms of Service
- Data Processing Agreement (DPA) — required for GDPR customers
- SOC 2 Type II audit scope

### 6.4 Right to Erasure (GDPR Art. 17)

CRP MUST support:
1. **Session erasure:** Delete specific session's audit trail and CKF contributions
2. **Account erasure:** Delete all customer data within 30 days of contract termination
3. **HMAC chain truncation:** If audit records are erased, the chain is marked as TRUNCATED from that point — partial erasure is documented, not silently modified

---

## 7. Security Headers Emitted by CRP Gateway

CRP Gateway endpoints MUST emit the following HTTP security headers:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Content-Security-Policy: default-src 'self'; frame-ancestors 'none'
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cache-Control: no-store, no-cache, private    (for API responses)
```

And the full CRP response header set (per CRP-SPEC-002).

---

## 8. Security Considerations for Implementors

### 8.1 Self-Hosted Deployments

When running the CRP sidecar self-hosted:
1. Generate session HMAC keys using a cryptographically secure random source (CSPRNG)
2. Store the HMAC master key outside the sidecar process (environment variable minimum; HSM recommended)
3. Enable TLS on the sidecar HTTP interface — do not expose plain HTTP outside localhost
4. Implement rate limiting on the sidecar endpoint — CRP does not provide built-in rate limiting
5. Pin the CRP sidecar version and verify SHA256 checksums of release packages

### 8.2 Browser/Client Exposure

CRP session tokens MUST NOT be exposed to browser JavaScript:
- Set `HttpOnly` flag equivalent in application-layer cookie handling
- Treat CRP-Session-Token as a server-side credential, not a client-side token
- Do not log or expose CRP response headers in browser console output

### 8.3 Multi-Agent Environments

In multi-agent deployments:
1. Each agent in a chain MUST have its own scoped CRP API key — do not share keys between agents
2. `CRP-Agent-Session-Parent` MUST be validated by the receiving agent — not blindly trusted
3. Safety Budget (`CRP-Agent-Safety-Budget`) MUST be read from the incoming header and respected — agents MUST halt if budget ≤ 0.05
4. `CRP-Safety-Policy` received from an upstream agent MAY be tightened but MUST NOT be relaxed

---

## 9. Vulnerability Disclosure

Security vulnerabilities in the CRP protocol specification or reference implementation should be reported to: `security@crprotocol.io`

PGP public key available at: `crprotocol.io/.well-known/security.txt`

Response SLA: Initial acknowledgement within 24 hours. Patch/advisory within 90 days.

---

## 10. References

- RFC 2104 — HMAC: Keyed-Hashing for Message Authentication
- RFC 5869 — HMAC-based Extract-and-Expand Key Derivation Function (HKDF)
- RFC 7519 — JSON Web Token (JWT)
- RFC 9110 — HTTP Semantics
- RFC 6265 — HTTP State Management Mechanism (Cookies)
- FIPS PUB 198-1 — The Keyed-Hash Message Authentication Code (HMAC)
- NIST SP 800-57 — Recommendation for Key Management
- OWASP API Security Top 10 (2023)
- EU AI Act Art. 9 (Risk management), Art. 13 (Transparency), Art. 14 (Oversight), Art. 64 (Logging)
- GDPR Art. 5 (Principles), Art. 17 (Right to erasure), Art. 25 (Privacy by design), Art. 32 (Security)
- ISO/IEC 27001:2022 — Information Security Management
- ISO/IEC 42001:2023 — AI Management Systems

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text).*

# CRP-SPEC-007: Session Token & State Relay

**Document:** CRP-SPEC-007  
**Title:** Context Relay Protocol (CRP) — Session Token & Stateless State Relay  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-004 (Continuation)

---

## Abstract

This document specifies the CRP Session Token — a signed, portable state container that enables stateless session relay across gateway instances, language boundaries, and process restarts. The session token is the AI equivalent of an HTTP cookie: the gateway issues it via `CRP-Set-Session`, the client echoes it back via `CRP-Session-Token`, and any CRP gateway instance can validate and resume the session from the token alone — without shared storage.

This document defines the token structure, payload schema, signing algorithm, validation rules, expiry and rotation semantics, and the security properties that make the token tamper-evident within the CRP HMAC chain.

---

## 1. Introduction

### 1.1 The Stateless Session Problem

HTTP solved stateless session continuity with cookies (RFC 6265). Before cookies, every request was independent — the server had no way to associate a request with a prior conversation. Cookies enabled stateful web applications without requiring sticky load balancing or shared session stores.

CRP faces the same problem. Each AI call to the sidecar/gateway is an independent HTTP request. Without a state relay mechanism:
- Sessions require server-side storage (preventing horizontal scaling)
- Gateway restarts lose session state
- Multi-language environments (Go calling Python sidecar) need shared databases
- Load balancers must use sticky sessions, defeating redundancy

### 1.2 The CRP Solution

The CRP Session Token carries signed session state in the HTTP response header. The client echoes it back on subsequent requests. Any CRP gateway instance that validates the signature can resume the session — no shared database, no sticky sessions.

The token is HMAC-signed with a per-session key derived from the gateway's master key. Tampering breaks the signature. The token also embeds the HMAC chain tip — meaning the token is itself part of the provenance chain.

---

## 2. Token Structure

### 2.1 Wire Format

```
CRP-Set-Session: token=<base64url(payload)>.<base64url(signature)>;
                 Path=/;
                 Max-Age=3600;
                 Signed;
                 SameSite=Strict;
                 Window=3;
                 QualityHistory=A,A,B
```

The format is deliberately similar to `Set-Cookie` (RFC 6265) for developer familiarity. The token itself is a two-part value (payload.signature) with metadata attributes following semicolons.

### 2.2 Payload Schema

```json
{
  "v": "3.0.0",
  "sid": "crp_sess_7f3a9bc2d4e1f083",
  "win": 3,
  "qh": ["A", "A", "B"],
  "sb": 0.78,
  "ct": "sha256:9bce472f...",
  "cid": "crp_cont_c1d4e5f6...",
  "dag": "LINEAR",
  "str": "reflexive",
  "pol": "sha256:policy_hash...",
  "ckf": "sha256:ckf_state_hash...",
  "scope": "crp_gw_prod_abc123...",
  "iat": 1748160000,
  "exp": 1748163600,
  "nonce": "base64:nZ8fXw=="
}
```

### 2.3 Field Definitions

| Field | Type | Description |
|-------|------|-------------|
| `v` | string | CRP protocol version |
| `sid` | string | Session identifier |
| `win` | integer | Current window number |
| `qh` | string[] | Quality tier history — one entry per window |
| `sb` | float | Safety budget remaining (0.0 – 1.0) |
| `ct` | string | HMAC chain tip — hash of the most recent window's HMAC |
| `cid` | string | Continuation ID for the next window |
| `dag` | string | DAG pattern: LINEAR / FAN_OUT / FAN_IN |
| `str` | string | Active dispatch strategy |
| `pol` | string | SHA-256 hash of the active Safety Policy string |
| `ckf` | string | SHA-256 hash of CKF state (for ETag validation) |
| `scope` | string | CRP Gateway API key prefix that created this session |
| `iat` | integer | Issued-at timestamp (Unix epoch seconds) |
| `exp` | integer | Expiry timestamp (Unix epoch seconds) |
| `nonce` | string | Safety Policy nonce (see CRP-SPEC-002 §5.16) |

### 2.4 Size Constraints

The serialised token payload MUST NOT exceed 4,096 bytes when base64url-encoded. This ensures the total `CRP-Set-Session` header value stays well under HTTP header size limits (typically 8KB per header, 16KB total across all headers for most servers).

---

## 3. Signing Algorithm

### 3.1 Key Derivation

Session signing keys are derived using HKDF (RFC 5869):

```
session_signing_key = HKDF-SHA256(
  IKM   = gateway_master_key,
  salt  = session_id_bytes,
  info  = "crp-session-sign-v3",
  L     = 32 bytes (256 bits)
)
```

This produces a unique signing key per session, derived from the gateway's master key. The master key is:
- Stored in HSM or cloud KMS (see CRP-SPEC-015 §4.4)
- Never transmitted over the network
- Never included in any CRP header
- Rotatable without invalidating existing sessions (see §6)

### 3.2 Signature Computation

```
header  = base64url({"alg": "HS256", "typ": "CRP"})
payload = base64url(JSON.stringify(payload_object))
input   = header + "." + payload
signature = HMAC-SHA256(input, session_signing_key)
token   = payload + "." + base64url(signature)
```

The format is intentionally JWT-compatible (header.payload.signature) for tooling interoperability, though the `typ` field is `CRP` (not `JWT`) to distinguish CRP tokens from standard JWTs.

### 3.3 Why HMAC-SHA256, Not RS256/ES256

Asymmetric signatures (RS256, ES256) are used when the signer and verifier are different parties. In CRP, the gateway both signs and verifies the token — there is no third-party verifier. HMAC-SHA256 provides:
- Faster signing and verification (important at scale)
- Simpler key management (no PKI infrastructure required)
- Smaller token size (32-byte signature vs 256+ for RS256)

If third-party token verification is needed (e.g., an auditor wants to verify a token without the master key), the gateway MUST provide a verification endpoint. Direct key sharing is NOT permitted.

---

## 4. Token Lifecycle

### 4.1 Issuance (Gateway → Client)

On the first AI call in a session:

```
HTTP/1.1 200 OK
CRP-Set-Session: token=eyJ2IjoiMy4wLjAi....<sig>;
                 Path=/; Max-Age=3600; Signed; SameSite=Strict;
                 Window=1; QualityHistory=A
CRP-Context-Session-Id: crp_sess_7f3a9bc2d4e1f083
```

### 4.2 Echo (Client → Gateway)

On subsequent calls:

```
POST /v1/chat HTTP/1.1
CRP-Session-Token: eyJ2IjoiMy4wLjAi....<sig>
CRP-Context-Continuation-Id: crp_cont_9a2fb3c1...
```

### 4.3 Refresh (Gateway → Client on Every Response)

Every CRP response includes an updated token:

```
CRP-Set-Session: token=<updated_token>;
                 Window=2; QualityHistory=A,A
```

The client MUST replace its stored token with the latest one on every response. Old tokens are invalidated by the chain tip check (see §5.3).

### 4.4 Expiry

Tokens expire at the `exp` timestamp. Default lifetime: 3600 seconds (1 hour).

On expiry:
- Gateway returns HTTP 401
- Client MUST start a new session
- The expired session's audit trail is preserved in CRP Comply
- No data loss — but the continuation chain cannot be extended

### 4.5 Session Termination

A session ends when:
- Token expires
- Maximum window depth reached
- Safety budget depleted to ≤ 0.00
- Client sends a request without `CRP-Session-Token` (new session started)
- Client sends `CRP-Session-Action: terminate` header (explicit termination)

---

## 5. Validation Rules

### 5.1 Signature Validation

On every request bearing `CRP-Session-Token`:

1. Split token into `payload_b64` and `signature_b64`
2. Decode payload, extract `sid` (session ID)
3. Derive `session_signing_key` from `sid` and `gateway_master_key` via HKDF
4. Recompute: `expected_sig = HMAC-SHA256(header + "." + payload_b64, session_signing_key)`
5. If `signature_b64 ≠ expected_sig` → reject with HTTP 401

### 5.2 Expiry Validation

If `current_time > exp` → reject with HTTP 401 and `CRP-Safety-Retry-After: 0` (start new session).

### 5.3 Chain Tip Validation

The token's `ct` (chain tip) field MUST match the gateway's recorded HMAC chain tip for this session:

```
if token.ct ≠ gateway.sessions[token.sid].hmac_chain_tip:
    reject with HTTP 409 Conflict
    // Token is stale — a newer window was created after this token was issued
    // Possible causes: race condition, replay attack, or client using old token
```

This prevents replay attacks where an attacker presents an older (less restrictive) token.

### 5.4 Scope Validation

The token's `scope` field MUST match the CRP API key presented in the request's `Authorization` header. A token scoped to API key `crp_gw_prod_abc123` MUST NOT be accepted for a request authenticated with API key `crp_gw_prod_def456`.

### 5.5 Safety Policy Hash Validation

The token's `pol` field contains the SHA-256 hash of the Safety Policy at session start. If the client presents a different `CRP-Safety-Policy` with the same token:
- Gateway recomputes the policy hash
- If hashes differ → validate that the new policy is MORE restrictive (tightening is allowed)
- If new policy is less restrictive → reject with HTTP 403

### 5.6 Nonce Validation

If `CRP-Safety-Nonce` is set, the token's `nonce` field MUST match. Mismatched nonces → HTTP 400.

---

## 6. Master Key Rotation

### 6.1 Rotation Without Downtime

When the gateway master key is rotated:

1. New key (`master_key_v2`) is deployed alongside old key (`master_key_v1`)
2. New sessions use `master_key_v2` for key derivation
3. Existing sessions continue using `master_key_v1` — the gateway tries both keys during validation
4. After `max_token_lifetime` (default: 1 hour), all `v1` sessions have expired
5. `master_key_v1` is decommissioned

### 6.2 Key Version Indicator

The token payload MAY include a `kv` (key version) field to allow the gateway to select the correct master key without trial-and-error:

```json
{
  "kv": 2,
  ...
}
```

---

## 7. Multi-Instance Session Relay

### 7.1 Stateless Relay Architecture

```
Client ─── CRP-Session-Token ──→ Gateway Instance A
                                       │
                                  (validates token)
                                  (derives session key from master key)
                                  (reconstructs session state from payload)
                                       │
                                  ← CRP-Set-Session (updated) ───

Client ─── CRP-Session-Token ──→ Gateway Instance B   ← different instance!
                                       │
                                  (same master key → same session key)
                                  (same validation → session continues)
```

All CRP gateway instances sharing the same `gateway_master_key` can validate any session token from any other instance. No shared session store is required.

### 7.2 What Must Be Shared

For multi-instance deployments, the ONLY shared state is:
- `gateway_master_key` — stored in HSM/KMS, accessible to all instances
- HMAC chain tips (for chain tip validation) — stored in a lightweight key-value store (Redis, DynamoDB)

The HMAC chain tips store is append-only and requires only two operations:
- `GET(session_id) → hmac_chain_tip`
- `SET(session_id, new_hmac_chain_tip)`

This is dramatically simpler than sharing full session state.

### 7.3 CKF State Consistency

The token's `ckf` field carries the CKF state hash. If the client presents a token and the gateway instance's CKF has a different state hash:
- `CRP-Context-If-Match` will fail → full envelope reconstruction
- This is correct behaviour — CKF state may differ across instances during replication lag

---

## 8. Cross-Language Relay

### 8.1 The Use Case

A Go-based orchestrator agent dispatches to a Python CRP sidecar. The orchestrator receives a session token from the sidecar and must relay it to another sidecar (possibly in a different language).

### 8.2 How It Works

The session token is an opaque string. The orchestrator:
1. Receives `CRP-Set-Session` header from Python sidecar
2. Stores the token value
3. Sends `CRP-Session-Token: <value>` to the next sidecar (Python, Go, Node.js — any)
4. The next sidecar validates the token using the same master key

No session state needs to cross language boundaries. The token IS the state.

---

## 9. Privacy Considerations

### 9.1 Token Payload as Sensitive Data

The token payload contains:
- Session ID (could be correlated to a user)
- Quality history (reveals AI system behaviour)
- Safety budget (reveals risk exposure)
- CKF state hash (reveals knowledge base version)

Tokens MUST be treated as sensitive credentials:
- MUST NOT be logged in full (only `sid` prefix logged)
- MUST NOT be transmitted over unencrypted channels (TLS required)
- MUST NOT be stored in browser-accessible storage (localStorage, cookies)
- SHOULD be treated as server-side credentials in application code

### 9.2 Token in Browser Contexts

If CRP is used in a browser-based application:
- `SameSite=Strict` MUST be set
- The application MUST store the token in a `httpOnly` equivalent (server-side session, not client-side)
- The token MUST NOT be accessible to JavaScript

---

## 10. Security Considerations

### 10.1 Token Forging

HMAC-SHA256 with a 256-bit key provides 128-bit security against forgery. An attacker without the master key cannot produce a valid token.

### 10.2 Token Replay

Token replay is mitigated by chain tip validation (§5.3). Replaying an older token will fail because the chain tip has advanced.

### 10.3 Token Theft

A stolen token allows session hijacking for the remaining token lifetime. Mitigations:
- Short token lifetime (default: 1 hour)
- `scope` binding to API key (stolen token useless without the API key)
- TLS-only transmission

### 10.4 Timing Attacks

HMAC comparison MUST use constant-time comparison to prevent timing side-channel attacks on the signature validation.

---

## 11. References

### Normative References

- RFC 2104 — HMAC
- RFC 5869 — HKDF
- RFC 6265 — HTTP State Management Mechanism (Cookies)
- RFC 7519 — JSON Web Token (JWT)
- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-004 — Window Continuation & DAG
- CRP-SPEC-015 — Security & Privacy

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*

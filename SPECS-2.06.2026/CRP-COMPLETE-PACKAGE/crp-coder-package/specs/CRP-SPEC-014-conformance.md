# CRP-SPEC-014: Conformance & Test Suite Specification

**Document:** CRP-SPEC-014  
**Title:** Context Relay Protocol (CRP) — Conformance Levels, Test Vectors & Certification Criteria  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0  
**Prerequisites:** All CRP-SPEC-001 through CRP-SPEC-013, CRP-SPEC-015

---

## Abstract

This document specifies the conformance requirements for CRP implementations, defines three conformance levels (Basic, Standard, Full), provides test vectors for every header and mechanism, and establishes the certification criteria for the "CRP-Compliant" designation. It is required for both IETF Proposed Standard status (which mandates two independent interoperable implementations verified against a common test suite) and for the CRP Certification Program (a commercial revenue stream where third-party AI products are certified as CRP-compliant).

---

## 1. Conformance Levels

### 1.1 CRP-Basic

**Target:** Minimum viable governance. Any implementation that can emit core safety and provenance headers.

**Requirements:**

| Requirement | Spec Reference | Mandatory Headers |
|------------|----------------|-------------------|
| Session management | CRP-SPEC-007 | `CRP-Context-Session-Id`, `CRP-Set-Session`, `CRP-Session-Token` |
| Hallucination risk scoring | CRP-SPEC-005 §7 | `CRP-Safety-Hallucination-Risk`, `CRP-Safety-Hallucination-Score` |
| HMAC chain | CRP-SPEC-011 §2 | `CRP-Provenance-HMAC`, `CRP-Provenance-Chain-Integrity` |
| HTTP 451 halt | CRP-SPEC-002 §13 | Must return 451 on CRITICAL risk when `halt-on CRITICAL` is set |
| Protocol version | CRP-SPEC-002 §4.15 | `CRP-Context-Protocol-Version` |
| Axiom 4 (transparency boundary) | CRP-SPEC-001 §3 | CRP headers stripped before LLM provider forwarding |

**Header count:** 7 mandatory headers  
**DPE requirement:** Stage 1 (claim segmentation) + Stage 5 (risk classification) minimum  
**Use case:** Self-hosted SDK deployments, prototype integrations, developer experimentation

### 1.2 CRP-Standard

**Target:** Production-grade governance. The level required for CRP Comply integration and for any deployment claiming CRP compliance.

**Requirements:** Everything in CRP-Basic, plus:

| Requirement | Spec Reference | Additional Mandatory Headers |
|------------|----------------|------------------------------|
| Full DPE pipeline (all 13 stages) | CRP-SPEC-005 | All `CRP-Safety-*` response headers |
| Quality Assurance (RQA) | CRP-SPEC-005 §18 | `CRP-Quality-Score`, `CRP-Quality-Repetition`, `CRP-Quality-Completeness`, `CRP-Quality-Flow` |
| Safety Policy enforcement | CRP-SPEC-006 | `CRP-Safety-Policy` parsing and enforcement |
| Context Envelope + Quality Tier | CRP-SPEC-003 | `CRP-Context-Quality-Tier`, `CRP-Context-Saturation`, `CRP-Context-ETag` |
| Compliance headers | CRP-SPEC-010 | `CRP-Compliance-EU-AI-Act`, `CRP-Compliance-Audit-Trail-Id`, `CRP-Compliance-Audit-Trail-URI` |
| Provenance headers | CRP-SPEC-011 | `CRP-Provenance-Claim-Count`, `CRP-Provenance-Attribution-Score`, `CRP-Provenance-Fidelity-Score`, `CRP-Provenance-Report-URI` |
| Continuation support | CRP-SPEC-004 | `CRP-Context-Window`, `CRP-Context-Continuation-Id` |
| Audit trail export | CRP-SPEC-011 §4 | NDJSON export of audit events |
| ETag conditional dispatch | CRP-SPEC-003 §11 | `CRP-Context-If-Match` → 304 response |

**Header count:** All 58 headers emitted when applicable  
**DPE requirement:** Full 13-stage pipeline including RQA (Stages 6–9)  
**Use case:** Production deployments, CRP Comply integration, regulatory compliance

### 1.3 CRP-Full

**Target:** Complete protocol implementation including advanced features. Required for CRP Certification.

**Requirements:** Everything in CRP-Standard, plus:

| Requirement | Spec Reference |
|------------|----------------|
| All 9 dispatch strategies | CRP-SPEC-008 |
| Multi-agent safety budget propagation | CRP-SPEC-012 |
| Safety Policy inheritance and tightening in agent chains | CRP-SPEC-012 §4 |
| Circuit breaker state transitions | CRP-SPEC-012 §5 |
| Fan-out / fan-in DAG with HMAC merge | CRP-SPEC-004 §6, §7, §9.3 |
| Streaming safety mode (buffer and pass-through) | CRP-SPEC-008 §9 |
| CRP-Safety-Stop-Inject (mid-stream halt) | CRP-SPEC-005 §1.3 |
| OCSF audit trail export | CRP-SPEC-011 §4.2 |
| mTLS client authentication | CRP-SPEC-015 §4.1 |
| CRP Comply real-time streaming integration | CRP-SPEC-011 §5 |
| CRP Visualise session data export | — |
| Industry-specific Safety Policy profiles | CRP-SPEC-006 §6 |
| Multi-region data residency enforcement | CRP-SPEC-002 §7.7 |

**Use case:** CRP Gateway (managed service), CRP Certification program, enterprise deployments

---

## 2. Test Vectors

### 2.1 Test Vector Format

Each test vector is a JSON object defining:

```json
{
  "test_id": "TV-001",
  "category": "headers | dpe | safety_policy | session | continuation | agent | hmac",
  "conformance_level": "basic | standard | full",
  "description": "Human-readable description of what is being tested",
  "input": { ... },
  "expected_output": { ... },
  "assertions": [ ... ]
}
```

### 2.2 Header Test Vectors

#### TV-001: Minimum Basic Header Set

```json
{
  "test_id": "TV-001",
  "category": "headers",
  "conformance_level": "basic",
  "description": "Verify that a CRP-Basic implementation emits all 7 mandatory headers on a simple push dispatch",
  "input": {
    "method": "POST",
    "path": "/v1/chat",
    "body": { "messages": [{ "role": "user", "content": "What is the EU AI Act?" }] }
  },
  "assertions": [
    { "header_present": "CRP-Context-Session-Id", "pattern": "^crp_sess_[a-zA-Z0-9]{16,32}$" },
    { "header_present": "CRP-Safety-Hallucination-Risk", "values": ["CRITICAL", "HIGH", "MEDIUM", "LOW"] },
    { "header_present": "CRP-Safety-Hallucination-Score", "range": [0.0, 1.0] },
    { "header_present": "CRP-Provenance-HMAC", "pattern": "^sha256:[a-f0-9]{64}$" },
    { "header_present": "CRP-Provenance-Chain-Integrity", "values": ["VALID", "UNVERIFIED"] },
    { "header_present": "CRP-Set-Session" },
    { "header_present": "CRP-Context-Protocol-Version", "pattern": "^3\\." }
  ]
}
```

#### TV-002: Axiom 4 — LLM Provider Header Stripping

```json
{
  "test_id": "TV-002",
  "category": "headers",
  "conformance_level": "basic",
  "description": "Verify that no CRP-* headers are forwarded to the LLM provider",
  "input": {
    "method": "POST",
    "path": "/v1/chat",
    "headers": {
      "CRP-Safety-Policy": "halt-on CRITICAL",
      "CRP-Accept-Quality": "S, A",
      "CRP-Session-Token": "eyJ..."
    }
  },
  "assertions": [
    { "provider_request_headers_absent": ["CRP-Safety-Policy", "CRP-Accept-Quality", "CRP-Session-Token"] },
    { "note": "Verify by inspecting the request sent to the LLM provider. No header starting with 'CRP-' may be present." }
  ]
}
```

#### TV-003: HTTP 451 on CRITICAL Risk

```json
{
  "test_id": "TV-003",
  "category": "headers",
  "conformance_level": "basic",
  "description": "Verify HTTP 451 returned when DPE produces CRITICAL risk and halt-on CRITICAL is set",
  "input": {
    "headers": { "CRP-Safety-Policy": "halt-on CRITICAL" },
    "body": { "messages": [{ "role": "user", "content": "Query designed to produce CRITICAL-risk response from test LLM" }] }
  },
  "assertions": [
    { "http_status": 451 },
    { "header_present": "CRP-Safety-Hallucination-Risk", "value": "CRITICAL" },
    { "header_present": "CRP-Safety-Retry-After" },
    { "header_present": "CRP-Compliance-Audit-Trail-URI" },
    { "body_json_field": "crp_halt_reason" }
  ]
}
```

#### TV-004: ETag Conditional Dispatch — 304

```json
{
  "test_id": "TV-004",
  "category": "headers",
  "conformance_level": "standard",
  "description": "Verify HTTP 304 returned when CRP-Context-If-Match matches current CKF state and no facts have changed",
  "input": {
    "step_1": { "method": "POST", "path": "/v1/chat", "body": { "messages": [{ "role": "user", "content": "What is ISO 42001?" }] } },
    "step_2": { "method": "POST", "path": "/v1/chat", "headers": { "CRP-Context-If-Match": "<etag_from_step_1>" }, "body": { "messages": [{ "role": "user", "content": "What is ISO 42001?" }] } }
  },
  "assertions": [
    { "step_1_header_present": "CRP-Context-ETag" },
    { "step_2_http_status": 304 },
    { "step_2_header_present": "CRP-Context-ETag", "equals": "<same_as_step_1>" },
    { "step_2_header_present": "CRP-Context-Cache-Status", "value": "HIT" }
  ]
}
```

### 2.3 DPE Test Vectors

#### TV-010: Fabrication Detection

```json
{
  "test_id": "TV-010",
  "category": "dpe",
  "conformance_level": "standard",
  "description": "Verify DPE detects a fabricated entity in an LLM response",
  "input": {
    "envelope_facts": [
      { "fact_id": "f1", "content": "The EU AI Act was adopted in 2024 by the European Parliament." },
      { "fact_id": "f2", "content": "The Act classifies AI systems into four risk levels." }
    ],
    "llm_response": "The EU AI Act was adopted in 2024. According to Commissioner Hans Müller, the Act classifies AI systems into four risk levels.",
    "note": "Hans Müller is a fabricated entity — no such commissioner exists in the envelope or as a known public figure."
  },
  "assertions": [
    { "header": "CRP-Safety-Fabrications", "value_gte": 1 },
    { "dpe_report_field": "fabrication_count", "value_gte": 1 },
    { "dpe_report_contains_entity": "Hans Müller" }
  ]
}
```

#### TV-011: Distortion Detection — Number Changed

```json
{
  "test_id": "TV-011",
  "category": "dpe",
  "conformance_level": "standard",
  "description": "Verify DPE detects when a number from the source is changed in the response",
  "input": {
    "envelope_facts": [
      { "fact_id": "f1", "content": "Revenue increased by 15% in Q3 2025." }
    ],
    "llm_response": "Revenue increased by 25% in Q3 2025."
  },
  "assertions": [
    { "header": "CRP-Safety-Distortions", "contains": "NUMBER_CHANGED" },
    { "dpe_report_field": "distortion_count", "value_gte": 1 }
  ]
}
```

#### TV-012: Cross-Window Contradiction

```json
{
  "test_id": "TV-012",
  "category": "dpe",
  "conformance_level": "standard",
  "description": "Verify DPE Stage 6 detects contradiction between current response and prior window",
  "input": {
    "prior_window_response": "The company's revenue declined by 3% in the fiscal year.",
    "current_response": "The company experienced strong revenue growth of 12% in the fiscal year."
  },
  "assertions": [
    { "header": "CRP-Safety-Contradictions", "contains": "cross-window" },
    { "dpe_report_field": "cross_window_contradictions", "length_gte": 1 }
  ]
}
```

#### TV-013: Repetition Detection

```json
{
  "test_id": "TV-013",
  "category": "dpe",
  "conformance_level": "standard",
  "description": "Verify DPE Stage 7 detects severe repetition between windows",
  "input": {
    "prior_window_response": "The EU AI Act classifies AI systems into four risk levels: unacceptable, high, limited, and minimal. Each level carries different regulatory obligations.",
    "current_response": "The EU AI Act classifies AI systems into four risk levels: unacceptable, high, limited, and minimal. The obligations vary by level. Each risk category carries different regulatory requirements."
  },
  "assertions": [
    { "header": "CRP-Quality-Repetition", "contains": "SIGNIFICANT" },
    { "note": "Semantic overlap > 0.50 expected due to near-verbatim content" }
  ]
}
```

### 2.4 Safety Policy Test Vectors

#### TV-020: Policy Parsing — Valid

```json
{
  "test_id": "TV-020",
  "category": "safety_policy",
  "conformance_level": "standard",
  "description": "Verify gateway correctly parses a complex Safety Policy",
  "input": {
    "header": "CRP-Safety-Policy: default-src context; halt-on CRITICAL; warn-on HIGH; require-grounding 0.75; block-ungrounded; upgrade-on-risk reflexive; report-uri https://comply.crprotocol.io/reports"
  },
  "assertions": [
    { "parsed_directive": "default-src", "value": ["context"] },
    { "parsed_directive": "halt-on", "value": "CRITICAL" },
    { "parsed_directive": "warn-on", "value": "HIGH" },
    { "parsed_directive": "require-grounding", "value": 0.75 },
    { "parsed_directive": "block-ungrounded", "value": true },
    { "parsed_directive": "upgrade-on-risk", "value": "reflexive" },
    { "parsed_directive": "report-uri", "value": "https://comply.crprotocol.io/reports" }
  ]
}
```

#### TV-021: Policy Parsing — Malformed Rejection

```json
{
  "test_id": "TV-021",
  "category": "safety_policy",
  "conformance_level": "standard",
  "description": "Verify gateway rejects malformed Safety Policy with unknown directive",
  "input": {
    "header": "CRP-Safety-Policy: default-src context; halt-on CRITICAL; allow-hallucination"
  },
  "assertions": [
    { "http_status": 400 },
    { "body_contains": "unknown directive" },
    { "note": "allow-hallucination is not a valid directive — gateway MUST reject, not silently ignore" }
  ]
}
```

#### TV-022: Policy Inheritance — Tightening Accepted

```json
{
  "test_id": "TV-022",
  "category": "safety_policy",
  "conformance_level": "full",
  "description": "Verify child agent can tighten parent's Safety Policy",
  "input": {
    "parent_policy": "halt-on CRITICAL; require-grounding 0.75",
    "child_policy": "halt-on HIGH; require-grounding 0.85; block-fabrication"
  },
  "assertions": [
    { "http_status": 200 },
    { "header": "CRP-Safety-Policy-Applied", "contains": "halt-on HIGH" }
  ]
}
```

#### TV-023: Policy Inheritance — Relaxation Rejected

```json
{
  "test_id": "TV-023",
  "category": "safety_policy",
  "conformance_level": "full",
  "description": "Verify child agent cannot relax parent's Safety Policy",
  "input": {
    "parent_policy": "halt-on CRITICAL; require-grounding 0.75",
    "child_policy": "warn-on CRITICAL; require-grounding 0.50"
  },
  "assertions": [
    { "http_status": 403 },
    { "body_json_field": "error", "value": "safety_policy_inheritance_violation" }
  ]
}
```

### 2.5 HMAC Chain Test Vectors

#### TV-030: Chain Verification — Valid

```json
{
  "test_id": "TV-030",
  "category": "hmac",
  "conformance_level": "basic",
  "description": "Verify HMAC chain is valid across 3 windows",
  "input": {
    "session_hmac_key": "hex:0123456789abcdef...",
    "windows": [
      { "window_number": 1, "content_hash": "sha256:aaa...", "dpe_hash": "sha256:bbb...", "timestamp": "2026-05-25T10:00:00Z" },
      { "window_number": 2, "content_hash": "sha256:ccc...", "dpe_hash": "sha256:ddd...", "timestamp": "2026-05-25T10:01:00Z" },
      { "window_number": 3, "content_hash": "sha256:eee...", "dpe_hash": "sha256:fff...", "timestamp": "2026-05-25T10:02:00Z" }
    ]
  },
  "assertions": [
    { "window_1_hmac": "sha256:<computed>", "note": "Previous HMAC is empty string for root" },
    { "window_2_hmac": "sha256:<computed>", "note": "Chains from window_1_hmac" },
    { "window_3_hmac": "sha256:<computed>", "note": "Chains from window_2_hmac" },
    { "header": "CRP-Provenance-Chain-Integrity", "value": "VALID" }
  ]
}
```

#### TV-031: Chain Verification — Broken (Tampered Event)

```json
{
  "test_id": "TV-031",
  "category": "hmac",
  "conformance_level": "basic",
  "description": "Verify chain integrity detects tampering when a window's content hash is modified after signing",
  "input": {
    "same_as": "TV-030",
    "modification": "window_2.content_hash changed from sha256:ccc... to sha256:zzz..."
  },
  "assertions": [
    { "header": "CRP-Provenance-Chain-Integrity", "value": "BROKEN" },
    { "note": "Window 2's recomputed HMAC will not match stored HMAC because content_hash was changed" }
  ]
}
```

### 2.6 Session Token Test Vectors

#### TV-040: Token Signature Validation — Valid

```json
{
  "test_id": "TV-040",
  "category": "session",
  "conformance_level": "basic",
  "description": "Verify gateway accepts a correctly signed session token",
  "input": {
    "master_key": "hex:fedcba9876543210...",
    "session_id": "crp_sess_7f3a9bc2d4e1f083",
    "token_payload": { "v": "3.0.0", "sid": "crp_sess_7f3a9bc2d4e1f083", "win": 1, "exp": 9999999999 }
  },
  "assertions": [
    { "signature_valid": true },
    { "session_resumed": true }
  ]
}
```

#### TV-041: Token Expiry Rejection

```json
{
  "test_id": "TV-041",
  "category": "session",
  "conformance_level": "basic",
  "description": "Verify gateway rejects an expired session token",
  "input": {
    "token_payload": { "exp": 1000000000 },
    "note": "exp is in the past"
  },
  "assertions": [
    { "http_status": 401 }
  ]
}
```

### 2.7 Safety Budget Test Vectors

#### TV-050: Budget Depletion Across Calls

```json
{
  "test_id": "TV-050",
  "category": "agent",
  "conformance_level": "full",
  "description": "Verify safety budget decrements correctly across multiple calls with different risk levels",
  "input": {
    "calls": [
      { "risk_level": "LOW", "expected_budget_after": 1.00 },
      { "risk_level": "MEDIUM", "expected_budget_after": 0.95 },
      { "risk_level": "HIGH", "expected_budget_after": 0.80 },
      { "risk_level": "HIGH", "expected_budget_after": 0.65 },
      { "risk_level": "CRITICAL", "expected_budget_after": 0.30 },
      { "risk_level": "MEDIUM", "expected_budget_after": 0.25 }
    ]
  },
  "assertions": [
    { "call_6_header": "CRP-Agent-Safety-Budget", "value_lte": 0.25 },
    { "call_6_header": "CRP-Safety-Budget-Warning", "value": "caution" },
    { "call_6_header": "CRP-Safety-Oversight-Mode", "note": "Not yet forced to human-review (budget > 0.10)" }
  ]
}
```

#### TV-051: Budget Depletion → Forced Halt

```json
{
  "test_id": "TV-051",
  "category": "agent",
  "conformance_level": "full",
  "description": "Verify session halts when safety budget depletes to ≤ 0.10",
  "input": {
    "budget_before_call": 0.12,
    "call_risk_level": "HIGH"
  },
  "assertions": [
    { "http_status": 451 },
    { "body_json_field": "crp_halt_reason", "value": "SAFETY_BUDGET_DEPLETED" },
    { "note": "Budget would be 0.12 - 0.15 = -0.03, which is ≤ 0.10 → halt" }
  ]
}
```

---

## 3. Certification Program

### 3.1 CRP-Compliant Certification

The "CRP-Compliant" certification is a commercial program operated by AutoCyber AI Pty Ltd. Third-party AI products and platforms can obtain certification to demonstrate they implement the CRP protocol correctly.

### 3.2 Certification Levels

| Level | Requires | Badge | Annual Fee |
|-------|----------|-------|-----------|
| **CRP-Basic Certified** | Pass all Basic test vectors | "CRP-Basic Compliant" | $5,000 |
| **CRP-Standard Certified** | Pass all Basic + Standard test vectors | "CRP-Standard Compliant" | $10,000 |
| **CRP-Full Certified** | Pass all Basic + Standard + Full test vectors | "CRP-Full Certified Partner" | $25,000 |

### 3.3 Certification Process

1. **Application:** Vendor submits application describing their implementation
2. **Self-Assessment:** Vendor runs the CRP Conformance Test Suite against their implementation and submits results
3. **Independent Verification:** AutoCyber AI (or a designated audit partner) runs the test suite independently against the vendor's implementation
4. **Gap Remediation:** Any failing test vectors are documented; vendor has 90 days to remediate
5. **Certification Issued:** On passing all test vectors for the target level
6. **Annual Renewal:** Re-run test suite annually; certification lapses if not renewed

### 3.4 Test Suite Distribution

The test suite is:
- Published as an open-source test runner at `github.com/crprotocol/conformance-tests`
- Runnable against any CRP-compatible HTTP endpoint
- Includes all test vectors defined in this document plus additional edge-case vectors
- Updated with each CRP protocol version release

### 3.5 IETF Interoperability Requirement

For IETF Proposed Standard status, at least two independent implementations MUST pass the CRP-Standard conformance suite. The test results MUST be published in the IETF implementation report.

---

## 4. Interoperability Testing

### 4.1 Cross-Implementation Tests

When two CRP implementations exist (e.g., the reference Python implementation and a third-party Go implementation):

1. **Client A → Gateway B:** Client using implementation A sends requests to gateway running implementation B. All test vectors must pass.
2. **Session Token Relay:** Token issued by Gateway A must be validatable by Gateway B (requires shared master key or compatible key derivation).
3. **HMAC Chain Verification:** Chain generated by Gateway A must be verifiable by Gateway B.
4. **Safety Policy Portability:** Policy parsed by Gateway A must produce identical enforcement behaviour in Gateway B.

### 4.2 Provider Compatibility Tests

CRP implementations MUST be tested against:
- OpenAI API (GPT-4o, GPT-4o-mini)
- Anthropic API (Claude Sonnet 4, Claude Haiku)
- Google Gemini API
- Ollama (local models)
- Azure OpenAI

Each provider test verifies:
- Axiom 4 compliance (no CRP headers leaked to provider)
- Correct tokenizer selection for the target model
- DPE operates correctly on provider-specific response formats

---

## 5. Conformance Statement Template

Implementations MUST publish a conformance statement:

```markdown
# CRP Conformance Statement

**Product:** [Product Name]
**Version:** [Version]
**CRP Protocol Version:** 3.0.0
**Conformance Level:** [Basic / Standard / Full]
**Test Suite Version:** [Version]
**Test Date:** [Date]
**Test Results:**
  - Basic vectors: [X/Y passed]
  - Standard vectors: [X/Y passed] (if applicable)
  - Full vectors: [X/Y passed] (if applicable)
**Known Deviations:** [List any test vectors that are not applicable or intentionally deviated from, with justification]
**Contact:** [Vendor contact for interoperability testing]
```

---

## 6. References

- All CRP-SPEC-001 through CRP-SPEC-013, CRP-SPEC-015
- IETF BCP 9 — The Internet Standards Process (interoperability requirement)
- OASIS SARIF v2.1.0 — Test output format compatibility

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

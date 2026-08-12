# CRP-SPEC-006: Safety Policy Directive Language

**Document:** CRP-SPEC-006  
**Title:** Context Relay Protocol (CRP) — Safety Policy Directive Language Specification  
**Version:** 3.0.0  
**Status:** Draft — IETF Internet-Draft Candidate  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0 (specification text)  
**Prerequisites:** CRP-SPEC-001 (Core), CRP-SPEC-002 (Headers), CRP-SPEC-005 (DPE)

---

## Abstract

This document specifies the `CRP-Safety-Policy` directive language — a declarative policy syntax for expressing AI safety requirements at the transport layer. The directive language is modelled after HTTP Content-Security-Policy (CSP) as defined in W3C CSP Level 3. It allows clients to declare what AI output characteristics are trusted, what risk levels trigger enforcement actions, and where violations should be reported. The CRP gateway enforces these policies on every AI response before delivery to the client. This document defines the complete directive grammar, enforcement semantics, violation reporting, and policy inheritance in multi-agent chains.

---

## 1. Introduction

### 1.1 Design Inspiration: Content-Security-Policy

CSP transformed browser security by moving enforcement from "check in JavaScript" to "declare at the transport layer and let the browser enforce." Before CSP, every web application implemented its own XSS protection. After CSP, a single header — `Content-Security-Policy: default-src 'self'` — enforced security across the entire page without application code changes.

`CRP-Safety-Policy` applies the same principle to AI safety. Before CRP-Safety-Policy, every AI application implements its own hallucination checking. After CRP-Safety-Policy, a single header — `CRP-Safety-Policy: default-src context; halt-on CRITICAL` — enforces safety across every AI call without application code changes. The CRP gateway is the enforcer, just as the browser is the enforcer for CSP.

### 1.2 Scope

This document defines:
- The complete ABNF grammar for `CRP-Safety-Policy` directives
- The enforcement semantics for each directive
- The interaction between directives
- Violation reporting (analogous to CSP `report-uri`)
- Policy inheritance and tightening in multi-agent chains
- The `CRP-Safety-Policy-Report-Only` header for monitoring without enforcement

---

## 2. Grammar

### 2.1 Complete ABNF

```abnf
; Top-level policy
safety-policy     = directive *( ";" OWS directive )

; Individual directives
directive         = source-directive
                  / halt-directive
                  / warn-directive
                  / require-directive
                  / block-directive
                  / upgrade-directive
                  / oversight-directive
                  / report-directive
                  / quality-directive

; Source trust — which grounding sources are acceptable
source-directive  = "default-src" SP source-list
source-list       = source-value *( SP source-value )
source-value      = "context"          ; CKF/envelope-grounded claims only
                  / "parametric"       ; LLM parametric memory allowed
                  / "ckf"             ; CKF cross-session knowledge allowed
                  / "cross-session"    ; Cross-session references allowed
                  / "'none'"          ; No sources trusted (blocks all output)

; Halt — stop response delivery at specified risk level
halt-directive    = "halt-on" SP risk-level
risk-level        = "CRITICAL" / "HIGH" / "MEDIUM"

; Warn — pass response but flag at specified risk level
warn-directive    = "warn-on" SP risk-level

; Require — minimum quality/score thresholds
require-directive = "require-grounding" SP threshold
                  / "require-entailment" SP threshold
                  / "require-quality" SP quality-list
                  / "require-oversight" SP oversight-mode
                  / "require-flow" SP threshold
                  / "require-completeness" SP threshold
threshold         = 1*DIGIT "." 1*2DIGIT   ; e.g., "0.80"
quality-list      = quality-tier *( SP quality-tier )
quality-tier      = "S" / "A" / "B" / "C" / "D"

; Block — reject output containing specified content
block-directive   = "block-ungrounded"     ; Block if any claim is ungrounded
                  / "block-parametric"     ; Block all parametric content
                  / "block-pii"           ; Block if PII detected
                  / "block-fabrication"    ; Block if any fabrication detected
                  / "block-repetition"     ; Block if SEVERE repetition detected

; Upgrade — auto-upgrade dispatch strategy on risk
upgrade-directive = "upgrade-on-risk" SP strategy-name
strategy-name     = "reflexive" / "hierarchical" / "batch"

; Oversight — human oversight requirements
oversight-directive = "oversight" SP oversight-mode
oversight-mode    = "auto" / "human-review" / "halt" / "log-only"

; Report — violation reporting endpoint
report-directive  = "report-uri" SP uri-reference
                  / "report-to" SP group-name
uri-reference     = <URI as defined in RFC 3986>
group-name        = 1*( ALPHA / DIGIT / "-" / "_" )

; Quality — response quality requirements (NEW v3.0)
quality-directive = "require-flow" SP threshold
                  / "require-completeness" SP threshold
                  / "max-repetition" SP repetition-level
repetition-level  = "NONE" / "MINOR" / "SIGNIFICANT"

OWS               = *( SP / HTAB )
SP                 = %x20
HTAB               = %x09
```

### 2.2 Header Syntax

```
CRP-Safety-Policy: <directive> ; <directive> ; ...
```

Example:
```
CRP-Safety-Policy: default-src context; halt-on CRITICAL; warn-on HIGH; require-grounding 0.75; block-ungrounded; upgrade-on-risk reflexive; report-uri https://comply.crprotocol.io/reports
```

---

## 3. Directive Reference

### 3.1 default-src (Source Trust)

**Purpose:** Declares which grounding sources are trusted for claims in the response.

**Enforcement:** After DPE Stage 2 (Attribution Analysis), any claim attributed to a source type not listed in `default-src` is treated as a policy violation.

| Source Value | Claims Allowed From |
|-------------|-------------------|
| `context` | Claims grounded in the Context Envelope (CKF + current session facts) |
| `parametric` | Claims from the LLM's parametric memory (training data) |
| `ckf` | Claims specifically from CKF Tier 3 (cross-session knowledge graph) |
| `cross-session` | Claims referencing prior session data |
| `'none'` | No claims trusted — effectively blocks all AI output |

**Examples:**
```
default-src context                    ; Only envelope-grounded claims
default-src context parametric         ; Allow both grounded and parametric
default-src context ckf                ; Allow envelope + cross-session CKF
default-src 'none'                     ; Block everything (useful for testing)
```

**Default (if `default-src` not specified):** `default-src context parametric`

### 3.2 halt-on (Halt Enforcement)

**Purpose:** Stop response delivery and return HTTP 451 when the DPE risk classification meets or exceeds the specified level.

**Enforcement:**
1. DPE runs fully (all 13 stages)
2. If `CRP-Safety-Hallucination-Risk` ≥ specified level → HTTP 451 returned
3. Response body contains halt reason, audit trail URI, retry condition
4. Webhook fired to `report-uri` (if configured)
5. `CRP-Safety-Retry-After: oversight-required` set on 451 response

**Behaviour by level:**
```
halt-on CRITICAL     ; Halt only on CRITICAL (most permissive halt)
halt-on HIGH         ; Halt on HIGH or CRITICAL
halt-on MEDIUM       ; Halt on MEDIUM, HIGH, or CRITICAL (strictest)
```

**Note:** `halt-on` and `warn-on` can coexist for different levels:
```
halt-on CRITICAL; warn-on HIGH    ; CRITICAL = halt, HIGH = pass with warning
```

### 3.3 warn-on (Warning Without Halt)

**Purpose:** Pass the response but emit risk-level headers when threshold is met.

**Enforcement:** Response passes through to client. The following headers are guaranteed to be present:
- `CRP-Safety-Hallucination-Risk: <level>`
- `CRP-Safety-Hallucination-Score: <score>`
- Violation report POSTed to `report-uri` (if configured)

### 3.4 require-grounding (Minimum Grounding Floor)

**Purpose:** Reject responses where the grounding percentage falls below the threshold.

**Enforcement:** If `CRP-Safety-Grounding-Pct` < threshold → response rejected.

**Rejection behaviour:** If `upgrade-on-risk` is set, the gateway re-dispatches with `context-strict` grounding mode. If re-dispatch also fails → HTTP 451.

**Examples:**
```
require-grounding 0.90     ; 90%+ of claims must be grounded (medical/legal)
require-grounding 0.75     ; 75%+ (standard production)
require-grounding 0.50     ; 50%+ (permissive, exploratory use)
```

### 3.5 require-entailment (Minimum Entailment Floor)

**Purpose:** Reject responses where the NLI entailment score falls below the threshold.

**Enforcement:** If `CRP-Safety-Entailment-Score` < threshold → response rejected (same flow as `require-grounding`).

### 3.6 require-quality (Minimum Quality Tier)

**Purpose:** Reject responses from envelopes below the specified quality tier.

**Enforcement:** If `CRP-Context-Quality-Tier` not in specified list → HTTP 503.

**Example:**
```
require-quality S A          ; Only S or A tier envelopes accepted
require-quality S A B        ; S, A, or B (excludes C and D)
```

### 3.7 require-flow (Minimum Flow Score) ★ NEW

**Purpose:** Ensure multi-window responses maintain coherent flow.

**Enforcement:** If `CRP-Quality-Flow` < threshold → re-dispatch with flow augmentation prompt (see CRP-SPEC-005 §11.5).

**Example:**
```
require-flow 0.60            ; Moderate flow coherence required
require-flow 0.80            ; High flow coherence (for user-facing content)
```

### 3.8 require-completeness (Minimum Completeness) ★ NEW

**Purpose:** Ensure the response addresses all constituent information needs of the query.

**Enforcement:** If `CRP-Quality-Completeness` score < threshold → auto-continuation window dispatched to cover uncovered sub-queries.

**Example:**
```
require-completeness 0.80    ; At least 80% of sub-queries must be addressed
```

### 3.9 block-ungrounded

**Purpose:** Block the response if any factual claim is ungrounded (PARAMETRIC or UNVERIFIABLE attribution with no source in the envelope).

**Enforcement:** Equivalent to `default-src context` but applied per-claim rather than as a default. Individual ungrounded claims cause rejection; `default-src context parametric` with `block-ungrounded` means parametric claims are allowed in the source trust model but individually ungrounded specific claims are still blocked.

### 3.10 block-pii

**Purpose:** Block the response if PII is detected by DPE Stage 11.

**Enforcement:** If `CRP-Compliance-GDPR-PII: true` → response rejected. Especially important for public-facing AI systems where PII exposure is a GDPR Art. 5(1)(f) violation.

### 3.11 block-fabrication

**Purpose:** Block the response if any fabricated entity is detected by DPE Stage 3a.

**Enforcement:** If `CRP-Safety-Fabrications` > 0 → response rejected. Strictest fabrication policy — used for medical, legal, financial domains.

### 3.12 block-repetition ★ NEW

**Purpose:** Block the response if SEVERE repetition is detected by DPE Stage 7.

**Enforcement:** If `CRP-Quality-Repetition` level is `SEVERE` → re-dispatch with anti-repetition prompt. If re-dispatch also produces SEVERE repetition → halt.

### 3.13 max-repetition ★ NEW

**Purpose:** Set the maximum tolerable repetition level.

**Enforcement:**
```
max-repetition NONE           ; Zero repetition tolerated
max-repetition MINOR          ; Minor overlap acceptable
max-repetition SIGNIFICANT    ; Up to significant overlap allowed
```

### 3.14 upgrade-on-risk (Strategy Auto-Upgrade)

**Purpose:** When risk exceeds the `warn-on` level, automatically upgrade the dispatch strategy.

**Enforcement:**
1. Initial dispatch with current strategy (e.g., `push`)
2. DPE detects HIGH risk
3. Gateway re-dispatches with specified strategy (e.g., `reflexive`)
4. Reflexive dispatch includes verification pass → lower risk expected
5. If re-dispatch still exceeds threshold → halt (if `halt-on` set) or pass with HIGH warning

**Example:**
```
upgrade-on-risk reflexive      ; Upgrade to reflexive on HIGH risk
upgrade-on-risk hierarchical   ; Upgrade to hierarchical aggregation
```

### 3.15 oversight (Human Oversight Mode)

**Purpose:** Set the human oversight level for the session.

**Enforcement:** See CRP-SPEC-002 §5.10 (`CRP-Safety-Oversight-Mode`).

### 3.16 report-uri (Violation Reporting)

**Purpose:** Specify the endpoint to which violation reports are POSTed.

**Report payload (JSON):**
```json
{
  "crp_version": "3.0.0",
  "session_id": "crp_sess_...",
  "window_id": "crp_win_...",
  "timestamp": "2026-05-25T10:00:00Z",
  "violation_type": "HALT_ON_CRITICAL | GROUNDING_BELOW_THRESHOLD | FABRICATION_DETECTED | PII_DETECTED | FLOW_BELOW_THRESHOLD",
  "directive_violated": "halt-on CRITICAL",
  "risk_level": "CRITICAL",
  "hallucination_score": 0.73,
  "grounding_pct": 0.61,
  "fabrication_count": 2,
  "audit_trail_uri": "https://comply.crprotocol.io/t/..."
}
```

**Note:** `report-uri` for CRP-Safety-Policy naturally integrates with CRP Comply — the `audit_trail_uri` in the report links directly to the Comply evidence record.

---

## 4. Policy Interaction Rules

### 4.1 Directive Precedence

When multiple directives interact, the most restrictive wins:

```
halt-on CRITICAL + warn-on HIGH
  → CRITICAL = halt, HIGH = warn, MEDIUM/LOW = pass

halt-on HIGH + warn-on MEDIUM
  → HIGH/CRITICAL = halt, MEDIUM = warn, LOW = pass

halt-on CRITICAL + upgrade-on-risk reflexive
  → HIGH = upgrade to reflexive and retry, CRITICAL = halt (even after upgrade)
```

### 4.2 CRP-Safety-Mode Override

`CRP-Safety-Mode` (see CRP-SPEC-002 §5.11) is a shorthand for common policy combinations:

| Mode | Equivalent Policy |
|------|------------------|
| `strict` | `halt-on CRITICAL; warn-on HIGH; block-ungrounded; require-grounding 0.75` |
| `warn` | `warn-on CRITICAL; warn-on HIGH` |
| `permissive` | (no enforcement directives) |

When both `CRP-Safety-Mode` and `CRP-Safety-Policy` are set, per-directive the more restrictive wins.

### 4.3 Report-Only Mode

The `CRP-Safety-Policy-Report-Only` header evaluates the policy but does NOT enforce it:

```
CRP-Safety-Policy-Report-Only: halt-on CRITICAL; require-grounding 0.80; report-uri https://comply.crprotocol.io/reports
```

All violations are computed and reported to `report-uri` but responses are never halted. This enables gradual policy rollout — observe violations before enforcing.

---

## 5. Policy Inheritance in Multi-Agent Chains

### 5.1 Tightening Rule

In multi-agent chains, a child agent's Safety Policy MUST be equal to or more restrictive than the parent's:

```
Parent policy:  halt-on CRITICAL; require-grounding 0.75
Child policy:   halt-on HIGH; require-grounding 0.80     ← VALID (tighter)
Child policy:   warn-on CRITICAL; require-grounding 0.50  ← INVALID (relaxed)
```

Gateway MUST reject child agent requests that attempt to relax the parent's policy.

### 5.2 Enforcement

When a child agent request is received:
1. Gateway reads `CRP-Agent-Session-Parent` to identify the parent session
2. Gateway retrieves the parent's Safety Policy
3. Gateway compares each directive in the child's policy against the parent's
4. Any directive that is less restrictive → reject with HTTP 403 and `CRP-Safety-Policy-Violation: inheritance`

### 5.3 Policy Propagation Header

When the gateway enforces policy inheritance, it emits:

```
CRP-Safety-Policy-Applied: halt-on HIGH; require-grounding 0.80
```

This indicates the effective policy after inheritance resolution (may differ from the client's requested policy).

---

## 6. Industry-Specific Policy Profiles

### 6.1 Pre-Defined Profiles

CRP defines named policy profiles for common industry use cases:

```
CRP-Safety-Policy: profile=medical
  → Expands to: default-src context; halt-on HIGH; require-grounding 0.90;
    require-entailment 0.85; block-ungrounded; block-pii; block-fabrication;
    oversight human-review; require-flow 0.70; require-completeness 0.90;
    report-uri https://comply.crprotocol.io/reports

CRP-Safety-Policy: profile=financial
  → Expands to: default-src context parametric; halt-on CRITICAL;
    warn-on HIGH; require-grounding 0.80; block-fabrication;
    upgrade-on-risk reflexive; require-completeness 0.80

CRP-Safety-Policy: profile=developer
  → Expands to: default-src context parametric; warn-on CRITICAL;
    require-quality S A B; oversight auto

CRP-Safety-Policy: profile=public-facing
  → Expands to: default-src context parametric; halt-on CRITICAL;
    warn-on HIGH; block-pii; require-flow 0.60;
    max-repetition MINOR; require-completeness 0.70
```

Profiles can be extended with additional directives:
```
CRP-Safety-Policy: profile=medical; report-uri https://my-hospital.com/ai-audit
```

---

## 7. Security Considerations

### 7.1 Policy Injection

An attacker who can inject or modify the `CRP-Safety-Policy` header can relax safety enforcement. Mitigations:
- `CRP-Safety-Nonce` (see CRP-SPEC-002 §5.16) binds the policy to a session nonce
- Gateway MUST validate policy syntax before accepting — malformed policies are rejected
- In multi-agent chains, the inheritance rule prevents child agents from relaxing parent policies

### 7.2 Report-URI as Exfiltration Vector

Violation reports contain session IDs, risk scores, and audit trail URIs. The `report-uri` destination MUST be trusted. Gateway SHOULD validate that `report-uri` is under the same domain as the CRP API key's registered organisation.

---

## 8. References

### Normative References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-005 — Decision Provenance Engine
- W3C Content Security Policy Level 3 (design inspiration)
- RFC 5234 — ABNF

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0 (specification text). CRP™ is a trademark of AutoCyber AI Pty Ltd.*

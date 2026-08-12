# Headers Reference

<div class="cr-hero" markdown>

## One control surface for every CRP call

CRP headers are the protocol's **governance control plane**. They carry
identity, context, provenance, safety, and audit signals between the SDK,
Gateway, Comply, and any third-party runtime. With the current SDK you rarely
need to set them by hand - `crp.SDKClient()` emits, validates, and forwards the
right headers automatically.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## Header Categories

| Category | Examples | Purpose |
|----------|----------|---------|
| Identity | `CRP-Session-Id`, `CRP-Window-Id`, `CRP-Call-Id` | Correlate requests, responses, windows |
| Context | `CRP-Envelope-Hash`, `CRP-Context-Tokens`, `CRP-CKF-Source` | Describe the envelope sent to the model |
| Continuation | `CRP-Continuation-Of`, `CRP-Window-Index`, `CRP-Deferred-Facts` | Window DAG bookkeeping |
| Provenance | `CRP-Provenance-HMAC`, `CRP-Provenance-Chain`, `CRP-Source-Map` | Cryptographic chain |
| Quality | `CRP-Quality-Tier`, `CRP-Flow-Score`, `CRP-Completeness-Ratio` | DPE output |
| Safety | `CRP-Safety-Policy`, `CRP-Safety-Verdict`, `CRP-Safety-Reason`, `CRP-Hallucination-Risk` | Safety enforcement |
| Compliance | `CRP-Compliance-EU-AI-Act`, `CRP-Compliance-ISO-42001`, `CRP-Compliance-GDPR`, `CRP-Compliance-NIST-AI-RMF` | Regulatory tagging |
| Audit | `CRP-Audit-Sink`, `CRP-Audit-Mode`, `CRP-Audit-Trail-URI` | Where evidence goes |
| Multi-agent | `CRP-Chain-Id`, `CRP-Chain-Budget`, `CRP-Chain-Step`, `CRP-Risk-Accumulator` | Multi-agent safety |
| Dispatch | `CRP-Dispatch-Strategy`, `CRP-Dispatch-Attempt`, `CRP-Retry-After-Risk` | Dispatch behaviour |

## Using headers from the SDK

The normative reference remains [SPEC-002](../spec/CRP-SPEC-002-headers.md),
submitted to the IANA HTTP Field Name Registry. In practice the SDK hides the
complexity:

```python
import crp

client = crp.SDKClient()
response = client.complete("Summarise the EU AI Act")

# The same signals are available as typed response fields:
print(response.crp.risk)       # LOW | MEDIUM | HIGH | CRITICAL
print(response.crp.grounded)   # True | False
print(response.crp.compliant)  # True | False
print(response.crp.audit_url)  # deep link into the audit trail
```

For raw infrastructure access, responses still expose `response.raw_headers`.

For the per-header normative table, see [SPEC-002 - Header Field Specification](../spec/CRP-SPEC-002-headers.md).

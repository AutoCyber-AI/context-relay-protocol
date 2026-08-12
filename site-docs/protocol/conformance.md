# Conformance Levels

<div class="cr-hero" markdown>

## Prove your implementation speaks CRP correctly

CRP conformance levels make interoperability verifiable. Whether you are
building a log shipper, a gateway, or an air-gapped sovereign deployment, the
levels tell buyers, auditors, and regulators exactly what guarantees are in
place.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

CRP defines three conformance levels in [SPEC-014](../spec/CRP-SPEC-014-conformance.md).
Implementations advertise their level in the response header
`CRP-Conformance-Level`.

<div class="cr-card" markdown>

| Level | What is required | Example implementations |
|-------|------------------|-------------------------|
| **1 - Header-Aware** | Implementation correctly emits and parses the mandatory `CRP-*` headers; produces a valid HMAC chain. | Log shipper, WAF rule set, observability tool |
| **2 - Full Interop** | Level 1 + DPE pipeline + Safety Policy enforcement + audit chain + regulatory tagging. | CRP reference implementation, CRP Gateway |
| **3 - Sovereign** | Level 2 + Zero-CKF mode + offline operation + sovereign audit sink + signed conformance attestation. | Air-gapped enterprise / government deployments |

</div>

## Test Suite

The conformance test suite is a public, vendor-neutral collection of
fixtures and expected behaviours. Any implementation can be tested
independently. The reference implementation in this repository is
**Level 2 conformant**; a Level 3 build is available for sovereign customers.

```python
import crp

client = crp.SDKClient()
client.complete("Hello, CRP.")

# Audit + compliance evidence are generated automatically:
print(client.audit.summary())
print(client.compliance.report())
```

[:octicons-arrow-right-24: SPEC-014 normative text](../spec/CRP-SPEC-014-conformance.md)
[:octicons-arrow-right-24: Run the conformance suite](../testing/running-tests.md)

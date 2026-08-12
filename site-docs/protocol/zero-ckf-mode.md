# Zero-CKF Mode & Progressive Activation

<div class="cr-hero" markdown>

## Governance that works before you ingest a single document

CRP delivers value the moment you import `crp`. Even with no pre-ingested
Contextual Knowledge Fabric - the "Zero-CKF" condition - safety, audit, and
provenance enforcement are already active. As you feed documents, quality and
attribution layers activate automatically.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## Why This Matters

A common objection - *"CRP needs domain documents to be useful"* - is wrong.
With no documents the protocol still delivers:

- Hallucination risk scoring (intrinsic claims only)
- Distortion detection
- Cross-window contradiction detection
- Repetition detection
- Completeness verification
- Flow analysis
- Full Safety Policy enforcement
- Full HMAC audit chain
- Full regulatory tagging

What it *cannot* deliver in Zero-CKF mode is **external attribution**  - 
binding a claim to a specific source document - because there are no source
documents.

## Progressive Activation

As you ingest documents, additional DPE capabilities activate automatically:

<div class="cr-stats" markdown>
<div class="cr-stat"><span class="num">0</span><span class="label">facts - Safety-only mode</span></div>
<div class="cr-stat"><span class="num">100+</span><span class="label">facts - Entailment scoring</span></div>
<div class="cr-stat"><span class="num">1k+</span><span class="label">facts - External attribution; tier A</span></div>
<div class="cr-stat"><span class="num">10k+</span><span class="label">facts - Cross-document contradiction; tier S</span></div>
</div>

## From the SDK

```python
import crp

client = crp.SDKClient()

# Zero-CKF governance works immediately.
r = client.complete("What is the EU AI Act?")
print(r.crp.risk, r.crp.grounded, r.crp.compliant)

# Ingest to unlock attribution and higher quality tiers.
client.ingest("./docs/")
a = client.ask("How does the EU AI Act affect our product?", depth="standard")
print(a.quality, a.sources)
```

## Implications

- You can deploy CRP today with zero domain documents and still get governance.
- The protocol degrades gracefully, never silently.
- The site, the spec, and the CRP Gateway all advertise the current mode in
  `CRP-CKF-State` so callers can reason about what they will and will not get.

[:octicons-arrow-right-24: SPEC-017 normative text](../spec/CRP-SPEC-017-zero-ckf-mode.md)

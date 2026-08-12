---
seo_title: "CRP Products — Gateway, Comply, Scan, Visualise & Scribe"
description: "Overview of CRP products: Gateway runtime, Comply evidence platform, Scan code scanner, Visualise, and Scribe."
---

# Products

<div class="hero-splash hero-splash--dark" markdown>

<div class="hero-kicker">🎯 The Agentic Positioning Layer for SLM-first AI</div>

<h2 class="hero-headline" markdown>
Five Products. One Agentic Positioning Engine.
</h2>

<p class="hero-sub">
The CRP ecosystem positions every agent on the right task, with the right context and tools,
then produces signed, tamper-evident proof that your safety, grounding, and policy controls
operated. EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, or SOC 2-for-AI: the same runtime data
becomes audit-ready evidence.
</p>

<div class="hero-buttons">
<a href="/control-evidence/" class="md-button md-button--primary">See Control-Evidence Mapping</a>
<a href="/getting-started/quickstart/" class="md-button">Start Free</a>
</div>

</div>

**Context Relay Protocol™** powers production-ready products built on top of the
core protocol. Every product leverages CRP's 6-stage extraction, HMAC audit trail,
and continuation engine — giving you capabilities that no other framework provides.

CRP Gateway and CRP Comply are **on the managed-cloud waitlist**. All products can also be self-hosted. White-label and OEM deployments are available for Enterprise.

---

<div class="product-grid" markdown>

<div class="product-card" markdown>

### CRP Gateway

<span class="product-badge badge-live">Managed-cloud waitlist</span>

**The AI Safety Firewall — govern every LLM call with one `base_url` change.**

A drop-in HTTPS endpoint that adds the Decision Provenance Engine, Safety Policy enforcement, automatic continuation, and HMAC audit emission to any OpenAI-compatible LLM call. Non-bypassable safety for every service that points its LLM client at the gateway.

- **Best for:** Teams that want safety, continuation, and audit on every LLM call without rebuilding their app.
- **Key outcome:** Every call returns risk, grounding, and provenance; long tasks finish instead of truncating.
- DPE pipeline ([SPEC-005](../spec/CRP-SPEC-005-dpe.md)) on every response
- `CRP-Safety-Policy` enforcement at the transport layer
- Audit chain emission into CRP Comply automatically
- AIUC-1: Security, Safety, Reliability controls
- Managed, self-hosted, sidecar, or edge deployment
- **Level 2 conformant** ([SPEC-014](../spec/CRP-SPEC-014-conformance.md))
- **Developer $29/mo · Team $199/mo**

[Learn more →](gateway.md){ .md-button .md-button--primary }
[Learn More →](gateway.md){ .md-button }

</div>

<div class="product-card" markdown>

### CRP Comply

<span class="product-badge badge-live">Managed-cloud waitlist</span>

**The Compliance Automation Engine — turn runtime evidence into regulator-ready compliance.**

A compliance gateway + dashboard that routes every LLM call through 13+ CRP security subsystems and generates EU AI Act, ISO 42001, GDPR, and AIUC-1 evidence packs from your actual system behaviour — not consultant PDFs.

- **Best for:** Organisations facing EU AI Act, ISO 42001, GDPR, or AIUC-1 deadlines that need audit-ready evidence.
- **Key outcome:** DPIAs, technical docs, and conformity packs generated in seconds from cryptographic audit trails.
- OpenAI-compatible proxy with PII scanning & injection detection
- HMAC-signed tamper-evident audit trail (7 regulatory frameworks)
- GDPR Art. 17 erasure, Art. 30 processing records, consent management
- AIUC-1: Accountability, Society, Data & Privacy controls
- One-click evidence packs for regulators
- **Free · Starter $49/mo · Scale $499/mo · Enterprise**

[Learn More →](comply.md){ .md-button .md-button--primary }

</div>

<div class="product-card" markdown>

### CRP Scan

<span class="product-badge badge-available">Available</span>

**The Pre-Production Security Scanner — catch ungoverned AI calls before they reach production.**

Add one workflow step and every pull request is checked for AI-system patterns that need CRP coverage: unaudited LLM calls, missing safety policies, ungoverned context construction, and regulatory mapping gaps. Free for public repos.

- **Best for:** Engineering teams that want governance gaps caught in CI, not during an audit.
- **Key outcome:** HIGH/CRITICAL findings are blocked before merge; auto-remediation PRs fix routing and policy stubs.
- Catches HIGH/CRITICAL governance gaps in PRs
- SARIF upload to GitHub code scanning
- Auto-remediation PRs with Gateway routing + policy stubs
- AIUC-1: Security, Accountability controls
- Specified in [SPEC-013](../spec/CRP-SPEC-013-github-action.md)

[Learn More →](scan.md){ .md-button .md-button--primary }

</div>

<div class="product-card" markdown>

### CRP Scribe

<span class="product-badge badge-coming">Roadmap</span>

**Unlimited Long-Form Document & Book Generation**

A generation engine that uses 28+ CRP subsystems to produce complete multi-chapter documents without hitting the LLM output wall. CRP's continuation engine, knowledge graph, voice profiling, and 6-stage extraction pipeline carry context across chapters - producing 50K+ word documents that are coherent from start to finish.

- 5 built-in templates (whitepaper, manual, guide, report, book)
- Per-chapter quality scoring (S/A/B/C/D tiers)
- Works with OpenAI, Anthropic, Ollama, LM Studio

[Learn More →](scribe.md){ .md-button }

</div>

<div class="product-card" markdown>

### CRP Visualise

<span class="product-badge badge-coming">Roadmap</span>

**Live Session Tracing for Auditors**

Renders the Window DAG, DPE verdicts, claim provenance, hallucination heat-maps, and Safety Policy evaluations for any CRP session - in real time, in the browser. Sealed read-only mode for external auditors and regulators.

- Window DAG explorer + continuation timeline
- Claim-to-fact provenance with click-through
- Safety Policy evaluation trail
- HMAC chain integrity verification

[Learn More →](visualise.md){ .md-button }

</div>

</div>

---

## Compare at a glance

| Product | What it does | Best for | Starting price |
|---------|--------------|----------|----------------|
| **CRP Gateway** | OpenAI-compatible proxy with DPE, safety policy, continuation, and audit | Teams adding governance to every LLM call | **$29/mo** Developer |
| **CRP Comply** | Compliance dashboard + evidence pack generator from runtime audit data | Organisations facing EU AI Act / ISO 42001 / GDPR deadlines | **Free** (100 calls/mo) |
| **CRP Scan** | GitHub Action + CLI scanner for ungoverned AI calls and remediation PRs | Teams that want CI governance gates | **Free** for public repos |
| **CRP Visualise** | Live session DAG, provenance, and risk browser *(roadmap)* | Auditors and incident responders | Roadmap / waitlist |
| **CRP Scribe** | Long-form document & book generation engine *(roadmap)* | Authors, analysts, and report teams | Roadmap / waitlist |

[:octicons-arrow-right-24: View full pricing](../pricing.md)

---

## One SDK for every product

All products are reachable through the same [CRP Python SDK](../guides/sdk.md):

```python
import crp

client = crp.SDKClient(provider="openai", model="gpt-4o")
client.ingest("./docs/")
answer = client.ask("Write a compliance report", depth="thorough")

print(answer.text)
print(answer.quality)   # S/A/B/C/D
print(answer.sources)   # cited facts
print(answer.crp.risk)  # LOW/MEDIUM/HIGH/CRITICAL
```

---

## Coming Soon

<div class="product-grid" markdown>

<div class="product-card" markdown>

### CRP Tutor

<span class="product-badge badge-coming">Roadmap</span>

**Adaptive Learning & Training Platform**

Multi-stage training programs with knowledge assessment, gap analysis,
and personalized learning paths - all backed by CRP's knowledge fabric.

</div>

<div class="product-card" markdown>

### CRP Analyst

<span class="product-badge badge-coming">Roadmap</span>

**Strategic Analysis Engine**

Cross-document analysis, trend identification, and insight extraction
across large document corpora with full provenance tracking.

</div>

<div class="product-card" markdown>

### CRP Code

<span class="product-badge badge-coming">Roadmap</span>

**Context-Aware Code Generation**

Multi-file code generation with architecture awareness, test scaffolding,
and documentation - maintaining coherence across arbitrarily large codebases.

</div>

</div>

---

## All Products Include

| Feature | Description |
|---------|-------------|
| **CRP Core** | 9 dispatch strategies, 6-stage extraction, continuation engine |
| **HMAC Audit Trail** | Cryptographically signed session evidence |
| **Quality Assessment** | S/A/B/C/D tiers with 4-signal completion detection |
| **Provider Agnostic** | OpenAI, Anthropic, Ollama, LM Studio - your choice |
| **Elastic License 2.0** | Free for your applications, protected from service theft |

---

## Contact

<div class="grid cards" markdown>

-   **General Enquiries**

    ---

    [info@crprotocol.io](mailto:info@crprotocol.io)

-   **Enterprise & Licensing**

    ---

    [contact@crprotocol.io](mailto:contact@crprotocol.io)

</div>

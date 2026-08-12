---
seo_title: Who CRP Is For — Developers, Enterprises, Compliance & Security Teams
description: CRP is built for developers, enterprises, security teams, compliance officers, and AI product teams that need governed LLM systems.
---

# Who CRP Is For

Context Relay Protocol is built for teams that ship AI in production and need it to be **coherent, governed, and compliant** - without rebuilding infrastructure from scratch.

---

## Developers & Engineering Teams

**The problem:** You want to add context management and safety governance to your AI features, but building it yourself takes quarters.

**CRP gives you:**

- **One-line integration:** Change `base_url` to `https://gateway.crprotocol.io/v1`
- **Progressive SDK:** Start with zero concepts, unlock depth, tools, and knowledge control when you need them
- **Local-first:** Runs on Ollama / LM Studio at $0 marginal cost
- **Multi-provider:** OpenAI, Anthropic, Gemini, Bedrock, local - same interface

### What changes in 30 days

- **Week 1:** Drop-in governance via `base_url` or `crp.SDKClient()` - no app rewrite.
- **Week 2:** Long-running tasks finish instead of truncating; quality scores replace guesswork.
- **Week 3:** Safety Policy blocks HIGH/CRITICAL issues in CI before they reach production.
- **Week 4:** Audit trail is queryable; compliance evidence is already generated from real calls.

```python
import crp

client = crp.SDKClient()
client.ingest("./docs/")
answer = client.ask("Write a deployment guide", depth="thorough")

print(answer.text)
print(answer.quality)   # S | A | B | C | D
print(answer.sources)   # cited facts from your documents
print(answer.crp.risk)  # LOW | MEDIUM | HIGH | CRITICAL
```

[:octicons-arrow-right-24: SDK Guide](guides/sdk.md)

---

## Enterprises & Regulated Companies

**The problem:** EU AI Act fines are up to €35M or 7% of global turnover. You need audit-ready evidence, not consultant PDFs.

**CRP gives you:**

- **AIUC-1 aligned** - 80%+ of AIUC-1 requirements covered out of the box, with a roadmap to accredited certification
- **EU AI Act Art. 6–17 coverage** - risk classification, technical documentation, record-keeping, transparency, human oversight, accuracy
- **ISO 42001:2023 alignment** - A.6.2.3–A.6.2.8 controls
- **Tamper-evident audit chain** - HMAC-SHA256, per-window, never updated in place
- **Evidence packs** - one-click regulator-ready bundles
- **SSO / SAML, data residency, private cloud**

### What changes in 30 days

- **Week 1:** EU AI Act risk classifier labels every deployed AI system.
- **Week 2:** DPIA, technical docs, and transparency declarations are generated from runtime evidence.
- **Week 3:** Auditor receives a tamper-evident evidence pack instead of static PDFs.
- **Week 4:** Data residency and SSO policies are enforced across all governed calls.

[:octicons-arrow-right-24: CRP Comply](products/comply.md)

---

## CISOs & Compliance Officers

**The problem:** You can't prove your AI system is safe because there's no runtime evidence.

**CRP gives you:**

- **Real-time risk scoring** on every call - LOW / MEDIUM / HIGH / CRITICAL
- **Control evidence** - HMAC-signed proof of every safety and governance decision for EU AI Act, AIUC-1, ISO 42001, NIST, and SOC 2-for-AI
- **AIUC-1 mapped controls** - adversarial robustness, filtering, harmful-output prevention, and audit
- **Hallucination detection** - 13-stage DPE pipeline
- **PII scanning** - 7 categories, hashed never stored raw
- **Safety Policy enforcement** - configurable halt levels
- **Compliance dashboard** - live view of every governed call

### What changes in 30 days

- **Week 1:** Every LLM call returns a risk score and grounding signal.
- **Week 2:** HIGH/CRITICAL outputs are halted or checkpointed automatically.
- **Week 3:** PII and prompt-injection attempts are flagged before leaving the Gateway.
- **Week 4:** Incident response time drops from days to minutes with session reconstruction.

[:octicons-arrow-right-24: The Safety Case](safety/index.md)

---

## Startups & Indie Builders

**The problem:** You need AI governance but can't afford enterprise tools or dedicated compliance staff.

**CRP gives you:**

- **Free tier:** 100 governed calls/mo, no card required
- **Starter:** $49/mo ($490/yr) - 5,000 calls, checkpoint inbox, evidence packs
- **No seat-based pricing** - pay for usage, not headcount
- **One-person setup** - configure safety policy via no-code console in minutes

### What changes in 30 days

- **Week 1:** Safety, audit, and continuation work out of the box with one integration line.
- **Week 2:** Long-form outputs and agent chains become shippable instead of experimental.
- **Week 3:** Compliance evidence is ready for investor and customer security reviews.
- **Week 4:** Usage scales to Team or Scale tiers without re-architecting governance.

[:octicons-arrow-right-24: Pricing](pricing.md)

---

## AI Product Managers

**The problem:** You are shipping governed AI features slowly because safety, compliance, and quality reviews happen late in the cycle.

**CRP gives you:**

- **Faster launches** - safety and provenance are built in from the first call, not bolted on before release
- **Built-in safety** - 13-stage DPE scoring, safety profiles, and human checkpoints reduce late-stage risk surprises
- **Compliance evidence** - EU AI Act, ISO 42001, and GDPR artifacts generated from runtime data
- **Clear quality metrics** - `answer.quality`, `answer.complete`, `answer.crp.risk`, and source attribution give stakeholders an objective signal

### What changes in 30 days

- **Week 1:** Define a safety policy that follows the feature into every environment.
- **Week 2:** Replace "we think it works" with S/A/B/C/D quality tiers on every output.
- **Week 3:** Compliance, legal, and security review cycles shrink from weeks to days.
- **Week 4:** Ship the feature with regulator-ready evidence and a tamper-evident audit trail.

[:octicons-arrow-right-24: SDK Guide](guides/sdk.md)

---

## AI Researchers & Data Scientists

**The problem:** You need to compare context strategies and reproduce results.

**CRP gives you:**

- **Built-in benchmarking** - compare CRP vs RAG vs Injection vs Hierarchical
- **SQB harness** - Semantic Quality Benchmark with per-window metrics
- **Reproducible pipelines** - every run is HMAC-signed and auditable
- **Local models** - test on Ollama, LM Studio, vLLM without API costs

[:octicons-arrow-right-24: Benchmarks](testing/benchmarks.md)

---

## Open Source & Standards Contributors

**The problem:** You want an open, vendor-neutral protocol for AI context and safety.

**CRP gives you:**

- **Open specification** - 50 specs, CC BY 4.0
- **Submitted to IETF, IANA, IEEE SA, ISO/IEC JTC 1/SC 42**
- **Reference implementation** - Elastic License 2.0
- **Conformance suite** - test your implementation against the protocol

[:octicons-arrow-right-24: Read the Spec](spec/index.md)

---

## Concrete use cases

<div class="pain-grid" markdown>
<div class="pain-card">
<h4>Long-form report generation</h4>
<p>Continuation engine + voice profile + document map + re-grounding.<br/><strong>Outcome:</strong> 30-section reports completed with a conclusion instead of truncating at section 8.</p>
</div>
<div class="pain-card">
<h4>Penetration testing workflows</h4>
<p>Each recon/tool-select/analysis/report step gets a fresh, fact-packed window.<br/><strong>Outcome:</strong> Tool outputs become persistent, ranked findings; final report carries all discoveries.</p>
</div>
<div class="pain-card">
<h4>Legal / contract analysis</h4>
<p>Auto-ingests million-token documents; CKF links clauses across pages.<br/><strong>Outcome:</strong> Cross-reference questions answered with source attribution.</p>
</div>
<div class="pain-card">
<h4>Medical literature review</h4>
<p>Cross-session CKF accumulates papers; community detection groups related findings.<br/><strong>Outcome:</strong> Synthesized evidence with provenance back to each paper.</p>
</div>
<div class="pain-card">
<h4>Customer-support automation</h4>
<p>PII detection, GDPR consent/retention records, EU AI Act risk classification.<br/><strong>Outcome:</strong> Regulated chatbot deployment with audit-ready evidence.</p>
</div>
<div class="pain-card">
<h4>Code generation across large codebases</h4>
<p>Multi-window generation with architecture facts in each envelope.<br/><strong>Outcome:</strong> Coherent multi-file output with structural integrity.</p>
</div>
<div class="pain-card">
<h4>Small-model deployment</h4>
<p>ORC/ICML/RTL scaffolding for 2B–7B local models.<br/><strong>Outcome:</strong> Local models perform reasoning tasks normally requiring 10× larger models.</p>
</div>
<div class="pain-card">
<h4>CI/CD governance scanning</h4>
<p>CRP Scan GitHub Action flags ungoverned LLM calls and opens remediation PRs.<br/><strong>Outcome:</strong> HIGH/CRITICAL AI governance gaps caught before merge.</p>
</div>
</div>

[:octicons-arrow-right-24: See the full capabilities reference](capabilities.md)

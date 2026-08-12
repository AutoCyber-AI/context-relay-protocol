# CRP Comply

**AI Governance & EU AI Act Compliance Platform**

---

<div class="hero-banner hero-comply" markdown>
<h2>EU AI Act enforcement begins August 2, 2026</h2>
<p>Fines up to <strong>€35 million</strong> or <strong>7% of global turnover</strong>. CRP Comply generates the compliance evidence regulators require - from your actual AI system behaviour, not consultant PDFs.</p>
<a href="#quick-start" class="md-button">Get Started →</a>
</div>

---

## What CRP Comply gives you

| Traditional Compliance | CRP Comply |
|------------------------|------------|
| Hire consultants for 6 months | Generate reports in seconds |
| Static PDF documents | Live reports from real system data |
| Manual evidence gathering | One-click conformity evidence packs |
| Outdated by next quarter | Always reflects current system state |
| Disconnected from code | Built into your AI infrastructure |
| Costs $50K–$500K per system | Self-hosted or managed SaaS |

!!! success "Evidence from reality, not paperwork"
    Every report CRP Comply generates is derived from **real cryptographic audit trails**, **real risk assessments**, and **real data governance controls** that CRP enforces at the protocol level. You don't describe what your system does - CRP Comply shows what it **actually did**.

---

## Why teams choose CRP Comply

- **Audit-ready evidence in seconds.** DPIAs, technical documentation, transparency declarations, and conformity evidence packs are generated from the same HMAC-chained audit data CRP captures at runtime.
- **33/35 EU AI Act technical controls mapped.** Articles 9–17 are addressed with implementation evidence, not gap-analysis slides.
- **Seven frameworks, one dashboard.** EU AI Act, ISO 42001, GDPR, NIST AI RMF, SOC 2, HIPAA, and ISO 27001 reports share the same underlying audit trail.

### Who it's for

| Role | Problem | How Comply helps |
|------|---------|------------------|
| **Compliance Officer** | EU AI Act deadline with no evidence | One-click evidence packs and live control status |
| **DPO / Privacy Lead** | GDPR Art. 35 DPIAs take weeks | Generate DPIAs from real data governance controls |
| **CTO / Engineering Lead** | Board wants AI governance without slowing delivery | Compliance-as-code; evidence is a byproduct of normal operation |
| **Auditor** | Need to verify claims independently | Tamper-evident audit chain + session reconstruction |

---

## Product Identity

<div class="product-identity" markdown>

| | |
|---|---|
| **Product** | CRP Comply |
| **Type** | Compliance Gateway + Dashboard + Report Generator (managed-cloud waitlist; self-host and white-label available) |
| **Powered By** | Context Relay Protocol™ v5.1.0 - 50 specs, DPE, STL, TCF |
| **What We Host** | Gateway proxy, web dashboard, audit trail storage, report generation API |
| **What You Provide** | Your LLM API key (OpenAI, Anthropic, or any OpenAI-compatible endpoint) |
| **Integration** | Change **one line** - point `base_url` to CRP Comply |
| **Pricing** | **Free** (100 calls/mo) · **Starter** $49/mo ($490/yr, ~17% off) · **Scale** $499/mo ($4,990/yr, ~17% off) · **Enterprise** contact sales |
| **Deployment** | Managed SaaS at `comply.crprotocol.io` on the waitlist; self-host and white-label available |
| **GitHub App** | Connect repos for automated scan + remediation PRs |
| **No-Code Setup** | Visual safety-policy builder, no YAML required |
| **License** | Elastic License 2.0 (ELv2) |

</div>

### How It Works

```
Your Application Code
    │
    │  Change base_url to your-comply.example/v1
    ▼
┌─────────────────────────────────────────────────┐
│              CRP Comply (We Host)               │
│                                                 │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ Compliance   │  │ 13+ CRP Security         │  │
│  │ Proxy        │──│ Subsystems:              │  │
│  │ (OpenAI-     │  │  • PII Scanner           │  │
│  │  compatible) │  │  • Injection Detector    │  │
│  └──────┬───────┘  │  • Risk Classifier       │  │
│         │          │  • Audit Trail (HMAC)    │  │
│  ┌──────┴───────┐  │  • Consent Manager       │  │
│  │ Dashboard    │  │  • Retention Manager     │  │
│  │ • Audit logs │  │  • Data Lineage          │  │
│  │ • Reports    │  │  • Erasure Manager       │  │
│  │ • DPIA       │  │  • Provenance Engine     │  │
│  │ • Evidence   │  │  • Quality Grading       │  │
│  └──────────────┘  └──────────────────────────┘  │
│                                                 │
└──────────────────────┬──────────────────────────┘
                       │  Forwards to your LLM
                       ▼
              Your LLM Provider
              (OpenAI / Anthropic / Ollama / etc.)
```

---

## What It Covers

### 7 Regulatory Frameworks

| Framework | Coverage | Status |
|-----------|---------|--------|
| **EU AI Act** (2024/1689) | Art. 5–17 - all high-risk requirements | ✅ 8/8 controls implemented |
| **ISO/IEC 42001:2023** | A.6.2.3–A.6.2.8, §9.1, §10.1 | ✅ 8/8 controls implemented |
| **GDPR** | Art. 7, 17, 30, 35 | ✅ Consent, erasure, records, DPIA |
| **SOC 2** | CC7.2, CC7.3 | ✅ Monitoring + anomaly detection |
| **HIPAA** | §164.312(b) | ✅ Tamper-resistant audit controls |
| **ISO 27001** | A.12.4 | ✅ Logging and monitoring |
| **NIST AI RMF** | GOVERN, MAP, MEASURE, MANAGE | ✅ All core functions |

### EU AI Act - Article-by-Article

| Article | What Regulators Require | What CRP Comply Generates |
|---------|------------------------|--------------------------|
| **Art. 6** | Risk classification | Multi-factor assessment across 12 AI system categories → MINIMAL / LIMITED / HIGH / UNACCEPTABLE |
| **Art. 9** | Risk management system | Continuous monitoring via session-level audit trails with 8-layer defence-in-depth |
| **Art. 10** | Data governance | 5-level data classification, PII detection, lineage tracking, retention policies, erasure support |
| **Art. 11** | Technical documentation | Auto-generated structured documentation covering architecture, security, data governance, oversight |
| **Art. 12** | Record-keeping | HMAC-SHA256 tamper-evident audit trail - 30+ event types, chain integrity verification |
| **Art. 13** | Transparency | Machine-readable declaration: AI involvement, data processed, limitations, oversight provisions |
| **Art. 14** | Human oversight | 4 configurable levels (NONE → INFORMED → APPROVAL → CONTROL) with halt-on-detection |
| **Art. 15** | Accuracy, robustness, cybersecurity | AES-256-GCM, BLAKE3 integrity chains, 3-tier RBAC, injection detection, anti-poisoning |
| **Art. 17** | Quality management | Tier grading (S/A/B/C/D), overhead tracking, resource metrics, envelope saturation |

---

## Features

### 8 Compliance Generators

<div class="grid cards" markdown>

-   **Risk Assessment**

    ---

    EU AI Act Art. 6 classification. Evaluates system category, data sensitivity, decision automation, fundamental rights impact, and safety criticality.

    [:octicons-arrow-right-24: Try it](#risk-assessment)

-   **Compliance Report**

    ---

    Per-control implementation status across EU AI Act and ISO 42001. Compliance score with implementation evidence for every control.

    [:octicons-arrow-right-24: Generate](#compliance-report)

-   **DPIA Generator**

    ---

    Full GDPR Art. 35 Data Protection Impact Assessment with risk categories, CRP-native mitigations, and residual risk analysis.

    [:octicons-arrow-right-24: Generate DPIA](#dpia)

-   **Transparency Declaration**

    ---

    Art. 13 machine-readable document covering AI involvement, data practices, system limitations, and oversight provisions.

    [:octicons-arrow-right-24: Generate](#transparency)

-   **Technical Documentation**

    ---

    Art. 11 structured documentation for national competent authorities - architecture, data governance, security, human oversight.

    [:octicons-arrow-right-24: Generate](#technical-docs)

-   **Session Audit**

    ---

    Per-session compliance analysis: audit trail integrity, PII detections, injection attempts, quality scores, findings, recommendations.

    [:octicons-arrow-right-24: Audit session](#session-audit)

-   **Conformity Evidence Pack**

    ---

    All compliance artifacts in a single export. Hand this to a regulator or auditor - risk assessment, compliance report, DPIA, technical docs, transparency declaration, and session audit.

    [:octicons-arrow-right-24: Generate pack](#evidence-pack)

-   **Signed Certificate** *(Cloud)*

    ---

    Digitally signed compliance certificate from AutoCyber AI. Verifiable online at `crprotocol.io/verify/`. Covers EU AI Act, ISO 42001, and GDPR Art. 35.

    [:octicons-arrow-right-24: Learn about Cloud](#cloud-tier)

</div>

<span id="risk-assessment"></span>
<span id="compliance-report"></span>
<span id="dpia"></span>
<span id="transparency"></span>
<span id="technical-docs"></span>
<span id="session-audit"></span>
<span id="evidence-pack"></span>

### Web Dashboard

A full-featured web dashboard with pages for:

- **Dashboard** - real-time compliance overview
- **Risk Assessment** - interactive risk classification wizard
- **Compliance Report** - control-by-control status with evidence
- **DPIA** - guided Data Protection Impact Assessment
- **Transparency** - auto-generated Art. 13 declarations
- **Technical Docs** - one-click Art. 11 documentation
- **Session Audit** - upload and analyse CRP session files
- **Evidence Pack** - generate regulator-ready bundles
- **Settings** - API key management, tier configuration

### REST API

14 endpoints at `/api/v1/` with interactive OpenAPI docs at `/api/docs`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health and version |
| POST | `/risk-assessment` | EU AI Act risk classification |
| POST | `/compliance-report` | Multi-framework compliance status |
| POST | `/compliance-report/markdown` | Compliance report as Markdown |
| POST | `/dpia` | GDPR Art. 35 DPIA |
| POST | `/transparency` | Art. 13 transparency declaration |
| POST | `/technical-docs` | Art. 11 technical documentation |
| POST | `/audit` | Session file compliance audit |
| POST | `/evidence-pack` | Complete conformity evidence |
| POST | `/full-report` | Full Markdown compliance report |
| POST | `/certificate` | Digitally signed certificate *(Cloud)* |
| POST | `/keys` | Create API key |
| GET | `/keys` | List API keys |
| DELETE | `/keys/{id}` | Revoke API key |

---

## Pricing

<div class="grid cards" markdown>

-   **Free**

    ---

    - 100 proxy requests/mo
    - 2 frameworks (EU AI Act, GDPR)
    - Risk Assessment (Art. 6)
    - Basic Compliance Report
    - PII scanning (7 categories)
    - Injection detection (21 patterns)
    - 7-day audit retention

    **$0/mo** - [Join waitlist →](mailto:info@crprotocol.io)

-   **Starter**

    ---

    Everything in Free, plus:

    - 5,000 proxy requests/mo
    - All 7 regulatory frameworks
    - DPIA Generator (GDPR Art. 35)
    - Transparency Declaration (Art. 13)
    - Technical Documentation (Art. 11)
    - Session Audit (Art. 12)
    - Conformity Evidence Pack
    - Right to Erasure (GDPR Art. 17)
    - Data classification
    - Chain verification
    - 90-day audit retention
    - Email support

    **$49/mo** ($490/yr) - [Join waitlist →](mailto:info@crprotocol.io)

-   **Scale**

    ---

    Everything in Starter, plus:

    - 50,000 proxy requests/mo
    - SSO / SAML
    - Data residency controls
    - Custom safety rules
    - Hosted LLM option
    - CRP-amplified compliance analyst
    - Session audit with HMAC chain verification
    - Hallucination risk scoring (DPE)
    - Risk classification (EU AI Act Art. 6)
    - GDPR Art. 30 processing records
    - Data classification (5 levels)
    - Custom compliance frameworks
    - Priority email + chat support + 99.9% SLA
    - Unlimited seats

    **$499/mo** ($4,990/yr) - [Join waitlist →](mailto:info@crprotocol.io)

-   **Enterprise**

    ---

    Everything in Scale, plus:

    - Unlimited proxy requests
    - **Digitally signed certificates**
    - Dedicated cloud or on-prem deployment
    - Private LLM routing (air-gapped capable)
    - GDPR Art. 17 erasure request tracking + audit chain
    - Retention policy enforcement
    - Regulatory export (JSON/CSV) + automated delivery
    - Dedicated compliance officer
    - On-call incident response
    - 7-year audit retention
    - Custom integrations
    - Signed DPA, ISO 27001 audit pack
    - 99.95% uptime SLA

    **Custom** - [Contact Sales →](mailto:sales@crprotocol.io)

</div>

<span id="cloud-tier"></span>
### Cloud Tier - Official & Trusted

The **Cloud** tier is the officially hosted, AutoCyber AI-managed deployment. It delivers what self-hosted tiers cannot:

| Capability | Detail |
|-----------|--------|
| **Signed Certificates** | HMAC-SHA256 digitally signed compliance certificates verifiable at `crprotocol.io/verify/{id}` |
| **Always Current** | Regulatory changes (delegated acts, technical standards) reflected automatically |
| **Audit-Ready Infra** | SOC 2 / ISO 27001 aligned infrastructure - your auditor doesn't need to assess your servers |
| **Data Residency** | Choose hosting region: Australia, EU, or US |
| **SLA-Backed** | 99.9% uptime guarantee with credit-backed remedies |
| **CRP Certified Badge** | Display trusted certification on your products and marketing |
| **Priority Support** | Direct access to the CRP compliance engineering team |

---

<span id="quick-start"></span>
## Quick Start

### 1. Join the waitlist

Managed SaaS sign-up is on the waitlist at [comply.crprotocol.io](mailto:info@crprotocol.io). Self-hosted deployment is available for Enterprise.

### 2. Connect Your LLM

In the dashboard, go to **Setup** and enter your LLM provider credentials:

- **OpenAI** - API key (`sk-...`)
- **Anthropic** - API key (`sk-ant-...`)
- **Custom** - Any OpenAI-compatible endpoint (Ollama, vLLM, LM Studio, etc.)

Your API key is encrypted at rest with AES-256-GCM and is only used to forward requests to your chosen provider.

### 3. Change One Line of Code

Point your existing OpenAI client at CRP Comply - that's it:

```python
# Before - direct to OpenAI
import openai
client = openai.OpenAI(api_key="sk-...")

# After - route through CRP Comply proxy
client = openai.OpenAI(
    api_key="sk-...",
    base_url="https://your-comply.example/v1",
    default_headers={"X-API-Key": "crc_your_comply_key"},
)

# Same API - now with full compliance coverage
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Analyse this contract..."}],
)
# Response includes X-CRP-Comply-Record-ID header for audit trail
```

Every request flows through CRP security subsystems automatically when routed through a CRP Gateway or Comply runtime.

### 4. Use the Dashboard

Access audit trails, compliance reports, DPIAs, evidence packs, and real-time compliance metrics - all from your browser at [comply.crprotocol.io](mailto:info@crprotocol.io) (managed-cloud waitlist).

### 5. REST API

When self-hosting, access the interactive API docs at your Comply URL (`/api/docs`). Managed SaaS docs are available at `comply.crprotocol.io/api/docs`.

---

## SDK compliance helpers

If you're using the [CRP Python SDK](../guides/sdk.md), compliance evidence is available directly from code:

```python
import crp

client = crp.SDKClient()

# EU AI Act Art. 6 risk classification
risk = client.compliance.classify(
    intended_purpose="Automated contract review",
    processes_personal_data=True,
    makes_automated_decisions=False,
)
print(risk["level"])  # MINIMAL | LIMITED | HIGH | UNACCEPTABLE

# Per-session compliance status
report = client.compliance.report()
print(report["score"], report["frameworks"])

# Tamper-evident audit summary
print(client.audit.summary())      # entry count + chain verified
valid, broken_at = client.audit.verify()
assert valid

# Export the full audit trail for CRP Comply
bundle = client.audit.export(include_signatures=True)
```

These helpers use the same security subsystems as CRP Comply, so the evidence you generate in code is exactly what the dashboard displays.

---

## CLI Tool

CRP Comply includes a command-line interface for offline compliance operations:

```bash
# Start the CRP Comply server locally
crp-comply serve --port 8400

# Generate EU AI Act + ISO 42001 compliance report
crp-comply report --format markdown

# Run EU AI Act Art. 6 risk assessment
crp-comply risk-assess --category healthcare --personal-data --json

# Generate GDPR Art. 35 DPIA
crp-comply dpia --system-name "Patient Triage AI" --format markdown

# Generate EU AI Act Art. 13 transparency declaration
crp-comply transparency

# Generate Art. 11 technical documentation
crp-comply technical-docs --category healthcare

# Audit a persisted CRP session file
crp-comply audit /path/to/session.json --format markdown

# Generate complete conformity evidence pack for regulators
crp-comply evidence-pack --system-name "My AI System" --output evidence.json
```

---

## Security

| Control | Implementation |
|---------|---------------|
| Authentication | API keys (SHA-256 hashed) + JWT tokens |
| Encryption | AES-256-GCM at rest, HMAC-SHA256 binding |
| Path safety | Session file access restricted to allow-listed directories |
| Input validation | All requests validated via Pydantic schemas |
| Docker | Non-root `comply` user, health checks |
| Secrets | JWT secret via env variable, never committed |

---

## Who Is This For?

| Role | Problem | Solution |
|------|---------|---------|
| **AI Engineer** | Building LLM apps, no time for compliance | Drop-in compliance - every CRP session is already audit-ready |
| **Compliance Officer** | EU AI Act deadline approaching, need evidence | One-click evidence packs, live compliance scoring |
| **CTO** | Board wants AI governance, you want to ship | Compliance-as-code - zero manual processes |
| **Auditor** | Need to verify AI system compliance | Tamper-evident audit trails, session reconstruction |
| **Regulator** | Need standardised AI documentation | Art. 11 tech docs, Art. 13 transparency, Art. 6 risk classification |

---

## Contact

<div class="grid cards" markdown>

-   **General Enquiries**

    ---

    [info@crprotocol.io](mailto:info@crprotocol.io)

-   **Enterprise & Licensing**

    ---

    [contact@crprotocol.io](mailto:contact@crprotocol.io)

-   **Security**

    ---

    [security@autocyberai.com](mailto:security@autocyberai.com)

</div>

---

## Get started

Start self-hosting CRP Comply today, or view pricing for Starter, Scale, and Enterprise tiers.

[View Pricing →](../pricing.md){ .md-button .md-button--primary }
[SDK Guide →](../guides/sdk.md){ .md-button }
[Self-hosting →](../guides/gateway-railway.md){ .md-button }

---

*CRP Comply is a product of AutoCyber AI Pty Ltd (ABN 22 697 087 166). Built on the [Context Relay Protocol](https://crprotocol.io). "Context Relay Protocol" is a trademark of Constantinos Vidiniotis (application pending, IP Australia Class 9).*

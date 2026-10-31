# EU AI Act

> Deploy high-risk AI systems under the EU AI Act with evidence-backed technical controls.
> CRP maps every session to the regulation's requirements and produces audit-ready risk
> classification, human-oversight checkpoints, transparency reports, and integrity evidence
> from the same SDK calls you already use.

!!! info "Availability"
    The CRP SDK and CRP Comply are available for self-hosting today.
    The managed SaaS console is on the waitlist at
    [comply.crprotocol.io](mailto:info@crprotocol.io).

## Business value

- **Reduce audit preparation** - export technical evidence directly from `client.audit.export()`.
- **Understand penalty exposure** - prohibited-practice violations can cost up to **€35 million or 7%** of global turnover; most high-risk violations up to **€15 million or 3%**.
- **Defensible risk classification** - reproducible classification with rationale and mapped controls.
- **Single integration** - compliance is a by-product of normal `client.complete()` / `client.ask()` usage.

## Risk Classification (Article 6)

CRP includes a built-in risk classifier aligned with the EU AI Act's risk categories:

| Risk Level       | EU AI Act Category              | CRP Response                         |
|------------------|----------------------------------|--------------------------------------|
| **Unacceptable** | Art. 5 - Prohibited practices    | Blocks deployment                    |
| **High**         | Art. 6 - Annex III systems       | Full compliance suite                |
| **Limited**      | Art. 50 - Transparency obligations | Transparency declarations           |
| **Minimal**      | Remaining systems                | Standard operation                   |

```python
import crp

client = crp.SDKClient()
client.configure(safety_profile="strict")

assessment = client.compliance.classify(
    framework="eu-ai-act",
    category="employment",
    purpose="Resume screening for job applications",
    personal_data=True,
    automated_decisions=True,
    fundamental_rights=True,
    safety_critical=False,
    profiling=True,
)
print(f"Risk level:  {assessment.risk_level}")
print(f"Category:    {assessment.system_category}")
print(f"Controls:    {assessment.controls}")
print(f"Mitigations: {assessment.mitigations}")
```

## Article-by-Article Mapping

### Article 9 - Risk Management System

| Requirement                          | CRP Implementation                                                            |
|--------------------------------------|-------------------------------------------------------------------------------|
| Identify and analyze known/foreseeable risks | `client.compliance.classify(...)` with risk dimensions                |
| Estimate and evaluate risks          | Quality tier system (S/A/B/C/D) with degradation formulas                     |
| Adopt risk management measures       | Automatic mitigations per risk level; configured via `client.configure()`     |
| Testing procedures                   | 3,500+ automated tests (non-live suite), live verification                    |

### Article 10 - Data and Data Governance

| Requirement                  | CRP Implementation                                              |
|------------------------------|-----------------------------------------------------------------|
| Training data quality        | 3-tier fact validation gate                                     |
| Data governance practices    | Event-sourced fact model with full provenance                   |
| Bias examination             | Content complexity routing, multi-aspect decomposition          |
| Relevant data characteristics| Fact graph with typed relationships; inspect with `client.knowledge.health()` |

### Article 11 - Technical Documentation

| Requirement                          | CRP Implementation                          |
|--------------------------------------|---------------------------------------------|
| Detailed description of AI system    | 9 specification documents (~19,200 lines) covering the CRPv6 protocol |
| Elements of the AI system            | Full protocol specification                 |
| Monitoring and functioning           | Quality reports, telemetry, session status  |

### Article 12 - Record-Keeping

| Requirement                          | CRP Implementation                          |
|--------------------------------------|---------------------------------------------|
| Automatic recording of events        | HMAC-SHA256 chained audit trail             |
| Traceability throughout lifecycle    | Window DAG with provenance tracking         |
| Identification of input data         | Fact lineage tracking from ingest to output |
| Tamper evidence                      | BLAKE3 hashing + HMAC chain signing         |

```python
report = client.audit.summary()
print(f"Chain valid: {report.chain_valid}")
print(f"Entries:     {report.entry_count}")
```

### Article 13 - Transparency

| Requirement                          | CRP Implementation                          |
|--------------------------------------|---------------------------------------------|
| Sufficient transparency for users    | Quality tier reports, envelope preview      |
| Instructions for use                 | Comprehensive documentation + demo app      |
| Capabilities and limitations         | Honest degradation reporting per quality tier |

Transparency evidence is surfaced through `client.compliance.report()` and the governance summary returned by `client.complete()`.

### Article 14 - Human Oversight

Human oversight is implemented in the CRP orchestrator and surfaced through
`client.compliance.controls()` and `client.audit.events()`. In strict safety profiles,
high-risk flows raise approval checkpoints before execution.

```python
client.configure(safety_profile="strict")
controls = client.compliance.controls(framework="eu-ai-act", article="14")
print(controls["human_oversight"])
```

**Oversight Levels:**

| Level       | Behavior                                              |
|-------------|-------------------------------------------------------|
| `NONE`      | Fully autonomous                                      |
| `INFORMED`  | Humans notified of all operations                     |
| `APPROVAL`  | Humans must approve before dispatch                   |
| `CONTROL`   | Humans control every step                             |

### Article 15 - Accuracy, Robustness, Cybersecurity

| Requirement                          | CRP Implementation                          |
|--------------------------------------|---------------------------------------------|
| Appropriate accuracy levels          | Quality tiers with degradation formulas     |
| Robustness                           | 8-layer security architecture               |
| Cybersecurity measures               | AES-256-GCM, HMAC-SHA256, RBAC              |
| Resilient to errors                  | 3-tier fact validation, echo detection, re-grounding |

### Article 17 - Quality Management System

| Requirement                          | CRP Implementation                          |
|--------------------------------------|---------------------------------------------|
| Quality management system            | Event-sourced fact model, quality gates, quality reports |
| Documented procedures                | Specification documents + RFC process       |
| Record-keeping obligations           | Append-only event log, snapshots every 50 windows |

Generate evidence packs with:

```python
report = client.compliance.report(framework="eu-ai-act")
audit = client.audit.export(format="json", framework="eu-ai-act")
```

## Coverage Gap

CRP implements **33/35** controls. The 2 gaps are:

1. **Notified body notification** - Organizational process, not technical
2. **Post-market monitoring plan** - Requires operational deployment data

!!! note
    Both gaps are organizational/procedural - CRP provides the **technical
    infrastructure** for compliance. The organizational processes sit on top.

## EU AI Act Timeline

The high-risk application dates were amended by **Regulation (EU) 2026/1744** (the
Digital Omnibus on AI), published in the Official Journal on 24 July 2026 and in force
from 27 July 2026:

```
2024 Aug ─── EU AI Act enters into force
2025 Feb ─── Prohibited practices (Art. 5) + AI literacy (Art. 4) apply
2025 Aug ─── GPAI model obligations (Art. 51-56) apply
2026 Aug ─── Article 50 transparency obligations apply (IN FORCE)
2026 Dec ─── Art. 50(2) watermarking grace ends for pre-existing systems;
             new Art. 5 bans (non-consensual intimate imagery, CSAM) apply
2027 Dec ─── ANNEX III HIGH-RISK REQUIREMENTS APPLY (stand-alone systems)
2028 Aug ─── Annex I high-risk requirements apply (AI embedded in regulated products)
```

!!! warning "Deadlines"
    - **Article 50 transparency obligations** (AI interaction disclosure, synthetic-content
      labelling) have applied since **2 August 2026** - they were *not* deferred.
    - **Annex III high-risk requirements** (Articles 6-17) apply from
      **2 December 2027**.
    - **Annex I product-embedded high-risk requirements** apply from **2 August 2028**.
    - Penalties: up to **€35 million or 7%** of global annual turnover for
      prohibited-practice violations; up to **€15 million or 3%** for most other
      violations, whichever is higher.

    The deferral is additional runway, not a reprieve: conformity assessment, technical
    documentation, and registration take quarters, not weeks.

---
seo_title: AI Compliance — EU AI Act, ISO 42001, NIST AI RMF & GDPR Evidence
description: Generate automated AI compliance evidence for EU AI Act, ISO/IEC 42001, NIST AI RMF, and GDPR with CRP's runtime audit chain and compliance headers.
tags:
  - ai-compliance
  - ai-governance
  - crp
---

# AI Compliance

**AI compliance** is the process of ensuring AI systems meet legal, regulatory, and contractual requirements. For organisations deploying LLMs, the most pressing AI compliance regimes in 2026 are the **EU AI Act**, **ISO/IEC 42001:2023**, **NIST AI Risk Management Framework**, and **GDPR**.

Context Relay Protocol (CRP) makes AI compliance continuous and evidence-based. Instead of collecting screenshots and consultant interviews before an audit, CRP generates compliance artefacts from the same runtime data that powers the AI system. CRP produces signed, tamper-evident control evidence for the EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, and SOC 2-for-AI. [See the full control-evidence mapping →](../control-evidence.md)

---

## The AI compliance challenge

Compliance teams usually work backwards from deployment:

1. Build the AI feature.
2. Hire consultants to document risks.
3. Manually map controls to frameworks.
4. Hope the documentation matches reality.

CRP reverses this. The protocol emits compliance headers on every call, maintains a tamper-evident audit chain, and exports pre-mapped evidence packs for each framework.

---

## Compliance evidence from runtime data

| Compliance artefact | Source in CRP | Typical manual effort |
|---|---|---|
| Risk classification | `CRP-Compliance-EU-AI-Act` header + system registry | Days of legal review |
| Technical documentation | Envelope packing, DPE, and safety policy records | Weeks of documentation |
| Record-keeping / audit trail | HMAC-chained window events | Spreadsheets and logs |
| Human oversight evidence | Checkpoint headers and approval records | Email chains |
| Accuracy & quality metrics | Quality tiers, grounding scores, contradiction counts | Ad-hoc testing |
| Transparency declaration | Provenance export + source attribution | Manual drafting |
| DPIA input | PII detection, data-source manifests, risk scores | Consultant interviews |

[:octicons-arrow-right-24: Compliance generators](../compliance/index.md)

---

## Framework coverage

### AIUC-1

CRP maps to AIUC-1 governance and compliance requirements across Accountability (activity
logging, AI disclosure, acceptable-use policy, accountability assignment), Society (quality
management, regulatory compliance), and Data & Privacy (input-data policy).

[:octicons-arrow-right-24: Full AIUC-1 mapping](../aiuc-1.md)

### EU AI Act

CRP addresses **33 of 35 technical controls** across EU AI Act Articles 6–17:

- Article 9 — Risk management system
- Article 10 — Data and data governance
- Article 13 — Transparency and provision of information
- Article 14 — Human oversight
- Article 15 — Accuracy, robustness, and cybersecurity
- Article 16 — Quality management system
- Article 17 — Record-keeping and logging

See the full mapping in [CRP-SPEC-010 Regulatory Controls Mapping](../spec/CRP-SPEC-010-regulatory-mapping.md).

### ISO/IEC 42001:2023

CRP features map to AI management system clauses including:

- 4. Context of the organisation
- 5. Leadership and commitment
- 6. Planning for AI risk and opportunity
- 7. Support (resources, competence, awareness)
- 8. Operation (risk treatment, AI system lifecycle)
- 9. Performance evaluation
- 10. Improvement

[:octicons-arrow-right-24: ISO 42001 alignment](../compliance/iso-42001.md)

### NIST AI Risk Management Framework

CRP supports all four NIST AI RMF functions:

| Function | CRP evidence |
|---|---|
| **GOVERN** | Policy headers, accountability identifiers, human oversight checkpoints |
| **MAP** | System registry, context-source manifests, risk classification |
| **MEASURE** | DPE scores, quality tiers, grounding percentages, contradiction counts |
| **MANAGE** | Safety budgets, circuit breakers, redaction, and response actions |

[:octicons-arrow-right-24: NIST AI RMF alignment](../compliance/nist-ai-rmf.md)

### GDPR

CRP helps with data protection by design:

- PII scanning on inputs and outputs
- Data-source manifests for Article 30 records
- DPIA-ready risk scores
- Right-of-erasure support via fact-level deletion in CKF

[:octicons-arrow-right-24: GDPR alignment](../compliance/gdpr.md)

---

## Generating a compliance report

```python
import crp

client = crp.SDKClient()
client.compliance.classify(framework="eu-ai-act")
report = client.compliance.report(framework="iso-42001")

report.save("iso-42001-evidence-pack.zip")
```

The report includes technical documentation, risk assessment, audit export, and signed provenance.

---

## Frequently asked questions about AI compliance

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is AI compliance?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "AI compliance is the process of ensuring AI systems meet legal and regulatory requirements such as the EU AI Act, ISO/IEC 42001, NIST AI RMF, and GDPR."
      }
    },
    {
      "@type": "Question",
      "name": "Does CRP generate EU AI Act evidence?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. CRP addresses 33 of 35 technical EU AI Act controls and exports risk classification, technical documentation, audit trails, and transparency declarations from runtime data."
      }
    },
    {
      "@type": "Question",
      "name": "Can CRP help with ISO 42001 certification?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP provides evidence aligned with ISO/IEC 42001:2023 clauses for AI management systems, including governance, risk treatment, lifecycle management, and continuous improvement."
      }
    }
  ]
}
</script>

### What is AI compliance?

AI compliance is the process of ensuring AI systems meet legal and regulatory requirements such as the EU AI Act, ISO/IEC 42001, NIST AI RMF, and GDPR.

### Does CRP generate EU AI Act evidence?

Yes. CRP addresses 33 of 35 technical EU AI Act controls and exports risk classification, technical documentation, audit trails, and transparency declarations from runtime data.

### Can CRP help with ISO 42001 certification?

CRP provides evidence aligned with ISO/IEC 42001:2023 clauses for AI management systems, including governance, risk treatment, lifecycle management, and continuous improvement.

---

## See also

- [Control-evidence mapping](../control-evidence.md)
- [AIUC-1 Aligned Safety & Security](../aiuc-1.md)
- [CRP Comply product](../products/comply.md)
- [EU AI Act compliance](../compliance/eu-ai-act.md)
- [ISO 42001](../compliance/iso-42001.md)
- [NIST AI RMF](../compliance/nist-ai-rmf.md)
- [GDPR](../compliance/gdpr.md)
- [AI Governance](ai-governance.md)

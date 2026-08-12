---
seo_title: AI Safety Protocol — Hallucination Detection & LLM Safety
description: Learn how CRP implements AI safety as a protocol layer with hallucination detection, fabrications, prompt injection shield, PII scanning, and safety budgets.
tags:
  - ai-safety
  - ai-governance
  - crp
---

# AI Safety Protocol

<div class="hero-splash hero-splash--dark" markdown>

<div class="hero-kicker">🎯 Agentic Positioning · Safety Built In</div>

<h2 class="hero-headline" markdown>
Adversarial-Tested AI Safety.<br/>Signed, Verifiable, On Every Call.
</h2>

<p class="hero-sub">
Your AI agents face prompt injection, jailbreak attempts, and data exfiltration attacks daily.
CRP Protocol's 13-stage DPE safety pipeline doesn't just detect these threats — it emits
HMAC-signed, tamper-evident proof that the safety control ran, what it decided, and who
authorised it. The evidence the EU AI Act, AIUC-1, ISO 42001, and NIST AI RMF all demand.
</p>

<div class="aiuc-badge-list">
<span class="aiuc-badge">AIUC-1 Security — Adversarial Robustness</span>
<span class="aiuc-badge">AIUC-1 Security — Real-time Input Filtering</span>
<span class="aiuc-badge">AIUC-1 Safety — Harmful Output Prevention</span>
</div>

<div class="hero-buttons">
<a href="/control-evidence/" class="md-button md-button--primary">See Control-Evidence Mapping</a>
<a href="/sdk/ai-safety/" class="md-button">SDK Safety Reference</a>
</div>

</div>

**AI safety** is the discipline of designing, building, and operating AI systems so they behave reliably, avoid harmful outputs, and remain under human control. For production LLMs, AI safety means detecting hallucinations, contradictions, fabrications, prompt injection, and personal-data leakage before they reach users.

Context Relay Protocol (CRP) implements AI safety at the **protocol layer** — every AI call is scored and annotated with standard HTTP headers, so safety signals are visible to applications, auditors, and downstream agents.

---

## The AI safety problem in deployed LLMs

| Risk | What happens without CRP | Business impact |
|---|---|---|
| **Hallucination** | The model invents facts, citations, or numbers | Customer trust loss, legal liability, bad decisions |
| **Contradiction** | The model contradicts itself across turns | Confusing user experience, compliance gaps |
| **Fabrication** | The model generates fake references or data | Reputational damage, regulatory sanction |
| **Prompt injection** | User or third-party input overrides system instructions | Data exfiltration, unauthorized actions |
| **PII leakage** | Personal data passes through inputs or outputs | GDPR breach, fines, privacy complaints |
| **Unbounded risk chains** | Multi-agent or multi-turn workflows accumulate risk | Catastrophic failures with no circuit breaker |

Traditional safety tools are often applied after the model responds, or require developers to instrument every call. CRP runs safety checks **inside the request/response cycle** and returns the result as machine-readable headers.

---

## How CRP enforces AI safety

### 1. Decision Provenance Engine (DPE)

The [DPE](../safety/dpe.md) is a 13-stage pipeline that runs in under 50 ms per window:

1. Claim detection
2. Attribution analysis
3. Fabrication detection
4. Distortion detection
5. Entailment checking
6. Contradiction detection
7. Repetition detection
8. Completeness scoring
9. Flow analysis
10. Hallucination-risk scoring
11. Quality tiering (S / A / B / C / D)
12. Policy evaluation
13. Provenance binding

Each stage emits standard headers such as `CRP-Safety-Hallucination-Risk`, `CRP-Safety-Fabrications`, and `CRP-Safety-Attribution`.

### 2. Safety Policy directives

Safety rules are declared as HTTP headers, not application code:

```http
CRP-Safety-Policy: halt-on CRITICAL;
                   redact-on HIGH PII;
                   require-grounding 0.80;
                   checkpoint-on HIGH
```

This makes policy enforcement **auditable, portable, and provider-agnostic**. See [Safety Policy Language](../protocol/safety-policy.md).

### 3. Safety budgets and circuit breakers

CRP tracks a per-session safety budget. Risky outputs decrement the budget; when it is exhausted, the Gateway opens a circuit and pauses the chain. This prevents runaway risk in multi-turn and multi-agent workflows.

### 4. Prompt-injection shield

CRP detects direct, indirect, goal-hijacking, exfiltration, delimiter-forgery, and embedded tool-call attacks. Detected attacks surface as `CRP-Safety-Injection-Detected` without requiring application-level filters.

---

## AI safety standards alignment

| Standard | How CRP helps |
|---|---|
| **AIUC-1** | One of CRP's strongest proof points: produces control evidence for Security (adversarial robustness, real-time input filtering), Safety (harmful-output prevention), and Reliability (hallucination prevention). [Full mapping →](../aiuc-1.md) |
| **EU AI Act** | Implements risk classification, human oversight, accuracy, and transparency controls across Articles 9–17. |
| **ISO/IEC 42001:2023** | Provides evidence for AI system impact assessment, risk treatment, and monitoring clauses. |
| **NIST AI RMF** | Supports GOVERN, MAP, MEASURE, and MANAGE functions with runtime metrics and audit trails. |
| **OWASP LLM Top 10 (2025)** | Addresses prompt injection, sensitive information disclosure, and excessive agency. |

---

## Try it

```python
import crp

client = crp.SDKClient(safety="strict")
answer = client.ask("Summarise the contract")

print(answer.crp.risk)               # LOW | MEDIUM | HIGH | CRITICAL
print(answer.crp.fabrications)       # count of invented claims
print(answer.crp.grounded)           # grounding score 0.0–1.0
print(answer.crp.injection_detected) # True / False
```

[:octicons-arrow-right-24: Explore the DPE pipeline](../safety/dpe.md)

---

## Frequently asked questions about AI safety

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is an AI safety protocol?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "An AI safety protocol is a standardized set of signals, policies, and enforcement mechanisms that detect and mitigate harmful or unreliable LLM outputs. CRP implements AI safety as HTTP headers so every AI call carries a machine-readable risk score."
      }
    },
    {
      "@type": "Question",
      "name": "How does CRP detect hallucinations?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP's Decision Provenance Engine (DPE) compares model outputs against the grounded facts in the Context Envelope and scores attribution, fabrication, contradiction, and distortion. The result is returned as CRP-Safety-Hallucination-Risk and CRP-Safety-Attribution headers."
      }
    },
    {
      "@type": "Question",
      "name": "Does CRP modify the LLM?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No. CRP wraps existing LLM calls through an OpenAI-compatible Gateway or SDK. The model receives system prompt, scored facts, and task; CRP metadata is stripped before forwarding."
      }
    },
    {
      "@type": "Question",
      "name": "Can CRP prevent prompt injection?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. CRP's prompt-injection shield detects direct, indirect, goal-hijacking, exfiltration, and delimiter-forgery patterns and flags them before the output reaches users."
      }
    }
  ]
}
</script>

### What is an AI safety protocol?

An AI safety protocol is a standardized set of signals, policies, and enforcement mechanisms that detect and mitigate harmful or unreliable LLM outputs. CRP implements AI safety as HTTP headers so every AI call carries a machine-readable risk score.

### How does CRP detect hallucinations?

CRP's Decision Provenance Engine (DPE) compares model outputs against the grounded facts in the Context Envelope and scores attribution, fabrication, contradiction, and distortion. The result is returned as `CRP-Safety-Hallucination-Risk` and `CRP-Safety-Attribution` headers.

### Does CRP modify the LLM?

No. CRP wraps existing LLM calls through an OpenAI-compatible Gateway or SDK. The model receives system prompt, scored facts, and task; CRP metadata is stripped before forwarding.

### Can CRP prevent prompt injection?

Yes. CRP's prompt-injection shield detects direct, indirect, goal-hijacking, exfiltration, and delimiter-forgery patterns and flags them before the output reaches users.

---

## See also

- [Control-evidence mapping](../control-evidence.md)
- [AIUC-1 Aligned Safety & Security](../aiuc-1.md)
- [The Safety Case](../safety/index.md)
- [DPE Pipeline](../safety/dpe.md)
- [Safety Policy Language](../protocol/safety-policy.md)
- [CRP vs RAG, MCP & Agents](crp-vs-rag-mcp.md)
- [EU AI Act Compliance](../compliance/eu-ai-act.md)

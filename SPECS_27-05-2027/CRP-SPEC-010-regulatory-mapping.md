# CRP-SPEC-010: Regulatory Controls Mapping

**Document:** CRP-SPEC-010  
**Title:** Context Relay Protocol (CRP) — Regulatory Controls Mapping  
**Version:** 3.0.0  
**Status:** Draft — PUBLIC DOCUMENT (intended for NIST/DISR submission)  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-05-25  
**License:** CC BY 4.0

---

## Abstract

This document maps every CRP feature, header, and mechanism to specific controls in the EU AI Act, GDPR, ISO/IEC 42001:2023, NIST AI RMF 1.0, SOC 2 Type II, and the Australian AI Ethics Framework. It serves as both a protocol specification appendix and a standalone reference for regulators, auditors, and compliance teams evaluating CRP as a technical implementation mechanism for AI governance requirements.

---

## 1. EU AI Act (Regulation 2024/1689)

| Article | Requirement | CRP Feature | CRP Header | CRP Comply Output |
|---------|------------|-------------|------------|-------------------|
| **Art. 5** | Prohibited AI practices | `CRP-Compliance-EU-AI-Act: UNACCEPTABLE` triggers HTTP 451 halt | `CRP-Compliance-EU-AI-Act` | Prohibition verification record |
| **Art. 6** | Risk classification | Per-call risk classification based on registered AI system type | `CRP-Compliance-EU-AI-Act` | Risk classification register |
| **Art. 9(1)** | Risk management system | DPE 13-stage pipeline as continuous risk assessment | `CRP-Safety-Hallucination-Risk`, `CRP-Safety-Hallucination-Score` | Continuous risk assessment log |
| **Art. 9(2)(a)** | Identification of foreseeable risks | DPE identifies hallucination, fabrication, distortion, contradiction, omission risks per-call | `CRP-Safety-Fabrications`, `CRP-Safety-Distortions`, `CRP-Safety-Omissions` | Per-call risk identification |
| **Art. 9(4)** | Residual risk mitigation | Safety Policy enforcement (`halt-on`, `upgrade-on-risk`) as automatic mitigation | `CRP-Safety-Policy` | Mitigation action log |
| **Art. 10** | Data governance | CKF fact provenance tracking, source registry, PII detection | `CRP-Compliance-GDPR-PII`, `CRP-Memory-CKF-Community` | Data governance report |
| **Art. 11** | Technical documentation | CRP Comply auto-generates Art. 11 documentation from audit trail | `CRP-Compliance-Audit-Trail-URI` | Technical Documentation (auto-generated) |
| **Art. 12** | Record-keeping | HMAC-chained audit trail with 30+ event types, tamper-evident | `CRP-Provenance-HMAC`, `CRP-Compliance-Audit-Trail-Id` | Complete audit trail export |
| **Art. 13** | Transparency | Attribution analysis per-call, grounding percentage disclosed | `CRP-Safety-Attribution`, `CRP-Safety-Grounding-Pct` | Transparency report |
| **Art. 14(1)** | Human oversight capability | Configurable oversight modes (auto/human-review/halt/log-only) | `CRP-Safety-Oversight-Mode` | Oversight event register |
| **Art. 14(3)(a)** | Ability to fully understand AI system | CRP Visualise provides live session tracing and provenance DAG | — (product feature) | Session replay reports |
| **Art. 14(4)(a)** | Ability to not use AI system | `halt-on CRITICAL` immediately stops response delivery | `CRP-Safety-Retry-After: oversight-required` | Halt event log |
| **Art. 17** | Quality management system | Quality Tier (S–D) tracking, quality degradation detection, RQA pipeline | `CRP-Context-Quality-Tier`, `CRP-Quality-Score` | Quality management evidence |
| **Art. 52** | Transparency obligations (limited risk) | `CRP-Compliance-EU-AI-Act: LIMITED` classification | `CRP-Compliance-EU-AI-Act` | Transparency obligation checklist |
| **Art. 64** | Logging obligations | 30+ event types in HMAC-chained audit trail | `CRP-Provenance-HMAC`, `CRP-Provenance-Chain-Integrity` | EU AI Act logging compliance report |
| **Art. 73** | Incident reporting | Safety violations (CRITICAL risk) auto-reported via `report-uri` webhook | `CRP-Safety-Report-URI` | Incident report template |

**Coverage: 16/16 mapped articles. CRP provides technical evidence for all applicable EU AI Act requirements for high-risk AI systems.**

---

## 2. GDPR (Regulation 2016/679)

| Article | Requirement | CRP Feature | CRP Header |
|---------|------------|-------------|------------|
| **Art. 5(1)(a)** | Lawfulness, fairness, transparency | Attribution analysis, provenance chain | `CRP-Safety-Attribution` |
| **Art. 5(1)(c)** | Data minimisation | `CRP-Context-Cache: no-store` prevents CKF persistence of PII | `CRP-Context-Cache` |
| **Art. 5(1)(d)** | Accuracy | DPE fidelity verification, fabrication detection | `CRP-Provenance-Fidelity-Score`, `CRP-Safety-Fabrications` |
| **Art. 5(1)(f)** | Integrity and confidentiality | HMAC chain integrity, TLS 1.3, encryption at rest | `CRP-Provenance-Chain-Integrity` |
| **Art. 13/14** | Information to data subject | Attribution type disclosed per-call | `CRP-Safety-Attribution` |
| **Art. 17** | Right to erasure | CKF fact deletion, HMAC chain truncation | — (operational) |
| **Art. 22** | Automated decision-making | Oversight mode enforcement, reproducibility seed | `CRP-Safety-Oversight-Mode`, `CRP-LLM-Reproducibility-Seed` |
| **Art. 25** | Data protection by design | CRP architecture embeds privacy controls (no-store, PII detection, data residency) | `CRP-Compliance-Data-Residency` |
| **Art. 32** | Security of processing | HMAC-SHA256, HKDF key derivation, AES-256-GCM at rest, TLS 1.3 | — (infrastructure) |
| **Art. 35** | DPIA | CRP Comply generates DPIA from protocol data | `CRP-Compliance-Audit-Trail-URI` |
| **Art. 44** | Transfer safeguards | Data residency header enforcement | `CRP-Compliance-Data-Residency` |

---

## 3. ISO/IEC 42001:2023 (AI Management Systems)

| Control | Requirement | CRP Feature | CRP Header |
|---------|------------|-------------|------------|
| **A.5.2** | AI policy | Safety Policy directive as code-level policy | `CRP-Safety-Policy` |
| **A.5.4** | Roles and responsibilities | Oversight mode assignment per session/system | `CRP-Safety-Oversight-Mode` |
| **A.6.1.2** | AI impact assessment | CRP Comply auto-generates impact assessment from live data | `CRP-Compliance-Audit-Trail-URI` |
| **A.6.2.2** | AI risk assessment | DPE composite risk scoring per-call | `CRP-Safety-Hallucination-Risk` |
| **A.7.3** | Competence and training | — (organisational, not protocol-level) | — |
| **A.8.2** | AI system development | Quality tier tracking, conformance levels | `CRP-Context-Quality-Tier` |
| **A.8.4** | AI system testing | Conformance test suite (CRP-SPEC-014) | — |
| **A.9.2** | Monitoring and measurement | Continuous DPE analysis on every call | All `CRP-Safety-*` headers |
| **A.9.3** | Internal audit | HMAC-chained audit trail, CRP Visualise | `CRP-Provenance-HMAC` |
| **A.9.4** | Corrective action | `upgrade-on-risk` automatic remediation, re-dispatch protocol | `CRP-Safety-Policy` |
| **A.10.2** | Continual improvement | Quality evolution tracking across windows | `CRP-Quality-Score` |
| **B.2.1** | AI system impact | CRP Comply generates AI system impact reports | `CRP-Compliance-ISO-42001` |

**Coverage: 11/12 mapped controls (A.7.3 is organisational, not protocol-level).**

---

## 4. NIST AI RMF 1.0

| Function | Category | CRP Feature | CRP Header |
|----------|----------|-------------|------------|
| **GOVERN 1.1** | Legal compliance awareness | EU AI Act, GDPR classification per-call | `CRP-Compliance-EU-AI-Act`, `CRP-Compliance-GDPR-PII` |
| **GOVERN 1.2** | Accountability structures | Audit trail with per-call provenance, oversight modes | `CRP-Safety-Oversight-Mode`, `CRP-Provenance-HMAC` |
| **GOVERN 1.5** | Risk management integration | DPE integrated into every AI call | `CRP-Safety-Hallucination-Risk` |
| **MAP 1.1** | Intended purpose documented | AI system registration in Gateway configuration | `CRP-Compliance-EU-AI-Act` |
| **MAP 1.6** | Risk tolerance defined | Safety Policy thresholds, safety budget, `CRP-Accept-Risk` | `CRP-Accept-Risk`, `CRP-Agent-Safety-Budget` |
| **MAP 3.5** | Bias and fairness | — (CRP does not currently assess bias; out of scope) | — |
| **MEASURE 1.1** | Appropriate methods selected | DPE 13-stage pipeline as measurement methodology | All `CRP-Safety-*` |
| **MEASURE 2.3** | AI system performance | Quality tier, completeness, flow scoring | `CRP-Context-Quality-Tier`, `CRP-Quality-Score` |
| **MEASURE 2.5** | Trustworthiness evaluation | Composite risk scoring with regulatory amplifiers | `CRP-Safety-Hallucination-Score` |
| **MEASURE 2.6** | Validation against requirements | Conformance test suite (CRP-SPEC-014) | — |
| **MANAGE 1.1** | Risk prioritisation | Risk classification (CRITICAL/HIGH/MEDIUM/LOW) | `CRP-Safety-Hallucination-Risk` |
| **MANAGE 2.2** | Monitoring frequency | Continuous (every AI call) | All `CRP-Safety-*` |
| **MANAGE 3.2** | Incident response | CRITICAL halt + webhook reporting + audit trail | `CRP-Safety-Report-URI` |
| **MANAGE 4.1** | Decommissioning | CKF erasure, session termination, data export | — (operational) |

**Coverage: 13/14 mapped categories. MAP 3.5 (bias/fairness) is out of CRP's current scope.**

---

## 5. SOC 2 Type II Trust Service Criteria

| Criterion | Requirement | CRP Feature |
|-----------|------------|-------------|
| **CC6.1** | Logical access controls | CRP API key authentication, scoped keys, mTLS | 
| **CC6.3** | Access control enforcement | Session token scope validation, API key binding |
| **CC7.1** | Detection of unauthorized activities | HMAC chain integrity verification (BROKEN = tampering) |
| **CC7.2** | Monitoring of system operations | Continuous DPE analysis, 30+ event types in audit trail |
| **CC7.4** | Incident management | CRITICAL risk halt, webhook reporting, CRP Comply alerts |
| **CC8.1** | Change management | CKF state hash (ETag), version tracking, fact lifecycle |
| **CC9.1** | Risk mitigation | Safety Policy enforcement, safety budget, oversight modes |
| **A1.2** | Availability monitoring | Gateway health checks, session token expiry management |

---

## 6. Australian AI Ethics Framework (CSIRO/DISR)

| Principle | Requirement | CRP Feature | CRP Header |
|-----------|------------|-------------|------------|
| **P1** Human-centred values | Human oversight capability | `CRP-Safety-Oversight-Mode` |
| **P2** Fairness | — (bias detection out of current scope) | — |
| **P3** Privacy | PII detection, no-store cache, data residency | `CRP-Compliance-GDPR-PII`, `CRP-Compliance-Data-Residency` |
| **P4** Reliability & safety | DPE risk scoring, safety budget, halt enforcement | `CRP-Safety-Hallucination-Risk`, `CRP-Agent-Safety-Budget` |
| **P5** Transparency | Attribution analysis, provenance chain, CRP Visualise | `CRP-Safety-Attribution`, `CRP-Provenance-Report-URI` |
| **P6** Contestability | HMAC chain enables audit replay, reproducibility seed | `CRP-LLM-Reproducibility-Seed` |
| **P7** Accountability | Complete audit trail, per-call evidence, CRP Comply | `CRP-Compliance-Audit-Trail-URI` |
| **P8** Human oversight | Configurable oversight modes, safety budget escalation | `CRP-Safety-Oversight-Mode` |

---

## 7. Cross-Regulation Coverage Summary

| CRP Feature | EU AI Act | GDPR | ISO 42001 | NIST RMF | SOC 2 | AU Ethics |
|-------------|-----------|------|-----------|----------|-------|-----------|
| DPE risk scoring | Art. 9 | Art. 5(1)(d) | A.6.2.2 | MEASURE 2.5 | CC9.1 | P4 |
| HMAC audit chain | Art. 12, 64 | Art. 5(1)(f) | A.9.3 | GOVERN 1.2 | CC7.1 | P7 |
| Human oversight modes | Art. 14 | Art. 22 | A.5.4 | MANAGE 3.2 | — | P1, P8 |
| Safety Policy | Art. 9(4) | — | A.5.2 | MAP 1.6 | CC9.1 | P4 |
| PII detection | — | Art. 5(1)(c) | — | — | — | P3 |
| Data residency | — | Art. 44 | — | — | — | P3 |
| CRP Comply evidence | Art. 11 | Art. 35 | A.6.1.2 | — | CC7.2 | P7 |
| Quality scoring | Art. 17 | — | A.10.2 | MEASURE 2.3 | — | P4 |
| Safety budget | — | — | — | MAP 1.6 | — | P4 |
| Attribution analysis | Art. 13 | Art. 13 | — | MEASURE 1.1 | — | P5 |

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

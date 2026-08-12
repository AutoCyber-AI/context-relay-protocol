# CRP™ Feasibility Assessment

**Document:** CRP-FEASIBILITY  
**Version:** 1.0  
**Date:** 2026-05-24  
**Status:** Internal Strategy — CONFIDENTIAL

---

## The Honest Answer First

**Is CRP feasible? Yes — the timing is exceptional.**  
**Is it THE solution to AI governance? No. Is it A crucial layer of it? Absolutely yes.**  
**Is it THE solution to context management? No. Is it the best safety-aware context protocol? Yes — and that gap is real.**

The distinction matters because it shapes positioning, pricing, and partnerships. Overselling leads to wrong customers. Underselling leaves money on the table.

---

## 1. Market Feasibility — The Numbers Are Real

The AI Governance Market is valued at USD 414 million in 2025 and is projected to reach USD 9.8 billion by 2035, growing at a CAGR of 37.21%. More immediately: 79% of regulated entities accelerated AI governance implementation in 2025 following final EU AI Act adoption, with compliance spending increasing 140% year-over-year to meet 2026 enforcement deadlines.

The enforcement reality is concrete: compliance for a single high-risk AI system can cost approximately €52,000 annually, and EU AI regulation could create a €17–38 billion compliance market by 2030. Critically: full enforcement activates August 2, 2026 — penalties up to €35 million or 7% global revenue begin.

**CRP's window: August 2026 enforcement is ~10 weeks away from today.** Enterprises are in emergency compliance mode right now. This is the best possible time to be selling continuous compliance infrastructure.

---

## 2. Is CRP THE Solution to AI Governance?

**No — and this is important to be honest about.**

CRP is a **technical infrastructure layer**, not a complete AI governance solution. The full governance stack requires:

| Layer | What's Needed | Does CRP Cover It? |
|-------|--------------|-------------------|
| Risk assessment | FRIA, DPIA, impact assessments | ✅ CRP Comply generates these |
| Technical documentation | Art. 11 EU AI Act tech docs | ✅ CRP Comply generates these |
| Runtime monitoring | Per-call risk, hallucination detection | ✅ Core DPE / headers |
| Human oversight mechanism | Art. 14 EU AI Act | ✅ CRP-Oversight-Mode |
| Data governance | GDPR data minimisation, PII controls | ⚠️ Partial — CRP detects PII, doesn't delete it |
| Model training governance | Bias testing, training data quality | ✗ Out of scope |
| Organisational governance | Policies, roles, training programs | ✗ Out of scope |
| Third-party AI auditing | Independent assessment | ✗ CRP provides evidence to auditors |

**CRP's honest positioning:** CRP covers the **runtime and evidence layer** better than any competitor — the part that is hardest to automate and most urgently needed. The parts CRP doesn't cover (org governance, model training) are either covered by other products or require human work regardless.

### The key differentiator nobody else has

Every competitor (Vanta, Regulativ, ISMS.online, OneTrust) generates compliance documents **from questionnaires**. That evidence is **assertions**. AI compliance failures caused $4.4 billion in losses across organizations in 2025. Regulators will increasingly reject questionnaire-based evidence as enforcement matures.

CRP generates evidence **from live cryptographically-chained protocol data**. When a regulator asks "prove your AI didn't hallucinate in this decision" — a Vanta customer has a filled-in form. A CRP customer has a verifiable HMAC chain with per-call DPE reports. That difference will become decisive.

---

## 3. Is CRP A Solution to Context Management?

**Yes — and this problem is more severe than most developers realise.**

In 2026, the context problem is not primarily about model capability — modern models handle enormous context windows. The real challenge is information discipline. Too many teams treat context windows like junk drawers, dumping everything inside and hoping the model figures it out.

Research confirmed that when models couldn't rely on surface-level pattern matching, 11 out of 13 LLMs dropped below 50% of their baseline scores at just 32K tokens. GPT-4o fell from 99.3% baseline to 69.7%. This is the **"lost in the middle" problem** — large context windows don't solve quality if you don't control what goes in.

**CRP's context management answer:** The 3-phase fact selection (select, rank, pack), quality tier assignment (S–D), and CKF graph are a structured answer to exactly this problem. CRP doesn't just make context bigger — it makes context **better**. The ETag caching, saturation scoring, and window DAG are genuinely differentiated from naive RAG implementations.

**Honest limitation:** CRP's context management is strongest for **document-heavy knowledge domains** (enterprise knowledge bases, regulatory content, technical documentation). It is less differentiated for simple conversational AI or pure creative generation where context quality matters less.

---

## 4. Adoption Feasibility — Who Will Actually Use This

### Tier 1: High likelihood, high urgency (target now)

**EU-regulated AI deployers** — any company with HIGH-risk AI systems under the EU AI Act facing August 2026 deadlines. These companies must have technical documentation, risk management, human oversight, and audit trails. CRP Comply directly generates this evidence.

**Financial services AI teams** — BFSI sector leads AI governance adoption because financial regulators enforce AI explainability, fairness, and audit documentation requirements earlier than other sectors.

**AI-native startups seeking enterprise sales** — enterprise procurement now requires AI governance evidence (SOC 2 AI annexes, ISO 42001). CRP Comply is the path to closing deals blocked by "how do you govern your AI?" questions.

### Tier 2: Moderate likelihood, strong pull

**DevOps / platform engineering teams** — the GitHub Action is the entry point. Enterprise AI teams in 2026 use RAG for retrieval, MCP for governed metadata delivery, and long-context models for complex reasoning. CRP slots into this stack as the governance layer — not replacing any of these but sitting alongside them.

**AI infrastructure companies** — companies building platforms (not just using AI) need CRP protocol compliance baked in to sell to regulated industries.

### Tier 3: Long-term, requires standard recognition

**Big Tech implementations** — OpenAI, Anthropic, Google will not adopt CRP until it's an IETF RFC. Do not pitch them as customers; pitch them as WG participants.

**Government AI systems** — high value but long sales cycles. NIST/DISR reference accelerates this.

### Adoption blockers (honest)

| Blocker | Severity | Mitigation |
|---------|----------|-----------|
| Developer inertia — "we already have logging" | Medium | GitHub Action shows the gap is real |
| Python SDK — excludes Node.js/Go shops | Medium | Gateway solves this (one URL change) |
| CRP Comply requires BYOK setup | Medium | Gateway removes this friction |
| "We'll wait for a standard" | High for enterprise | IANA registration + IETF I-D starts the clock |
| Gateway is not yet built | High | This is the critical build |

---

## 5. Competitive Moat Assessment

| Moat | Strength | Durability |
|------|----------|-----------|
| Protocol-native evidence (vs questionnaire tools) | ★★★★★ | High — architectural |
| HMAC chain provenance | ★★★★☆ | High — hard to replicate |
| DPE hallucination detection | ★★★☆☆ | Medium — others will build detection |
| Header standard (if IANA/IETF registered) | ★★★★★ | Very high — name ownership |
| CKF knowledge graph | ★★★★☆ | High — data network effect |
| CRP Comply evidence chain | ★★★★★ | Very high — switching cost |

**The moat compounds:** The longer a customer uses CRP, the more their audit trail is in the HMAC chain. Switching away means losing years of verifiable compliance history. That's the stickiest possible enterprise SaaS.

---

## Summary Verdict

| Question | Answer |
|----------|--------|
| Is the market real? | ✅ $2.5B and growing at 37% CAGR |
| Is timing right? | ✅ EU AI Act enforcement August 2026 — NOW |
| Is CRP THE governance solution? | ⚠️ No — it's the best **runtime evidence layer** |
| Is CRP THE context solution? | ⚠️ No — it's the best **safety-aware context protocol** |
| Will developers adopt it? | ✅ Via Gateway (frictionless) and GitHub Action |
| Will enterprises adopt it? | ✅ If IANA registration + I-D submitted (credibility) |
| What could kill it? | Big cloud providers shipping built-in governance headers at zero marginal cost |

*© 2025–2026 AutoCyber AI Pty Ltd. CONFIDENTIAL.*

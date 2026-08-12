# CRP-SPEC-041: Adoption & Ecosystem — Time-to-Value, Integrations, and Growth

**Document:** CRP-SPEC-041  
**Title:** Context Relay Protocol (CRP) — Adoption & Ecosystem: Framework Adapters, Onboarding, Templates, and the Growth Engine  
**Version:** 1.0.0  
**Status:** Foundational — Adoption-Critical  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Date:** 2026-06-01  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-032, CRP-SPEC-040  

---

## Abstract

A protocol's quality determines whether it deserves adoption; its ecosystem determines whether it gets it. CRP has the engine (40 specs) and the steering wheel (the SDK, SPEC-032), but adoption depends on factors no protocol spec has yet addressed: how a developer gets to value in the first five minutes, whether CRP works inside the frameworks they already use (LangChain, LlamaIndex, the Vercel AI SDK), whether there are templates and examples to start from, and how free usage converts to paid. This document specifies the adoption layer: framework adapters that make CRP one import inside existing stacks, a concrete onboarding flow with a quickstart that delivers value in minutes, a template/example gallery, the free-to-paid conversion mechanics, and the developer-facing growth surfaces (docs, showcase, community). The principle: meet developers exactly where they are, get them to a working governed-and-grounded result before they have to learn anything, and make the path from first call to production frictionless.

---

## 1. Framework Adapters — CRP Where Developers Already Are

Most developers building AI are already inside a framework. CRP must be one
import in those frameworks, not a migration away from them.

### 1.1 The Adapters

| Framework | Integration | Usage |
|-----------|------------|-------|
| **OpenAI SDK** | drop-in base_url (SPEC-032 §2) | change one line |
| **Anthropic SDK** | drop-in base_url | change one line |
| **LangChain** | `CRPChatModel` drop-in for `ChatOpenAI` | `llm = CRPChatModel(model="gpt-4o")` |
| **LlamaIndex** | CRP as the LLM + retriever | `Settings.llm = CRPLlamaLLM()` |
| **Vercel AI SDK** | CRP provider | `crp()` provider in `generateText` |
| **LiteLLM** | CRP as a provider target | route through CRP |
| **Haystack / CrewAI / AutoGen** | CRP-governed model wrapper | wrap the agent's LLM |

### 1.2 The Adapter Guarantee

Each adapter preserves the framework's interface exactly — the developer's
existing code keeps working — while routing every call through CRP
governance. A LangChain user swaps `ChatOpenAI` for `CRPChatModel` and gets
governance, grounding, and audit with zero other changes. The adapter is the
on-ramp: no rewrite, no new mental model, immediate value inside the tools
they already chose.

```python
# LangChain — before
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o")

# LangChain — after (governed + grounded, everything else unchanged)
from crp.langchain import CRPChatModel
llm = CRPChatModel(model="gpt-4o")
```

---

## 2. The Onboarding Flow — Value in Five Minutes

### 2.1 The Concrete Path

```
1. pip install crprotocol                              [30 sec]
2. crp init                                            [interactive, 1 min]
   → picks provider, writes crp.config.yaml, sets keys
3. First governed call works immediately               [zero-CKF mode]
   client.complete("hello")  → governance signals returned
4. crp ingest ./docs                                   [1-2 min]
5. client.ask("...")  → grounded, full-quality output  [value delivered]
```

Total: under five minutes from install to a governed, grounded result. The
`crp init` command is critical — it removes the configuration cliff by
generating the config interactively.

### 2.2 The Quickstart Repo

A public `crp-quickstart` repository the developer clones, runs, and sees
working in one command — governance, ingestion, ask, a checkpoint, and the
governance summary, all in a single runnable example. Seeing it work end-to-
end in their own terminal is worth more than any documentation.

### 2.3 Time-to-Value Is the North-Star Metric

The adoption team's primary metric: median time from `pip install` to first
successful grounded `ask`. Target: under 5 minutes. Everything in onboarding
optimises this number. If it rises above 10 minutes, onboarding has a defect.

---

## 3. The Template & Example Gallery

Developers start faster from a working example than from a blank file. A
gallery of runnable templates, each a complete governed application:

| Template | Demonstrates |
|----------|-------------|
| Governed chatbot | conversation (SPEC-028) + safety + checkpoints |
| RAG over your docs | ingest + CDR/CDGR grounded ask |
| Compliance-ready agent | tools + checkpoints + audit + evidence |
| Document generator | long-form quality-at-quantity (CDR) |
| Local-first deployment | BYO-storage (SPEC-038), no data egress |
| Code-governance CI | CRP Scan in a GitHub Action |
| Multi-agent system | safety budget + delegated agents |

Each template is copy-runnable and maps to a real use case. The gallery is
both onboarding and marketing — it shows what CRP makes easy.

---

## 4. Free-to-Paid Conversion Mechanics

### 4.1 The Funnel (concrete)

```
DISCOVER → CRP Scan (free GitHub Action) finds ungoverned AI in their repo
   │         OR they pip install for governance/quality
   ▼
ACTIVATE → first governed grounded ask works in <5 min (onboarding §2)
   │
   ▼
HABIT    → they ship it; the observability dashboard (SPEC-040 §5) shows
   │        fabrications caught, quality trends — value made visible
   ▼
CONVERT  → they hit a paid trigger:
   │         - need the checkpoint inbox (human oversight)
   │         - need compliance evidence (a regulator/customer asks)
   │         - need Scan auto-remediation PRs
   │         - exceed free quota / retention
   ▼
EXPAND   → more systems, more seats, Business/Enterprise (data residency,
            SSO, custom frameworks)
```

### 4.2 The Conversion Triggers Are Value-Aligned

Each paid trigger is a moment of genuine need, not an artificial wall: a
regulator asks for evidence → generate it (paid); an AI decision needs human
sign-off → the checkpoint inbox (paid); Scan finds 20 ungoverned calls →
auto-remediation PRs (paid). The free tier delivers real value (governance,
quality, detection); paying unlocks management, proof, and action. This is
sustainable conversion — developers pay when CRP has already proven itself.

---

## 5. Developer Growth Surfaces

| Surface | Purpose |
|---------|---------|
| **docs.crprotocol.io** | the progressive-disclosure documentation (SPEC-032 §8) — quickstart → guides → reference |
| **Templates gallery** | runnable starting points (§3) |
| **Showcase** | real systems built on CRP (social proof) |
| **Community** (Discord/GitHub Discussions) | support + ecosystem contributions (adapters, backends) |
| **Changelog / roadmap** | public progress; builds trust for a standards-track protocol |
| **Standards page** | the IETF/IANA story (credibility for enterprise) |

### 5.1 Open Protocol as Adoption Engine

The protocol being open and standards-tracked (IETF, IANA) is itself an
adoption driver: enterprises adopt standards more readily than proprietary
lock-in, and the open spec invites community adapters and backends (SPEC-038)
that expand the ecosystem without AutoCyber AI building every integration.
Open drives adoption; the products (Gateway, Comply, Scan) capture revenue.

---

## 6. The Observability-as-Adoption Insight

A subtle but important point: CRP's value is mostly invisible (it prevents
bad outcomes). The observability dashboard (SPEC-040 §5) makes the invisible
visible — "47 fabrications caught this week," "quality trending up," "38%
token savings." Making value visible is an adoption mechanism: developers
who can *see* what CRP caught and saved stay and convert. Invisible value
churns; visible value retains.

---

## 7. Honest Status & Limits

This is the least "protocol" and most "go-to-market" specification — it is
product and growth engineering, not protocol design. It is included because
adoption is what determines whether the 40 specs of engineering matter at
all. The framework adapters are real engineering (each framework's interface
must be tracked as it changes); the onboarding, templates, and docs are
content and tooling work.

The conversion model is a hypothesis until validated with real funnel data.
The triggers (§4.2) are reasoned but unproven; the adoption team must measure
actual conversion and adjust. Time-to-value (§2.3) is the metric that will
reveal whether onboarding actually works.

Framework adapters create a maintenance burden — each upstream framework
changes independently. The adapter set should start with the highest-usage
frameworks (OpenAI SDK, LangChain, LlamaIndex, Vercel AI SDK) and expand by
demand, not cover everything upfront.

---

## 8. References

- CRP-SPEC-032 — Developer Experience (the SDK adapters wrap)
- CRP-SPEC-038 — Storage Backends (community-extensible ecosystem)
- CRP-SPEC-040 — CRP Comply (the conversion destination)
- CRP-SPEC-013/036 — Scan (the discovery funnel entry)

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

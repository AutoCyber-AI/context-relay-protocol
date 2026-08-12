# CRP Scribe

!!! warning "Future product"
    CRP Scribe is a **roadmap product**. The implementation code is not in this
    repository today, the managed SaaS at `scribe.crprotocol.io` is not live, and
    no pricing tier is available for purchase. The documentation below describes
    the planned surface once it is built. Self-hosted deployment is the likely
    first delivery model.

**Generate long-form documents of any length with your own LLM keys.**

CRP Scribe removes the output wall. Books, manuals, regulatory reports, and
whitepapers are generated chapter-by-chapter using CRP's continuation engine,
fact graph, and quality scoring - while keeping your data and API keys under
your control.

---

!!! info "Any Model, Any Length"
    CRP Scribe will use the continuation engine to generate documents of
    *unlimited* length - books, manuals, whitepapers, regulatory reports.
    The output wall doesn't exist.

## Product Identity

<div class="product-identity" markdown>

| | |
|---|---|
| **Product** | CRP Scribe |
| **Type** | Long-form document generation engine *(roadmap)* |
| **Powered By** | Context Relay Protocol™ - continuation engine, knowledge graph, voice profiling, quality scoring |
| **Deployment** | Self-hosted first; managed SaaS at `scribe.crprotocol.io` planned later |
| **License** | Elastic License 2.0 (ELv2) |

</div>

### How It Works

```
You provide: Topic + Template + LLM API Key
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│              CRP Scribe (Planned)               │
│                                                 │
│  ┌─────────────┐  ┌──────────────────────────┐  │
│  │ Generation   │  │ CRP Subsystems:          │  │
│  │ Orchestrator │──│  • Extraction            │  │
│  │ (chapter by  │  │  • Knowledge Graph (CKF) │  │
│  │  chapter)    │  │  • Voice Profiling       │  │
│  └─────┬───────┘  │  • Quality Scoring       │  │
│        │          │  • Continuation Engine   │  │
│  ┌─────┴─────┐    │  • Circuit Breaker       │  │
│  │ Dashboard  │    │  • Fact Integrity Chain  │  │
│  │ • Progress │    │  • Cross-Chapter Valid.  │  │
│  │ • Templates│    │  • PII/Injection Scan    │  │
│  │ • Documents│    │                          │  │
│  └────────────┘    └──────────────────────────┘  │
│                                                 │
└──────────────────────┬──────────────────────────┘
                       │  Calls your LLM per chapter
                       ▼
              Your LLM Provider
              (OpenAI / Anthropic / Ollama / LM Studio)
```

You get: 50K+ word document with per-chapter quality metrics and full fact graph.

---

## Overview

Every LLM has a finite output window. Ask for a 30-chapter book and you get
8 chapters before truncation. CRP Scribe eliminates this limitation entirely.

It combines CRP's continuation engine with a template system and outline
generator to produce complete, coherent, multi-chapter documents in a single
command.

---

## Quick Start

!!! warning "Not available yet"
    Sign-up, dashboard, and API endpoints at `scribe.crprotocol.io` are not live.

### 1. Sign Up

Planned: visit `scribe.crprotocol.io` and create your account.

### 2. Generate Documents

Planned: use the web dashboard to generate unlimited-length documents. Choose a template, provide your topic, and let the CRP continuation engine handle the rest.

### 3. API Access (Pro & Enterprise)

Planned API example:

```python
import requests

response = requests.post(
    "https://scribe.crprotocol.io/api/v1/generate",
    headers={"X-API-Key": "crc_your_scribe_key"},
    json={
        "topic": "AI Governance and the EU AI Act",
        "template": "whitepaper",
        "num_chapters": 10,
    },
)

result = response.json()
print(f"Chapters: {len(result['chapters'])}")
```

---

## Templates

CRP Scribe is planned to ship with built-in templates:

| Template | Best For | Default Chapters |
|----------|----------|-----------------|
| `whitepaper` | Industry analysis, thought leadership, regulatory briefs | 8 |
| `technical_manual` | API docs, deployment guides, runbooks | 12 |
| `guide` | How-to guides, tutorials, onboarding docs | 8 |
| `report` | Audit reports, assessments, findings | 6 |
| `book` | Full-length books, comprehensive references | 15 |

---

## Outline Generation

Planned: generate a structured outline before writing. The outline can be LLM-powered
(when a provider is available) or use intelligent defaults.

---

## Full Document Generation

Planned: the dashboard will provide real-time progress tracking as each chapter is generated.
Documents will be auto-saved and available for download in Markdown format.

---

## Output Format

Planned output:

- **Full text** - complete document as a single string
- **Per-chapter breakdown** - each chapter with title, content, word count, and CRP quality tier (S/A/B/C/D)
- **Metadata** - generation timestamp, model used, template applied
- **Export** - download as Markdown, or via API as JSON

---

## Pricing

!!! warning "Not final"
    Pricing tiers below are illustrative; they are not live products.

<div class="grid cards" markdown>

-   **Free**

    ---

    - 50 generations/mo
    - 2 templates (whitepaper, guide)
    - 1 LLM provider (OpenAI)
    - Max 5,000 words per document
    - Markdown export
    - 7-day version history

    **$0/mo** *(planned)*

-   **Pro**

    ---

    Everything in Free, plus:

    - 500 generations/mo
    - All templates
    - All LLM providers
    - Max 50,000 words per document
    - MD, PDF, DOCX export
    - 90-day version history
    - API access
    - Email support

    **$39/mo** *(planned)*

-   **Enterprise**

    ---

    Everything in Pro, plus:

    - Unlimited generations
    - Custom templates
    - Private models (Ollama, LM Studio)
    - Unlimited document length
    - All export formats + API export
    - Unlimited version history
    - SSO (SAML / OIDC)
    - Priority support

    **Custom** *(planned)*

</div>

---

## Provider Support

CRP Scribe will work with any CRP-supported LLM provider:

| Provider | Setup |
|----------|-------|
| **OpenAI** | `export OPENAI_API_KEY=sk-...` |
| **Anthropic** | `export ANTHROPIC_API_KEY=sk-ant-...` |
| **Ollama** | `--provider ollama --model llama3` |
| **LM Studio** | `--provider lmstudio --model local-model` |

---

## Contact

- **General enquiries:** [info@crprotocol.io](mailto:info@crprotocol.io)
- **Enterprise licensing:** [contact@crprotocol.io](mailto:contact@crprotocol.io)

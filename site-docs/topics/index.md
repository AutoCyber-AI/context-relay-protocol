---
seo_title: AI Safety, AI Governance & Context Management Topics
description: Explore CRP topic hubs for AI safety, AI governance, AI compliance, control evidence, AIUC-1 alignment, and context management. Open HTTP-header standard for governed LLM systems.
hide:
  - toc
---

# AI Safety, Governance & Context Management

Context Relay Protocol (CRP) is an open, production-ready layer for **AI safety**, **AI security**, **AI governance**, **AI compliance**, **control evidence**, **AIUC-1 alignment**, and **LLM context management**. The pages below explain each domain, how CRP implements it at the protocol level, and where to go next.

<div class="product-grid" markdown>
<div class="product-card">
<h3>🛡️ AI Safety</h3>
<p>How CRP detects hallucinations, fabrications, contradictions, prompt injection, and PII on every LLM call.</p>
<a href="/topics/ai-safety/" class="md-button button--small mt-1">Read the AI Safety guide</a>
</div>
<div class="product-card">
<h3>⚖️ AI Governance</h3>
<p>Policies, oversight, accountability, and audit trails that make AI systems transparent and controllable.</p>
<a href="/topics/ai-governance/" class="md-button button--small mt-1">Read the AI Governance guide</a>
</div>
<div class="product-card">
<h3>📋 AI Compliance</h3>
<p>Automated evidence for the EU AI Act, ISO/IEC 42001, NIST AI RMF, and GDPR.</p>
<a href="/topics/ai-compliance/" class="md-button button--small mt-1">Read the AI Compliance guide</a>
</div>
<div class="product-card">
<h3>🧠 Context Management</h3>
<p>Unbounded context, automatic continuation, knowledge graphs, and retrieval for LLMs.</p>
<a href="/topics/context-management/" class="md-button button--small mt-1">Read the Context Management guide</a>
</div>
<div class="product-card">
<h3>🏅 Control Evidence</h3>
<p>Signed, tamper-evident proof that AI safety and security controls operate for EU AI Act, AIUC-1, ISO 42001, NIST AI RMF, and SOC 2-for-AI.</p>
<a href="/control-evidence/" class="md-button button--small mt-1">Control-evidence mapping</a>
</div>
<div class="product-card">
<h3>🏅 AIUC-1 Aligned</h3>
<p>Enterprise AI trust infrastructure mapped to the AIUC-1 AI agent security, safety, and reliability standard.</p>
<a href="/aiuc-1/" class="md-button button--small mt-1">AIUC-1 proof point</a>
</div>
<div class="product-card">
<h3>🔍 CRP vs RAG, MCP &amp; Agents</h3>
<p>A clear comparison of where CRP fits relative to RAG, MemGPT, LangChain, MCP, and A2A.</p>
<a href="/topics/crp-vs-rag-mcp/" class="md-button button--small mt-1">See the comparison</a>
</div>
<div class="product-card">
<h3>❓ Frequently Asked Questions</h3>
<p>Short answers to the most common questions about CRP, safety, governance, and getting started.</p>
<a href="/faq/" class="md-button button--small mt-1">Read the FAQ</a>
</div>
</div>

---

## Why a protocol layer?

Most AI safety, governance, and compliance work today is done in application code or bolt-on SaaS tools. CRP moves these concerns to a **wire-level protocol**:

- **Safety signals** travel as standard HTTP headers on every AI request/response.
- **Governance policies** are declared once and enforced at the Gateway boundary.
- **Compliance evidence** is generated continuously from runtime audit data.
- **Context state** is relayed between windows, sessions, and agents without vendor lock-in.

The result is AI systems that are safer, more auditable, and easier to deploy under regulation — with one `base_url` change.

[:octicons-arrow-right-24: Read why CRP exists](../why-crp.md)

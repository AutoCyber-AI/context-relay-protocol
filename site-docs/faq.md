---
seo_title: Frequently Asked Questions about CRP, AI Safety & AI Governance
description: Answers to common questions about Context Relay Protocol (CRP), AI safety, AI governance, AI compliance, context management, and getting started.
tags:
  - faq
  - crp
  - ai-safety
  - ai-governance
  - ai-compliance
  - context-management
---

# Frequently Asked Questions

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is Context Relay Protocol (CRP)?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Context Relay Protocol (CRP) is an open HTTP-header standard that adds AI safety, governance, compliance evidence, and context management to every LLM call. It works as a drop-in Gateway proxy or SDK and is provider-agnostic."
      }
    },
    {
      "@type": "Question",
      "name": "Is CRP open source?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Yes. The CRP specification is open and free to implement. The reference SDK and CLI are published under the Elastic License 2.0 on GitHub and PyPI."
      }
    },
    {
      "@type": "Question",
      "name": "How do I get started with CRP?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Install the Python SDK, change your OpenAI-compatible base URL to a CRP Gateway, or call crp.SDKClient(). The Quickstart guide gets you running in under 5 minutes."
      }
    },
    {
      "@type": "Question",
      "name": "What LLM providers does CRP support?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP supports any OpenAI-compatible endpoint including OpenAI, Anthropic, Gemini, Bedrock, Mistral, Cohere, Ollama, LM Studio, vLLM, TGI, and llama.cpp."
      }
    },
    {
      "@type": "Question",
      "name": "Does CRP replace RAG?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No. CRP complements RAG. RAG retrieves documents; CRP extracts structured facts, manages continuation, scores quality, enforces safety, and maintains audit trails."
      }
    },
    {
      "@type": "Question",
      "name": "Does CRP replace MCP?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "No. MCP standardises how agents access tools. CRP governs the AI calls that use those tools, adding safety headers, provenance, and audit trails."
      }
    },
    {
      "@type": "Question",
      "name": "How does CRP improve AI safety?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP's Decision Provenance Engine (DPE) scores every output for hallucination, fabrication, contradiction, grounding, and injection risk. Results are returned as standard HTTP headers so applications can act on them automatically."
      }
    },
    {
      "@type": "Question",
      "name": "What compliance frameworks does CRP support?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP generates evidence aligned with the EU AI Act, ISO/IEC 42001:2023, NIST AI Risk Management Framework, GDPR, SOC 2, and HIPAA."
      }
    },
    {
      "@type": "Question",
      "name": "What is context management in CRP?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP extracts atomic facts, stores them in a graph-structured Contextual Knowledge Fabric (CKF), packs the most relevant facts into each window, and automatically continues generation when the model hits its output limit."
      }
    },
    {
      "@type": "Question",
      "name": "Is there a managed cloud option?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "CRP Gateway and CRP Comply are available for self-hosting today. A managed-cloud option is on the waitlist. The open-source SDK, CLI, and GitHub Action are available now."
      }
    }
  ]
}
</script>

## What is Context Relay Protocol (CRP)?

Context Relay Protocol (CRP) is an open HTTP-header standard that adds AI safety, governance, compliance evidence, and context management to every LLM call. It works as a drop-in Gateway proxy or SDK and is provider-agnostic.

[:octicons-arrow-right-24: Read the full introduction](index.md)

## Is CRP open source?

Yes. The CRP specification is open and free to implement. The reference SDK and CLI are published under the Elastic License 2.0 on GitHub and PyPI.

[:octicons-arrow-right-24: GitHub repository](https://github.com/AutoCyber-AI/context-relay-protocol){:target="_blank" rel="noopener noreferrer"}

## How do I get started with CRP?

Install the Python SDK, change your OpenAI-compatible base URL to a CRP Gateway, or call `crp.SDKClient()`. The Quickstart guide gets you running in under 5 minutes.

[:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

## What LLM providers does CRP support?

CRP supports any OpenAI-compatible endpoint including OpenAI, Anthropic, Gemini, Bedrock, Mistral, Cohere, Ollama, LM Studio, vLLM, TGI, and llama.cpp.

[:octicons-arrow-right-24: Providers](getting-started/providers.md)

## Does CRP replace RAG?

No. CRP complements RAG. RAG retrieves documents; CRP extracts structured facts, manages continuation, scores quality, enforces safety, and maintains audit trails.

[:octicons-arrow-right-24: CRP vs RAG, MCP & Agents](topics/crp-vs-rag-mcp.md)

## Does CRP replace MCP?

No. MCP standardises how agents access tools. CRP governs the AI calls that use those tools, adding safety headers, provenance, and audit trails.

[:octicons-arrow-right-24: Tools & Agents SDK](sdk/tools-and-agents.md)

## How does CRP improve AI safety?

CRP's Decision Provenance Engine (DPE) scores every output for hallucination, fabrication, contradiction, grounding, and injection risk. Results are returned as standard HTTP headers so applications can act on them automatically.

[:octicons-arrow-right-24: AI Safety topic](topics/ai-safety.md)

## What compliance frameworks does CRP support?

CRP generates evidence aligned with the EU AI Act, ISO/IEC 42001:2023, NIST AI Risk Management Framework, GDPR, SOC 2, and HIPAA.

[:octicons-arrow-right-24: AI Compliance topic](topics/ai-compliance.md)

## What is context management in CRP?

CRP extracts atomic facts, stores them in a graph-structured Contextual Knowledge Fabric (CKF), packs the most relevant facts into each window, and automatically continues generation when the model hits its output limit.

[:octicons-arrow-right-24: Context Management topic](topics/context-management.md)

## Is there a managed cloud option?

CRP Gateway and CRP Comply are available for self-hosting today. A managed-cloud option is on the waitlist. The open-source SDK, CLI, and GitHub Action are available now.

[:octicons-arrow-right-24: Pricing](pricing.md)

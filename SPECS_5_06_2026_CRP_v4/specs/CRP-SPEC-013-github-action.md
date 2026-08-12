# CRP-SPEC-013: GitHub Action & Scanner Specification

**Document:** CRP-SPEC-013  
**Title:** Context Relay Protocol (CRP) — crp-scan GitHub Action & Repository Scanner  
**Version:** 3.0.0  
**Status:** Draft  
**Author:** Constantinos Vidiniotis, AutoCyber AI Pty Ltd  
**Contact:** contact@crprotocol.io  
**Date:** 2026-05-25  
**License:** CC BY 4.0  
**Prerequisites:** CRP-SPEC-001, CRP-SPEC-002, CRP-SPEC-010

---

## Abstract

This document specifies `crp-scan` — a GitHub Action and standalone CLI tool that performs AI governance static analysis on source code repositories. It detects AI integration points (LLM API calls, agent framework usage, prompt definitions), classifies them by governance risk level, identifies which CRP headers would be missing without CRP integration, generates SARIF reports for GitHub's Security tab, and links each finding to CRP Comply for remediation. This is the top-of-funnel product in the CRP ecosystem — free for basic scanning, paid for full header gap analysis and auto-remediation.

---

## 1. Detection Engine

### 1.1 AI Integration Point Detection

The scanner detects AI integration points by matching against a registry of known patterns across languages and frameworks.

### 1.2 Pattern Registry

#### 1.2.1 Direct LLM Provider API Calls

| Provider | Language | Pattern Examples |
|----------|----------|-----------------|
| OpenAI | Python | `openai.ChatCompletion.create`, `client.chat.completions.create`, `from openai import OpenAI` |
| OpenAI | JavaScript/TS | `new OpenAI()`, `openai.chat.completions.create` |
| OpenAI | Go | `openai.NewClient`, `client.CreateChatCompletion` |
| Anthropic | Python | `anthropic.Anthropic()`, `client.messages.create`, `from anthropic import Anthropic` |
| Anthropic | JavaScript/TS | `new Anthropic()`, `client.messages.create` |
| Google Gemini | Python | `genai.GenerativeModel`, `model.generate_content` |
| Azure OpenAI | Python | `AzureOpenAI()`, `azure.ai.inference` |
| Ollama | Any | `localhost:11434`, `ollama.chat`, `ollama.generate` |
| Bedrock | Python | `bedrock-runtime`, `invoke_model` |

#### 1.2.2 Agent Framework Detection

| Framework | Pattern Examples |
|-----------|-----------------|
| LangChain | `from langchain`, `ChatOpenAI`, `LLMChain`, `AgentExecutor` |
| LlamaIndex | `from llama_index`, `VectorStoreIndex`, `QueryEngine` |
| CrewAI | `from crewai`, `Agent(`, `Crew(`, `Task(` |
| AutoGen | `from autogen`, `AssistantAgent`, `UserProxyAgent` |
| Semantic Kernel | `import semantic_kernel`, `kernel.add_service` |
| Haystack | `from haystack`, `Pipeline`, `PromptBuilder` |
| Vercel AI SDK | `import { streamText }`, `generateText`, `@ai-sdk/openai` |
| MCP client | `from mcp`, `ClientSession`, `StdioServerParameters` |

#### 1.2.3 Raw HTTP Calls to Known AI Endpoints

| Endpoint Pattern | Provider |
|-----------------|----------|
| `api.openai.com/v1/chat` | OpenAI |
| `api.anthropic.com/v1/messages` | Anthropic |
| `generativelanguage.googleapis.com` | Google Gemini |
| `*.openai.azure.com` | Azure OpenAI |
| `bedrock-runtime.*.amazonaws.com` | AWS Bedrock |

#### 1.2.4 Prompt Definition Detection

The scanner also detects prompt definitions that indicate AI usage even when the API call itself is abstracted:

| Pattern | Type |
|---------|------|
| Variables named `system_prompt`, `system_message`, `prompt_template` | Prompt definition |
| String literals containing `"You are a"`, `"As an AI"`, `"assistant"` in system-context positions | Prompt content |
| YAML/JSON files with `prompt:`, `system:`, `template:` keys | Prompt configuration |
| `.prompt` or `.promptflow` file extensions | Prompt files |

### 1.3 Detection Confidence Levels

Each detection is assigned a confidence level:

| Level | Meaning | Example |
|-------|---------|---------|
| `HIGH` | Direct SDK import + API call confirmed | `from openai import OpenAI; client.chat.completions.create(...)` |
| `MEDIUM` | SDK import detected but no confirmed API call in scope | `from openai import OpenAI` (imported but call may be elsewhere) |
| `LOW` | Heuristic match on URL pattern or variable name | `fetch("https://api.openai.com/...")` in a config file |

---

## 2. Governance Gap Analysis

### 2.1 For Each Detected Integration Point

The scanner evaluates which CRP header namespaces would be absent without CRP integration:

| Header Namespace | What's Missing | Risk Classification |
|-----------------|---------------|-------------------|
| `CRP-Safety-*` | No hallucination risk monitoring, no fabrication detection | HIGH |
| `CRP-Provenance-*` | No tamper-evident audit trail, no HMAC chain | HIGH |
| `CRP-Compliance-*` | No EU AI Act classification, no audit trail URI | HIGH (for regulated entities) |
| `CRP-Context-*` | No quality tier tracking, no context management | MEDIUM |
| `CRP-Agent-*` | No safety budget, no loop depth control (agentic only) | CRITICAL (if agentic pattern detected) |
| `CRP-Memory-*` | No CKF cache, no knowledge freshness tracking | LOW |

### 2.2 Risk Classification of Findings

Each finding is classified:

| Finding Risk | Criteria | SARIF Level |
|-------------|----------|-------------|
| `CRITICAL` | Agentic pattern with no safety budget or loop depth control | `error` |
| `HIGH` | Any LLM call with no safety or provenance headers | `warning` |
| `MEDIUM` | LLM call present but missing context management or quality tracking | `note` |
| `LOW` | AI SDK imported but no confirmed ungoverned call | `note` |

### 2.3 Remediation Suggestions

Each finding includes a specific remediation:

**For direct API calls:**
```
Remediation: Change base_url to CRP Gateway endpoint.
  Before: client = OpenAI(api_key="sk-...")
  After:  client = OpenAI(api_key="crp_gw_...", base_url="https://gateway.crprotocol.io/v1")
  
  This single change enables all 58 CRP headers automatically.
  No other code changes required.

  → Create your free CRP account: https://comply.crprotocol.io/signup?source=github-scan
```

**For agent frameworks:**
```
Remediation: Wrap the agent's LLM provider with CRP Gateway.
  LangChain: ChatOpenAI(base_url="https://gateway.crprotocol.io/v1", api_key="crp_gw_...")
  LlamaIndex: OpenAI(api_base="https://gateway.crprotocol.io/v1", api_key="crp_gw_...")
  
  Add CRP-Safety-Policy header for agent safety budget:
  CRP-Safety-Policy: halt-on CRITICAL; upgrade-on-risk reflexive
  
  → Create your free CRP account: https://comply.crprotocol.io/signup?source=github-scan
```

---

## 3. SARIF Output

### 3.1 SARIF Schema

The scanner outputs SARIF v2.1.0 (Static Analysis Results Interchange Format) for native GitHub Security tab integration.

```json
{
  "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [{
    "tool": {
      "driver": {
        "name": "crp-scan",
        "organization": "AutoCyber AI",
        "version": "1.0.0",
        "informationUri": "https://crprotocol.io/scan",
        "rules": [
          {
            "id": "CRP001",
            "name": "UngoverneAICall",
            "shortDescription": { "text": "Ungoverned AI API call detected" },
            "fullDescription": { "text": "An AI LLM API call was detected without CRP governance. This call has no hallucination risk monitoring, no audit trail, and no EU AI Act classification." },
            "helpUri": "https://crprotocol.io/scan/rules/CRP001",
            "defaultConfiguration": { "level": "warning" }
          },
          {
            "id": "CRP002",
            "name": "AgenticNoSafetyBudget",
            "shortDescription": { "text": "Agentic AI pattern with no safety budget" },
            "fullDescription": { "text": "An agentic AI pattern was detected (agent framework, loop, or delegation) without CRP safety budget tracking. Risk can accumulate unboundedly across the agent chain." },
            "helpUri": "https://crprotocol.io/scan/rules/CRP002",
            "defaultConfiguration": { "level": "error" }
          },
          {
            "id": "CRP003",
            "name": "HardcodedPrompt",
            "shortDescription": { "text": "Hardcoded system prompt without governance" },
            "fullDescription": { "text": "A system prompt definition was detected outside of a governed CRP context. Prompts should be managed through CRP's grounding mode system." },
            "helpUri": "https://crprotocol.io/scan/rules/CRP003",
            "defaultConfiguration": { "level": "note" }
          },
          {
            "id": "CRP004",
            "name": "NoComplianceHeaders",
            "shortDescription": { "text": "AI call missing compliance classification" },
            "fullDescription": { "text": "An AI call is missing CRP-Compliance-* headers. This means no EU AI Act risk classification, no GDPR PII detection, and no audit trail deep-link." },
            "helpUri": "https://crprotocol.io/scan/rules/CRP004",
            "defaultConfiguration": { "level": "warning" }
          },
          {
            "id": "CRP005",
            "name": "ExposedLLMKey",
            "shortDescription": { "text": "LLM provider API key potentially exposed" },
            "fullDescription": { "text": "An LLM provider API key pattern was detected in source code. Use CRP Gateway's key vault to avoid key exposure." },
            "helpUri": "https://crprotocol.io/scan/rules/CRP005",
            "defaultConfiguration": { "level": "error" }
          }
        ]
      }
    },
    "results": []
  }]
}
```

### 3.2 SARIF Result Example

```json
{
  "ruleId": "CRP001",
  "level": "warning",
  "message": {
    "text": "Ungoverned OpenAI API call. Missing: CRP-Safety-* (hallucination risk), CRP-Provenance-HMAC (audit trail), CRP-Compliance-EU-AI-Act (regulatory classification). Fix: change base_url to gateway.crprotocol.io/v1. → comply.crprotocol.io/signup"
  },
  "locations": [{
    "physicalLocation": {
      "artifactLocation": { "uri": "src/api/chat.py" },
      "region": { "startLine": 47, "startColumn": 1 }
    }
  }]
}
```

---

## 4. GitHub Action Configuration

### 4.1 Action YAML

```yaml
name: 'CRP AI Governance Scan'
description: 'Scan repository for ungoverned AI integration points'
author: 'AutoCyber AI'

inputs:
  fail_on:
    description: 'Minimum finding severity to fail the check (CRITICAL, HIGH, MEDIUM, LOW, NONE)'
    default: 'HIGH'
  report_format:
    description: 'Output format (sarif, markdown, json)'
    default: 'sarif'
  require_headers:
    description: 'Comma-separated list of CRP headers that must be present'
    default: 'CRP-Safety-Hallucination-Risk,CRP-Provenance-HMAC,CRP-Compliance-EU-AI-Act'
  safety_policy:
    description: 'Recommended CRP-Safety-Policy for detected integration points'
    default: 'default-src context; halt-on CRITICAL'
  comply_link:
    description: 'Include CRP Comply signup link in findings'
    default: 'true'
  exclude_paths:
    description: 'Glob patterns to exclude from scanning'
    default: 'node_modules/**,vendor/**,.venv/**,test/**'

runs:
  using: 'node20'
  main: 'dist/index.js'
```

### 4.2 Workflow Example

```yaml
name: AI Governance
on: [push, pull_request]

jobs:
  crp-scan:
    runs-on: ubuntu-latest
    permissions:
      security-events: write     # Required for SARIF upload
      contents: read
    steps:
      - uses: actions/checkout@v4
      
      - name: CRP AI Governance Scan
        uses: crprotocol/crp-scan@v1
        with:
          fail_on: HIGH
          report_format: sarif
          comply_link: true
      
      - name: Upload SARIF
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: crp-scan-results.sarif
```

---

## 5. Free vs Pro Feature Split

| Feature | Free | Pro ($29/repo/mo) |
|---------|------|-------------------|
| AI integration point detection | ✓ | ✓ |
| Basic risk classification | ✓ | ✓ |
| SARIF output for GitHub Security tab | ✓ | ✓ |
| PR annotations | ✓ | ✓ |
| CRP Comply signup link | ✓ | ✓ |
| Full header gap analysis (which of 58 headers missing) | ✗ | ✓ |
| Auto-remediation PR (generates CRP wrapper code) | ✗ | ✓ |
| EU AI Act pre-classification per detected system | ✗ | ✓ |
| CRP Comply sync (findings in compliance dashboard) | ✗ | ✓ |
| Block merge on configurable risk levels | ✗ | ✓ |
| Weekly governance report email | ✗ | ✓ |
| Custom rule configuration | ✗ | ✓ |

### 5.1 Funnel Integration

Every free-tier finding includes a link:

```
→ Fix this with CRP Gateway (free tier available): https://gateway.crprotocol.io
→ Generate compliance evidence: https://comply.crprotocol.io/signup?source=github-scan&finding=CRP001
```

The Comply signup link is pre-populated with:
- The detected AI provider (OpenAI, Anthropic, etc.)
- The detected framework (LangChain, raw API, etc.)
- The number of ungoverned calls found
- The highest risk finding classification

This reduces the signup friction from "create account from scratch" to "confirm pre-filled information."

---

## 6. CLI Mode

`crp-scan` is also available as a standalone CLI tool for local development:

```bash
# Install
npm install -g @crprotocol/crp-scan

# Scan current directory
crp-scan .

# Scan with specific output format
crp-scan . --format sarif --output results.sarif

# Scan with fail threshold
crp-scan . --fail-on HIGH

# Scan specific files
crp-scan src/api/ src/agents/
```

---

## 7. VS Code Extension

A VS Code extension is planned that provides:
- Real-time inline annotations on detected AI integration points
- Quick-fix actions that insert CRP Gateway wrapper code
- CRP Comply dashboard panel within VS Code
- Safety Policy snippet completion

---

## 8. References

- CRP-SPEC-001 — Core Protocol Specification
- CRP-SPEC-002 — Header Field Specification
- CRP-SPEC-010 — Regulatory Controls Mapping
- SARIF v2.1.0 — OASIS Static Analysis Results Interchange Format
- GitHub Code Scanning — SARIF Upload Documentation

---

*Copyright © 2025–2026 AutoCyber AI Pty Ltd. Licensed under CC BY 4.0. CRP™ is a trademark of AutoCyber AI Pty Ltd.*

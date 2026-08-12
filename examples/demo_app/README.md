# CRP Demo Application

> **The definitive showcase of the Context Relay Protocol** — all 9 dispatch strategies,
> AI governance compliance, and CRP's context continuity engine, in one interactive demo.

## What This Demo Shows

### 1. Compare: Direct LLM vs CRP (`compare`)
A side-by-side comparison where the same LLM and token cap produce **truncated output**
when called directly versus **complete output** when orchestrated through CRP's
continuation engine.

### 2. All 9 Dispatch Strategies (`strategies`)
Every CRP dispatch strategy demonstrated with clear explanations:

| # | Strategy | Pattern | Best For |
|---|----------|---------|----------|
| 1 | `dispatch()` | PUSH — pre-packed envelope | General tasks |
| 2 | `dispatch_with_tools()` | PULL — LLM requests context | LLM-driven exploration |
| 3 | `dispatch_reflexive()` | Verify-then-Refine | Fact-checking, accuracy |
| 4 | `dispatch_progressive()` | Index-then-Detail | Large knowledge bases |
| 5 | `dispatch_stream_augmented()` | Real-time Context Injection | Dynamic exploration |
| 6 | `dispatch_agentic()` | 8-phase Cognitive Engine | Complex multi-step tasks |
| 7 | `dispatch_stream()` | Streaming tokens + events | Real-time UIs, chatbots |
| 8 | `dispatch_batch()` | Sequential multi-task | Report generation |
| 9 | `dispatch_hierarchical()` | Map-Reduce | Large document analysis |

### 3. AI Governance Compliance (`compliance`)
Live demonstration of CRP's built-in regulatory controls:
- **Risk classification** (EU AI Act Art. 6)
- **Human oversight levels** (Art. 14)
- **HMAC-SHA256 audit trail** (Art. 12 record-keeping)
- **PII scanning** (GDPR Art. 5 data minimization)
- **Processing records** (GDPR Art. 30)
- **Compliance report generation** (EU AI Act + ISO 42001 + NIST AI RMF)

### 4. Full Showcase (`full`)
Runs all three demos sequentially.

## Requirements

```bash
pip install crprotocol[full]           # Core CRP with NLP + security
```

**For real LLM usage** (optional — mock mode works without any API key):
```bash
pip install openai              # Or: pip install anthropic
export OPENAI_API_KEY="sk-..."  # Or: export ANTHROPIC_API_KEY="sk-ant-..."
```

## Usage

```bash
# Interactive menu (auto-detects provider or uses mock)
python demo.py

# Specific demo modes
python demo.py compare                        # Direct LLM vs CRP
python demo.py strategies                     # All 9 dispatch strategies
python demo.py compliance                     # EU AI Act / GDPR compliance
python demo.py full                           # Complete showcase

# Provider options
python demo.py compare --mock                 # Offline — no API key needed
python demo.py strategies --provider openai   # Use OpenAI
python demo.py full --provider anthropic --model claude-sonnet-4-20250514

# Output control
python demo.py compare --verbose              # Show session details + audit trail
python demo.py strategies --quiet             # Minimal output
```

## Mock Mode (No API Key Required)

The demo includes a built-in mock provider that simulates realistic LLM behavior:
- Generates structured technical content with extractable facts
- Simulates token limit truncation (finish_reason="length")
- Produces compliance and evaluation responses
- Demonstrates CRP's full pipeline without any external dependencies

**Mock mode is the default** when no API key is detected.

## What to Look For

| Metric | Direct LLM | CRP-Orchestrated |
|--------|------------|------------------|
| **Completion** | Truncated mid-sentence | Full document with conclusion |
| **Sections** | 5 of 10 | 10 of 10 |
| **Facts extracted** | 0 | Auto-extracted by 6-stage pipeline |
| **Audit trail** | None | HMAC-SHA256 chained, tamper-evident |
| **Quality score** | N/A | S/A/B/C/D tier assessment |
| **Context accumulation** | None | Facts carry across windows |
| **Compliance** | None | EU AI Act Art. 6-17, GDPR, ISO 42001 |

## Architecture

```
demo.py
├── Interactive Menu
├── compare — Direct LLM vs CRP
│   ├── Phase 1: Raw LLM call (truncated)
│   └── Phase 2: CRP dispatch (complete + extraction + audit)
├── strategies — All 9 Dispatch Strategies
│   ├── PUSH (dispatch)
│   ├── PULL (dispatch_with_tools)
│   ├── Reflexive (verify-then-refine)
│   ├── Progressive (index-then-detail)
│   ├── Stream-Augmented (real-time injection)
│   ├── Agentic (8-phase cognitive engine)
│   ├── Streaming (token + extraction events)
│   ├── Batch (sequential multi-task)
│   └── Hierarchical (map-reduce)
├── compliance — AI Governance
│   ├── Risk classification (EU AI Act Art. 6)
│   ├── Human oversight (Art. 14)
│   ├── HMAC audit trail (Art. 12)
│   ├── PII scanning (GDPR Art. 5)
│   ├── Processing records (GDPR Art. 30)
│   └── Compliance report (multi-framework)
└── Mock Provider
    └── _DemoMockProvider (offline, no API key)
```

## Files

| File | Description |
|------|-------------|
| `demo.py` | Comprehensive demo — all 9 strategies + compliance |
| `demo_v1.py` | Original v1 demo (archived) |
| `README.md` | This file |

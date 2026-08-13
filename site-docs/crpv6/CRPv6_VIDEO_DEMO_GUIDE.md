# CRPv6 Video Demo Guide

> One-take, screen-recorded proof that a local 8B model becomes an agent through CRPv6.  
> Demo file: `examples/crp_demos/live_crp_slm_proof.py`

---

## What this demo proves

The video shows the same small local language model (`meta-llama-3.1-8b-instruct`) doing the same tasks twice:

1. **Raw LLM** — the model is given tool descriptions inside the system prompt and must figure everything out.
2. **CRPv6 Agent** — the model is wrapped by `crp.Agent`, which positions the task, selects tools, runs the loop, and emits governance.

The contrast makes four selling points visible in one take:

- **Tool use** without hand-written parsing.
- **Tool chains** without the model hallucinating function calls.
- **RAG** without the model claiming it has no data.
- **Long-form output** that stays structured and on-topic.

For a version that uses live public APIs (Open-Meteo, CoinGecko, Wikipedia) instead of offline fixtures, see the [Real-World API Proof](../crpv6/CRPv6_PUBLIC_DEMO_AND_TEST_GUIDE.md#42-demo-real-world-public-api-proof).

---

## Setup before you hit record

### 1. Start LM Studio

1. Open LM Studio.
2. Load `meta-llama-3.1-8b-instruct` (or any other 8B instruct model you have).
3. Start the local server on **port `1234`**.
4. Confirm the server log shows:
   ```
   POST http://192.168.1.17:1234/v1/chat/completions
   ```

### 2. Open a terminal

Activate the environment where `crprotocol` is installed:

```powershell
# Windows
.venv\Scripts\activate
```

```bash
# Git Bash / macOS / Linux
source .venv/bin/activate
```

Check the version:

```bash
python -m pip show crprotocol | findstr Version
```

Expected: `Version: 6.0.0` or newer.

### 3. Run the demo once off-camera

```powershell
# PowerShell / CMD
set CRP_LMSTUDIO_URL=http://192.168.1.17:1234/v1
set CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct
python examples/crp_demos/live_crp_slm_proof.py
```

```bash
# Git Bash / Linux / macOS
CRP_LMSTUDIO_URL=http://192.168.1.17:1234/v1 \
CRP_LMSTUDIO_MODEL=meta-llama-3.1-8b-instruct \
python examples/crp_demos/live_crp_slm_proof.py
```

If the output looks good, clear the terminal and run it again on camera.

---

## What is captured live

Everything that appears on screen during the run is generated in real time:

| Output | Source |
|--------|--------|
| Raw LLM text | The live LM Studio model responding to the raw prompt. |
| CRP answer | The same model, after CRP positioned the task and called the tools. |
| `risk`, `grounded`, `chain_valid` | Computed by CRP from tool observations and the audit chain. |
| `operations` | The STL operations CRP chose (`RETRIEVE`, `TRANSFORM`, `ANALYSE`, `GENERATE`). |
| `sources` | Tool observations with fact IDs and provenance timestamps. |

The only hardcoded value in the script is the weather tool return (`22°C and sunny`). This is deliberate so the demo works without internet. The **decision to call the tool** is not hardcoded.

---

## What to highlight in the video

### Scene 1 — setup (15 seconds)

Show:

- LM Studio running with the 8B model loaded.
- The terminal with the version check.
- A quick `dir examples\crp_demos\live_crp_slm_proof.py` or `ls` so viewers see the file.

Script suggestion:
> “This is a stock Meta Llama 3.1 8B model running on my local machine. No OpenAI, no Claude, no cloud. I’m going to run one Python file and show you the difference between prompting the model directly and running it through CRPv6.”

### Scene 2 — single tool (30 seconds)

Point at the screen when the raw LLM outputs JSON and stops.

Script suggestion:
> “Raw prompt: I told the model it has a `get_weather` tool. It responded with JSON. That’s it. It did not call the tool. CRPv6 actually invoked the function and returned a natural answer, plus this governance block that says the answer is grounded and the chain is valid.”

Highlight:

- `risk: LOW`
- `grounded: true`
- `sources` contains `capability_id: get_weather`

### Scene 3 — tool chain (45 seconds)

This is the strongest visual proof. The raw LLM produces broken function-composition syntax:

```json
{"tool": "convert_temp", "arguments": {"celsius": "[get_weather(city='Sydney')]"}}
```

The CRP answer is a clean two-step result:

```
## RETRIEVE
The weather in Sydney is 22°C and sunny.

## TRANSFORM
22°C is 71.6°F.
```

Script suggestion:
> “This is the failure mode you hit in every agentic app. The model tries to nest one fake function call inside another. CRPv6 ran the first tool, took the real output, and passed it to the second tool. That is an agent loop, not a prompt trick.”

Highlight:

- Two sources in the governance block.
- Operations `retrieve` → `transform`.

### Scene 4 — RAG (45 seconds)

The raw LLM says it has no information and wants to search online. CRPv6 searches the local KB, reads the article, and answers.

Script suggestion:
> “Without CRP, the 8B model says it doesn’t know. With CRP, it retrieves the right article from a local knowledge base and analyses it. Same model. The difference is the protocol.”

Highlight:

- `operations: ["retrieve", "analyse"]`
- Source payload contains the real KB excerpt.

### Scene 5 — long-form report (60 seconds)

This answers the repetition/coherence question. The raw LLM truncates mid-sentence. CRPv6 produces a structured five-paragraph report.

Script suggestion:
> “People ask whether small models can write long, non-repetitive content. Here is the raw model truncating after one paragraph. CRPv6 gives it the structure — one paragraph per benefit — and the same 8B model produces a complete report on cost, privacy, latency, offline operation, and sustainability.”

Highlight:

- Raw output is cut off.
- CRP output has five clean sections.
- No repeated headings.

### Scene 6 — closing (15 seconds)

End with the final banner:

```
All CRP results above include runtime governance computed by the protocol.
No governance values are hardcoded in this script.
```

Script suggestion:
> “Every CRP response carries risk, grounding, chain validity, operations, and sources. That is the proof. Not marketing slides — terminal output from a local model.”

---

## Recording tips

- **Zoom the terminal** so the text is readable on mobile.
- **Do not edit cuts inside a single run**; viewers trust a continuous terminal recording.
- If a run is slow because the model is cold, keep the pause in the video — it proves it is real.
- Show your face in a corner if you want, but keep the terminal as the hero.
- Add captions only for the six script snippets above; let the terminal output speak for itself.

---

## One-liner for the post caption

> “Same 8B model. Same laptop. Raw prompt vs. CRPv6. One returns JSON and stops. The other executes tools, chains them, retrieves a knowledge base, and writes a structured report — with full governance metadata. Local SLMs can be agents. #CRPv6 #AgenticAI #LocalLLM”

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Connection refused` | LM Studio server is not running or wrong URL. |
| `No module named 'setfit'` | Harmless warning; CRP falls back to rule-based intent. To silence it, run `pip install setfit` in the active environment. |
| Raw LLM answers in prose instead of JSON | Re-run; sampling varies. The demo is still valid because CRPv6 always uses the tool interface. |
| Output is slow | Expected on CPU or a small GPU. Keep the pause in the video — it proves real inference. |

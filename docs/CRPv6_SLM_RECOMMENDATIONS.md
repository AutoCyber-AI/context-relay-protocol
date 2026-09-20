# CRPv6 — Small / Local Language Model Recommendations

> Evidence-based guidance on which SLMs benefit most from CRP's positioning layer, and which models still need stronger scaffolding.

---

## 1. The positioning advantage

CRPv6 was built to make **small, local models useful as governed agents**. The main failure mode of a small model in an agent loop is not bad reasoning per se — it is **context flooding**. When the prompt contains every tool schema, every safety rule, every memory fact, and every instruction at once, a 7–8B model:

* misses tool-call formatting,
* ignores safety instructions,
* repeats earlier output,
* hallucinates capability names.

CRP's positioning layer fixes this by:

1. Classifying intent into one of 8 STL operations.
2. Selecting only 1–3 relevant tools for that operation.
3. Building a small, focused Tool Positioning Frame.
4. Running safety scans and checkpoints outside the model's window.
5. Carrying state forward in the CSO so the window stays small.

That means the **same 7–8B model** can reliably do work it could not do in a flooded loop.

---

## 2. Verified model tiers

| Tier | Params | Models tested | Best for | CRP profile |
|------|--------|---------------|----------|-------------|
| **Frontier** | — | `kimi-k2.6`, GPT-4o, Claude 3.5 Sonnet | Full SQB gate, compound tool calls, long reasoning | `frontier` |
| **Capable local** | 7–8B | `meta-llama-3.1-8b-instruct`, `qwen2.5-7b-instruct` | Single-purpose tool calls, short reasoning, on-device | `capable-local` |
| **Small local** | ≤4B | `qwen3-4b`, `gemma-3-270m-it-qat` | Toy demos only today | `small-local` |

### What "works" means

* **Frontier:** passes the full SQB benchmark (`examples/crp_demos/sqb_benchmark.py --mode kimi`) and handles compound prompts.
* **Capable local:** passes the harness end-to-end under the `capable-local` profile with relaxed thresholds.
* **Small local:** currently fails structured tool calling with default prompts; needs tighter frames.

---

## 3. Recommended models by use case

### 3.1 Best all-round capable-local model

**`meta-llama-3.1-8b-instruct` (GGUF Q4_K_M)**

* **Why:** Strong tool-call format compliance, reliable JSON output, good instruction following.
* **Context:** 128K native; CRP probes the live server and respects the loaded context.
* **Format:** GGUF via LM Studio, Ollama, llama.cpp server.
* **Profile:** `capable-local`
* **Gotcha:** Compound multi-part prompts can confuse it; keep each operation focused.

### 3.2 Best multilingual capable-local model

**`qwen2.5-7b-instruct`**

* **Why:** Strong multilingual and code understanding.
* **Context:** 128K native.
* **Format:** GGUF / AWQ via LM Studio / Ollama.
* **Profile:** `capable-local`
* **Gotcha:** More likely to answer from parametric knowledge than call the calculator; tune the tool prompt.

### 3.3 Best model for the video demo

**`meta-llama-3.1-8b-instruct` loaded in LM Studio**

* Runs entirely offline.
* Single-purpose prompts (`"What is the weather in Sydney?"`) execute reliably.
* The contrast with a raw LLM (emits JSON but executes nothing) is obvious and honest.

### 3.4 Frontier judge / gate model

**`kimi-k2.6`**

* **Why:** Proven to pass all five SQB gate criteria.
* **Context:** 256K.
* **Profile:** `frontier`
* **Cost:** ~3–5× more tokens than a local run; reserve for gates and judge tasks.

### 3.5 Models to avoid for agentic work today

| Model | Why |
|-------|-----|
| `gemma-3-270m-it` | Too small to follow tool schema; ignores tool format. |
| `qwen3-4b` | Returns empty or malformed responses in agent loop. |
| Hardcoded `gemma-2-2b` fallbacks | Dead weight; replaced by modern 7–8B options. |

---

## 4. Format and serving recommendations

| Provider | Format | Pros | Cons |
|----------|--------|------|------|
| **LM Studio** | GGUF | Local GUI, auto-detect, OpenAI-compatible endpoint | Windows OpenMP quirks; set `OMP_NUM_THREADS=1` at load time |
| **Ollama** | GGUF | Easy CLI, model management | Abstracts context size; verify loaded context |
| **llama.cpp server** | GGUF | Lightweight, scriptable | Manual model download |
| **vLLM** | AWQ / GPTQ / GGUF | Fast batched serving | Requires GPU for best results |
| **Python MCP/HTTP bridge** | Any | Lets CRP consume remote tools | Adds latency |

**Recommendation:** For development and demos, use **LM Studio** on Windows with `meta-llama-3.1-8b-instruct-Q4_K_M.gguf`. For Linux servers, use **Ollama** or **vLLM**.

---

## 5. Context window strategy

CRP intentionally **does not** rely on a huge context window. The protocol uses:

* **Per-operation frames:** only the current operation's tools + CSO facts.
* **Continuation:** generates longer output in windows rather than one giant prompt.
* **CKF facts:** a small number of high-relevance facts, not full document text.

Therefore the **effective context needed per call is small**. A model advertised at 128K is useful only because KV-cache growth is bounded by the small per-window size.

| Real per-window size | Typical operation | Notes |
|----------------------|-------------------|-------|
| 1–3K | Single tool call + system prompt + preset | Most CRP agent calls |
| 4–8K | Reasoning preset with multiple phases + retrieval | Still well inside 8K |
| 8–16K | Exhaustive depth + verification relay | Frontier models recommended |

---

## 6. Profiles and when to use them

```python
# Capable local — default for 7–8B models
agent = crp.Agent(model="local/llama3.1", profile="capable-local")

# Frontier — for strong cloud/API models
agent = crp.Agent(model="openai/gpt-4o", profile="frontier")

# Small local — for ≤4B experiments
agent = crp.Agent(model="local/qwen3-4b", profile="small-local")
```

The `capable-local` profile:

* Reduces the number of tools offered per operation to 1–2.
* Uses shorter tool descriptions.
* Lowers verification thresholds.
* Allows relaxed lexical-repetition gates.

The `small-local` profile is currently **experimental**. It needs:

* Very small tool sets (1–2 tools).
* Very explicit system prompts.
* Strong output-format enforcement.

---

## 7. Bottom line for marketing

**Safe claims:**

* "CRPv6 makes 7–8B local instruct models reliable as tool-using agents."
* "Single-purpose tool calls work offline with `meta-llama-3.1-8b-instruct`."
* "Frontier models pass the full SQB gate; local models clear a relaxed profile."

**Honest limits:**

* Sub-4B models are not yet reliable for structured tool calling under default CRP prompts.
* Compound multi-part prompts are harder for 8B models than for frontier models.
* The bottleneck is usually model capability, not CRP structure.

---

## 8. Next profiling work

1. Measure `meta-llama-3.1-8b-instruct` and `qwen2.5-7b-instruct` on a fixed 10-task suite across single vs. compound prompts.
2. Tighten `small-local` profile prompts for `qwen3-4b`.
3. Add `phi-4` (14B) and `mistral-small` (24B) to the comparison table.

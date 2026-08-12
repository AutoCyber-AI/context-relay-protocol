# Resource Management for Local LLM/SLM Inference on Consumer Hardware

**A comprehensive survey of what works, what's emerging, and what still doesn't exist**

*Compiled June 2026. Reflects the state of the ecosystem as of Q2 2026.*

---

## 0. How to read this report

Running a model locally is no longer the hard part. **Managing finite resources well** is. This report maps the entire problem space as a stack of seven intervention layers — from "pick a smaller model" up to "orchestrate ten models on one box" — then covers hardware-level approaches, a synthesis of what is *proven* effective by hardware tier, and an honest accounting of the gaps: the solutions that **do not exist yet**.

The single most important conceptual move in this whole domain is to stop thinking about "memory" as one thing. There are **three separate resource budgets**, and confusing them is the root cause of most bad hardware purchases and most disappointing benchmarks.

---

## 1. The three resource budgets (and which one actually binds)

| Budget | What it limits | Unit | Typical consumer ceiling |
|---|---|---|---|
| **Memory capacity** (VRAM + RAM) | *Whether the model loads at all* | GB | 8–24 GB VRAM; 16–128 GB RAM; 16–128 GB unified |
| **Memory bandwidth** | *How fast it generates tokens* (decode) | GB/s | 120 GB/s (M4 Pro) → 400 GB/s (M2 Ultra) → ~900 GB/s (RTX 3090/4090) |
| **Compute (FLOPs)** | *Prompt processing / prefill, batching* | TFLOPs / TOPS | Highly variable; rarely the binding constraint for single-user decode |

The non-obvious, load-bearing fact: **single-user token generation is memory-bandwidth-bound, not compute-bound.** During decode, the GPU spends most of its time streaming weights and KV-cache out of memory into the compute units; the arithmetic itself is cheap and the cores sit largely idle. An H100 has ~3.35 TB/s of bandwidth but ~989 TFLOPS of FP16 — the ratio tells you which one runs dry first. ([jobsbyculture.com][1])

Two consequences fall out of this and drive everything below:

1. **Capacity and speed are different problems with different solutions.** Quantization and offloading solve *capacity* (fitting the model). They only help *speed* indirectly, by reducing the bytes that must be streamed per token.
2. **Bandwidth improves far more slowly than FLOPs.** A 2026 benchmark found a brand-new Blackwell RTX 5060 Ti only ~1.48× faster than an 8-year-old GTX 1080 Ti at single-user generation — eight years of silicon, less than 1.5× — precisely because decode tracks bandwidth, and bandwidth has barely moved. ([inventivehq.com][2]) This is the wall every software trick is ultimately fighting.

> **Rule of thumb for capacity:** Q4 quantization needs roughly **0.5–1 GB of memory per billion parameters** for weights, *before* KV cache. A 14B model ≈ 7–8 GB weights; a 70B model ≈ 35–40 GB. ([sitepoint.com][3])

> **Rule of thumb for speed:** ~5–8 tok/s is comfortable reading speed; >15 tok/s feels real-time. ([runaihome.com][4])

---

## 2. The seven-layer strategy stack

Each layer is an independent lever. Real deployments stack several. They are ordered from "reduce the problem" to "manage the problem."

### Layer 1 — Model selection: don't solve a problem you can avoid

The cheapest resource management is needing fewer resources.

**Small Language Models (SLMs, ~0.5–9B).** The 2026 reality is that sub-10B models routinely beat *2024-era GPT-4* on standard benchmarks, driven by synthetic-data training, distillation from frontier teachers, and architecture refinement. ([callsphere.ai][5]) Practical anchors as of mid-2026:

- **Phi-4-mini (3.8B)** — best small reasoner, ~3 GB VRAM at Q4, 128K context, MIT license. ([tinyweights.dev][6])
- **Gemma 3 4B** — best small *multimodal* option (vision), 140+ languages. ([localaimaster.com][7])
- **Qwen3 / Qwen3.5 (0.6–9B)** — strong native tool-calling, very long context (262K on some 4B variants), Apache 2.0. ([kdnuggets.com][8])
- **SmolLM3-3B** — fully open training pipeline, genuine 128K context, runs in ~6 GB RAM. ([bentoml.com][9])
- **Gemma 3n / Gemma 4 E2B** — *selective parameter activation*: ~5–8B total params but runs with the memory footprint of a ~2B model. ([kdnuggets.com][8])

**The SLM-first routing pattern** is the dominant architectural idea: a small local model handles 70–80% of an agentic loop (parsing, tool calls, formatting, classification), escalating only the genuinely hard turns to a larger local model or a frontier API. NVIDIA formalised the thesis in June 2025 ("Small Language Models are the Future of Agentic AI"); 2026 produced the model supply to match it. ([digitalapplied.com][10])

**Mixture-of-Experts (MoE)** changes what "parameter count" even means, and is now the dominant frontier architecture — by April 2026, essentially every open-weight frontier model is MoE (DeepSeek, Qwen, GLM, Kimi, GPT-OSS, Llama-MoE). ([digitalapplied.com][11]) A MoE model has a large *total* parameter count but only activates a small fraction per token (e.g., DeepSeek V3: 671B total, 37B active; Qwen3-30B-A3B: 30B total, 3B active). This has two profound resource implications, covered in Layers 3 and 4: the **KV cache is sized by the active architecture, not the total**, and the rarely-used expert weights can be pushed off the GPU cheaply.

**Distillation** (e.g., DeepSeek-R1-Distill-Qwen-1.5B) is now standard playbook: compress a massive teacher's behaviour into a fraction of the parameters. ([kdnuggets.com][8])

### Layer 2 — Weight compression (quantization): shrink the bytes

Quantization maps 16-bit weights to fewer bits (8/6/5/4/3/2), trading a little accuracy for large memory and bandwidth savings. **This is the single highest-leverage technique** because it attacks capacity *and* (by reducing bytes-per-token) bandwidth at once.

A critical vocabulary distinction that causes endless confusion: **format ≠ algorithm.** GGUF, EXL3, and MLX are *formats* (containers), each welded to a runtime. GPTQ and AWQ are *algorithms* whose output is stored as ordinary Hugging Face safetensors. Pairing a format with hardware it was never built for is the most common mistake. ([digitalapplied.com][12])

| Method | Type | Bits | Best hardware | Notes |
|---|---|---|---|---|
| **GGUF** (k-quants & i-quants) | Format (llama.cpp) | 2–8, mixed | CPU, consumer GPU, Apple Silicon, hybrid | The default for *local* anything. Single-file, runs on CPU/GPU/both, true file-size reduction. Q4_K_M is the standard sweet spot. I-quants (importance-based) are smaller-but-smarter. ([runaihome.com][13]) |
| **AWQ** | Algorithm | 4 (INT4) | NVIDIA GPU | Activation-aware scaling. Has *overtaken GPTQ* on NVIDIA — cut the INT4 perplexity penalty ~74% and beats GPTQ on reasoning at 4-bit. GPU-only, no CPU fallback. Pairs with vLLM/SGLang/TensorRT-LLM. ([digitalapplied.com][12]) |
| **GPTQ** | Algorithm | 3–4 | NVIDIA GPU | The original 4-bit method; uses second-order (Hessian) info + calibration data. Still solid, now largely superseded by AWQ for new models. AutoGPTQ was archived April 2025; successor is GPTQModel. ([bestaiweb.ai][14]) |
| **EXL3** (ExLlamaV3) | Format | 2–8, *fractional* | Single NVIDIA GPU | Dials bitrate to your exact VRAM (e.g., 4.65 bpw). Best for squeezing a model into a specific card. ([digitalapplied.com][12]) |
| **MLX** | Format | 4/8 | Apple Silicon only | Exploits unified memory; now the default Apple-Silicon backend inside Ollama. ([digitalapplied.com][12]) |
| **bitsandbytes (NF4)** | Algorithm | 4 (NF4) | NVIDIA | The only *training-safe* option here — powers QLoRA fine-tuning. Every other entry is inference-only. ([digitalapplied.com][12]) |
| **FP8** | GPU-native | 8 | Modern NVIDIA (Hopper/Blackwell), AMD | Near-baseline quality, much faster throughput; increasingly the production default for serving. ([sesamedisk.com][15]) |

**Where the frontier is heading:** INT6 schemes are emerging as a superior balance for serving — ~2.7× smaller than FP16 with minimal accuracy loss, better than the traditional 8-bit/4-bit poles. ([arxiv.org][16]) But note the hard limit (see §5): you cannot losslessly quantize an existing model to 2-bit. True extreme low-bit (BitNet-style 1.58-bit) requires training *from scratch* in that regime.

A measured example to calibrate expectations: on Qwen3-32B, AWQ delivered a 42% GPU-memory reduction for a 1.2% accuracy drop. ([dasroot.net][17])

### Layer 3 — KV cache management: the cost that grows with your conversation

The KV cache stores the attention keys/values for every token in context. Its size scales as roughly *(context length × layers × hidden size × bytes)*, and **it grows linearly with context.** At 32K context on a 70B model, the KV cache alone can exceed 20 GB — frequently larger than the quantized weights you worked so hard to shrink. ([runaihome.com][13]) This is *the* bottleneck for long-context and agentic workloads, and it is an entire research field. Strategies divide cleanly:

**(a) Compression — make each cached token smaller**
- **KV quantization.** Store K/V at lower precision (8/4/2-bit). In llama.cpp: `-ctk q8_0 -ctv q8_0` can shrink the cache dramatically (one config went from 3584 MiB → 59.5 MiB). K-cache is more sensitive than V-cache, so quantize K less aggressively. ([ikawrakow-ik_llama-cpp.mintlify.app][18]) Notable methods: **KIVI** (tuning-free 2-bit, handles outliers, no retraining — the safest plug-and-play choice) ([arxiv.org][19]); **KVQuant** (sub-4-bit for contexts up to 10M); **KVTuner** (sensitivity-aware layer-wise mixed precision); and Google's **TurboQuant**/PolarQuant line (ICLR/AISTATS 2026) which fixes a systematic bias in prior scalar quantizers via random orthogonal rotation. ([marktechpost.com][20])
- **Low-rank / cross-layer.** **MiniCache** reuses K/V across layers; **XQuant** uses cross-layer compression for ultra-low-bit. ([arxiv.org][21])
- **Architectural (the biggest win, but requires the right model).** **Multi-head Latent Attention (MLA)**, used by the DeepSeek architecture, compresses the KV footprint by ~98% vs standard multi-head attention. In llama.cpp: `-mla 3`. This is why DeepSeek/Kimi models punch far above their weight on context. ([spheron.network][22])

**(b) Retention management — keep fewer tokens**
- **Eviction.** Discard "unimportant" tokens. **StreamingLLM** keeps "attention sinks" (initial tokens) + a sliding window of recent tokens. **H2O** keeps "heavy hitter" tokens by cumulative attention score; **SnapKV**, **Scissorhands** are variants. The catch: eviction is **irreversible information loss** and can degrade needle-in-a-haystack recall and multi-turn dialogue; it's especially risky for chain-of-thought reasoning. ([arxiv.org][23])
- **Sliding window attention.** Built into models like Gemma and GPT-OSS; bounds the cache by construction.
- **On-device specialists.** **InfiniPot** uses "Continual Context Distillation" to hold the cache in a fixed-size budget, explicitly designed for mobile/NPU memory limits. **TailorKV** serves a 128K-context 8B model on a single RTX 3090. ([arxiv.org][24])

**(c) Allocation — manage the memory layout (Layer 4 territory, but KV-specific)**
- **PagedAttention** (vLLM) manages the cache in fixed-size blocks like OS virtual memory, eliminating fragmentation and enabling far larger batches — the basis of vLLM's throughput advantage. ([codersera.com][25])
- **Prefix caching / RadixAttention** (SGLang) shares the KV of common prefixes (system prompts, RAG context) across requests — a large win for agentic and repeated-prompt workloads. ([tensorfoundry.io][26])
- **KV offload to RAM.** `--no-kv-offload` lets the cache live in system RAM, freeing VRAM for weights when context exceeds VRAM. ([github.com][27])

**Key caveat:** aggressive KV quantization or eviction disproportionately hurts *reasoning* models (long CoT), because the discarded/blurred tokens were load-bearing for the chain of thought. Match the technique to the workload. ([arxiv.org][28])

### Layer 4 — Memory placement & offloading: fit a model bigger than your VRAM

This is the layer that lets a 24 GB card run a 70B model, or a laptop run a 120B MoE. The core idea: not all weights need to be on the fastest hardware at once.

**(a) Layer offloading (dense models).** Put as many transformer layers on GPU as fit (`-ngl N` in llama.cpp), spill the rest to CPU/RAM. The RAM-resident layers become a bottleneck, so this trades speed for capacity. Expect ~5–15× slowdown for the CPU-resident portion depending on memory bandwidth. ([sitepoint.com][3])

**(b) MoE expert offloading — the most important recent advance for consumer hardware.** Because a MoE model only activates a few experts per token, and the routed experts are the *bulk* of the weights, you keep the "always-active" parts (attention, embeddings, shared experts, layer norms) on GPU and push the sparse expert FFN tensors to RAM. The result is **near-GPU generation speed at a fraction of the VRAM cost.** This is the technique that made running massive MoE models on consumer hardware viable. ([huggingface.co][29]) In llama.cpp / ik_llama.cpp:
- `--cpu-moe` — all expert weights to RAM (simplest).
- `--n-cpu-moe N` — experts for the first N layers to RAM (counting from the highest-numbered layers).
- `-ot "\.ffn_.*_exps\.=CPU"` — surgical regex tensor placement (most powerful; e.g., assign specific layers/tensor-types to specific devices). ([gist.github.com][30])

Real configurations from the field: Qwen3-30B-A3B (30B/3B) on dual consumer GPUs with 90K+ context (active path in 32 GB VRAM, experts in 64 GB+ RAM); DeepSeek V3/R1 671B on 4× RTX 4090 + 256 GB DDR5 at 2–4 tok/s. ([github.com][27]) Dense FFN layers (often the first ~3 layers, e.g., DeepSeek V3, GLM-5) should *always* stay in VRAM. **Crucially, only `llama.cpp` and its derivatives provide genuine MoE-expert-aware CPU offloading — vLLM and SGLang are architected around tensor parallelism on homogeneous GPU clusters and do not.** ([github.com][27])

**(c) Sparse-activation engines (the research-grade frontier).** **PowerInfer** extends the offloading idea with *neuron-level* sparsity: it profiles which neurons fire frequently ("hot") and pins them to GPU, computing the rare "cold" neurons on CPU — hitting ~13–29 tok/s on OPT-175B-class models on a single RTX 4090, only ~18% below an A100. ([github.com][31]) Its descendants **DynamicInfer** (runtime-adaptive partitioning, up to 2.5× over llama.cpp) and **SparseInfer** (training-free sparsity prediction) push further. ([openreview.net][32]) **The major caveat:** these shine on **ReLU-family** models (>90% FFN sparsity). Modern SwiGLU models (Llama, Qwen) are only ~50% sparse, so the gains are muted unless you use "ReLUfied" or TurboSparse variants. This is why sparse-activation engines never became the universal default.

**(d) Disk offloading & memory mapping.** `mmap` lets the OS page model weights from disk on demand (llama.cpp default), so a model can "load" larger than RAM — but anything actually streamed from an SSD per token is brutally slow. Frameworks like AirLLM/FlexGen push layer-by-layer disk streaming for "run it overnight" batch use. Practical for throughput-insensitive jobs, painful for interactive chat.

**(e) Unified memory (the hardware shortcut — see §3).** On Apple Silicon, Strix Halo, and DGX Spark, CPU and GPU share one large memory pool, so "offloading" is nearly free in capacity terms — the model just lives in the shared pool. The catch is always bandwidth, not capacity.

### Layer 5 — Compute & throughput optimization: go faster within your budget

These reduce wasted work and exploit the idle compute that the bandwidth wall leaves on the table.

- **Flash Attention** (`-fa`) fuses the attention computation into a single kernel operating on blocks in fast SRAM, avoiding materialising the full N×N attention matrix in HBM. Lower memory, faster, no quality cost. Near-mandatory. ([jobsbyculture.com][1])
- **Speculative decoding** is the headline single-user *latency* optimization. A small fast "draft" model proposes K tokens (typically 3–8); the large "target" model verifies all K in a single parallel forward pass; correct guesses are accepted with **mathematically identical output distribution** (zero quality loss). Because verifying N tokens costs about as much as generating one, and decode is bandwidth-bound, this fills idle bandwidth with useful work — typically **1.5–3× speedup**. ([vucense.com][33]) Enable via `--model-draft` (llama.cpp). Good 2026 pairs: Llama 3.2 1B → 3.3 70B (~2.1×), Qwen3 0.6B → 8B (~1.9×). ([vucense.com][33]) Two important caveats: (1) it helps *latency at low concurrency* but can *reduce* aggregate throughput under high concurrency (the draft competes for compute); (2) gains depend on acceptance rate, which is high for predictable text (code) and lower for creative output. As of **mlx-lm 0.21 (May 2026)**, Apple Silicon finally got a production-grade implementation, closing a two-year gap with CUDA. ([contracollective.com][34])
- **Continuous (in-flight) batching** dynamically packs requests so the GPU never waits between sequences — the core of vLLM's ~16–20× concurrency advantage over Ollama. Matters for serving, irrelevant for single-user. ([codersera.com][25])
- **Graph reuse / CUDA graphs** (`-gr`, `-smgs` in ik_llama) shave per-token launch overhead with no quality cost. ([gist.github.com][30])

### Layer 6 — Runtime / engine choice: the tool decides what's possible

The engine is the *first* real decision — not the model. The 2026 landscape has cleanly bifurcated; treating these as five flavours of one thing is the fastest way to choose badly. ([codersera.com][25])

| Engine | Sweet spot | Strengths | Weaknesses |
|---|---|---|---|
| **Ollama** | Solo dev, prototyping, any OS | One-command pull-and-run, OpenAI-compatible API, keep-alive model management; now uses an **MLX backend on Apple Silicon**. The best default. ([digitalapplied.com][35]) | Single-user throughput far below vLLM; NPU not exposed. |
| **LM Studio** | GUI-first, model browsing | Polished desktop app, runs GGUF + MLX side by side, headless `llmster` daemon for CI/small teams. ([digitalapplied.com][35]) | ~300–500 MB Electron overhead; no native Linux desktop. |
| **llama.cpp / ik_llama.cpp** | Embedded, weird hardware, max control, MoE offload | The foundation under Ollama/LM Studio. Unmatched **fine-grained control** (`-ot`, `-ngl`, KV quant, MLA). **ik_llama** adds graph-split multi-GPU and MoE-specific flags. The only path for genuine MoE-expert CPU offload. ([codersera.com][25]) | Steep learning curve; trial-and-error tuning. |
| **MLX / mlx-lm** | Apple Silicon power users | Exploits unified memory directly, avoids Metal translation overhead; **20–87% faster than llama.cpp for models <14B** (where decode is compute-bound). Now has speculative decoding. ([groundy.com][36]) | Apple-only; gap collapses to ~zero at 27B+ where bandwidth dominates. |
| **vLLM** | Multi-user GPU serving | PagedAttention + continuous batching → ~16–20× Ollama throughput at concurrency; the de-facto production standard. ([codersera.com][25]) | Heavy; **MPS/Apple support is broken** (deep CUDA dependency); overkill for one user. ([contracollective.com][34]) |
| **SGLang** | Prefix-heavy RAG / multi-turn | RadixAttention KV-cache sharing is the main lever for repeated prompts. ([bizon-tech.com][37]) | Production-serving focus; NVIDIA/AMD clusters. |
| **ExLlamaV3** | Single NVIDIA GPU, max squeeze | EXL3 fractional-bitrate quant to fit a specific card exactly. | Niche; NVIDIA-only. |
| **TensorRT-LLM** | Peak NVIDIA throughput | 10–20% above vLLM on NVIDIA. ([local-llm.net][38]) | High operational complexity; NVIDIA-only. |

**Notable 2026 ecosystem shift:** Hugging Face's Text Generation Inference (TGI) went into **maintenance mode and was archived on 21 March 2026**; HF now points new builds at vLLM, SGLang, llama.cpp, or MLX. Don't start new projects on TGI. ([bizon-tech.com][37])

### Layer 7 — Orchestration: managing multiple models on one box

This is the layer most people skip and then hit a wall on. Once you want a coding model, a chat model, an embedding model, and a vision model — all through one endpoint, without OOM — you need orchestration on top of the runtime.

- **Keep-alive / TTL eviction.** Ollama maintains a warm pool and evicts by recency; `keep_alive: 0` unloads immediately. Crude but zero-config. ([glukhov.org][39])
- **llama-swap** — a single Go binary + YAML that sits in front of any OpenAI/Anthropic-compatible upstream and **hot-swaps models on demand**: reads the requested model, starts the right backend (llama.cpp, vLLM, TabbyAPI…), evicts idle ones after a TTL. Its **`groups`** feature allows *concurrent* residency of compatible small models (`swap: false`) while heavy models stay exclusive (`swap: true`). Process-level isolation means one model crashing doesn't take down the others. ([modelslab.com][40])
- **llama-server router mode** (llama.cpp, post-mid-2024 builds) — `--models-dir`/`--models-preset` bring Ollama-like dynamic switching natively, without the wrapper. ([glukhov.org][41])
- **LiteLLM** — sits above llama-swap for unified API-key management, aliasing, routing, rate limits, and fallback chains. The common production stack on big-unified-memory boxes is **LiteLLM → llama-swap → (vLLM / llama.cpp / Ollama)**. ([dredyson.com][42])

**The hard limits of this layer** (and why it's orchestration, not a solution — see §5): switching a model is a **full unload-and-reload cycle** (~3–10 s for a 7B Q5; much longer for large/MoE). Only **one model is genuinely resident per GPU** at a time; true parallel residency needs separate processes on separate GPUs or a large unified pool. And repeated load/unload cycles cause **CUDA memory fragmentation** — total free VRAM looks sufficient but allocation fails for lack of a contiguous block, with no reliable fix except restarting the process. ([sitepoint.com][43])

---

## 3. Hardware-level approaches

Software can only manage the budget; hardware sets it. Three distinct consumer strategies exist in 2026.

### (a) Discrete GPU + GDDR — the speed king
A consumer NVIDIA card (RTX 3090/4090/5090) offers ~900 GB/s+ bandwidth — far above any unified-memory machine — so it wins decisively on *interactive* 7–32B inference where the model fits in VRAM. The constraint is hard VRAM capacity (8–24/32 GB), which Layers 2–4 exist to work around. This is the path mainstream tooling is built for: **GGUF in, fast tokens out.** ([digitalapplied.com][44])

### (b) Unified memory — the capacity king
Apple Silicon, AMD Strix Halo (Ryzen AI Max+ 395), and NVIDIA's DGX Spark (GB10) put a large pool of memory behind both CPU and GPU. A unified-memory Mac or a 128 GB Strix Halo box can hold a **70B-class model that a discrete GPU simply cannot.** ([groundy.com][36]) The unavoidable trade-off is **bandwidth governs the resulting tok/s once the model fits**:

| Machine | Memory | Bandwidth | Reality |
|---|---|---|---|
| M4 Pro | up to 48 GB unified | ~120 GB/s | Holds a 27B Q4; ~7 tok/s baseline (painful for chat, fine for batch). ([vinoth12940.github.io][45]) |
| M2 Ultra | up to 192 GB | ~400 GB/s | The practical Apple sweet spot for large models. ([groundy.com][36]) |
| Strix Halo (Ryzen AI Max+ 395) | up to 128 GB (96 GB to iGPU) | ~256 GB/s | Runs a quantized 70B at ~14 tok/s — **on the iGPU, not the NPU.** ~$2k+. ([digitalapplied.com][44]) |
| DGX Spark (GB10) | 128 GB unified | ~273 GB/s | Dev/prototyping appliance; Llama 70B decodes at just ~2.7 tok/s. Capacity, not speed. ~$4,699. ([runaihome.com][46]) |

The honest framing: **buy unified memory for capacity (running big models at all), buy a discrete GPU for speed (running mid-size models fast).**

### (c) NPUs — the most over-marketed, under-delivering option for LLMs
Every 2026 laptop ships a 40–80 TOPS NPU (Copilot+ floor is 40 TOPS), and the marketing implies they're the new center of gravity for local AI. **For LLMs, they are not** — and this is one of the largest gaps in the whole ecosystem:

- **Mainstream runtimes don't use the NPU at all.** Ollama, llama.cpp, and LM Studio route to the iGPU (Vulkan/ROCm/Metal) or CPU. If you "download a model and run it," you're on the iGPU or CPU regardless of how many TOPS the box advertises. ([digitalapplied.com][44])
- **The NPU path is a separate, specialist stack.** Accelerating an LLM on the NPU requires *hand-converted ONNX models* via Qualcomm's QNN or Intel's OpenVINO (or Windows ML / DirectML 2.0), and in mainstream tooling is **limited to ~4B parameters.** Intel's IPEX-LLM is furthest along but model-limited and not plug-and-play. ([localaimaster.com][47])
- **TOPS is the wrong metric.** TOPS measures peak low-precision throughput for small models; LLM decode is bandwidth-bound. Real-world NPU LLM throughput lands at single-digit-to-low-double-digit tok/s on 8B models (Lunar Lake NPU ~18–20 tok/s), which a five-year-old GPU clears faster and cheaper. ([runaihome.com][46])
- **What NPUs are genuinely good for:** always-on, low-power *background* AI — Windows Recall, live captions, Studio Effects, short on-device summarization (Phi Silica), and Apple Intelligence writing tools — at ~40–45% lower power than a GPU. That's the actual job. ([localaimaster.com][48])

**Microsoft's own direction confirms the NPU-only framing was wrong:** Windows AI Foundry now selects across NPU/GPU/CPU and integrates Foundry Local with Ollama and NVIDIA NIMs — i.e., the platform itself routes around the NPU's limits. ([digitalapplied.com][44])

---

## 4. What is *proven* effective — synthesis by hardware tier

Cutting through the layers, here is what actually works in practice, matched to what you have:

**8 GB VRAM (e.g., RTX 3060/4060 laptop):**
- Run 3–8B models at Q4_K_M (GGUF). Phi-4-mini, Gemma 3 4B, Qwen3 8B, Llama 3.2 3B.
- Flash attention on; KV at q8_0 if context is long.
- For anything bigger: a small MoE (Qwen3-30B-A3B) with `-ot` expert offload to system RAM is the single best trick — you get ~30B "knowledge" at ~3B active speed.
- Engine: Ollama (easy) or llama.cpp (control).

**16–24 GB VRAM (e.g., RTX 4080/4090/3090):**
- Run 14–32B dense at Q4–Q5 fully in VRAM (fast).
- 70B dense via layer offload to RAM (slower) **or** a MoE via expert offload (near-GPU speed).
- Speculative decoding with a 0.5–1B draft for 1.5–2.5× on long generations.
- TailorKV/KV-quant for 128K context on a single card.

**32–128 GB unified (Apple Silicon / Strix Halo):**
- Capacity is solved — run 70B-class models that no consumer GPU can hold.
- Accept bandwidth-bound speeds (single-to-mid double-digit tok/s).
- MLX on Mac for <14B; llama.cpp for >27B and long context (where the gap closes anyway).

**Multi-model / agentic workstation:**
- llama-swap or router mode + LiteLLM for dynamic loading; `groups` for concurrent small models.
- SLM-first routing: cheap local model handles the bulk, escalate the hard turns.
- SGLang prefix caching if you have large repeated system prompts / RAG context.

**Universally effective, regardless of tier:**
1. Q4_K_M GGUF (or AWQ on NVIDIA serving) — the default.
2. Flash attention.
3. KV quantization for long context (mind the reasoning caveat).
4. Pick a model with MLA or sliding-window attention if context is your bottleneck.
5. Use MoE + expert offload to break the VRAM ceiling cheaply.
6. Speculative decoding for single-user latency.

---

## 5. What does *not* exist (or is immature): the honest gaps

This is the part most surveys skip. These are the unsolved or half-solved problems as of mid-2026 — the white space.

**1. A universal NPU path for general LLM inference.** Despite 40–80 TOPS in every new laptop, there is **no drop-in way to run an arbitrary GGUF model on the NPU.** It requires per-vendor ONNX conversion (QNN/OpenVINO), is capped around ~4B params in mainstream tooling, and is bypassed entirely by Ollama/llama.cpp/LM Studio. A GGUF→NPU compiler with broad model coverage simply doesn't exist. This is the single biggest hardware-software gap in consumer AI. ([digitalapplied.com][44])

**2. Zero-overhead / instant model hot-swapping.** Every switch is a full unload-and-reload (seconds to tens of seconds). Only one model is truly resident per GPU. There is **no production technique for instant swapping or sharing common weights across models in memory** — orchestrators (llama-swap, router mode) *manage* this limit, they don't remove it. ([glukhov.org][41])

**3. CUDA memory fragmentation has no clean fix.** After repeated load/unload cycles, allocations fail despite sufficient *total* free VRAM, and the only reliable remedy is restarting the process. No mature consumer-grade defragmenting allocator solves this. ([sitepoint.com][43])

**4. The memory-bandwidth wall.** This is physics, not a missing feature. Single-user decode is bandwidth-bound; bandwidth improves far slower than FLOPs (1.5× over 8 years of GPU generations). Speculative decoding *mitigates* by using idle compute, but caps out at acceptance-rate limits and helps only low-concurrency, predictable workloads. **No software trick fully escapes this ceiling.** ([inventivehq.com][2])

**5. Lossless extreme quantization.** You cannot take an existing FP16 model and quantize it to 2-bit (let alone 1.58-bit) without meaningful, often unpredictable, quality loss — and the loss falls hardest on *reasoning/CoT*. True extreme-low-bit models (BitNet-style) must be **trained from scratch** in that regime; post-hoc compression to that level doesn't work. Below ~2-bit, accuracy degradation is severe across the board. ([arxiv.org][21])

**6. Long-context on consumer hardware remains genuinely painful.** KV cache is still the dominant cost; every mitigation has a real downside — quantization blurs reasoning, eviction loses information irreversibly, MLA requires a model architected for it. There is **no plug-and-play technique that gives lossless, cheap, arbitrarily-long context on a small machine.** It's an active research field precisely because it's unsolved. ([arxiv.org][24])

**7. Disk-streamed MoE with predictive prefetch is research-stage.** Expert offload to *RAM* works well. But streaming experts from *NVMe* with accurate prediction — the thing that would let a laptop run a 671B model at usable speed — is immature, because activation patterns are input-dependent and hard to prefetch, and the SSD bandwidth gap is large. Sparse-activation engines (PowerInfer) that could help are largely confined to ReLU-family models, which modern SwiGLU frontier models are not. ([github.com][31])

**8. No automatic, hardware-aware resource manager.** Today the user manually tunes `-ngl`, `-ot` regex, `--n-cpu-moe`, KV-quant levels, context size, and batch size **by trial and error**, re-checking `nvidia-smi`/`nvtop` on every launch. There is **no mature system that profiles your specific hardware + model and auto-computes the optimal weight placement, KV strategy, and quant level.** Auto-offload heuristics exist but are crude. This is arguably the most impactful *missing product* in the local-inference stack — the layer that would make all the techniques above accessible to non-experts. ([gist.github.com][30])

**9. Persistent, cross-session/cross-process prompt caching for local setups.** SGLang has in-process prefix caching, but a robust, *persistent* prompt cache — so a large system prompt isn't reprocessed on every cold start across tools and restarts — is not well solved in consumer tooling.

**10. Thermal / sustained-throughput on mobile form factors.** Laptops and phones throttle under sustained inference; this is a power/thermal envelope problem with no software escape. Benchmarks quoting peak tok/s rarely reflect a 10-minute agentic run on battery.

---

## 6. Practical playbook (the decision order)

When you sit down to run a model locally, resolve the budgets in this order:

1. **Can a smaller/sparser model do the job?** (Layer 1) Try an SLM or a MoE first. Cheapest possible answer.
2. **Does it fit in VRAM at Q4?** (Layer 2) Quantize. Q4_K_M GGUF locally, AWQ for NVIDIA serving. Use the 0.5–1 GB/B rule.
3. **If not, what's the cheapest way to fit it?** (Layer 4) MoE → expert offload (`-ot`) is the best ceiling-breaker. Dense → layer offload (`-ngl`), accept the slowdown.
4. **Is context (KV cache) blowing the budget?** (Layer 3) Quantize KV (`-ctk/-ctv`), pick an MLA/sliding-window model, or apply eviction — minding the reasoning caveat.
5. **Is it fast enough?** (Layer 5) Flash attention always; speculative decoding for single-user latency; continuous batching only if serving many users.
6. **Did I pick the right engine?** (Layer 6) Ollama (easy) / llama.cpp (control) / MLX (Mac, <14B) / vLLM (serving).
7. **Running more than one model?** (Layer 7) llama-swap or router mode + LiteLLM; SLM-first routing.

And know the four things you *cannot* buy your way out of with software: the **bandwidth wall**, **lossless 2-bit**, **the NPU gap**, and **cheap lossless long context.** Plan around them.

---

## References

1. Red Hat — *llama.cpp vs vLLM: Choosing the right local LLM inference engine* (2026) — https://developers.redhat.com/articles/2026/06/15/llamacpp-vs-vllm-choosing-right-local-llm-inference-engine
2. local-llm.net — *Local LLM Inference Engines Compared: 2026 Guide* — https://www.local-llm.net/compare/inference-engines-2026/
3. Contra Collective — *llama.cpp vs MLX vs Ollama vs vLLM (Apple Silicon, 2026)* — https://contracollective.com/blog/llama-cpp-vs-mlx-ollama-vllm-apple-silicon-2026
4. Digital Applied — *Run Local LLMs 2026: Ollama vs LM Studio vs vLLM* — https://www.digitalapplied.com/blog/run-local-llms-ollama-vs-lm-studio-vs-vllm-2026-guide
5. Codersera — *Ollama vs LM Studio vs vLLM vs llama.cpp vs MLX 2026* — https://codersera.com/blog/ollama-vs-lm-studio-vs-vllm-vs-llama-cpp-vs-mlx-2026/
6. BIZON — *Choosing the best LLM inference engine in 2026* — https://bizon-tech.com/blog/best-llm-inference-engines
7. TensorFoundry — *LLM Inference Servers Compared* — https://tensorfoundry.io/blog/llm-inference-servers-compared
8. Digital Applied — *GGUF vs AWQ vs GPTQ vs MLX: Quant Formats 2026* — https://www.digitalapplied.com/blog/gguf-vs-awq-vs-gptq-vs-mlx-llm-quantization-formats-2026
9. Sesame Disk — *Quantization Techniques 2026: GGUF, AWQ, GPTQ, FP8* — https://sesamedisk.com/quantization-techniques-ai-inference-2026/
10. dasroot.net — *GGUF vs GPTQ vs AWQ Compared* — https://dasroot.net/posts/2026/01/gguf-vs-gptq-vs-awq-llm-quantization-methods-compared/
11. RunAI Home — *Local LLM Quantization Explained* — https://runaihome.com/blog/local-llm-quantization-explained/
12. Best AI Web — *GPTQ vs AWQ vs GGUF vs bitsandbytes Tradeoffs* — https://www.bestaiweb.ai/gptq-vs-awq-vs-gguf-vs-bitsandbytes-quantization-formats-and-their-tradeoffs-explained/
13. arXiv — *FlexQ: INT6 Post-training Quantization for LLM Serving* — https://arxiv.org/pdf/2508.04405
14. MarkTechPost — *Top 10 KV Cache Compression Techniques* (Apr 2026) — https://www.marktechpost.com/2026/04/29/top-10-kv-cache-compression-techniques-for-llm-inference-reducing-memory-overhead-across-eviction-quantization-and-low-rank-methods/
15. arXiv — *KVTuner: Sensitivity-Aware Layer-Wise Mixed-Precision KV Quantization* — https://arxiv.org/pdf/2502.04420
16. arXiv — *XQuant: Ultra-Low Bit KV Cache Quantization with Cross-Layer Compression* — https://arxiv.org/pdf/2510.11236
17. arXiv — *KV Cache Optimization Strategies for Scalable LLM Inference* — https://arxiv.org/html/2603.20397v1
18. arXiv — *SkipKV / KV eviction survey context* — https://arxiv.org/pdf/2512.07993
19. Hugging Face (Doctor-Shotgun) — *Performant local MoE CPU inference with GPU acceleration in llama.cpp* — https://huggingface.co/blog/Doctor-Shotgun/llamacpp-moe-offload-guide
20. GitHub gist (DocShotgun) — *Guide to optimizing MoE inference across CPU+GPU* — https://gist.github.com/DocShotgun/a02a4c0c0a57e43ff4f038b46ca66ae0
21. ik_llama.cpp docs — *Hybrid CPU/GPU inference* — https://ikawrakow-ik_llama-cpp.mintlify.app/inference/hybrid-cpu-gpu
22. GitHub — *LLMKube #280: Hybrid GPU/CPU offloading for MoE models* — https://github.com/defilantech/LLMKube/issues/280
23. Hugging Face — *gpt-oss-20b MoE CPU offload GGUF* — https://huggingface.co/MikeKuykendall/gpt-oss-20b-moe-cpu-offload-gguf
24. Spheron — *MoE Model Inference: Expert Parallelism, Memory, Cost (2026)* — https://www.spheron.network/blog/moe-inference-optimization-gpu-cloud/
25. Digital Applied — *MoE Architecture: GPT, Claude, DeepSeek, Qwen Compared* — https://www.digitalapplied.com/blog/moe-architecture-comparison-gpt-claude-deepseek-qwen
26. arXiv — *PowerInfer: Fast LLM Serving with a Consumer-grade GPU* — https://arxiv.org/pdf/2312.12456
27. GitHub (Tiiny-AI) — *PowerInfer* — https://github.com/Tiiny-AI/PowerInfer
28. OpenReview — *DynamicInfer: Runtime-Aware Sparse Offloading (ICLR 2026)* — https://openreview.net/forum?id=CvjmvjlczZ
29. arXiv — *SparseInfer: Training-free Activation Sparsity Prediction* — https://arxiv.org/pdf/2411.12692
30. Vucense — *Speculative Decoding Explained (Ollama + llama.cpp, 2026)* — https://vucense.com/dev-corner/speculative-decoding-explained-2x-faster-local-llms-ollama-llama-cpp-2026/
31. InventiveHQ — *llama.cpp Speculative Decoding on Cheap GPUs* — https://inventivehq.com/blog/llama-cpp-speculative-decoding-consumer-gpu
32. Jobs by Culture — *LLM Inference Optimization: A Practical Guide (2026)* — https://jobsbyculture.com/blog/llm-inference-optimization-guide-2026
33. Groundy — *MLX vs llama.cpp on Apple Silicon* — https://groundy.com/articles/mlx-vs-llamacpp-on-apple-silicon-which-runtime-to-use-for-local-llm-inference/
34. SitePoint — *DeepSeek R1 Local Deployment Guide 2026* — https://www.sitepoint.com/deepseek-r1-local-deployment-guide-2026/
35. Local AI Master — *Best Small Language Models 2026* — https://localaimaster.com/blog/small-language-models-guide-2026
36. BentoML — *Best Open-Source Small Language Models* — https://www.bentoml.com/blog/the-best-open-source-small-language-models
37. KDnuggets — *Best Small Language Models on Hugging Face Right Now* — https://www.kdnuggets.com/best-small-language-models-on-hugging-face-right-now
38. Digital Applied — *Small Language Models for On-Device Agents 2026* — https://www.digitalapplied.com/blog/small-language-models-on-device-agents-2026-guide
39. CallSphere — *Small Models That Beat GPT-4: Phi-4, Gemma-3, SmolLM-3* — https://callsphere.ai/blog/small-language-models-beat-gpt4-phi-4-gemma-3-smollm-3-2026
40. TinyWeights — *Best Small Language Models in 2026* — https://tinyweights.dev/posts/best-small-language-models-2026/
41. Local AI Master — *NPU Comparison 2026: Intel vs Qualcomm vs AMD vs Apple* — https://localaimaster.com/blog/npu-comparison-2026
42. Digital Applied — *AI PCs and NPUs in 2026: Can They Really Run Local AI?* — https://www.digitalapplied.com/blog/ai-pc-npu-copilot-plus-local-ai-2026-buyers-guide
43. Local AI Master — *Copilot+ PC vs RTX GPU for Local AI (2026)* — https://localaimaster.com/blog/copilot-plus-pc-vs-rtx-local-ai
44. RunAI Home — *Computex 2026 AI Hardware Reality Check* — https://runaihome.com/blog/computex-2026-ai-hardware-roundup-home-lab-2026/
45. Microsoft Learn — *Develop AI applications for Copilot+ PCs (Windows ML/NPU)* — https://learn.microsoft.com/en-us/windows/ai/npu-devices/
46. SitePoint — *Breaking the Speed Limit: Strategies for 17k Tokens/Sec Local Inference* — https://www.sitepoint.com/breaking-the-speed-limit-strategies-for-17k-tokens-sec-local-inference/
47. Glukhov — *llama-swap Quickstart* / *llama-server Router Mode* — https://www.glukhov.org/llm-hosting/llama-swap/ · https://www.glukhov.org/llm-hosting/llama-cpp/llama-server-router-mode/
48. ModelsLab — *Hot-Swap Local LLMs: llama-swap Setup Guide (2026)* — https://modelslab.com/blog/api/hot-swap-local-llms-instantly-llama-swap-setup-guide-2026
49. SitePoint — *Running Multiple Local Models: Memory Management Strategies* — https://www.sitepoint.com/multiple-local-models-memory-management/
50. Dre Dyson — *Multi-Model LLM Stack on DGX Spark GB10 (LiteLLM + llama-swap)* — https://dredyson.com/how-i-built-a-production-ready-multi-model-llm-stack-on-a-single-nvidia-dgx-spark-gb10-a-saas-founders-complete-step-by-step-guide-to-running-litellm-llama-swap-vllm-llama-cpp-and-ollam/

*Note: many cited sources are commercial/SEO-oriented blogs; technical claims (quantization tradeoffs, KV/MoE techniques, bandwidth-bound behaviour, NPU limitations) are corroborated by the primary arXiv papers, the llama.cpp/ik_llama.cpp documentation, and Microsoft/Hugging Face official docs listed above. Specific benchmark numbers should be treated as directional and re-verified against your own hardware.*

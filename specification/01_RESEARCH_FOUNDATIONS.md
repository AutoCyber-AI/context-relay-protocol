<!--
  Copyright (c) 2026 Constantinos Vidiniotis. All rights reserved.
  Licensed under the terms described in LICENSE.md in the root of this repository.
-->

# 01 — Research Foundations

**Context Relay Protocol (CRP) v2.0** · [README](../README.md) · **01 Research** · [02 Core Protocol](02_CORE_PROTOCOL.md) · [03 Envelope](03_CONTEXT_ENVELOPE.md) · [04 Generation](04_TOKEN_GENERATION_PROTOCOL.md) · [05 Integration](05_SYSTEM_WIDE_INTEGRATION.md) · [06 Implementation](06_IMPLEMENTATION_PLAN.md)

> Academic and empirical research backing every CRP design decision.

---

## 1. THE ATTENTION DEGRADATION PROBLEM

When LLMs process long contexts, attention quality degrades. This is not speculation — it's measured:

### 1.1 Lost in the Middle (Liu et al., 2023)

**Finding**: LLMs perform best when relevant information appears at the very beginning or very end of the context window. Information in the **middle** is systematically underweighted.

**Implication for CRP**: A single window stuffed with planning context + tool results + history + output instructions means the **critical information for the current task is buried in the middle**. Fresh, dedicated windows ensure every task's critical information is at the start — where attention is strongest.

### 1.2 Attention Sinks (StreamingLLM — Xiao et al., 2023, ICLR 2024)

**Paper**: "Efficient Streaming Language Models with Attention Sinks" (arXiv:2309.17453)

**Finding**: Transformers allocate disproportionate attention to initial tokens ("attention sinks") regardless of semantic importance. Keeping initial KV entries + a sliding recent window enables stable generation over 4M+ tokens.

**Implication for CRP**: Each fresh window naturally resets attention sinks. The system prompt occupies the privileged initial position every time, and the context envelope (not stale history) gets prime attention real estate.

### 1.3 Infini-attention (Munkhdalai et al., 2024)

**Paper**: "Leave No Context Behind: Efficient Infinite Context Transformers with Infini-attention" (arXiv:2404.07143)

**Finding**: Compressive memory integrated into attention allows processing of infinitely long inputs with bounded memory. Demonstrated on 1M+ token sequences.

**Implication for CRP**: CRP achieves a similar effect at the **application layer** — compressive memory (the context envelope) feeds into each fresh window. The model doesn't need architectural modifications; the protocol provides the infinite context externally.

---

## 2. CONTEXT WINDOW SCALING — WHY BIGGER ISN'T BETTER

### 2.1 Data Engineering for 128K Context (Fu et al., 2024)

**Paper**: "Data Engineering for Scaling Language Models to 128K Context" (arXiv:2402.10171)

**Finding**: The ability to use information at arbitrary positions is largely acquired during pretraining and can be extended to 128K with relatively small fine-tuning data (500M-5B tokens). But **using** that full window efficiently at inference time is a separate challenge.

**Implication for CRP**: Even models trained for 128K don't use all 128K equally well. CRP ensures each window is filled with **only relevant, task-specific content** rather than everything accumulated so far.

### 2.2 Ring Attention (Liu et al., 2023)

**Paper**: "Ring Attention with Blockwise Transformers for Near-Infinite Context" (arXiv:2310.01889)

**Finding**: Context can be distributed across devices by processing blocks of KV pairs in a ring topology, enabling millions of tokens of context. But this is a hardware-level solution.

**Implication for CRP**: CRP achieves distributed context at the **application layer** — each "device" is a fresh LLM call. No special hardware required.

### 2.3 Mixture-of-Depths (Raposo et al., 2024)

**Paper**: "Mixture-of-Depths: Dynamically allocating compute in transformer-based language models" (arXiv:2404.02258)

**Finding**: Not all tokens need the same compute depth. Using top-k routing, transformers can dynamically allocate FLOPs to specific positions, matching baseline performance with a fraction of the compute.

**Implication for CRP**: CRP is the application-level analog. Not all TASKS need the same context budget. CRP allocates **per-task windows of appropriate size** through natural context saturation.

---

## 3. VIRTUAL CONTEXT & MEMORY MANAGEMENT

### 3.1 MemGPT (Packer et al., 2023)

**Paper**: "MemGPT: Towards LLMs as Operating Systems" (arXiv:2310.08560)

**Finding**: Virtual context management — inspired by OS hierarchical memory — allows LLMs to operate on documents far exceeding their context window.

**CRP Relationship**: MemGPT is the **closest prior work** to CRP. Key differences:
- **MemGPT**: One window, pages data in/out → paging overhead, LLM must understand paging commands
- **CRP**: N windows, each dedicated → no paging overhead, model doesn't know the protocol exists (Axiom 4: Model Ignorance)

### 3.2 RET-LLM (Modarressi et al., 2023)

**Paper**: "RET-LLM: Towards a General Read-Write Memory for Large Language Models" (arXiv:2305.14322)

**Finding**: LLMs equipped with explicit read-write memory outperform baselines on QA tasks.

**Implication for CRP**: The context envelope IS a read-write memory unit — but CRP's envelope is **maximally-saturated**, not limited to triplets.

### 3.3 Generative Agents (Park et al., 2023)

**Paper**: "Generative Agents: Interactive Simulacra of Human Behavior" (arXiv:2304.03442)

**Finding**: Agents that observe → reflect → plan produce believable emergent behavior. **Reflection** (synthesizing observations into higher-level insights) is critical.

**Implication for CRP**: The envelope construction step between windows IS structured reflection — without requiring an LLM call. The extraction pipeline replaces LLM-based reflection with deterministic, graduated NLP.

### 3.4 MemWalker (Chen et al., 2023)

**Paper**: "Walking Down the Memory Maze: Beyond Context Limit through Interactive Reading" (arXiv:2310.05029)

**Finding**: Processing long text into a tree of summaries, then navigating that tree to answer queries, outperforms both long-context windows and retrieval methods.

**Implication for CRP**: CRP's four-tier memory hierarchy implements this pattern. The DAG structure provides even richer navigation than a tree.

---

## 4. PROMPT COMPRESSION — WHY CRP'S ENVELOPE ISN'T "LOSSY"

### 4.1 LongLLMLingua (Jiang et al., 2024, ACL 2024)

**Paper**: "LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression" (arXiv:2310.06839)

**Finding**: Compressing prompts by 2-6× actually **improves** performance by up to 21.4% — because compression removes noise and increases key-information density.

**Implication for CRP**: The envelope between windows is **signal amplification**, not lossy compression. The extraction pipeline produces facts that are BETTER inputs than raw data.

### 4.2 Dense X Retrieval / Propositions (Chen et al., 2023)

**Paper**: "Dense X Retrieval: What Retrieval Granularity Should We Use?" (arXiv:2312.06648)

**Finding**: Indexing text as fine-grained **propositions** (atomic, self-contained facts) significantly outperforms passage-level indexing.

**Implication for CRP**: CRP's envelope stores facts as atomic propositions — aligning with empirically-proven best retrieval granularity.

---

## 5. TOKEN GENERATION SCALING

### 5.1 The Autoregressive Bottleneck

LLM token generation is **sequential by nature** — each token depends on the previous. This creates a fundamental throughput ceiling for single-window generation.

### 5.2 Speculative Decoding (Leviathan et al., 2023; Chen et al., 2023)

Use a smaller draft model to propose multiple tokens, then verify in parallel with the main model. Achieves 2-3× speedup without quality loss. **Compatible with CRP**: operates within a single window, orthogonal to the protocol.

### 5.3 Medusa (Cai et al., 2024)

**Paper**: "Medusa: Simple LLM Inference Acceleration Framework with Multiple Decoding Heads" (arXiv:2401.10774)

Multiple decoding heads predict subsequent tokens in parallel, verified via tree attention. 2.2-3.6× speedup. **CRP provides a DIFFERENT kind of parallelism**: task-level parallelism via multiple windows.

### 5.4 SpecInfer (Miao et al., 2024, ASPLOS 2024)

**Paper**: "SpecInfer: Accelerating Generative LLM Serving with Tree-based Speculative Inference" (arXiv:2305.09781)

Token trees dramatically increase acceptance rates. 1.5-2.8× speedup. **Ideal companion** to CRP's continuation protocol for accelerating each window.

### 5.5 Chained Generation Windows — CRP's Innovation

None of the above papers address the **application-layer** solution to unbounded output: **chained generation windows with extraction-built envelopes**. Each window generates at peak quality. Continuation at the physical output limit (`finish_reason: "length"`) transfers state via extracted facts, not raw text overlap. Total output throughput is unbounded: $N_{\text{windows}} \times G$ where $G$ = generation reserve per window. Effective quality is tiered — see 02_CORE_PROTOCOL Section 10.

**Key mechanisms** (specified in 02_CORE_PROTOCOL Sections 4.2, 4.7, 4.8):
- Physical wall detection via `finish_reason` from the LLM API
- Gap analysis determines what's still needed vs. what's been produced
- Continuation envelope carries: extracted facts + structural state + task gap + style anchor
- Stitch algorithm with echo detection and clean boundary trimming
- Master continuation loop with three termination conditions (gap zero, info flow zero, max continuations)

**For input exceeding the context window** (specified in 02_CORE_PROTOCOL Section 4.6):
- Auto-ingest: chunk at natural boundaries with 10% overlap, extract facts per chunk (zero LLM calls), store in warm state, re-dispatch with envelope

---

## 6. AGENT ARCHITECTURE — TASK DECOMPOSITION

### 6.1 LLM-Based Autonomous Agents Survey (Wang et al., 2023)

**Paper**: "A Survey on Large Language Model based Autonomous Agents" (arXiv:2308.11432)

All successful agent architectures decompose complex tasks into: Profile + Memory + Planning + Action. But they all share one context window across these layers.

**CRP Innovation**: Separate windows for each layer. No layer starves another. The model doesn't know it's part of a multi-window protocol.

### 6.2 LATS (Zhou et al., 2023)

**Paper**: "Language Agent Tree Search Unifies Reasoning Acting and Planning" (arXiv:2310.04406)

MCTS with LM-powered value functions achieves SOTA. Each tree node is already an independent LLM call. **CRP formalizes this** with structured envelope passing between nodes.

---

## 7. GRAMMAR-CONSTRAINED GENERATION

### 7.1 Outlines (Willard & Louf, 2023)

**Paper/Library**: "Efficient Guided Generation for Large Language Models" (arXiv:2307.09702)

**Finding**: Finite-state machine (FSM) based logit masking guarantees that LLM output conforms to an arbitrary regular expression or context-free grammar. Compilation to FSM is done once; per-token overhead is negligible (array lookup).

**Implication for CRP**: Grammar-constrained generation is available for **user-specified output schemas**, not for protocol metadata. When the caller provides `output_schema` (JSON schema) or `output_grammar` (GBNF), the protocol compiles it to an FSM and applies logit masking during generation. This guarantees structurally valid output without requiring the model to understand format instructions — the FSM enforces it at the token level.

### 7.2 LMQL (Beurer-Kellner et al., 2023)

**Paper**: "Prompting Is Programming: A Query Language for Large Language Models" (PLDI 2023)

**Finding**: Constraint-based prompting language that allows declarative specification of output structure with type constraints, length constraints, and logical conditions. Integrates with the generation loop for efficient constraint satisfaction.

**Implication for CRP**: Validates CRP's approach of separating structural guarantees (FSM/grammar) from generation content. The model generates freely within structural constraints rather than being asked to self-enforce format rules.

---

## 8. EXTRACTION WITHOUT LLMs

### 8.1 GLiNER (Zaratiana et al., 2023)

**Paper**: "GLiNER: Generalist Model for Named Entity Recognition using Bidirectional Transformer" (arXiv:2311.08526)

**Finding**: A bidirectional transformer trained for NER that accepts **arbitrary entity labels at inference time**. Unlike traditional NER (fixed label set) or LLM-based extraction (expensive), GLiNER combines generality with efficiency (~200MB model, ~50ms per extraction).

**Implication for CRP**: GLiNER is Stage 3 of the graduated extraction pipeline. Entity labels are derived from the task input's noun phrases — no hardcoded domain-specific labels. When the task says "analyze vulnerabilities in the web server," noun phrases ["vulnerabilities", "web server"] become GLiNER labels. This makes extraction task-aware without any configuration.

### 8.2 Universal NER (Ye et al., 2024)

**Paper**: "Universal NER: A Gold-Standard Multilingual Named Entity Recognition Benchmark"

**Finding**: Validates the feasibility of NER systems that generalize across entity types and domains without retraining.

**Implication for CRP**: Confirms that CRP's approach of deriving entity labels from task input is sound — modern NER models handle arbitrary label sets.

### 8.3 TextRank (Mihalcea & Tarau, 2004)

**Paper**: "TextRank: Bringing Order into Texts" (EMNLP 2004)

**Finding**: Graph-based ranking algorithm that extracts key sentences and keywords from text without any training data or domain knowledge. Based on PageRank applied to sentence similarity graphs.

**Implication for CRP**: TextRank is Stage 2 of the extraction pipeline. It extracts key sentences from LLM output using only statistical properties — no model loading, no training, pure algorithm. Cost: ~5ms for typical output length.

### 8.4 BERTSum (Liu & Lapata, 2019)

**Paper**: "Text Summarization with Pretrained Encoders" (EMNLP 2019)

**Finding**: BERT-based extractive summarization identifies the most important sentences by fine-tuning on summarization datasets.

**Implication for CRP**: Alternative to TextRank for Stage 2 when higher extraction quality is needed. The tradeoff is model loading (~400MB) vs. pure algorithm. CRP's hardware-adaptive approach (Axiom 8) selects between them based on available resources.

---

## 9. GENERATION QUALITY RESEARCH

### 9.1 Repetition and Degeneration (Holtzman et al., 2020)

**Paper**: "The Curious Case of Neural Text Degeneration" (ICLR 2020)

**Finding**: Maximizing token probability leads to degenerate, repetitive text. Nucleus sampling (top-p) produces significantly more diverse and coherent text than beam search or pure greedy decoding.

**Implication for CRP**: Validates using information flow measurement (new facts per token) as the completion signal. When generation degenerates into repetition, information flow drops to zero — a directly measurable signal that doesn't require configured thresholds.

### 9.2 Self-Consistency (Wang et al., 2023)

**Paper**: "Self-Consistency Improves Chain of Thought Reasoning in Language Models" (ICLR 2023)

**Finding**: Sampling multiple reasoning paths and selecting the most consistent answer improves accuracy across arithmetic, commonsense, and symbolic reasoning tasks.

**Implication for CRP**: CRP's multi-pass generation (Strategy 5 in 04_TOKEN_GENERATION_PROTOCOL) enables multiple generation attempts within a single window, selecting the best by quality measurement — applying self-consistency at the window level.

---

## 10. KEY SYNTHESIS — WHAT THE RESEARCH TELLS US

| Research Finding | CRP Design Decision |
|-----------------|---------------------|
| Attention degrades in the middle of long contexts | **Fresh window per task** — critical info always at start |
| Prompt compression IMPROVES performance | **Extraction-built envelope is signal amplification** |
| Propositions > passages for retrieval | **Graduated extraction pipeline produces atomic facts** |
| Virtual context management enables infinite context | **Application-layer unbounded context** without model changes (quality-tiered at scale) |
| Reflection is critical for agent behavior | **Extraction pipeline IS structured reflection** (no LLM needed) |
| Not all tokens need equal compute | **Maximum context saturation adapts per task** |
| FSM-based grammar guarantees valid structure | **Grammar-constrained generation for user schemas** (not protocol overhead) |
| GLiNER handles arbitrary entity labels | **Task-derived entity labels — no domain configuration** |
| TextRank extracts key sentences without training | **Stage 2 extraction: zero-cost statistical NLP** |
| Repetition/degeneration is measurable | **Information flow measurement as universal completion signal** |
| Task decomposition is universal in agent architectures | **One window per task with DAG provenance** |
| Hierarchical memory is superior to flat context | **4-tier memory with graduated extraction** |
| LLMs work best with focused, relevant context | **Semantic scoring fills each window with only relevant facts** |

**No existing system combines all of these findings into a unified, zero-configuration protocol.** CRP is the first.

---

## 11. META-LEARNING AND IN-CONTEXT LEARNING RESEARCH

### 11.1 MAML: Model-Agnostic Meta-Learning (Finn et al., ICML 2017)

**Paper**: "Model-Agnostic Meta-Learning for Fast Adaptation of Deep Networks" (arXiv:1703.03400)

**Finding**: A model trained with MAML finds parameter initializations that are maximally sensitive to task-specific updates — enabling fast adaptation with only a few gradient steps on a new task.

**Implication for CRP**: While MAML requires gradient updates (which CRP cannot do — Axiom 6 requires model-agnosticism), the CONCEPT of meta-learning inspires CRP's approach: the envelope construction acts as the "initialization" — CRP "initializes" the model's context to be maximally learnable for the current task. The Reasoning Template Library (02_CORE §19.3) applies the meta-learning principle at the orchestration level: successful reasoning patterns are stored and retrieved for similar future tasks.

### 11.2 In-Context Learning as Implicit Gradient Descent (Dai et al., ACL 2023)

**Paper**: "Why Can GPT Learn In-Context? Language Models Implicitly Perform Gradient Descent as Meta-Optimizers" (arXiv:2212.10559)

**Finding**: Transformer attention has a dual form of gradient descent. LLMs produce "meta-gradients" from demonstration examples during in-context learning. ICL behaves similarly to explicit fine-tuning from multiple perspectives.

**Implication for CRP**: This provides the theoretical foundation for CRP's In-Context Meta-Learning (ICML, 02_CORE §19.2). By structuring the envelope with carefully selected reasoning examples from the Reasoning Template Library, CRP leverages the model's ICL mechanism to perform implicit task adaptation — teaching the model HOW to reason about the current task type without any weight updates.

### 11.3 STaR: Self-Taught Reasoner (Zelikman et al., NeurIPS 2022)

**Paper**: "STaR: Bootstrapping Reasoning With Reasoning" (arXiv:2203.14465)

**Finding**: Models can bootstrap reasoning ability by iteratively learning from their own correct reasoning traces. The Self-Taught Reasoner generates rationales, keeps only those that produced correct answers, and fine-tunes on them — iterating to increasingly complex reasoning.

**Implication for CRP**: CRP implements this concept at the orchestration level WITHOUT fine-tuning: successful Orchestrated Reasoning Chains (02_CORE §19.2) are stored in the Reasoning Template Library. Over multiple sessions, the RTL accumulates increasingly effective reasoning patterns. New tasks retrieve and adapt these patterns — enabling progressive reasoning bootstrapping across sessions without any model modification.

### 11.4 Distilling Step-by-Step (Hsieh et al., ACL 2023)

**Paper**: "Distilling Step-by-Step! Outperforming Larger Language Models with Less Training Data and Smaller Model Sizes" (arXiv:2305.02301)

**Finding**: A fine-tuned 770M T5 model outperforms few-shot 540B PaLM when given step-by-step rationales as additional supervision. Small models can dramatically outperform 700× larger models when given the right scaffolding.

**Implication for CRP**: This validates CRP's Orchestrated Reasoning Chains (02_CORE §19.2): by decomposing complex tasks into step-by-step micro-tasks and providing reasoning scaffolds in the envelope, CRP can amplify small model capabilities far beyond their native ceiling. The 770M-vs-540B finding suggests the scaffolding approach is not just incremental — it can be transformative.

### 11.5 A Survey on In-Context Learning (Dong et al., 2024)

**Paper**: "A Survey on In-context Learning" (arXiv:2301.00234)

**Finding**: ICL effectiveness depends on: (1) demonstration selection and ordering, (2) prompt format/template, (3) training data distribution. The survey identifies that ICL can be enhanced through strategic demonstration retrieval.

**Implication for CRP**: CRP's envelope construction IS strategic demonstration retrieval. The multi-aspect scoring, graph-structured knowledge, and reasoning template selection all optimize the in-context learning signal. The CKF's community detection ensures diverse, representative knowledge is included.

---

## 12. RETRIEVAL AUGMENTATION AT SCALE

### 12.1 Retrieval Augmentation for Long Context (Xu et al., ICLR 2024)

**Paper**: "Retrieval meets Long Context Large Language Models" (arXiv:2310.03025)

**Finding**: "Retrieval can significantly improve the performance of LLMs regardless of their extended context window sizes." Retrieval-augmented Llama2-70B with 32K context outperforms GPT-3.5-turbo-16K and Davinci-003 on long-context tasks.

**Implication for CRP**: This is the scientific backing for CRP's irreplacability claim (02_CORE §21). CRP's approach — semantically scored, graph-structured, source-grounded retrieval — COMPLEMENTS native long context. It does not become redundant as context windows grow. CRP makes each window's context BETTER, not just bigger.

### 12.2 RAPTOR: Recursive Abstractive Processing (Sarthi et al., ICLR 2024)

**Paper**: "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval" (arXiv:2401.18059)

**Finding**: Recursively clustering and summarizing chunks into a tree with different abstraction levels, then retrieving from the appropriate level, improves multi-step reasoning by 20% absolute on the QuALITY benchmark.

**Implication for CRP**: RAPTOR's hierarchical retrieval aligns with CRP's hierarchical processing (02_CORE §11) and the RAPTOR-style hierarchical retrieval described in the Learning on Context roadmap (02_CORE §20.3). CRP can apply RAPTOR's tree structure to the fact graph in the CKF for multi-resolution retrieval.

---

## 13. UPDATED KEY SYNTHESIS

| Research Finding | CRP Design Decision |
|-----------------|---------------------|
| Attention degrades in the middle of long contexts | **Fresh window per task** — critical info always at start |
| Prompt compression IMPROVES performance | **Extraction-built envelope is signal amplification** |
| Propositions > passages for retrieval | **Graduated extraction pipeline produces atomic facts** |
| Virtual context management enables infinite context | **Application-layer unbounded context** without model changes (quality-tiered at scale) |
| Reflection is critical for agent behavior | **Extraction pipeline IS structured reflection** (no LLM needed) |
| Not all tokens need equal compute | **Maximum context saturation adapts per task** |
| ICL performs implicit gradient descent | **CRP envelopes as in-context learning signals** — structured demonstrations teach reasoning |
| Small models outperform large with step-by-step rationales | **Orchestrated Reasoning Chains decompose complex tasks** into capability-appropriate micro-steps |
| Bootstrapping reasoning from own traces | **Reasoning Template Library accumulates successful patterns** across sessions |
| Retrieval augmentation improves ALL models regardless of context size | **CRP complements native context** — irreplaceable even with infinite windows |
| Recursive hierarchical retrieval improves multi-step reasoning | **Hierarchical processing + RAPTOR-style retrieval** at scale |
| Source grounding eliminates interpretation drift | **Source-grounded envelopes** include original text alongside compressed facts |

**No existing system combines all of these findings into a unified, zero-configuration protocol.** CRP is the first.

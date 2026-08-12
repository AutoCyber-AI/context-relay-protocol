# Research Foundations

<div class="cr-hero" markdown>

## Every design choice is backed by peer-reviewed research

CRP integrates findings from attention mechanics, context scaling, memory
systems, extraction, and meta-learning into a single coherent protocol. This
page documents the academic basis for each design decision.

</div>

<span class="cr-badge cr-badge-live">Self-hosted today</span>
<span class="cr-badge cr-roadmap">Managed-cloud waitlist for Gateway and Comply; more endpoints on the roadmap</span>

## Attention Degradation

### Lost-in-the-Middle (Liu et al., 2023)

LLMs perform worse when relevant information is placed in the middle of the
context window. Performance follows a U-curve: best at the beginning and end,
worst in the middle.

**CRP's response**: Fresh windows for each continuation. No information gets
buried in the middle of a 128K context. Each window starts clean with an
optimized envelope.

### Attention Sinks / StreamingLLM (Xiao et al., 2023)

The first few tokens in a sequence act as "attention sinks" - they receive
disproportionate attention regardless of content. This degrades as sequences
grow.

**CRP's response**: Each continuation window resets the attention pattern.
Attention sinks form at the start of the envelope (where CRP places the most
important facts), not in the middle of stale context.

### Infini-attention (Munkhdalai et al., 2024)

Compressive memory that sustains attention over infinite context via
learned compression.

**CRP's response**: CRP achieves compressive memory at the application layer
through the extraction pipeline. No model modification needed.

## Context Window Scaling

### Data Engineering for 128K (Fu et al., 2024)

Scaling context windows requires careful data engineering. Longer context ≠
better performance without position-aware training data.

**CRP's response**: Rather than relying on model-native long context, CRP
allocates per-task windows of appropriate size. A 4K model with CRP can
outperform a 128K model on structured tasks.

### Ring Attention (Liu et al., 2023)

Distributes attention computation across devices for near-infinite context.

### Mixture-of-Depths (Raposo et al., 2024)

Dynamically allocates computation budget per token, reducing cost for
"easy" tokens.

## Virtual Context & Memory

### MemGPT (Packer et al., 2023)

The closest prior work to CRP. MemGPT uses virtual memory paging
within a single context window - swapping information in and out like an OS.

**CRP vs MemGPT**:

<div class="cr-compare" markdown>
<div class="bad" markdown>

### MemGPT

- 1 window with paging
- Attention degraded by swaps
- LLM-based extraction
- Bounded by window size
- Requires function calling

</div>
<div class="good" markdown>

### CRP

- N dedicated windows
- Fresh attention per window
- 6-stage extraction pipeline
- Unbounded output via continuation
- Model-agnostic

</div>
</div>

### Generative Agents (Park et al., 2023)

Believable simulacra that maintain memory through reflection and retrieval.
CRP's CKF (Contextual Knowledge Fabric) draws from this for long-term
fact persistence across sessions.

### MemWalker (Chen et al., 2023)

Interactive memory navigation. Influenced CRP's graph-based fact retrieval
in the CKF.

## Prompt Compression

### LongLLMLingua (Jiang et al., 2024)

Key finding: **compression IMPROVES performance**. Removing irrelevant tokens
forces the model to focus on signal.

**CRP's response**: The envelope is signal amplification, not lossy compression.
CRP extracts the most relevant facts and presents them cleanly - this is
functionally equivalent to intelligent compression.

### Dense X Retrieval (Proposition-Level)

Propositions (atomic factual statements) are better retrieval units than
passages.

**CRP's response**: The extraction pipeline produces proposition-level facts,
not passage chunks. These are the native unit in CRP's warm state.

## Token Generation Scaling

### Speculative Decoding

Draft model generates candidate tokens, oracle model verifies. Speeds
generation without quality loss.

### Medusa (Cai et al., 2024)

Multiple decoding heads predict several tokens simultaneously.

### CRP's Innovation: Chained Generation Windows

Prior work focused on generating tokens faster. CRP focuses on generating
**more** tokens by chaining multiple windows:

$$N_{windows} \times G_{tokens/window} = \text{unbounded output}$$

Wall detection via `finish_reason: "length"` triggers the next window.
No model modification needed.

## Agent Architecture

### LLM Agents Survey (Wang et al., 2023)

Comprehensive survey of agent architectures. Identifies the need for
memory, planning, and tool use.

**CRP's response**: CRP provides the memory layer (envelope + CKF) and
planning layer (gap analysis + continuation) that agents need. Each agent
layer gets its own window - no layer starves another.

### LATS (Zhou et al., 2023)

Language Agent Tree Search - combines planning, acting, and reasoning.
CRP's agentic dispatch mode draws from this for multi-step task execution.

## Grammar-Constrained Generation

### Outlines (Willard & Louf, 2023)

FSM-based logit masking for structured output. Forces JSON/schema compliance
at the token level.

### LMQL (Beurer-Kellner et al., 2023)

Query language for constrained LLM generation.

**CRP's response**: Grammar constraints are available for user-defined schemas
(`expected_output_type: "json"` with a schema). CRP does NOT use grammar
constraints for its own protocol - the envelope is natural language.

## Extraction Without LLMs

### GLiNER (Zaratiana et al., 2023)

Generalist model for Named Entity Recognition. Zero-shot entity extraction
without LLM calls.

**CRP's response**: GLiNER powers Stage 3 of the extraction pipeline. Entity
labels are derived from the task intent, enabling zero-shot extraction
tailored to each specific task. Runs in ~50ms.

### TextRank (Mihalcea & Tarau, 2004)

Graph-based keyword extraction using co-occurrence networks.

**CRP's response**: TextRank powers Stage 2 (keyword extraction).
Graph-based, zero-cost, produces the weighted keyword set used for
envelope relevance scoring.

### BERTSum

Extractive summarization using BERT. Informs CRP's approach to selecting
representative sentences for the voice profile.

## Generation Quality

### Neural Text Degeneration (Holtzman et al., 2020)

Shows that greedy and beam search produce degenerate, repetitive text.
Nucleus sampling (top-p) produces more natural output.

**CRP's response**: CRP's information flow monitor detects degeneration
(repetitive content, declining new-fact rate) and triggers termination
rather than producing garbage.

### Self-Consistency (Wang et al., 2023)

Multiple reasoning paths sampled and majority-voted for accuracy.

**CRP's response**: CRP's progressive dispatch mode uses multiple windows
with varied prompts, then consolidates - a form of self-consistency
applied to generation.

## Meta-Learning & In-Context Learning

### MAML (Finn et al., 2017)

Model-Agnostic Meta-Learning - learning to learn from few examples.
Foundation for CRP's RTL (Reasoning Template Library).

### ICL as Implicit Gradient Descent (Dai et al., 2023)

In-context learning is functionally equivalent to gradient descent.
Justifies CRP's approach of providing few-shot examples in the envelope.

### STaR: Self-Taught Reasoner (Zelikman et al., 2022)

Models improve by learning from their own successful reasoning traces.
Foundation for CRP's trace storage and reuse.

### Distilling Step-by-Step (Hsieh et al., 2023)

**Key finding**: A 770M parameter model with step-by-step scaffolding
outperforms a 540B parameter model on certain tasks.

**CRP's response**: This directly motivates ORC (Orchestrated Reasoning
Chains). Small models with CRP scaffolding can match much larger models.

### ICL Survey (Dong et al., 2024)

Comprehensive survey of in-context learning mechanisms. Validates CRP's
multi-signal approach (facts + examples + scaffolding).

## Retrieval-Augmented Generation

### Retrieval Meets Long Context (Xu et al., 2024)

Even with 128K context, retrieval still helps. Long context and RAG are
complementary, not competing.

**CRP's response**: CRP's envelope-based approach is complementary to
native long context. Even if a model has infinite context, CRP's
extraction, quality monitoring, and continuation still add value.

### RAPTOR (Sarthi et al., 2024)

Recursive Abstractive Processing for Tree-Organized Retrieval. Hierarchical
summarization for multi-level retrieval.

**CRP's response**: CRP's CKF community detection (Leiden algorithm)
produces hierarchical fact clusters similar to RAPTOR's tree structure.

## Key Synthesis

Each research finding maps to a specific CRP design decision:

| Research Finding | CRP Design Decision |
|-----------------|-------------------|
| Attention degrades with length | Fresh windows per continuation |
| Middle content is forgotten | Signal-first envelope packing |
| Compression improves performance | Extracted facts, not raw text |
| Propositions > passages | Proposition-level fact extraction |
| Generation can be chained | Continuation via wall detection |
| Small models + scaffolding work | ORC, ICML, RTL |
| ICL is implicit learning | Few-shot traces in envelope |
| Grammar constraints exist | User schema support, not protocol |
| GLiNER for zero-shot NER | Task-derived entity extraction |
| Memory systems help agents | CKF for cross-session persistence |
| Retrieval + long context together | Envelope complements native context |
| Self-consistency improves quality | Progressive dispatch consolidation |
| Info flow detects degeneration | Continuation termination signal |

No existing system combines all of these findings into a single coherent
protocol. CRP is the integration layer.

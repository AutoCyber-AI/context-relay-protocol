---
title: "The Architecture of Understanding in Agentic AI Systems"
subtitle: "A Comprehensive Technical and Non-Technical Report on What Constitutes Machine Understanding, How to Build It with Local Small Language Models, Python Implementations, and the Role of the Context Relay Protocol (CRP)"
author: "Prepared for Constantinos Vidiniotis, AutoCyber AI Pty Ltd"
date: "July 2026"
toc: true
toc-depth: 2
numbersections: true
---

\newpage

# Executive Summary

This report answers a deceptively simple question: **what makes an AI agent understand?** Understand what it is being given, what tools to use, what to respond with, how to respond, and when to say "I don't know." The question matters more in 2026 than ever, because the industry has pivoted from monolithic large language models (LLMs) toward *agentic systems built from small language models (SLMs)* running locally — a shift formalised by NVIDIA researchers in mid-2025 and now supported by a deep bench of capable on-device models (Belcak et al., 2025). In an SLM-first world, understanding cannot be assumed to live inside the model's weights. It must be *engineered into the system* around the model.

The report makes five core arguments:

1. **Understanding is a systems property, not a model property.** Semantics — knowing what words mean — is necessary but radically insufficient. Genuine functional understanding emerges from the orchestrated interaction of at least ten distinguishable components: syntax, semantics, pragmatics, world knowledge, reasoning, memory, causal modelling, meta-cognition, normative awareness, and active information-seeking. Each is engineerable today, to different degrees, and each has concrete Python implementations covered in Part III.

2. **For SLMs, the protocol layer *is* the cognition layer.** A 3–8B parameter model cannot carry an LLM's breadth in its weights. But positioned correctly — with the right context, the right one to three tools, structured knowledge instead of flat chunks, verified reasoning scaffolds, and calibrated uncertainty signals — a small model can achieve functional understanding within scope that rivals ungoverned frontier models. This is precisely the thesis of the Context Relay Protocol (CRP) v5.1, and this report evaluates that thesis rigorously, including where it holds, where it needs extension, and where it overreaches.

3. **The single biggest gap in today's agentic stacks — CRP included — is *verification of reasoning*, not retrieval of facts.** Grounding pipelines verify claims against sources. Almost nothing verifies inference steps against logic. Process reward models, symbolic verifiers, and LLM-Modulo architectures (Kambhampati et al., 2024) close this gap and are implementable now.

4. **The second biggest gap is *predictive world modelling*.** Knowledge graphs describe what is; world models predict what will happen. The 2025–2026 neurosymbolic world-model literature (Zhou et al., 2025; and successors) shows that agents which learn action–outcome rules from their own experience dramatically outperform agents that merely retrieve facts. Agent action logs are, formally, *intervention data* — which makes agentic systems the first place where causal learning from language becomes tractable.

5. **Some things honestly do not exist.** Genuine machine comprehension (in the philosophical sense), general causal discovery from text, robust theory of mind, unified confidence calibration, and weight-level continual learning on consumer devices remain open research problems. This report is explicit about the boundary between what can be built this quarter, what can be researched this year, and what remains frontier science.

The report is structured in four parts. **Part I** teaches the foundations from first principles — no prior expertise assumed. **Part II** dissects each component of machine understanding in technical depth, surveying the 2024–2026 state of the art. **Part III** provides working Python code templates for every component, designed to run against local SLMs (Ollama, LM Studio, vLLM) and to compose into a complete understanding-oriented agent loop, with explicit CRP integration points. **Part IV** synthesises: a concrete improvement roadmap for CRP v5.1, an honest catalogue of open problems, and a prioritised build plan. Full APA 7 references follow.

\newpage

# PART I — FOUNDATIONS: WHAT UNDERSTANDING IS

# How to Read This Report

Readers come to this material from different directions. If you are non-technical, read Part I fully, skim the opening section of each chapter in Part II (each begins with a plain-language framing before the technical depth), and jump to Part IV. If you are an engineer, Part I sections 3–5 establish shared vocabulary quickly; Parts II and III are your core material. If you are evaluating or extending CRP specifically, the CRP Connection subsections throughout Part II and the roadmap in Part IV are written for you.

A note on intellectual honesty. This report distinguishes three epistemic tiers throughout, and flags them explicitly:

- **[SHIPPED]** — exists in production-grade open-source or commercial form today.
- **[RESEARCH]** — demonstrated in peer-reviewed or preprint literature, replicable, but not productised.
- **[OPEN]** — does not exist; anyone claiming otherwise is overselling.

# What "Understanding" Means: From Philosophy to Engineering

## The plain-language version

When we say a person understands a sentence, we mean something layered. They parsed the grammar (syntax). They know what the words refer to (semantics). They grasped what the speaker was *trying to do* with the sentence — request, warn, joke (pragmatics). They connected it to what they know about the world (grounding). They can draw consequences from it (inference). They can relate it to what was said five minutes ago (memory and discourse). They can predict what happens if they act on it (world modelling). They know how confident to be (meta-cognition). And they know whether acting on it would be appropriate (normativity).

Strip away any one layer and understanding degrades in a characteristic way. Someone with perfect vocabulary but no pragmatics takes "Can you pass the salt?" as a question about arm function. Someone with no world model follows instructions off a cliff. Someone with no meta-cognition asserts falsehoods with total confidence — which is precisely the signature failure mode of language models, and the reason "hallucination" is the industry's defining quality problem (Ji et al., 2023; Huang et al., 2023).

## The philosophical baseline: why this is contested at all

Searle's (1980) Chinese Room argument remains the sharpest formulation of the sceptical position: a system can manipulate symbols according to rules well enough to pass any behavioural test while understanding nothing, because syntax is not sufficient for semantics. Harnad (1990) generalised this as the **symbol grounding problem**: symbols defined only in terms of other symbols never touch the world; meaning must ultimately be anchored in non-symbolic experience.

Modern LLMs sharpen rather than resolve the puzzle. Bender and Koller (2020) argued that models trained purely on linguistic form cannot, in principle, learn meaning, coining the "octopus test." Against this, empirical work has shown that LLMs develop internal representations that track world state — board positions in Othello-playing models (Li et al., 2023), linear representations of space and time (Gurnee & Tegmark, 2024) — suggesting that *some* grounding-like structure emerges from prediction alone.

This report takes a deliberately engineering stance, following Dennett's (1987) intentional-stance pragmatism: we define **functional understanding** as *behaviour indistinguishable from understanding within a specified scope, achieved reliably, with calibrated self-knowledge of the scope boundary*. This definition is buildable, testable, and auditable — three properties the philosophical definition lacks. Whether functional understanding "really" is understanding is a question this report flags as **[OPEN]** and does not pretend to settle. What matters operationally: every component that makes human understanding work has an engineerable analogue, and systems that implement more of them fail less often, in more predictable ways, with better evidence trails.

## The ten-component model of machine understanding

Synthesising the cognitive science tradition (Marr, 1982; Lake et al., 2017) with the 2023–2026 agentic AI literature, this report organises understanding into ten components. This extends the eight-layer model explored in your earlier analysis (causal, intentional, temporal, epistemic, normative, embodied, analogical, active) by making **syntax/semantics** and **task routing/orchestration** explicit first-class layers, since in SLM-first systems both are engineered rather than assumed.

| # | Component | Question it answers | Human analogue | Primary engineering lever (2026) |
|---|-----------|--------------------|----------------|----------------------------------|
| 1 | Syntax & form | Is this well-formed? What structure? | Grammar | Tokenisation, parsing, constrained decoding |
| 2 | Semantics | What do the symbols mean? | Lexicon, concepts | Embeddings, model weights |
| 3 | Pragmatics & intent | What is the speaker doing? | Social cognition | Intent/speech-act classifiers, dialogue state |
| 4 | World knowledge | What is true of the world? | Long-term memory | RAG, knowledge graphs, ontologies |
| 5 | Reasoning & inference | What follows from this? | System-2 thinking | CoT, self-consistency, verifiers, symbolic solvers |
| 6 | Memory & temporal coherence | What happened before? | Episodic memory | Session state, temporal KGs, continuation protocols |
| 7 | Causal & world modelling | What will happen if...? | Mental simulation | Learned transition rules, neurosymbolic world models |
| 8 | Meta-cognition | How sure am I? | Feeling of knowing | Uncertainty quantification, calibration, semantic entropy |
| 9 | Normative awareness | Should I? | Conscience, norms | Policy-as-code, constitutional constraints, HITL |
| 10 | Active understanding & routing | What should I do about it, with what? | Executive function | Task routing, tool selection, clarification, escalation |

The central claim of this report — and the claim CRP's architecture embodies — is that in small-model systems, components 3 through 10 live substantially **outside the model**, in the protocol and orchestration layer. Component 2 (semantics) is the only one an SLM must carry in its weights; everything else can be scaffolded, and increasingly *should* be, because scaffolded components are inspectable, auditable, and improvable without retraining.

# Anatomy of an Agentic AI System

## What an agent is

An AI agent is a software system that pursues goals by perceiving inputs, deciding on actions, executing those actions (often via tools), observing results, and iterating — an OODA-style loop wrapped around a language model. Belcak et al. (2025) put it bluntly: an agent is "a heavily instructed and externally choreographed gateway to a language model." The choreography is where understanding is won or lost.

## The canonical agentic loop

```
              +---------------------------------------------------------+
              |                     AGENTIC LOOP                        |
              |                                                         |
   Input ---> | 1. PERCEIVE      raw text / files / tool results        |
              |        |                                                |
              | 2. INTERPRET     intent, entities, references, risk     |
              |        |          (NLU layer -- Ch. 6)                  |
              | 3. RECALL        relevant knowledge & session state     |
              |        |          (Memory + KG -- Ch. 7, 9)             |
              | 4. PLAN/ROUTE    decompose task, pick operation,        |
              |        |          pick model, pick 1-3 tools (Ch. 11)   |
              | 5. SIMULATE      predict outcome of intended action     |
              |        |          (World model -- Ch. 10) [often absent]|
              | 6. ACT           dispatch to SLM / tool / human         |
              |        |                                                |
              | 7. VERIFY        ground claims, check reasoning steps,  |
              |        |          score risk (Ch. 8, 12)                |
              | 8. LEARN         extract facts, update rules & memory,  |
              |        |          update router statistics (Ch. 9, 10)  |
              +--------+------------------------------------------------+
                       |
                Output + evidence (provenance, quality tier, audit)
```

*Figure 1. The eight-stage agentic loop. Most production agents in 2026 implement stages 1, 3, 4, 6 and a thin version of 7. Stages 2 (deep interpretation), 5 (simulation), and the rule-learning half of 8 are the differentiators this report focuses on.*

## The 2026 protocol ecosystem: MCP, A2A, and the positioning layer

Three protocol families now structure the agent stack. The **Model Context Protocol (MCP)** (Anthropic, 2024) standardises how agents discover and invoke tools. **Agent-to-Agent (A2A)** protocols (Google, 2025) standardise inter-agent messaging. Neither addresses the question this report is about: *given a task, what context, tools, and constraints should this specific model receive so that it behaves as if it understands?* That is the positioning question, and it is the layer CRP occupies — "MCP exposes tools. A2A connects agents. CRP positions every agent" (AutoCyber AI, 2026). Whatever one thinks of any specific protocol, the *layer* is real: someone must decide what goes in the window, and in SLM systems that decision dominates output quality.

## Why SLM-first changes everything

The economic and technical case, per Belcak et al. (2025) and the 2026 deployment literature:

- **Sufficiency.** Most agentic invocations are repetitive, narrow, and non-conversational (parse this, format that, extract these fields, call this API). Specialist small models match or beat generalist giants on such scoped work; fine-tuned sub-1B models have been shown to outperform frontier models on specific tool-calling and API-orchestration domains (Red Hat, 2026).
- **Economics.** Agent loops invoke models thousands of times per task; a 10–30× per-call cost difference compounds into orders of magnitude.
- **Privacy and sovereignty.** Local execution keeps data on-device — decisive for the confidentiality-bound professionals and regulated industries that are CRP's declared audience.
- **Adaptability.** SLMs fine-tune overnight on consumer GPUs; behaviour can track regulation and user needs weekly.

The cost of this shift is that **the model brings less understanding to the table**. A 4B model has thinner world knowledge, shorter effective reasoning horizons, brittler instruction following, and worse-calibrated confidence than a frontier model. Every chapter in Part II is, at bottom, an answer to the question: *how do we supply from outside what the small model lacks inside?*

# The Transformer Substrate: What the Model Itself Contributes

## Plain-language framing

A language model is a next-token predictor: given text so far, it outputs a probability distribution over what comes next. Everything a model "knows" is encoded in how those probabilities shift with context. This is simultaneously less than understanding (no goals, no persistent state, no access to truth) and more than autocomplete (accurate prediction of human text forces the compression of grammar, facts, styles of argument, and approximations of the processes that generated the text).

## What is actually in the weights

Mechanistic interpretability research gives a reasonable 2026 picture. Transformer layers implement: token and position embeddings that place words in a high-dimensional semantic space (component 2 — semantics — lives here); attention heads that implement soft pattern-matching over context, including induction heads that copy and generalise patterns (Olsson et al., 2022); and MLP layers that act as key–value stores of factual associations (Geva et al., 2021; Meng et al., 2022). Features are stored in **superposition** — more concepts than neurons, disentangleable with sparse autoencoders (Bricken et al., 2023; Templeton et al., 2024).

Practical consequences for the systems designer:

1. **Parametric knowledge is lossy, frozen, and unattributable.** A fact in the weights has no source, no timestamp, no confidence. This is why external knowledge (Ch. 7) with provenance is non-negotiable for governed systems — and why CRP's two-sided provenance treats "parametric" as one source kind among many, correctly.
2. **In-context learning is real computation.** Transformers implement something like gradient-descent-on-the-fly over the prompt (von Oswald et al., 2023). This is the mechanism that makes *positioning* powerful: a well-constructed context genuinely reconfigures the function the model computes, which is why scaffolding (Ch. 8) lets a 770M model beat a 540B model on structured tasks (Hsieh et al., 2023).
3. **Attention has geometry problems.** Models attend most reliably to the beginning and end of context — the "lost in the middle" effect (Liu et al., 2024). Envelope design (what goes where in the window) is therefore a first-order quality lever, not a detail. CRP's bookend strategy (repeating top facts at the envelope's end) is a direct, correct response to this finding.
4. **Small models degrade non-uniformly.** Compression (fewer parameters, quantisation) costs long-tail knowledge and long-horizon reasoning first, while preserving syntax, common semantics, and short-horizon pattern completion. This asymmetry is exactly why external scaffolding works: what SLMs lose is precisely what protocols can supply.

## Reasoning models and test-time compute

The 2024–2026 wave of "reasoning models" (OpenAI o1/o3, DeepSeek-R1, Qwen-with-thinking variants) established that **test-time compute is a third scaling axis** alongside parameters and data (Snell et al., 2024). DeepSeek-R1 demonstrated that reinforcement learning on verifiable rewards elicits long-chain reasoning even in distilled small models (DeepSeek-AI, 2025). The systems implication: reasoning depth is now *dialable at inference*, which means orchestration layers can trade latency for correctness per-operation — the design rationale behind depth negotiation (quick/standard/thorough/exhaustive) as a protocol primitive.

\newpage
# PART II — THE COMPONENTS OF MACHINE UNDERSTANDING

# Natural Language Understanding: Intent, Entities, Reference, and Pragmatics

## Plain-language framing

NLU is the interpretation stage: turning a raw utterance into a structured picture of *what was meant*. Classical NLU decomposes this into intent detection (what does the user want done?), entity recognition (what things are involved?), reference resolution (what do "it," "that one," "the second option" point to?), and pragmatic interpretation (is this a request, a question, a complaint, a joke; how direct; how urgent?). LLMs blurred these lines by doing all of it implicitly — but *implicit* means unauditable and, for small models, unreliable. SLM-first systems are re-explicitising NLU, because a 10 ms classifier that tags intent correctly beats a 4B model guessing.

## Intent and speech-act classification [SHIPPED]

Speech act theory (Austin, 1962; Searle, 1969) distinguishes the locutionary content of an utterance from its illocutionary force: "Can you check the contract?" is interrogative in form but directive in force. Production systems operationalise this as intent classification. The 2026 toolkit:

- **Few-shot fine-tuned classifiers**: SetFit (Tunstall et al., 2022) achieves strong intent accuracy with 8–32 examples per class by contrastively fine-tuning a sentence transformer — ideal for agent-specific intent taxonomies. Latency: ~5–15 ms on CPU.
- **Zero-shot NLI classifiers**: DeBERTa-v3 models fine-tuned on natural language inference classify arbitrary labels without training (Laurer et al., 2024).
- **Embedding-router hybrids**: embed the utterance, nearest-centroid over intent clusters; trivially updatable.

Design rule: the intent tag should travel *with* the task into the model's context. A model told "the user's intent is: request-with-uncertainty; directness: low; they may want options rather than execution" behaves measurably differently — this is positioning applied to pragmatics.

## Named entities and relation extraction [SHIPPED]

Modern zero-shot NER — GLiNER (Zaratiana et al., 2024) — matches or beats LLMs on entity extraction at a fraction of the cost, extracting arbitrary user-specified entity types with a ~300M bidirectional encoder. Universal Information Extraction (UIE) models (Lu et al., 2022) generalise this to relations and events. These are exactly the components in CRP's 6-stage extraction pipeline (regex → statistical NLP → GLiNER NER → UIE relations → RST discourse → LLM-assisted relational), which represents current best practice for graduated, cost-aware extraction. The design insight worth naming: **extraction stages should self-gate by content complexity** — spending an LLM call to extract from a log line is waste; spending only regex on a legal clause is negligence.

## Coreference and discourse deixis [SHIPPED, underused]

Reference resolution is the highest-leverage *neglected* NLU component in agentic systems. Multi-turn failures ("update it" — update *what*?) trace overwhelmingly to unresolved anaphora. State of the art: fastcoref (Otmazgin et al., 2022) for speed; Maverick (Martinelli et al., 2024) for accuracy — both run locally, both under 500M parameters. The architectural pattern that works: maintain a **session entity registry** (each entity: canonical name, type, aliases, last-mentioned turn, salience score); run coreference over the recent window; *rewrite* ambiguous references to canonical names before the text ever reaches retrieval or the model. Retrieval by similarity does not resolve reference — "it" embeds near nothing useful. Resolution must precede retrieval.

## Discourse structure [RESEARCH → SHIPPED at small scale]

Rhetorical Structure Theory (Mann & Thompson, 1988) models how spans of text relate: elaboration, contrast, cause, condition. Discourse parsing tells a system *which parts of a document carry the argumentative load* — critical for summarisation fidelity and for extracting facts with their hedges attached ("X, *however only if* Y" must not become the fact "X").

## Ambiguity detection and clarification [OPEN as a protocol primitive]

Humans handle ambiguity by asking. Agents overwhelmingly handle it by guessing. Research exists — CLAM (Kuhn et al., 2023) on selective clarification, AmbigQA (Min et al., 2020) — but **no agent protocol (MCP, A2A, or CRP as shipped) defines a first-class "clarification required" response type** with structured options, confidence, and resumption semantics. This is genuinely open protocol territory, examined in the CRP roadmap (Part IV). The engineering trigger is simple: when the intent classifier's top-2 margin is small, or two parses retrieve disjoint context, emit a clarification instead of an answer.

## CRP Connection

CRP's extraction pipeline covers entities/relations/discourse well [SHIPPED]. Missing: pre-envelope intent/speech-act tagging, session-scoped coreference rewriting, and clarification-as-protocol-primitive. All three are small components (each <500M parameters or pure logic), all three fit CRP's "position, don't inject" philosophy — they produce *metadata that shapes the envelope*, not in-window instructions.

# World Knowledge: RAG, Knowledge Graphs, and Ontologies

## Plain-language framing

A model's weights hold a compressed, undated, unsourced impression of its training data. Real systems need knowledge that is current, attributable, editable, and structured. The field's answer evolved in three waves: retrieval-augmented generation (find relevant text, paste it in), graph-structured knowledge (store *facts and their relations*, not text chunks), and ontology-grounded knowledge (constrain facts to a formal domain schema).

## Wave 1 — Vector RAG and its ceiling [SHIPPED]

Classic RAG (Lewis et al., 2020): embed documents into vectors, retrieve nearest chunks to the query, prepend to prompt. Robust, cheap, and fundamentally limited: similarity is not relevance; chunks sever cross-references; multi-hop questions ("which clauses in contract A conflict with the amendment in document B?") require *connecting* facts that no single chunk contains; and repeated retrieval re-sends the same context every turn, burning tokens.

Refinements that matter in practice: hybrid retrieval (BM25 + dense, fused with reciprocal rank fusion), cross-encoder reranking of the top-k (the bi-encoder-then-cross-encoder pattern CRP uses in 3-phase fact selection), query rewriting/HyDE (Gao et al., 2023), and late-interaction models (ColBERT; Khattab & Zaharia, 2020).

## Wave 2 — GraphRAG and knowledge fabrics [SHIPPED 2024–2026]

Microsoft's GraphRAG (Edge et al., 2024) demonstrated the pattern now considered state of practice: extract an entity–relation graph from the corpus, detect communities (Leiden algorithm; Traag et al., 2019), pre-summarise communities, and answer queries by combining graph traversal with community summaries. Gains concentrate exactly where vector RAG fails: global sensemaking questions and multi-hop reasoning. Temporal knowledge graphs (Zep/Graphiti; Rasmussen et al., 2025) add **bi-temporal modelling** — distinguishing when a fact became true from when the system learned it — which is essential for "what did we know on date X?" audit questions.

CRP's Contextual Knowledge Fabric (typed KG + HNSW vector index + Leiden community detection + event-sourced history, with four retrieval modes and coverage-differential ranking) is architecturally a GraphRAG-class system with two additions worth highlighting as genuinely differentiating: **CDR** (rank facts by *novelty relative to what the session already knows* — an anti-redundancy criterion missing from mainline GraphRAG) and **event-sourcing** (append-only fact log, enabling temporal reconstruction). The one mainline idea CKF should absorb from Graphiti is explicit bi-temporal validity intervals on facts (valid-from/valid-to vs recorded-at), rather than recency scoring alone.

## Wave 3 — Ontology grounding [RESEARCH → early SHIPPED]

An ontology is a formal schema of a domain: entity types, permissible relations, constraints. Ontology-constrained systems restrict what the extraction layer may assert and what the reasoning layer may conclude. Evidence is accumulating that this is a large lever: OG-RAG reported +55% fact recall from ontological structuring (Sharma et al., 2025), and enterprise neurosymbolic deployments report large accuracy gains from three-layer ontological grounding across industry verticals (Bhattacharya et al., 2026). For domain-authoritative agents (CRP SPEC-044's "Authoritative Domain Agent"), an optional ontology layer over CKF types is the natural next step: the graph stops being "whatever extraction found" and becomes "facts legal under the domain schema" — with schema violations surfacing as extraction-quality signals.

## The knowledge stack, summarised

```
   Query
     |
     v
  +---------------------------+     +---------------------------+
  | RESOLUTION (Ch.6)         |     |  KNOWLEDGE STORE          |
  | coref-rewritten query     |     |                           |
  +------------+--------------+     |  Ontology (types, rules)  |
               |                    |        ^                  |
               v                    |  Typed KG (facts, edges,  |
  +---------------------------+    |   provenance, validity)   |
  | HYBRID RETRIEVAL           |<-->|        ^                  |
  | BM25 + dense + graph walk  |    |  Vector index (HNSW)     |
  +------------+--------------+    |        ^                  |
               |                    |  Raw documents / events   |
               v                    +---------------------------+
  +---------------------------+
  | RERANK (cross-encoder)     |
  | + novelty filter (CDR)     |
  +------------+--------------+
               |
               v
        Scored facts -> envelope
```

*Figure 2. The 2026 knowledge stack. Every layer adds a property: vectors add recall, graphs add relations and multi-hop, ontologies add validity, event-sourcing adds time, provenance adds accountability.*

# Reasoning and Inference: From Chain-of-Thought to Verified Cognition

## Plain-language framing

Reasoning is deriving what follows. Language models do not reason the way logic engines do; they *generate text that resembles reasoning*, and the resemblance is good enough often enough to be useful — and wrong often enough to be dangerous. The decade's central discovery is that reasoning quality is not fixed by the model: it is a function of **how generation is structured and whether it is verified**. This chapter covers the full ladder, from prompting patterns to formal verification.

## Rung 1 — Elicitation: chain-of-thought and its family [SHIPPED]

Chain-of-thought prompting (Wei et al., 2022) — induce intermediate steps before the answer — remains the foundational move; zero-shot CoT ("let's think step by step"; Kojima et al., 2022) made it free. Least-to-most prompting (Zhou et al., 2023) decomposes problems into ordered subproblems, which is the direct ancestor of orchestrated micro-step decomposition (CRP's ORC). Crucial small-model caveat: raw CoT can *hurt* models under ~7B, which produce plausible-but-broken chains; small models need *externally structured* decomposition (the orchestrator holds the plan, the model executes one micro-step per window) rather than free-form thinking. This is the empirical basis of the claim that scaffolding lets a 770M model beat a 540B model on structured tasks (Hsieh et al., 2023): the scaffold carries the plan the small model cannot hold.

## Rung 2 — Aggregation: self-consistency and search [SHIPPED]

Self-consistency (Wang et al., 2023): sample N reasoning paths, majority-vote the answer. Beyond accuracy, the *disagreement rate across samples* is a free, well-calibrated uncertainty signal (see Ch. 12). Tree-of-Thoughts (Yao et al., 2023) generalises to explicit search over reasoning states with lookahead and backtracking — expensive, and worth it only for genuine planning problems. Monte-Carlo tree search variants over reasoning steps power the strongest math systems.

## Rung 3 — Verification: process reward models and LLM-Modulo [RESEARCH → SHIPPED]

The decisive 2023–2026 shift: from verifying *answers* to verifying *steps*. Process supervision — training a verifier to score each reasoning step — significantly outperforms outcome-only supervision (Lightman et al., 2023), and process reward models (PRMs) are now the standard quality mechanism in frontier reasoning systems and are distillable into sub-2B verifiers deployable locally.

Complementary and philosophically important: Kambhampati et al. (2024) argue LLMs **cannot plan but can help planning** in "LLM-Modulo" frameworks — the LLM generates candidates; external sound verifiers (logic checkers, simulators, constraint solvers) critique; the loop iterates until the verifier accepts. This resolves the "do LLMs reason?" debate operationally: it doesn't matter, if the system only emits verified conclusions.

Deterministic verifiers available today, all local, all free:

- **Arithmetic/algebra**: SymPy; or generated Python executed in a sandbox (program-aided language models, PAL; Gao et al., 2023).
- **Logical constraints/scheduling/configuration**: Z3 SMT solver (de Moura & Bjørner, 2008).
- **Rule-based domain checks**: datalog engines; Prolog via PySwip.
- **KG-faithful reasoning**: graph-constrained decoding restricts generation to paths that exist in the knowledge graph (Luo et al., 2024) — the model literally cannot assert an edge the graph lacks.

## Rung 4 — Trained reasoning: RL on verifiable rewards [SHIPPED in models]

DeepSeek-R1 (DeepSeek-AI, 2025) showed reinforcement learning against automatically checkable rewards elicits emergent long-chain reasoning, and that these behaviours distil into small models — the reason 2026's 4–8B local models reason far better than their 2024 ancestors. Systems consequence: the orchestration layer should *know which model variant it holds* (thinking vs instruct) and budget tokens accordingly.

## Rung 5 — Neurosymbolic integration [RESEARCH]

The research frontier fuses neural generation with symbolic structure bidirectionally: symbolic knowledge constrains neural generation (graph-constrained reasoning, ontology grounding), and neural models induce symbolic artefacts (rules, programs, graphs) that are then executed soundly. Surveys (Hakim et al., 2026) catalogue the integration patterns. Part of what makes this practical now is that code is the interlingua: LLMs write programs; programs execute deterministically; results ground the next generation.

## The reasoning ladder, summarised

| Rung | Technique | Cost | What it buys | Small-model fit |
|------|-----------|------|--------------|-----------------|
| 1 | CoT / decomposition | ~1× | Elicits latent capability | Needs external scaffold <7B |
| 2 | Self-consistency (N samples) | N× | Accuracy + free uncertainty | Excellent (cheap samples) |
| 3a | PRM step verification | +0.3–1× | Catches broken chains | Verifier can be tiny |
| 3b | Symbolic verifiers | ~0 | Soundness where formalisable | Perfect |
| 4 | Reasoning-tuned model | 1–5× tokens | Native long chains | Now available at 4–8B |
| 5 | Neurosymbolic loop | varies | Verified novel conclusions | The target architecture |

## CRP Connection

CRP's ORC/ICML/RTL triad covers rung 1 thoroughly and rung 2 partially (ROS, SPEC-021, includes self-consistency). The material gaps are rung 3 — no step-level verification stage exists in the 13-stage DPE (which verifies claims-vs-sources, not steps-vs-logic) and no symbolic-verifier dispatch targets exist — and the wiring of self-consistency divergence into quality tiers and risk. These are the two highest-value reasoning upgrades and are specified concretely in Part IV.

\newpage
# Memory and Temporal Coherence

## Plain-language framing

Understanding accumulates. A system that meets every conversation as a stranger, or that forgets section 3 while writing section 20, does not understand in any useful sense. Cognitive science distinguishes working memory (what you're holding right now), episodic memory (what happened), semantic memory (what you know), and procedural memory (what you know how to do). The 2024–2026 agent-memory literature has converged on exactly this taxonomy.

## The four memories, engineered

- **Working memory = the context window**, managed. The core disciplines: envelope construction (what goes in, in what order — priority-ordered sections, protection against mid-window attention loss), and compaction (summarise-and-replace as the window fills). MemGPT (Packer et al., 2023) established the OS metaphor — context as RAM, external store as disk, with paging — that Letta and most 2026 frameworks now implement.
- **Episodic memory = event logs and session state.** Append-only event streams with periodic snapshots (event sourcing) give perfect reconstructability — which doubles as the audit substrate. CRP's event-sourced fact model and window DAG are this pattern.
- **Semantic memory = the knowledge fabric** (Ch. 7), with consolidation: periodic jobs that deduplicate, resolve contradictions between old and new facts, decay stale relevance, and promote repeated episodic patterns into stable facts. Mem0 (Chhikara et al., 2025) productised extract-update-resolve consolidation; Graphiti added temporal validity.
- **Procedural memory = reusable skills and reasoning traces.** Voyager (Wang et al., 2023) demonstrated agents that write, verify, and store executable skills for reuse; CRP's Reasoning Template Library (store and reuse high-quality reasoning traces) is the reasoning-trace analogue. The upgrade path for any RTL-style system: store traces *with their PRM verification scores and outcome quality*, retrieve by task-type similarity, and prune traces whose reuse correlates with poor outcomes — turning a template library into a self-curating skill store.

## Long-horizon coherence: the continuation problem

Generation beyond one output window is a memory problem in disguise: the model must remain consistent with commitments it can no longer see. The naive fix (resend everything) hits quadratic cost; the correct fixes are (a) a compact, typed state object carried between windows — established facts, decisions taken, open questions, dependencies — and (b) *measured-drift re-grounding*: monitor degradation (repetition, contradiction with established state, vocabulary collapse) and rebuild state from accumulated output when a threshold is crossed. CRP's Cognitive State Object relay and 15%-degradation re-grounding are, to this report's knowledge, the most explicit protocol-level treatment of this pattern in the field [SHIPPED, differentiated]. The published benchmark (11.8× more content completed, 25/30 vs 8/30 sections) is consistent with what the mechanism should deliver.

## What memory still cannot do [OPEN]

Weight-level continual learning — the model itself improving from experience without catastrophic forgetting — remains unsolved for deployed systems (Kirkpatrick et al., 2017, and the decade since). Everything above is *context-level* learning: the system learns; the model does not. This is an acceptable trade (context-level learning is auditable and reversible; weight-level is neither), but it bounds what "the agent got smarter" can honestly mean.

# Causal and World Modelling: From Describing to Predicting

## Plain-language framing

A knowledge graph answers "what is true?" A world model answers "what will happen if I do X?" The difference is the difference between a library and a flight simulator, between correlation and causation (Pearl, 2009), and — in Pearl's ladder of causation — between rung one (seeing), rung two (doing), and rung three (imagining). Almost every deployed agent in 2026 lives entirely on rung one. This is the deepest gap in machine understanding, and the one where the research frontier moved fastest in 2024–2026.

## Why prediction is the hard core of understanding

An agent that cannot predict consequences cannot plan (it can only react), cannot be safe proactively (only stopped reactively), and cannot distinguish a reversible action from an irreversible one. LeCun's (2022) JEPA programme makes the general argument: intelligence requires predictive models of the world learned largely by observation. For language agents the tractable version arrived via a different route.

## LLMs as world models, aligned neurosymbolically [RESEARCH, rapidly maturing]

The breakthrough pattern (WALL-E, Zhou et al., 2024; WALL-E 2.0, Zhou et al., 2025): use the LLM's broad priors as a base world model, then **align it to the specific environment by learning symbolic artefacts from experience** — action rules, knowledge graphs, scene graphs, induced as code by comparing the LLM's predictions against observed outcomes. The aligned agent plans against the rule-corrected model. Results: 16–52% success-rate improvements over baselines and a 98% ALFWorld success rate after only four alignment iterations (Zhou et al., 2025). The 2026 extensions treat symbolic scores as an energy term modulating the neural model's distribution (neuro-symbolic synergy for world modelling) and extend text world models to enterprise workflow environments and computer use (Gupta et al., 2026; Guan et al., 2026).

The generalisable recipe:

1. Log every (state, action, outcome) triple the agent experiences.
2. Where the base model's predicted outcome diverges from the observed one, induce a rule (as code or structured pattern) that corrects the divergence.
3. Keep rules that keep predicting correctly; discard those that don't.
4. Before acting, check proposed actions against the rule set; before *risky* actions, simulate.

## The causal insight nobody exploits: agent actions are interventions

Causal discovery from observational text is unreliable — text reports claimed causality, not verified causality, and identification formally requires interventions or strong assumptions (Pearl, 2009). But an agent's own actions **are interventions**: the agent did X in state S and observed O. An action log is, formally, a stream of do-operations. This makes agentic systems the first mainstream setting where genuine causal rule learning from language-mediated experience is tractable — a point the world-model literature exploits implicitly and almost no protocol or product exploits explicitly. [RESEARCH opportunity, arguably publishable.]

## CRP Connection

This is CRP's largest architectural opportunity, because CRP already owns every prerequisite: the positioned tool loop captures every action; Tier-E ephemeral context captures every tool result; the event-sourced CKF can store induced rules as typed nodes; the safety control plane provides the natural enforcement point ("simulate-before-act on HIGH risk"). What's missing is only the rule-induction pass and the pre-dispatch rule check — a "Predictive Positioning" layer specified in Part IV. It would also upgrade the compliance story: EU AI Act Article 14 human oversight becomes *anticipatory* (checkpoint on predicted violation) rather than reactive (checkpoint on detected violation).

# Task Routing, Orchestration, and Active Understanding

## Plain-language framing

Understanding culminates in doing the right thing: choosing what operation the task requires, which model should perform it, which tools it needs, how much effort to spend, and whether to ask before acting. In humans this is executive function. In agentic systems it is the router/orchestrator — and in SLM-first systems it is *the* determinant of perceived intelligence, because the whole SLM thesis rests on matching narrow tasks to sufficient models (Belcak et al., 2025).

## The routing decision space

Every inbound task implies five simultaneous choices:

1. **Operation**: which step of which workflow is this? (intent → operation mapping)
2. **Model**: which of the available models is sufficient? (capability-aware selection)
3. **Tools**: which minimal tool set? (the fewer the better — small models degrade sharply as tool count and schema complexity grow)
4. **Depth**: how much test-time compute? (quick single pass vs sampled-and-verified)
5. **Autonomy**: act, simulate-then-act, ask-first, or refuse?

## Learned routing [SHIPPED]

RouteLLM (Ong et al., 2024) and successors established that a small trained router choosing between weak and strong models can retain ~90–95% of strong-model quality at a fraction of the cost. The training signal problem — where do routing labels come from? — has an elegant answer in any system that scores its own outputs: **log (task features, routing decision, outcome quality) and train the router on your own telemetry.** Systems with built-in quality scoring get router supervision for free. This is a self-improving flywheel: routing improves → quality labels improve → routing improves.

## The escalation ladder [SHIPPED as pattern]

The converged 2026 SLM-first deployment pattern: attempt locally with the small model; monitor failure signals (low quality score, low self-consistency, verifier rejection, low confidence); escalate to a larger local model, then to a frontier API, only on signal. Break-even analyses show most loop steps never escalate. The pattern needs only three primitives: per-model capability profiles (benchmarked, not assumed), calibrated failure signals (Ch. 12), and a policy language to express thresholds ("escalate when quality < B").

## Tool selection and schema adaptation for SLMs [RESEARCH → SHIPPED]

Two robust findings. First, *tool subset minimisation*: presenting a small model with 1–3 relevant tools rather than a full catalogue dramatically improves call accuracy — the design CRP's positioned tool loop implements. Second, *adapt schemas to models, not models to schemas* (Kim et al., 2025): SLMs fail on deeply nested JSON schemas that frontier models tolerate; flattening structures, renaming parameters to natural language, and constraining enums recovers most of the gap without any fine-tuning. Third, enforce validity mechanically: **grammar-constrained decoding** (Outlines, Willard & Louf, 2023; XGrammar, llguidance) makes malformed tool calls *impossible* at the token level rather than detectable after the fact — the single cheapest reliability win in local agent engineering.

## Clarification as a routing outcome [OPEN as protocol]

The fifth routing choice — ask instead of act — is where current stacks are weakest (Ch. 6). A complete router treats "emit structured clarification request" as a first-class operation with the same telemetry as any other, so the system also *learns when asking pays off*.

## CRP Connection

The positioned tool loop is the right chassis. The upgrades: (1) make the router a trained component supervised by CRP's own quality tiers — CRP is unusually well-positioned here because it already logs all three elements of the training triple; (2) per-model capability profiles measured by the Semantic Quality Benchmark (SPEC-026) driving heterogeneous-fleet routing; (3) `escalate-on` as a Safety Policy Directive verb; (4) a schema-simplification transform per model profile; (5) grammar-constrained decoding enforced at the Gateway. Detailed in Part IV.

# Meta-Cognition: Uncertainty, Calibration, and Knowing What You Don't Know

## Plain-language framing

The most human thing a system can say is "I'm not sure." Hallucination is not primarily a knowledge failure — it is a *calibration* failure: the model asserts with identical fluency whether it knows or guesses. Meta-cognition is the layer that attaches honest confidence to every output and routes low-confidence cases to verification, retrieval, escalation, or humans.

## The measurable signals [SHIPPED / RESEARCH]

- **Token-level probability** (logprobs, perplexity of the answer span): cheap, weak alone, useful in ensembles.
- **Self-consistency divergence**: sample N answers; the entropy of the answer distribution is a strong correctness predictor at N as low as 3–5 (Wang et al., 2023) — the best *free* signal in systems already sampling for quality.
- **Semantic entropy** (Farquhar et al., 2024, *Nature*): cluster sampled answers by *meaning* (bidirectional entailment), compute entropy over meaning-clusters — detects confabulations markedly better than lexical methods. Semantic entropy *probes* (Kossen et al., 2025) approximate it from hidden states at near-zero cost.
- **Verbalised confidence**: asking the model to state confidence is weakly calibrated in small models — usable only after per-model recalibration.
- **Conformal prediction** (Angelopoulos & Bates, 2023): distribution-free wrapper that converts any score into sets with guaranteed coverage ("with 90% coverage, the answer is in this set") — the right formal tool when you must make statistical guarantees to a regulator.
- **Faithfulness/grounding scores** (NLI-based entailment of each claim against retrieved sources): the deployed workhorse of hallucination detection, and the core of CRP's DPE.

## Calibration as an asset [largely OPEN in products]

A signal is only useful if thresholded correctly *for this model on this task type*. The practice that should be standard and almost never is: maintain per-model, per-task-type **calibration curves** — predicted confidence vs verified correctness over time — and set policy thresholds from the curves, not from vibes. A system that knows "model M is overconfident by ~20 points on legal reasoning" can position accordingly (stricter grounding thresholds, mandatory verification). No shipped protocol maintains such epistemic profiles; Part IV specifies one for CRP.

## Abstention and honesty

The end state of meta-cognition is principled abstention: below threshold, the system retrieves more, verifies, escalates, asks, or declines — and says which and why. R-Tuning and related work show models can be tuned to refuse beyond their knowledge (Zhang et al., 2024); at the system level, abstention should be a *routing outcome with provenance*, not an apology.

# Normative Understanding, Grounding, and the Remaining Layers

## Normative awareness [SHIPPED at the system level]

Understanding "you should not share PII" requires treating norms as constraints, not content. The two operative mechanisms: **training-time values** (Constitutional AI; Bai et al., 2022) and **runtime policy-as-code** — declarative rules enforced at a layer the application cannot skip, with evidence that they ran. The 2024–2026 regulatory wave (EU AI Act, Regulation 2024/1689; ISO/IEC 42001:2023; NIST AI RMF) effectively mandates the runtime layer, and the universal audit failure it exposes is proof-of-operation, not existence-of-policy. This is CRP's home turf and its most defensible differentiation: declarative safety policy at the wire level, HMAC-chained evidence that controls operated, generated from runtime rather than paperwork. The report notes it and moves on: this layer is the one CRP does *not* need to be told how to build.

## Embodied and multimodal grounding [SHIPPED multimodal; OPEN embodied-local]

Multimodal SLMs (vision-language models at 2–8B) now run locally and ground language in pixels, charts, and documents — sufficient for the document-centric grounding an office agent needs. Sensorimotor grounding (Harnad's full answer) remains the province of robotics labs; no consumer-hardware path exists yet. Honest scope statement: local agents in 2026 ground in *documents and interfaces*, not in the physical world.

## Analogy and abstraction [RESEARCH]

Structure-mapping theory (Gentner, 1983) holds that analogy is alignment of relational structure, not surface similarity — which implies graph-structured knowledge is the natural substrate for analogical retrieval (find subgraphs isomorphic to the current problem's structure). Preliminary graph-based analogical retrieval exists in research; nothing production-grade. A knowledge fabric with typed edges is halfway there structurally; the retrieval mode is unbuilt.

## Theory of mind [OPEN]

Benchmarks show LLMs pass some false-belief tests and fail perturbed variants (Ullman, 2023); collaborative belief-state tracking exists in multi-agent research settings (zeroth- and first-order belief worlds updated Bayesian-style). Nothing production-grade models the *user's* evolving beliefs and goals beyond coarse identity/preference records. Honest status: fragments only.

\newpage
# PART III — BUILDING IT: PYTHON TEMPLATES FOR LOCAL, UNDERSTANDING-ORIENTED AGENTS

The templates below are designed as a coherent set: consistent interfaces, local-first (every model runs on consumer hardware), and composable into the complete agent loop in Chapter 20. They target Python 3.11+. Each template states its dependencies, its role in the ten-component model, and its CRP integration point. Code is written for clarity over micro-optimisation; each template is a starting point intended to be adapted, exactly as requested.

# The Local SLM Substrate

Every subsequent template talks to a local model through the OpenAI-compatible API that Ollama, LM Studio, vLLM, and llama.cpp's server all expose. This uniformity is the practical miracle of the 2026 local stack — and it is also precisely the interception point that makes gateway-style governance (one `base_url` change) possible.

```python
# substrate.py — one client for any local runtime (and any gateway in front of it)
# pip install openai
from openai import OpenAI
from dataclasses import dataclass, field

@dataclass
class ModelProfile:
    """Capability profile for heterogeneous-fleet routing (Ch. 11, 19).
    Populate `skill` scores from your own benchmark runs, never from vibes."""
    name: str
    context_len: int
    reasoning_variant: bool          # thinking-mode model?
    skill: dict = field(default_factory=dict)   # e.g. {"code": .78, "extract": .91}
    schema_complexity_max: int = 2   # max JSON nesting this model handles reliably

# The fleet: swap base_url to route through a governance gateway (e.g. CRP Gateway)
LOCAL = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")   # Ollama
# LOCAL = OpenAI(base_url="http://localhost:1234/v1", api_key="lmstudio") # LM Studio
# LOCAL = OpenAI(base_url="https://your-crp-gateway.example/v1", api_key=KEY)

FLEET = {
    "fast":   ModelProfile("qwen3:4b",  32_768, reasoning_variant=False,
                           skill={"extract": .90, "route": .88, "chat": .80}),
    "smart":  ModelProfile("qwen3:14b", 32_768, reasoning_variant=True,
                           skill={"code": .82, "reason": .84, "chat": .88}),
}

def complete(model: str, system: str, user: str, *, temperature=0.2,
             max_tokens=1024, n=1) -> list[str]:
    r = LOCAL.chat.completions.create(
        model=model, temperature=temperature, max_tokens=max_tokens, n=n,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    return [c.message.content for c in r.choices]
```

Sizing guidance for consumer hardware: 3–4B models (Q4 quantisation) fit comfortably in 8 GB and handle extraction/routing/formatting; 7–8B in 12–16 GB handle general chat and moderate reasoning; 14B in 24 GB (or unified-memory Macs) is the local reasoning workhorse; escalate beyond that to APIs. Quantisation to 4-bit costs little on scoped tasks and much on long-tail knowledge — one more reason the knowledge lives outside the model.

# Template: Intent and Speech-Act Classification (Component 3)

Role: convert each utterance into structured pragmatics *before* routing. Two implementations: a zero-shot NLI classifier (works today, no training data) and a SetFit fine-tune (better, needs 8–32 examples per class).

```python
# intent.py — pip install transformers sentence-transformers setfit torch
from transformers import pipeline
from dataclasses import dataclass

SPEECH_ACTS = ["a direct request to perform an action",
               "a question seeking information",
               "a statement providing information",
               "an expression of feeling or opinion",
               "an ambiguous or underspecified message"]

INTENTS = ["search or look something up", "create or write content",
           "modify existing content", "analyze or summarize",
           "execute a tool or workflow", "small talk or social"]

_zs = pipeline("zero-shot-classification",
               model="MoritzLaurer/deberta-v3-base-zeroshot-v2.0")  # ~180M, CPU-fast

@dataclass
class Interpretation:
    speech_act: str; intent: str
    act_conf: float; intent_conf: float; margin: float
    needs_clarification: bool

def interpret(utterance: str, clarify_margin: float = 0.15) -> Interpretation:
    a = _zs(utterance, SPEECH_ACTS)
    i = _zs(utterance, INTENTS)
    margin = i["scores"][0] - i["scores"][1]           # top-2 gap = ambiguity signal
    return Interpretation(
        speech_act=a["labels"][0], intent=i["labels"][0],
        act_conf=a["scores"][0], intent_conf=i["scores"][0], margin=margin,
        needs_clarification=(margin < clarify_margin or i["scores"][0] < 0.35))

# --- Upgrade path: few-shot SetFit when you have examples -------------------
# from setfit import SetFitModel, Trainer
# model = SetFitModel.from_pretrained("BAAI/bge-small-en-v1.5")
# Trainer(model=model, train_dataset=your_8_to_32_examples_per_class).train()
# -> 5-15 ms CPU inference; retrain in minutes as your taxonomy evolves.
```

CRP integration point: the `Interpretation` object becomes envelope metadata — the operation selector consumes `intent`, the clarification protocol (Ch. 20) consumes `needs_clarification`, and the speech-act tag is rendered as one line in the task brief ("User's communicative intent: question, not a request to act").

# Template: Entities and Coreference (Components 1, 3, 6)

Role: extract typed entities zero-shot (GLiNER) and rewrite ambiguous references against a session entity registry *before* retrieval, so "update it" retrieves what "it" is.

```python
# resolve.py — pip install gliner fastcoref
from gliner import GLiNER
from fastcoref import FCoref
from dataclasses import dataclass, field

ner = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")   # ~300M, zero-shot NER
coref = FCoref()                                             # fast neural coreference

@dataclass
class EntityRegistry:
    """Session-scoped discourse memory: who/what has been mentioned, how recently."""
    entities: dict = field(default_factory=dict)   # canonical -> {type, aliases, last_turn}

    def update(self, text: str, turn: int, labels=("person","organization",
               "document","system","product","task")):
        for e in ner.predict_entities(text, list(labels), threshold=0.45):
            key = e["text"].strip().lower()
            rec = self.entities.setdefault(key, {"type": e["label"],
                                                 "aliases": set(), "last_turn": turn})
            rec["last_turn"] = turn

    def most_salient(self, etype: str | None = None):
        pool = [(k, v) for k, v in self.entities.items()
                if etype is None or v["type"] == etype]
        return max(pool, key=lambda kv: kv[1]["last_turn"])[0] if pool else None

def rewrite_references(history: list[str], current: str) -> str:
    """Resolve pronouns/deixis in `current` against recent history; return a
    rewritten utterance safe to embed, retrieve with, and show to a small model."""
    doc = " ".join(history[-6:]) + " " + current
    pred = coref.predict(texts=[doc])[0]
    resolved = current
    for cluster in pred.get_clusters(as_strings=True):
        # canonical mention = longest non-pronoun string in the cluster
        canon = max((m for m in cluster if len(m.split()) > 0), key=len)
        for mention in cluster:
            if mention.lower() in {"it","this","that","they","them","he","she",
                                   "the former","the latter","this one"}:
                if mention in resolved:
                    resolved = resolved.replace(mention, canon, 1)
    return resolved
```

CRP integration point: run `rewrite_references` on the user turn before CDR/CDGR retrieval; feed GLiNER entities into the CKF as discourse-mention nodes linked to their canonical knowledge nodes. This is the "resolution precedes retrieval" rule from Chapter 6 made concrete.

# Template: Graph Memory with Provenance and Bi-Temporal Validity (Components 4, 6)

Role: a minimal but honest knowledge fabric — typed facts with sources, confidence, validity intervals, embeddings for semantic recall, graph edges for multi-hop, and a novelty filter so the same facts aren't resent every turn (the CDR idea).

```python
# fabric.py — pip install networkx sentence-transformers numpy
import time, hashlib, numpy as np, networkx as nx
from sentence_transformers import SentenceTransformer

emb = SentenceTransformer("BAAI/bge-small-en-v1.5")    # 33M params, CPU-fine

class Fabric:
    def __init__(self):
        self.g = nx.MultiDiGraph()
        self.vecs: dict[str, np.ndarray] = {}
        self.sent_hashes: set[str] = set()             # session novelty memory (CDR-lite)

    def assert_fact(self, subj, rel, obj, *, source, confidence=0.8,
                    valid_from=None, valid_to=None, causal=False):
        """Bi-temporal: `valid_from/to` = when true in the world;
        `recorded_at` = when the system learned it. `causal=True` marks
        intervention-grade edges (learned from the agent's own actions)."""
        fid = hashlib.blake2s(f"{subj}|{rel}|{obj}".encode(), digest_size=8).hexdigest()
        self.g.add_node(subj); self.g.add_node(obj)
        self.g.add_edge(subj, obj, key=fid, rel=rel, source=source,
                        confidence=confidence, causal=causal,
                        valid_from=valid_from, valid_to=valid_to,
                        recorded_at=time.time())
        self.vecs[fid] = emb.encode(f"{subj} {rel} {obj}", normalize_embeddings=True)
        return fid

    def semantic(self, query: str, k=8):
        q = emb.encode(query, normalize_embeddings=True)
        scored = sorted(self.vecs.items(), key=lambda kv: -float(q @ kv[1]))[:k*3]
        return [self._edge(fid) for fid, _ in scored][:k*3]

    def neighborhood(self, node: str, hops=2):
        if node not in self.g: return []
        nodes = nx.single_source_shortest_path_length(self.g.to_undirected(), node,
                                                      cutoff=hops)
        return [self._fmt(u, v, d) for u, v, kk, d in self.g.edges(keys=True, data=True)
                if u in nodes and v in nodes]

    def retrieve(self, query: str, anchors: list[str] = (), k=8) -> list[str]:
        """Hybrid semantic + graph-walk retrieval with a novelty gate:
        facts already sent this session are suppressed (coverage-differential)."""
        cands = self.semantic(query, k)
        for a in anchors: cands += self.neighborhood(a, hops=2)
        fresh = []
        for line in dict.fromkeys(cands):              # dedupe, keep order
            h = hashlib.blake2s(line.encode(), digest_size=8).hexdigest()
            if h not in self.sent_hashes:
                fresh.append(line); self.sent_hashes.add(h)
            if len(fresh) == k: break
        return fresh

    def _edge(self, fid):
        for u, v, kk, d in self.g.edges(keys=True, data=True):
            if kk == fid: return self._fmt(u, v, d)
    @staticmethod
    def _fmt(u, v, d):
        tag = "CAUSAL " if d.get("causal") else ""
        return f"{tag}{u} --{d['rel']}--> {v}  [src={d['source']}, conf={d['confidence']:.2f}]"
```

Scaling notes: replace the dict vector store with hnswlib or sqlite-vec at >50k facts; add Leiden community detection (`pip install graspologic` or igraph+leidenalg) and pre-summarised communities for GraphRAG-style global questions; persist with SQLite and treat every `assert_fact` as an append-only event for audit reconstruction — at which point you have rebuilt, deliberately, the skeleton of a CKF.

# Template: Verified Reasoning — Self-Consistency + Symbolic Verifier + Step Judge (Component 5)

Role: the rung-1-through-3 ladder from Chapter 8 in one composable function: decompose externally, sample multiple chains, verify formally where possible, judge steps where not, and emit *calibrated* confidence from agreement.

```python
# reason.py — pip install sympy
import re, collections, contextlib, io
from substrate import complete
from sympy import sympify

def _extract_final(text: str) -> str | None:
    m = re.search(r"FINAL:\s*(.+)", text)
    return m.group(1).strip() if m else None

def _sandbox_python(code: str) -> str:
    """Deterministic verifier for computable claims (PAL pattern).
    NOTE: for production use a real sandbox (subprocess + seccomp, or a jail)."""
    buf = io.StringIO()
    allowed = {"__builtins__": {"range": range, "len": len, "sum": sum, "min": min,
                                "max": max, "abs": abs, "round": round, "print": print}}
    with contextlib.redirect_stdout(buf):
        exec(code, allowed, {})
    return buf.getvalue().strip()

def step_judge(model: str, facts: list[str], step: str, prior_steps: list[str]) -> bool:
    """A tiny process-reward check: is this step entailed by facts + prior steps?
    In production, distil this into a dedicated <2B verifier for 10x speed."""
    verdict = complete(model,
        "You are a strict logic checker. Answer only VALID or INVALID.",
        f"FACTS:\n" + "\n".join(facts) +
        f"\n\nPRIOR STEPS:\n" + "\n".join(prior_steps) +
        f"\n\nPROPOSED STEP:\n{step}\n\nIs the proposed step logically justified?")[0]
    return "VALID" in verdict.upper()

def reason(task: str, facts: list[str], *, model="qwen3:14b",
           n_samples=5, verify_steps=True) -> dict:
    system = ("Reason step by step using ONLY the provided facts. "
              "Number each step. End with a line 'FINAL: <answer>'.")
    user = "FACTS:\n" + "\n".join(f"- {f}" for f in facts) + f"\n\nTASK: {task}"
    chains = complete(model, system, user, temperature=0.7, n=n_samples,
                      max_tokens=1500)

    votes, kept = collections.Counter(), []
    for ch in chains:
        ans = _extract_final(ch)
        if ans is None: continue
        if verify_steps:
            steps = [s for s in ch.splitlines() if re.match(r"\s*\d+\.", s)]
            if steps and not all(step_judge("qwen3:4b", facts, s, steps[:i])
                                 for i, s in enumerate(steps)):
                continue                        # discard chains with a broken step
        votes[ans] += 1; kept.append(ch)

    if not votes:
        return {"answer": None, "confidence": 0.0, "abstain": True,
                "reason": "no chain survived verification"}
    answer, top = votes.most_common(1)[0]
    confidence = top / max(1, len(kept))        # agreement rate = calibrated-ish signal

    # Symbolic escape hatch: if the answer is numeric, confirm it deterministically
    if re.fullmatch(r"-?\d+(\.\d+)?", answer or ""):
        with contextlib.suppress(Exception):
            check = complete(model, "Write ONLY Python that prints the answer "
                             "to the task. No prose.", user, max_tokens=400)[0]
            code = re.sub(r"^```(python)?|```$", "", check.strip(), flags=re.M)
            if _sandbox_python(code) == answer:
                confidence = max(confidence, 0.95)
    return {"answer": answer, "confidence": confidence,
            "abstain": confidence < 0.5, "samples": len(kept), "votes": dict(votes)}
```

The three quality mechanisms compose: agreement across samples supplies calibrated confidence for free; the step judge kills fluent-but-broken chains (the small-model signature failure); the symbolic check makes computable claims *sound* rather than probable. CRP integration point: `confidence` feeds the quality tier; a `False` from the step judge is precisely the missing "stage 14" of the DPE; the sandbox and SymPy are verifier dispatch targets.

# Template: Grammar-Constrained Tool Calls (Components 1, 10)

Role: make invalid tool calls impossible rather than detectable — structured generation at the token level, the cheapest reliability win in local agents.

```python
# constrained.py — pip install outlines pydantic
import outlines
from pydantic import BaseModel, Field
from typing import Literal

class ToolCall(BaseModel):
    """Flat, SLM-friendly schema (Ch. 11: adapt schemas to models)."""
    tool: Literal["search_docs", "read_file", "send_summary", "none"]
    argument: str = Field(description="single string argument for the tool")
    why: str = Field(max_length=200)

model = outlines.models.openai("qwen3:4b", base_url="http://localhost:11434/v1",
                               api_key="ollama")
call_generator = outlines.generate.json(model, ToolCall)

def choose_tool(task: str, tool_docs: str) -> ToolCall:
    return call_generator(
        f"Available tools:\n{tool_docs}\n\nTask: {task}\n"
        f"Pick exactly one tool (or 'none') and one argument.")
    # Output is guaranteed schema-valid: the sampler cannot emit invalid JSON.
```

Note the schema design: one enum, one string, one bounded rationale — flat by intention. Kim et al. (2025) show schema simplification recovers most SLM tool-calling failures without touching the model; constrained decoding then guarantees whatever the model picks is well-formed. CRP integration point: enforce the grammar in the Gateway at dispatch time, per model profile.

# Template: Learned Router with Escalation Ladder (Component 10)

Role: choose model + depth per task from measured capability profiles and *learn from outcomes* — the quality-tier-supervised routing flywheel.

```python
# router.py — pip install scikit-learn sentence-transformers numpy
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression

emb = SentenceTransformer("BAAI/bge-small-en-v1.5")
LADDER = ["fast", "smart", "frontier_api"]     # cheap -> expensive
QUALITY_TO_LABEL = {"S": 1, "A": 1, "B": 1, "C": 0, "D": 0}

class Router:
    """Predicts, per rung, P(cheapest sufficient rung succeeds). Cold-starts on
    heuristics; every completed task with a quality score becomes training data."""
    def __init__(self):
        self.X, self.y = [], []                # features, "fast-was-sufficient" labels
        self.clf = None

    def _features(self, task: str, interp) -> np.ndarray:
        v = emb.encode(task, normalize_embeddings=True)
        extra = np.array([len(task) / 1000.0, interp.intent_conf, interp.margin])
        return np.concatenate([v, extra])

    def route(self, task: str, interp) -> dict:
        if self.clf is None:                   # cold start heuristic
            hard = any(w in task.lower() for w in
                       ("prove", "plan", "architecture", "legal", "compare", "why"))
            rung = "smart" if hard else "fast"
        else:
            p_fast_ok = self.clf.predict_proba([self._features(task, interp)])[0, 1]
            rung = "fast" if p_fast_ok > 0.6 else "smart"
        depth = "thorough" if rung != "fast" else "quick"
        return {"model": rung, "depth": depth,
                "escalate_on": {"confidence_below": 0.5, "quality_below": "B"}}

    def learn(self, task: str, interp, used_rung: str, quality: str):
        """Supervision for free: if 'fast' was used and quality >= B, fast sufficed."""
        if used_rung == "fast":
            self.X.append(self._features(task, interp))
            self.y.append(QUALITY_TO_LABEL.get(quality, 0))
            if len(self.y) >= 50 and len(set(self.y)) == 2:
                self.clf = LogisticRegression(max_iter=1000).fit(self.X, self.y)

def escalate(current: str) -> str | None:
    i = LADDER.index(current)
    return LADDER[i + 1] if i + 1 < len(LADDER) else None
```

This 60-line router captures the entire economic logic of SLM-first deployment: default cheap, escalate on measured failure signals, and convert your own quality telemetry into routing intelligence. CRP integration point: the `(task, decision, answer.quality)` triple is already logged by any CRP deployment — the training loop is a nightly job over the audit chain.

# Template: World-Model Rule Learning from the Action Log (Component 7)

Role: the WALL-E pattern minimised — learn action→outcome rules from the agent's own experience (intervention data), check proposed actions against them, and gate risky actions on predicted outcomes.

```python
# worldmodel.py
import time
from dataclasses import dataclass, field
from collections import defaultdict

@dataclass
class Transition:
    state_tags: frozenset; action: str; outcome: str; ok: bool; t: float

@dataclass
class WorldModel:
    log: list = field(default_factory=list)
    rules: dict = field(default_factory=dict)   # (tags, action) -> stats

    def observe(self, state_tags: set[str], action: str, outcome: str, ok: bool):
        """Every agent action is an intervention: do(action) in state -> outcome."""
        tr = Transition(frozenset(state_tags), action, outcome, ok, time.time())
        self.log.append(tr)
        key = (tr.state_tags, action)
        s = self.rules.setdefault(key, {"n": 0, "ok": 0, "outcomes": defaultdict(int)})
        s["n"] += 1; s["ok"] += int(ok); s["outcomes"][outcome] += 1

    def predict(self, state_tags: set[str], action: str) -> dict:
        """Match learned rules by state-tag subset; most specific rule wins."""
        matches = [(k, v) for k, v in self.rules.items()
                   if k[1] == action and k[0] <= frozenset(state_tags)]
        if not matches:
            return {"known": False}
        key, s = max(matches, key=lambda kv: (len(kv[0][0]), kv[1]["n"]))
        top = max(s["outcomes"], key=s["outcomes"].get)
        return {"known": True, "p_success": s["ok"] / s["n"],
                "expected_outcome": top, "evidence_n": s["n"]}

    def gate(self, state_tags: set[str], action: str, *, risk: str) -> str:
        """Simulate-before-act for risky operations."""
        p = self.predict(state_tags, action)
        if risk in ("HIGH", "CRITICAL"):
            if not p["known"]:
                return "CHECKPOINT"            # never do novel risky actions blind
            if p["p_success"] < 0.7:
                return "CHECKPOINT"
        return "PROCEED"
```

Sixty lines, and it changes the agent's character: novel risky actions route to humans; actions with a bad track record in similar states get flagged *before* execution; and the rule store — because it is learned from interventions, not text — carries genuine causal weight (Ch. 10). CRP integration points: `observe()` is a hook on the positioned tool loop; rules persist as `causal=True` facts in the fabric; `gate()` plugs into the safety control plane before dispatch; `CHECKPOINT` is CRP's existing HITL primitive, now fired *anticipatorily*.

# Template: The Complete Understanding Loop (All Components)

Role: composition. Interpret → resolve → recall → route → simulate → act (verified) → learn — with abstention and clarification as first-class outcomes.

```python
# agent.py — composition of every prior template
from intent import interpret
from resolve import rewrite_references, EntityRegistry
from fabric import Fabric
from reason import reason
from router import Router, escalate
from worldmodel import WorldModel
from substrate import FLEET

class UnderstandingAgent:
    def __init__(self):
        self.fabric, self.registry = Fabric(), EntityRegistry()
        self.router, self.world = Router(), WorldModel()
        self.history: list[str] = []; self.turn = 0

    def __call__(self, utterance: str) -> dict:
        self.turn += 1
        # 1-2. PERCEIVE + INTERPRET (pragmatics before anything else)
        interp = interpret(utterance)
        if interp.needs_clarification:
            return {"type": "clarification",
                    "question": f"I want to make sure I understand — are you asking "
                                f"me to {interp.intent}, or something else?",
                    "confidence": interp.intent_conf}       # ask > guess

        # 2b. RESOLVE references, update discourse memory
        resolved = rewrite_references(self.history, utterance)
        self.registry.update(resolved, self.turn)

        # 3. RECALL — hybrid retrieval, novelty-gated, anchored on salient entities
        anchors = [a for a in [self.registry.most_salient()] if a]
        facts = self.fabric.retrieve(resolved, anchors=anchors, k=8)

        # 4. ROUTE — model, depth, escalation policy
        plan = self.router.route(resolved, interp)

        # 5. SIMULATE — world-model gate for consequential intents
        if interp.intent == "execute a tool or workflow":
            verdict = self.world.gate(set(interp.intent.split()), resolved, risk="HIGH")
            if verdict == "CHECKPOINT":
                return {"type": "checkpoint",
                        "message": "This action is novel or has a poor track record "
                                   "in similar situations. Please approve.", "plan": plan}

        # 6-7. ACT with verified reasoning; escalate on failure signals
        rung = plan["model"]
        while True:
            result = reason(resolved, facts, model=FLEET[rung].name
                            if rung in FLEET else "gpt-frontier")
            if not result["abstain"]:
                break
            nxt = escalate(rung)
            if nxt is None:
                return {"type": "abstain", "message":
                        "I can't answer this reliably from what I know.",
                        "confidence": result["confidence"]}   # honesty > fluency
            rung = nxt

        # 8. LEARN — memory, router telemetry, world model
        self.fabric.assert_fact("session", "answered", result["answer"][:80],
                                source=f"turn:{self.turn}", confidence=result["confidence"])
        quality = "A" if result["confidence"] > 0.8 else \
                  "B" if result["confidence"] > 0.6 else "C"
        self.router.learn(resolved, interp, plan["model"], quality)
        self.history.append(utterance)
        return {"type": "answer", "answer": result["answer"],
                "confidence": result["confidence"], "quality": quality,
                "model_used": rung, "facts_used": facts}
```

Under 200 lines of orchestration, every one of the ten components is present in at least skeletal form — and each skeleton has a named production upgrade path from Part II. The pedagogical point is the shape, not the lines: **understanding is what this loop does, not what any single call inside it does.**

## Wiring the loop into CRP

The same loop, deployed against CRP, collapses substantially — which is the correct test of a positioning protocol:

```python
import crp
client = crp.SDKClient(safety="strict")           # governance, audit, DPE: 1 line
client.ingest("./knowledge/")                     # CKF replaces fabric.py

answer = client.ask(resolved_utterance, depth=plan["depth"],
                    tools=[chosen.tool] if chosen.tool != "none" else [],
                    safety={"halt_on": "CRITICAL", "require_grounding": 0.75})
# answer.quality -> router.learn()               (the flywheel, from live tiers)
# answer.crp.risk, answer.crp.grounded           (meta-cognition signals)
# answer.sources, answer.crp.chain_valid          (provenance + audit)
```

What CRP replaces: fabric, envelope construction, continuation, grounding verification, provenance, audit, policy. What the templates still add *on top of* CRP as shipped: intent/speech-act interpretation, coreference rewriting, the step judge and symbolic verifiers, the learned router trained on quality tiers, grammar-constrained tool calls, and world-model gating — which is exactly the improvement roadmap of Part IV, arrived at from the builder's direction.

\newpage
# Template: Grounding Verification and Semantic Uncertainty (Component 8)

Role: the meta-cognitive instruments from Chapter 12 as running code — claim-level grounding against sources (the deployed workhorse of hallucination detection) and semantic entropy over sampled answers (the strongest cheap confabulation signal; Farquhar et al., 2024). Together these are the output-side verification core that any DPE-class pipeline is built from, and building a minimal one teaches you exactly what the production versions are doing.

```python
# verify_output.py — pip install transformers sentence-transformers torch numpy
import math, re, itertools, numpy as np
from transformers import pipeline

# NLI model: the universal instrument of output verification.
# premise -> hypothesis: ENTAILMENT / NEUTRAL / CONTRADICTION
_nli = pipeline("text-classification",
                model="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
                top_k=None)

def _nli_label(premise: str, hypothesis: str) -> dict:
    scores = {d["label"].lower(): d["score"]
              for d in _nli({"text": premise, "text_pair": hypothesis})}
    return scores   # {'entailment': p, 'neutral': p, 'contradiction': p}

def split_claims(answer: str) -> list[str]:
    """Naive claim splitter; production systems use a claim-extraction model.
    Sentences that assert something checkable = claims."""
    sents = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [s for s in sents if len(s.split()) > 3]

def grounding_report(answer: str, sources: list[str]) -> dict:
    """For each claim: is it entailed by at least one source (grounded),
    contradicted by any source (distortion), or unsupported (fabrication risk)?
    This is, in miniature, the attribution/fabrication/contradiction core
    of a decision-provenance pipeline."""
    claims, results = split_claims(answer), []
    for c in claims:
        best_ent, worst_con = 0.0, 0.0
        for s in sources:
            sc = _nli_label(s, c)
            best_ent = max(best_ent, sc.get("entailment", 0))
            worst_con = max(worst_con, sc.get("contradiction", 0))
        status = ("GROUNDED" if best_ent > 0.7 else
                  "CONTRADICTED" if worst_con > 0.7 else "UNSUPPORTED")
        results.append({"claim": c, "status": status,
                        "entailment": round(best_ent, 3),
                        "contradiction": round(worst_con, 3)})
    n = max(1, len(results))
    grounded = sum(r["status"] == "GROUNDED" for r in results) / n
    fabricated = sum(r["status"] == "UNSUPPORTED" for r in results)
    contradicted = sum(r["status"] == "CONTRADICTED" for r in results)
    risk = ("CRITICAL" if contradicted else
            "HIGH" if grounded < 0.5 else
            "MEDIUM" if grounded < 0.8 else "LOW")
    return {"grounding_score": round(grounded, 3), "fabrication_count": fabricated,
            "contradiction_count": contradicted, "risk": risk, "claims": results}

def semantic_entropy(sampled_answers: list[str]) -> dict:
    """Farquhar et al. (2024): cluster answers by MEANING via bidirectional
    entailment, then compute entropy over meaning-clusters. High entropy over
    meanings (not words) = the model is confabulating, not just paraphrasing."""
    clusters: list[list[str]] = []
    for a in sampled_answers:
        placed = False
        for cl in clusters:
            rep = cl[0]
            fwd = _nli_label(rep, a).get("entailment", 0) > 0.6
            bwd = _nli_label(a, rep).get("entailment", 0) > 0.6
            if fwd and bwd:                    # bidirectional entailment = same meaning
                cl.append(a); placed = True; break
        if not placed:
            clusters.append([a])
    n = len(sampled_answers)
    probs = [len(cl) / n for cl in clusters]
    H = -sum(p * math.log(p) for p in probs)
    return {"clusters": len(clusters), "entropy": round(H, 3),
            "confabulating": H > 0.8,          # tune per model on a validation set
            "majority_meaning": max(clusters, key=len)[0]}
```

Two design lessons are embedded here. First, *the NLI model is the Swiss-army knife of output verification*: grounding, contradiction, and semantic clustering are all the same instrument pointed in different directions, which is why one ~180M encoder can power a whole verification pipeline in under 50 ms on the answer lengths agents typically produce. Second, *the thresholds are the product*: 0.7 entailment and 0.8 entropy are starting points; the calibrated values differ per model and per task type, which is precisely the argument for the epistemic profiles of Chapter 12 and roadmap item R5.

CRP integration point: this template is a working miniature of DPE stages 1–6 and 10 (claim detection → attribution → fabrication → distortion → entailment → contradiction → hallucination risk), and `semantic_entropy` is the concrete mechanism for wiring ROS self-consistency divergence into quality tiers (roadmap R1).

# Template: Normative Policy Engine (Component 9)

Role: policy-as-code in miniature — declarative rules, evaluated on every output, producing enforceable actions and an evidence record. Fifty lines that demonstrate why the normative layer belongs in the protocol, not the application: the application *cannot forget* to run what the pipeline always runs.

```python
# policy.py
import hashlib, hmac, json, time, re

POLICY = """
halt-on CRITICAL
redact-on HIGH pii
require-grounding 0.75
checkpoint-on HIGH
escalate-on quality<B
"""

PII_PATTERNS = {
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone_au": r"(\+?61|0)4\d{2}[ -]?\d{3}[ -]?\d{3}",
    "tfn": r"\b\d{3}[ -]?\d{3}[ -]?\d{3}\b",
}

SECRET = b"rotate-me-in-production"

class PolicyEngine:
    def __init__(self, policy: str = POLICY):
        self.rules = [l.strip() for l in policy.strip().splitlines() if l.strip()]
        self.chain_prev = b"genesis"
        self.events: list[dict] = []

    def evaluate(self, answer: str, verdicts: dict) -> dict:
        """verdicts = output of grounding_report() + quality tier + risk."""
        actions, redacted = [], answer
        risk, quality = verdicts["risk"], verdicts.get("quality", "B")
        pii_hits = {k: re.findall(p, answer) for k, p in PII_PATTERNS.items()}
        pii = any(v for v in pii_hits.values())

        for rule in self.rules:
            if rule == "halt-on CRITICAL" and risk == "CRITICAL":
                actions.append("HALT")
            if rule == "redact-on HIGH pii" and pii and risk in ("HIGH", "CRITICAL"):
                for pat in PII_PATTERNS.values():
                    redacted = re.sub(pat, "[REDACTED]", redacted)
                actions.append("REDACT")
            if rule.startswith("require-grounding"):
                if verdicts["grounding_score"] < float(rule.split()[-1]):
                    actions.append("WARN_UNGROUNDED")
            if rule == "checkpoint-on HIGH" and risk == "HIGH":
                actions.append("CHECKPOINT")
            if rule == "escalate-on quality<B" and quality in ("C", "D"):
                actions.append("ESCALATE")

        # Tamper-evident evidence that the controls RAN (the audit failure
        # every assurance framework shares is proof-of-operation, not policy):
        event = {"t": time.time(), "risk": risk, "quality": quality,
                 "actions": actions, "grounding": verdicts["grounding_score"],
                 "pii": pii}
        payload = json.dumps(event, sort_keys=True).encode()
        sig = hmac.new(SECRET, self.chain_prev + payload,
                       hashlib.sha256).hexdigest()
        event["hmac"], self.chain_prev = sig, sig.encode()
        self.events.append(event)

        final = "HALT" if "HALT" in actions else \
                "CHECKPOINT" if "CHECKPOINT" in actions else \
                "ESCALATE" if "ESCALATE" in actions else "PASS"
        return {"decision": final, "answer": redacted, "actions": actions,
                "evidence": event}

    def verify_chain(self) -> bool:
        prev = b"genesis"
        for e in self.events:
            body = {k: v for k, v in e.items() if k != "hmac"}
            payload = json.dumps(body, sort_keys=True).encode()
            if hmac.new(SECRET, prev + payload, hashlib.sha256).hexdigest() != e["hmac"]:
                return False
            prev = e["hmac"].encode()
        return True
```

The chained HMAC over policy events is the same construction that makes an audit trail *evidence* rather than logging: any post-hoc alteration breaks every subsequent signature. Note also the natural home of roadmap item R2's `escalate-on quality<B` — one line in a policy grammar, connecting the normative layer (Ch. 13) to the routing layer (Ch. 11).

# Evaluating Understanding: The Measurement Harness

## Why evaluation deserves its own chapter

A system's understanding is exactly as good as your ability to measure it, and the measurement discipline is where most agent projects quietly fail. Three principles govern honest evaluation of understanding-oriented systems:

1. **Evaluate components separately before evaluating the loop.** A wrong final answer can come from misinterpretation (Ch. 6), bad retrieval (Ch. 7), broken reasoning (Ch. 8), or bad routing (Ch. 11); loop-level accuracy alone cannot localise the failure. The evaluation harness must record per-stage artefacts — the interpretation, the retrieved facts, the chains, the routing decision — so every failure is attributable. (This is the observability argument for provenance made from the QA direction.)
2. **Evaluate calibration, not just accuracy.** Two systems with identical accuracy differ enormously in value if one knows when it is wrong. Report expected calibration error and selective-prediction curves (accuracy at each coverage level when the system may abstain) alongside accuracy. A system that answers 80% of queries at 95% accuracy and abstains on the rest is, for most deployments, strictly better than one that answers 100% at 88%.
3. **Guard against contamination and Goodharting.** Public benchmark items leak into training data; scores on famous suites overstate capability. Prefer held-out, private, periodically refreshed task sets drawn from your actual domain — the design philosophy behind maintaining a private semantic-quality benchmark rather than relying on public leaderboards.

## The relevant public benchmark families (2026)

For orientation rather than worship: **GPQA** and **MMLU-Pro** for knowledge-plus-reasoning; **GSM8K/MATH** descendants for verifiable multi-step reasoning (largely saturated for frontier models, still discriminative for SLMs); **τ-bench and BFCL** for tool calling and agentic API use; **SWE-bench** families for software agents; **LongBench/RULER** for long-context behaviour (which measures something different from context *length* — models advertise windows their attention cannot service); **ToMi/BigToM perturbations** for theory-of-mind fragility (Ullman, 2023). For SLM fleets, per-model scores on *your own* task taxonomy beat all of the above — which is what capability profiles (Ch. 11) formalise.

## Template: a minimal component-attributing eval harness

```python
# evalharness.py
import json, statistics, time
from dataclasses import dataclass, asdict

@dataclass
class Case:
    query: str
    expected: str | None            # None = the correct behaviour is to abstain/clarify
    kind: str                       # "factual" | "multihop" | "ambiguous" | "tool" ...

CASES = [
    Case("What is the grounding threshold in our default policy?", "0.75", "factual"),
    Case("Compare it with the strict profile", None, "ambiguous"),   # 'it' + no referent
    Case("If clause 4 requires X and clause 9 forbids X, what governs?",
         "conflict", "multihop"),
]

def run_eval(agent, cases=CASES) -> dict:
    rows = []
    for c in cases:
        t0 = time.time()
        out = agent(c.query)
        row = {"kind": c.kind, "latency_s": round(time.time() - t0, 2),
               "type": out["type"], "confidence": out.get("confidence", 0)}
        if c.expected is None:
            # correct behaviour on ambiguous/unanswerable = NOT answering
            row["correct"] = out["type"] in ("clarification", "abstain")
        else:
            row["correct"] = (out["type"] == "answer"
                              and c.expected.lower() in out["answer"].lower())
        rows.append(row)

    by_kind = {}
    for k in {r["kind"] for r in rows}:
        sub = [r for r in rows if r["kind"] == k]
        by_kind[k] = round(sum(r["correct"] for r in sub) / len(sub), 3)

    answered = [r for r in rows if r["type"] == "answer"]
    coverage = len(answered) / len(rows)
    selective_acc = (sum(r["correct"] for r in answered) / len(answered)
                     if answered else 0.0)
    # crude calibration: mean |confidence - correctness| on answered items
    ece = (statistics.mean(abs(r["confidence"] - r["correct"]) for r in answered)
           if answered else 0.0)
    return {"per_kind_accuracy": by_kind, "coverage": round(coverage, 3),
            "selective_accuracy": round(selective_acc, 3),
            "calibration_gap": round(ece, 3), "rows": rows}
```

The three numbers that matter are in the return value: per-kind accuracy (localises which component fails), coverage vs selective accuracy (rewards honest abstention rather than punishing it), and the calibration gap (measures whether confidence means anything). Note the deliberate inclusion of `expected=None` cases: **a benchmark that contains no unanswerable or ambiguous items cannot measure understanding at all**, because it never distinguishes the system that knows its limits from the one that doesn't.

# The 2025–2026 Trends Landscape: What Moved, What's Moving, What to Watch

## What moved (settled shifts you should build on)

**Test-time compute became the third scaling axis.** The o1/R1 wave established that structured inference-time reasoning, trained by RL on verifiable rewards, beats parameter scaling on reasoning tasks per dollar (Snell et al., 2024; DeepSeek-AI, 2025) — and that the behaviours distil into small models. Consequence: reasoning depth is a *dial*, and orchestration layers that expose the dial per-operation (depth negotiation) match the hardware of the moment.

**The SLM-first thesis went from position paper to supply chain.** Belcak et al. (2025) argued it; 2026 delivered the model bench (Phi-4-class, Gemma-4-class, Qwen3-class, Llama-3.2-class), the runtimes (Ollama with MLX, Apple's on-device foundation framework, vLLM/llama.cpp maturity), and the deployment evidence — including sub-1B specialists outperforming frontier generalists on scoped tool-orchestration domains (Red Hat, 2026). The correlated finding with the biggest design consequence: adapt *schemas and scaffolds* to small models rather than fine-tuning small models toward frontier interfaces (Kim et al., 2025).

**Verification moved from answers to steps.** Process supervision (Lightman et al., 2023) → productised PRMs → distilled small verifiers. The emerging norm in serious systems: nothing consequential ships unverified, and the verifier is a separate, smaller, cheaper model or a symbolic engine (Kambhampati et al., 2024). Generation and verification are decoupling into distinct system roles — arguably the most important architectural trend of the period.

**Memory became a product category.** MemGPT/Letta's OS metaphor, Mem0's consolidation pipeline, Zep/Graphiti's temporal graphs: agent memory is now infrastructure you buy or standardise on, not a prompt trick. The differentiating axes settled as: structure (flat vs graph), time (snapshot vs bi-temporal), and consolidation (append vs resolve-and-merge).

**Governance became runtime.** The EU AI Act's staged applicability (prohibitions and AI-literacy from February 2025, GPAI obligations from August 2025, high-risk obligations phasing through 2026–2027), ISO/IEC 42001 certification demand, and NIST AI RMF adoption converged on the same operational requirement: continuous, verifiable evidence that controls operate — which pulled compliance out of documents and into the request path. This is the wave CRP is built to ride, and the report's assessment is that the positioning is correct: proof-of-operation is the universal audit failure, and runtime evidence generation is the only scalable answer.

## What's moving (contested, adopt with judgement)

**World models for language agents.** The WALL-E line (Zhou et al., 2024, 2025) and its 2026 successors (energy-based neuro-symbolic fusion; enterprise-workflow and computer-use world models; Gupta et al., 2026; Guan et al., 2026) are the fastest-moving understanding-relevant literature. Not yet productised; the recipe (Ch. 10) is stable enough to implement now, which is why R3 is rated frontier-credible rather than speculative.

**Agentic RL.** Training agents end-to-end with RL over multi-step tool-use trajectories (beyond single-response RLHF) is producing strong results inside labs; open replication is early. Watch, don't bet the roadmap.

**The protocol layer consolidation.** MCP won tool exposure decisively; A2A-class messaging is consolidating; the positioning/governance layer beneath them is genuinely unclaimed at standards level — which is simultaneously CRP's opportunity and its race. The clarification-semantics gap (R4) is a concrete wedge: small, novel, and demonstrably absent from both incumbent protocols.

**Interpretability-informed control.** Sparse-autoencoder feature steering and activation-level monitors (Templeton et al., 2024, and successors) are crossing from research into safety tooling. For black-box governance layers this matters as a *complement*: weight-level and boundary-level oversight will eventually compose, and boundary-level systems should design their evidence schemas so interpretability signals can slot in as additional DPE-style stages later.

## What to watch (early, potentially reshaping)

Continual/on-device learning breakthroughs (would change the memory chapter's ceiling); consumer NPU maturity actually delivering LLM-relevant throughput (would change the fleet economics); JEPA-class non-generative world models reaching language-agent applicability (would change Chapter 10's recipe); and standardisation outcomes at IETF/ISO for the agent stack (would decide whose vocabulary the industry speaks — a race you are already in).

\newpage
# Appendix A — The Python Library Map: Component → Tooling Quick Reference

This appendix consolidates every library referenced in Parts II–III into a single procurement-and-learning map. All entries run locally on consumer hardware unless marked; sizes are approximate model footprints, not package sizes.

| Component | Purpose | Library / model | Size / cost | Maturity |
|---|---|---|---|---|
| Substrate | Local inference runtimes | Ollama, LM Studio, vLLM, llama.cpp | — | Production |
| Substrate | Uniform client | `openai` (pointed at local `base_url`) | — | Production |
| 1. Syntax | Guaranteed-valid structured output | `outlines`, `llguidance`, XGrammar | ~0 overhead | Production |
| 2. Semantics | Embeddings | `sentence-transformers` (bge-small/large, gte) | 33M–435M | Production |
| 3. Pragmatics | Zero-shot intent / NLI | `transformers` + DeBERTa-v3 zeroshot | ~180M | Production |
| 3. Pragmatics | Few-shot intent fine-tuning | `setfit` | ~33–110M | Production |
| 6/3. Reference | Coreference resolution | `fastcoref`; Maverick | ~90–500M | Production |
| 4. Knowledge | Zero-shot NER | `gliner` | ~300M | Production |
| 4. Knowledge | Relations/events (UIE) | `transformers` UIE checkpoints | ~700M | Solid |
| 4. Knowledge | Graph substrate | `networkx` (proto) → Neo4j/Kùzu (scale) | — | Production |
| 4. Knowledge | Vector index | `hnswlib`, `sqlite-vec`, FAISS, Qdrant | — | Production |
| 4. Knowledge | Communities (GraphRAG) | `igraph` + `leidenalg`, `graspologic` | — | Production |
| 4. Knowledge | Reranking | `sentence-transformers` cross-encoders; bge-reranker | 100–600M | Production |
| 4. Knowledge | Ready GraphRAG | `graphrag` (Microsoft), `llama-index` graph stores | — | Solid |
| 5. Reasoning | Symbolic math | `sympy` | — | Production |
| 5. Reasoning | SMT / constraints | `z3-solver` | — | Production |
| 5. Reasoning | Logic programming | `pyswip` (Prolog), datalog engines | — | Solid |
| 5. Reasoning | Program-aided verification | stdlib sandboxing → containers/jails in prod | — | Pattern |
| 6. Memory | Consolidating memory service | `mem0ai`; Letta | — | Solid |
| 6. Memory | Temporal graph memory | `graphiti-core` (Zep) | — | Solid |
| 7. World model | Rule induction / gating | ~60 lines of Python (Template, Ch. 19) | — | DIY [RESEARCH] |
| 8. Meta-cognition | NLI grounding / entailment | DeBERTa-v3 MNLI-FEVER-ANLI | ~180M | Production |
| 8. Meta-cognition | Conformal wrappers | `mapie`, `crepes` | — | Solid |
| 9. Normative | Policy engines | DIY grammar (Template, Ch. 22); OPA/Rego for infra | — | Production |
| 10. Routing | Learned routing | `scikit-learn` on your telemetry; RouteLLM | — | Production |
| Eval | Harnesses | `lm-eval-harness`, `deepeval`, `ragas`; DIY (Ch. 23) | — | Production |
| Governance | Positioning + evidence layer | `crp` SDK / CRP Gateway | — | Shipping |

## Install manifest for the complete template set

```bash
# Core inference + orchestration
pip install openai outlines pydantic

# NLU: intent, entities, reference
pip install transformers torch setfit gliner fastcoref

# Knowledge fabric
pip install networkx sentence-transformers hnswlib numpy

# Reasoning + verification
pip install sympy z3-solver

# Routing, calibration, evaluation
pip install scikit-learn mapie

# Optional productised memory / graph layers
pip install mem0ai graphiti-core

# Local runtime (choose one): https://ollama.com  |  LM Studio  |  vLLM
ollama pull qwen3:4b && ollama pull qwen3:14b
```

Total additional model weight beyond the SLMs themselves: roughly 1.5–2 GB covering embeddings, NLI, NER, coreference, and intent — the entire *understanding scaffold* costs less disk than one quantised 4B model, which is the economic heart of the argument that components 3–10 belong outside the weights.

# Appendix B — CRP Quick Card: Concept → CRP Mechanism → Proposed Extension

A one-page navigation aid connecting this report's vocabulary to CRP's, for use in specs, papers, and standards conversations.

| Understanding concept (this report) | CRP v5.1 mechanism (shipped) | Proposed extension (Part IV) |
|---|---|---|
| Envelope discipline, attention geometry | Maximally-saturated 11-section envelope; bookend strategy; zero in-window overhead | — (leading) |
| Semantics | Model weights (correctly out of scope) | Capability profiles per model (R2) |
| Intent & speech acts | Content-complexity routing only | Pre-envelope interpretation layer (R4) |
| Reference resolution | Multi-horizon retrieval (similarity-based) | Session coreference rewriting before CDR (R4) |
| Clarification | HITL checkpoints (risk-triggered only) | `CRP-Clarification-Required` primitive (R4) |
| Knowledge structure | CKF: typed KG, HNSW, Leiden, event-sourced | Ontology option per domain agent; bi-temporal validity (R5) |
| Anti-redundancy retrieval | CDR novelty ranking; CDGR graph walk | — (differentiated) |
| Reasoning scaffolds | ORC micro-steps; ICML scaffolds; RTL traces | Verifier-scored, self-curating RTL (R1) |
| Step verification | Absent (DPE verifies claims, not steps) | DPE stage 14: PRM judge; symbolic dispatch targets (R1) |
| Consistency-as-uncertainty | ROS computes it; not wired onward | Divergence → quality tier + risk (R1) |
| Temporal coherence | CSO relay; measured-drift re-grounding; stitching | — (leading) |
| World model / simulation | Absent | Predictive Positioning: rule induction over action log; simulate-before-act gate (R3) |
| Causality | Associative/typed edges only | `causal=True` intervention-grade edges from action log (R3) |
| Calibration | Output-side tiers and risk only | Epistemic profiles: per-model, per-task calibration curves as evidence (R5) |
| Routing | Positioned tool loop (1–3 tools, per-op windows) | Quality-tier-supervised learned router; `escalate-on` verb; schema simplification; grammar-constrained dispatch (R2) |
| Normativity & evidence | Declarative policy; 13-stage DPE; HMAC chain; compliance generators | — (the moat; extend evidence schema to admit verifier + calibration signals) |

Read down the middle column and CRP's honest 2026 identity is visible: **leading on memory, envelope, provenance, and governance; solid on knowledge and scaffolding; absent on interpretation-layer pragmatics, step verification, and prediction.** Read down the right column and the roadmap is equally visible: R1 buys correctness, R2 buys economics, R3 buys the research frontier, R4 buys the standards wedge, R5 buys trust. None requires abandoning the architecture; all five extend machinery already in place — which is the strongest possible evidence that the architecture is sound.

\newpage
# PART IV — SYNTHESIS

# CRP v5.1 Against the Ten Components: Audit and Improvement Roadmap

## The scorecard

Assessed against the ten-component model, from the published protocol surface (crprotocol.io, specs 001–048, capabilities reference, July 2026):

| Component | CRP v5.1 status | Verdict |
|---|---|---|
| 1. Syntax/form | Envelope discipline, zero in-window protocol overhead, content-type-aware stitching | **Strong** |
| 2. Semantics | Delegated to the model (correct for a protocol) | **Correct scoping** |
| 3. Pragmatics/intent | Content-complexity routing only; no speech-act/intent layer; no clarification primitive | **Gap** |
| 4. World knowledge | CKF: typed KG + HNSW + Leiden + event sourcing; CDR/CDGR; multi-horizon tiers | **Strong / leading** (add ontology option + bi-temporal validity) |
| 5. Reasoning | ORC/ICML/RTL scaffolding; ROS self-consistency | **Good scaffold, no verification** — the #1 gap |
| 6. Memory/temporal | CSO relay, measured-drift re-grounding, continuation + stitching | **Leading** |
| 7. Causal/world model | Absent (facts, not transition rules; no simulate-before-act) | **Gap** — the #2 opportunity |
| 8. Meta-cognition | Quality tiers, risk scores, grounding scores — output-side only | **Partial** (no calibration profiles; consistency-divergence not wired to tiers) |
| 9. Normative | Declarative policy, HITL checkpoints, HMAC evidence, compliance generators | **Leading — the moat** |
| 10. Routing/active | Positioned tool loop (1–3 tools, per-op windows); depth negotiation | **Good chassis; router unlearned, fleet-blind, no escalate verb, no clarification outcome** |

## The prioritised roadmap (proposed as five spec-shaped additions)

**R1 — Verification Relay (highest impact / medium effort).** A 14th DPE stage for step-level reasoning verification (PRM-style judge, depth-gated to thorough/exhaustive), plus symbolic verifiers (sandboxed Python, SymPy, Z3, datalog-over-CKF, graph-constrained decoding) as first-class dispatch targets in the continuation loop — the LLM-Modulo pattern natively in the protocol. Wire self-consistency divergence (already computed in ROS) into quality tiers and risk. *Claimable outcome: CRP becomes the first governance protocol that verifies reasoning, not just grounding.*

**R2 — Quality-Tier-Supervised Routing (highest leverage / low effort).** CRP already logs the full training triple (task, routing decision, outcome tier) in the audit chain. A nightly job trains the operation/model/depth router on it; per-model capability profiles are measured by SQB (SPEC-026); `escalate-on quality<B` and `escalate-on confidence<0.5` become Safety Policy Directive verbs; a schema-simplification transform per model profile plus Gateway-enforced grammar-constrained decoding closes SLM tool-call failures. *This is a self-improving flywheel competitors cannot copy without first copying the quality-tier telemetry.*

**R3 — Predictive Positioning (frontier-credible / medium effort).** Rule induction over the event-sourced action log (state-pattern, action → outcome, p-success), rules stored as causal-typed CKF facts, pre-dispatch rule check, and simulate-before-act gating on HIGH/CRITICAL operations feeding the existing checkpoint mechanism. Because action logs are intervention data, the induced rules are causally grounded in a way text-extracted "causes" edges cannot be — the research-paper-worthy claim. *Compliance framing: anticipatory Article-14 human oversight.*

**R4 — Interpretation Layer (low effort / immediate UX gain).** Pre-envelope intent/speech-act tagging (sub-500M classifier, ~10 ms), session-scoped coreference rewriting before retrieval, and — the genuinely novel protocol move — a structured `CRP-Clarification-Required` response type with options, confidence, and resumption semantics. No protocol in the MCP/A2A ecosystem has clarification semantics; first-mover standardisation opportunity.

**R5 — Epistemic Profiles (low effort / trust dividend).** Per-model, per-task-type calibration curves accumulated from DPE-verified outcomes; positioning consumes them (stricter grounding thresholds where a model is measured-overconfident); profiles exportable as evidence ("we know, quantitatively, when this model doesn't know"). Add bi-temporal validity intervals to CKF facts (valid-from/valid-to vs recorded-at) while touching the fact schema.

Sequencing note: R2 and R4 are weeks-scale; R1 is the quality headline; R3 is the differentiated research story worth an IETF-adjacent draft and an arXiv paper; R5 rides along with R1's verification data.

# What Honestly Does Not Exist: The Open Problems

Stated plainly, because these are the claims not to make — in specs, marketing, or standards submissions:

1. **Machine comprehension in the strong sense [OPEN].** Every system described in this report — CRP, frontier labs, the templates in Part III — achieves *functional* understanding: reliable, scoped, calibrated behaviour. Whether symbol manipulation plus grounding scaffolds constitutes understanding remains philosophically unresolved (Searle, 1980; Bender & Koller, 2020, vs. Li et al., 2023). Honest positioning: "behaves as if it understands, within scope, with evidence" — which happens to be the only version regulators can audit anyway.
2. **General causal discovery from text [OPEN].** Causal edges extracted from language are *reported* causality. Verified causality requires interventions or strong identification assumptions (Pearl, 2009). The one tractable path — learning from agent action logs, which are interventions — is exactly R3, and it yields environment-specific rules, not general causal knowledge.
3. **Robust theory of mind [OPEN].** Fragments exist in research (belief-state tracking in multi-agent settings; partial false-belief performance that collapses under perturbation; Ullman, 2023). Nothing production-grade models a user's evolving beliefs and goals.
4. **Unified calibration [OPEN].** Semantic entropy (Farquhar et al., 2024) is the best cheap confabulation signal; conformal prediction gives formal guarantees on specific tasks; but no mechanism makes a model *generally* know what it doesn't know. Everything deployable is per-task, per-model, empirically maintained — hence R5.
5. **Weight-level continual learning on-device [OPEN].** All deployed "learning" is context-level. The model that improves from its own experience without forgetting, on consumer hardware, does not exist.
6. **Clarification/ambiguity negotiation as an inter-agent standard [OPEN — and claimable].** Neither MCP nor A2A defines it. This is the one open problem on this list that a protocol author can simply *solve by specifying it* — R4.
7. **Embodied grounding on consumer hardware [OPEN].** Local multimodal models ground in documents and interfaces; sensorimotor grounding remains robotics-lab territory.
8. **Automatic hardware-aware local resource management [OPEN, adjacent].** As identified in prior research sessions: no system yet automatically matches model, quantisation, KV-cache policy, and offloading strategy to the device and the task. It is the systems-layer sibling of the routing problem, and whoever ships it owns a chokepoint of the local stack.

# Recommendations: The Build Plan

**This month (all [SHIPPED]-tier parts):** deploy the interpretation layer (intent + coreference, Templates 15–16) in front of existing retrieval; enforce grammar-constrained tool calls at the Gateway; start logging the routing-supervision triple; add `escalate-on` to the policy language.

**This quarter:** ship the Verification Relay (step judge distilled to a ≤2B verifier; SymPy/Z3/sandbox dispatch targets); wire consistency-divergence into quality tiers; train the first quality-tier-supervised router from accumulated telemetry; add bi-temporal validity to CKF facts.

**This year ([RESEARCH]-tier):** Predictive Positioning — rule induction over the action log, simulate-before-act gating, and the accompanying paper ("Agent action logs as intervention data: causally grounded world-model alignment in governed agentic systems" is, frankly, a title waiting for you); epistemic profiles as exportable evidence; the clarification-semantics draft into the IETF conversation while the dispatch thread is warm.

**Framing to carry into everything:** semantics is the vocabulary the model brings; the protocol supplies the grammar, the memory, the conscience, the simulator, and the narrator. In SLM-first systems, understanding is not in the model — it is in the loop. Build the loop, verify the loop, and prove the loop ran.

# Glossary

**A2A** — Agent-to-Agent protocol family for inter-agent messaging. **Bi-temporal model** — storing both when a fact was true and when the system learned it. **CDR/CDGR** — CRP's novelty-ranked and graph-walk retrieval modes. **CKF** — Contextual Knowledge Fabric, CRP's typed knowledge graph. **CoT** — chain-of-thought prompting. **Conformal prediction** — distribution-free method producing prediction sets with guaranteed coverage. **CSO** — Cognitive State Object; typed state carried across generation windows. **DPE** — Decision Provenance Engine; CRP's 13-stage output verification pipeline. **Grounding (NLP)** — verifying claims against sources; **(philosophy)** anchoring symbols in non-symbolic experience. **GraphRAG** — retrieval over an extracted entity graph with community summaries. **HITL** — human-in-the-loop. **LLM-Modulo** — architecture where LLMs generate and sound external verifiers accept/reject (Kambhampati et al., 2024). **MCP** — Model Context Protocol for tool exposure. **NLI** — natural language inference (entailment classification). **PRM** — process reward model; scores individual reasoning steps. **Pragmatics** — meaning as use: speaker intent, speech acts, context. **RAG** — retrieval-augmented generation. **Self-consistency** — sampling multiple reasoning chains and aggregating. **Semantic entropy** — uncertainty over meaning-clusters of sampled answers. **SLM** — small language model (≲10B parameters; Belcak et al., 2025). **Speech act** — the action performed by an utterance (request, assertion, question). **Symbol grounding problem** — how symbols acquire meaning beyond other symbols (Harnad, 1990). **World model** — a predictive model of action consequences.

\newpage

# References

Angelopoulos, A. N., & Bates, S. (2023). Conformal prediction: A gentle introduction. *Foundations and Trends in Machine Learning, 16*(4), 494–591. https://doi.org/10.1561/2200000101

Austin, J. L. (1962). *How to do things with words*. Oxford University Press.

AutoCyber AI. (2026). *Agentic positioning protocol for SLM-first AI — CRP v5.1*. Context Relay Protocol. https://crprotocol.io/

Bai, Y., Kadavath, S., Kundu, S., Askell, A., Kernion, J., Jones, A., ... Kaplan, J. (2022). Constitutional AI: Harmlessness from AI feedback. *arXiv*. https://doi.org/10.48550/arXiv.2212.08073

Belcak, P., Heinrich, G., Diao, S., Fu, Y., Dong, X., Muralidharan, S., Lin, Y. C., & Molchanov, P. (2025). Small language models are the future of agentic AI. *arXiv*. https://doi.org/10.48550/arXiv.2506.02153

Bender, E. M., & Koller, A. (2020). Climbing towards NLU: On meaning, form, and understanding in the age of data. In *Proceedings of the 58th Annual Meeting of the Association for Computational Linguistics* (pp. 5185–5198). ACL. https://doi.org/10.18653/v1/2020.acl-main.463

Bhattacharya, R., et al. (2026). Ontology-constrained neural reasoning in enterprise agentic systems: A neurosymbolic architecture for domain-grounded AI agents. *arXiv*. https://arxiv.org/abs/2604.00555

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., ... Olah, C. (2023). Towards monosemanticity: Decomposing language models with dictionary learning. *Transformer Circuits Thread*. https://transformer-circuits.pub/2023/monosemantic-features

Chhikara, P., Khant, D., Aryan, S., Singh, T., & Yadav, D. (2025). Mem0: Building production-ready AI agents with scalable long-term memory. *arXiv*. https://doi.org/10.48550/arXiv.2504.19413

DeepSeek-AI. (2025). DeepSeek-R1: Incentivizing reasoning capability in LLMs via reinforcement learning. *arXiv*. https://doi.org/10.48550/arXiv.2501.12948

de Moura, L., & Bjørner, N. (2008). Z3: An efficient SMT solver. In *Tools and algorithms for the construction and analysis of systems* (pp. 337–340). Springer. https://doi.org/10.1007/978-3-540-78800-3_24

Dennett, D. C. (1987). *The intentional stance*. MIT Press.

Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A., Truitt, S., & Larson, J. (2024). From local to global: A graph RAG approach to query-focused summarization. *arXiv*. https://doi.org/10.48550/arXiv.2404.16130

European Parliament & Council of the European Union. (2024). *Regulation (EU) 2024/1689 laying down harmonised rules on artificial intelligence (Artificial Intelligence Act)*. Official Journal of the European Union.

Farquhar, S., Kossen, J., Kuhn, L., & Gal, Y. (2024). Detecting hallucinations in large language models using semantic entropy. *Nature, 630*, 625–630. https://doi.org/10.1038/s41586-024-07421-0

Gao, L., Ma, X., Lin, J., & Callan, J. (2023). Precise zero-shot dense retrieval without relevance labels. In *Proceedings of ACL 2023* (pp. 1762–1777). ACL. https://doi.org/10.18653/v1/2023.acl-long.99

Gao, L., Madaan, A., Zhou, S., Alon, U., Liu, P., Yang, Y., Callan, J., & Neubig, G. (2023). PAL: Program-aided language models. In *Proceedings of the 40th International Conference on Machine Learning* (pp. 10764–10799). PMLR.

Gentner, D. (1983). Structure-mapping: A theoretical framework for analogy. *Cognitive Science, 7*(2), 155–170. https://doi.org/10.1207/s15516709cog0702_3

Geva, M., Schuster, R., Berant, J., & Levy, O. (2021). Transformer feed-forward layers are key-value memories. In *Proceedings of EMNLP 2021* (pp. 5484–5495). ACL. https://doi.org/10.18653/v1/2021.emnlp-main.446

Guan, Y., Yu, R., Zhang, J., Wang, L., Zhang, C., Li, L., ... Zhang, D. (2026). Computer-using world model. *arXiv*. https://arxiv.org/abs/2602.17365

Gupta, L., Li, L., Liu, Y., Subramanian, S. G., Suleman, K., Zhang, Z., Lu, H., & Pasupalak, S. (2026). World of workflows: A benchmark for bringing world models to enterprise systems. *arXiv*. https://arxiv.org/abs/2601.22130

Gurnee, W., & Tegmark, M. (2024). Language models represent space and time. In *Proceedings of the Twelfth International Conference on Learning Representations*. ICLR.

Hakim, S. B., Adil, M., Velasquez, A., & Song, H. H. (2026). Neuro-symbolic agentic AI: Architectures, integration patterns, applications, open challenges and future research directions. *Information Fusion*. https://doi.org/10.1016/j.inffus.2026.103110

Harnad, S. (1990). The symbol grounding problem. *Physica D: Nonlinear Phenomena, 42*(1–3), 335–346. https://doi.org/10.1016/0167-2789(90)90087-6

Hsieh, C.-Y., Li, C.-L., Yeh, C.-K., Nakhost, H., Fujii, Y., Ratner, A., Krishna, R., Lee, C.-Y., & Pfister, T. (2023). Distilling step-by-step! Outperforming larger language models with less training data and smaller model sizes. In *Findings of ACL 2023* (pp. 8003–8017). ACL. https://doi.org/10.18653/v1/2023.findings-acl.507

Huang, L., Yu, W., Ma, W., Zhong, W., Feng, Z., Wang, H., ... Liu, T. (2023). A survey on hallucination in large language models: Principles, taxonomy, challenges, and open questions. *arXiv*. https://doi.org/10.48550/arXiv.2311.05232

International Organization for Standardization. (2023). *ISO/IEC 42001:2023 — Information technology — Artificial intelligence — Management system*. ISO.

Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang, Y., Madotto, A., & Fung, P. (2023). Survey of hallucination in natural language generation. *ACM Computing Surveys, 55*(12), 1–38. https://doi.org/10.1145/3571730

Kambhampati, S., Valmeekam, K., Guan, L., Verma, M., Stechly, K., Bhambri, S., Saldyt, L., & Murthy, A. (2024). Position: LLMs can't plan, but can help planning in LLM-modulo frameworks. In *Proceedings of the 41st International Conference on Machine Learning*. PMLR. https://arxiv.org/abs/2402.01817

Khattab, O., & Zaharia, M. (2020). ColBERT: Efficient and effective passage search via contextualized late interaction over BERT. In *Proceedings of SIGIR 2020* (pp. 39–48). ACM. https://doi.org/10.1145/3397271.3401075

Kim, J., et al. (2025). Don't adapt small language models for tools; adapt tool schemas to the models. *arXiv*. https://arxiv.org/abs/2510.07248

Kirkpatrick, J., Pascanu, R., Rabinowitz, N., Veness, J., Desjardins, G., Rusu, A. A., ... Hadsell, R. (2017). Overcoming catastrophic forgetting in neural networks. *Proceedings of the National Academy of Sciences, 114*(13), 3521–3526. https://doi.org/10.1073/pnas.1611835114

Kojima, T., Gu, S. S., Reid, M., Matsuo, Y., & Iwasawa, Y. (2022). Large language models are zero-shot reasoners. In *Advances in Neural Information Processing Systems 35* (pp. 22199–22213).

Kossen, J., Han, J., Razzak, M., Schut, L., Malik, S., & Gal, Y. (2025). Semantic entropy probes: Robust and cheap hallucination detection in LLMs. In *Proceedings of the International Conference on Learning Representations*. ICLR. https://arxiv.org/abs/2406.15927

Kuhn, L., Gal, Y., & Farquhar, S. (2023). CLAM: Selective clarification for ambiguous questions with generative language models. *arXiv*. https://doi.org/10.48550/arXiv.2212.07769

Lake, B. M., Ullman, T. D., Tenenbaum, J. B., & Gershman, S. J. (2017). Building machines that learn and think like people. *Behavioral and Brain Sciences, 40*, e253. https://doi.org/10.1017/S0140525X16001837

Laurer, M., van Atteveldt, W., Casas, A., & Welbers, K. (2024). Less annotating, more classifying: Addressing the data scarcity issue of supervised machine learning with deep transfer learning and BERT-NLI. *Political Analysis, 32*(1), 84–100. https://doi.org/10.1017/pan.2023.20

LeCun, Y. (2022). *A path towards autonomous machine intelligence* (Version 0.9.2). OpenReview. https://openreview.net/forum?id=BZ5a1r-kVsf

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., ... Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. In *Advances in Neural Information Processing Systems 33* (pp. 9459–9474).

Li, K., Hopkins, A. K., Bau, D., Viégas, F., Pfister, H., & Wattenberg, M. (2023). Emergent world representations: Exploring a sequence model trained on a synthetic task. In *Proceedings of the Eleventh International Conference on Learning Representations*. ICLR.

Lightman, H., Kosaraju, V., Burda, Y., Edwards, H., Baker, B., Lee, T., Leike, J., Schulman, J., Sutskever, I., & Cobbe, K. (2023). Let's verify step by step. *arXiv*. https://doi.org/10.48550/arXiv.2305.20050

Liu, N. F., Lin, K., Hewitt, J., Paranjape, A., Bevilacqua, M., Petroni, F., & Liang, P. (2024). Lost in the middle: How language models use long contexts. *Transactions of the Association for Computational Linguistics, 12*, 157–173. https://doi.org/10.1162/tacl_a_00638

Lu, Y., Liu, Q., Dai, D., Xiao, X., Lin, H., Han, X., Sun, L., & Wu, H. (2022). Unified structure generation for universal information extraction. In *Proceedings of ACL 2022* (pp. 5755–5772). ACL. https://doi.org/10.18653/v1/2022.acl-long.395

Luo, L., Zhao, Z., Haffari, R., Li, Y.-F., Gong, C., & Pan, S. (2024). Graph-constrained reasoning: Faithful reasoning on knowledge graphs with large language models. *arXiv*. https://doi.org/10.48550/arXiv.2410.13080

Mann, W. C., & Thompson, S. A. (1988). Rhetorical structure theory: Toward a functional theory of text organization. *Text, 8*(3), 243–281. https://doi.org/10.1515/text.1.1988.8.3.243

Marr, D. (1982). *Vision: A computational investigation into the human representation and processing of visual information*. W. H. Freeman.

Martinelli, G., Barba, E., & Navigli, R. (2024). Maverick: Efficient and accurate coreference resolution defying recent trends. In *Proceedings of ACL 2024* (pp. 13380–13394). ACL. https://doi.org/10.18653/v1/2024.acl-long.722

Meng, K., Bau, D., Andonian, A., & Belinkov, Y. (2022). Locating and editing factual associations in GPT. In *Advances in Neural Information Processing Systems 35* (pp. 17359–17372).

Min, S., Michael, J., Hajishirzi, H., & Zettlemoyer, L. (2020). AmbigQA: Answering ambiguous open-domain questions. In *Proceedings of EMNLP 2020* (pp. 5783–5797). ACL. https://doi.org/10.18653/v1/2020.emnlp-main.466

National Institute of Standards and Technology. (2023). *Artificial intelligence risk management framework (AI RMF 1.0)* (NIST AI 100-1). U.S. Department of Commerce. https://doi.org/10.6028/NIST.AI.100-1

Olsson, C., Elhage, N., Nanda, N., Joseph, N., DasSarma, N., Henighan, T., ... Olah, C. (2022). In-context learning and induction heads. *Transformer Circuits Thread*. https://transformer-circuits.pub/2022/in-context-learning-and-induction-heads

Ong, I., Almahairi, A., Wu, V., Chiang, W.-L., Wu, T., Gonzalez, J. E., Kadous, M. W., & Stoica, I. (2024). RouteLLM: Learning to route LLMs with preference data. *arXiv*. https://doi.org/10.48550/arXiv.2406.18665

Otmazgin, S., Cattan, A., & Goldberg, Y. (2022). F-coref: Fast, accurate and easy to use coreference resolution. In *Proceedings of AACL-IJCNLP 2022: System Demonstrations* (pp. 48–56). ACL.

Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). MemGPT: Towards LLMs as operating systems. *arXiv*. https://doi.org/10.48550/arXiv.2310.08560

Pearl, J. (2009). *Causality: Models, reasoning, and inference* (2nd ed.). Cambridge University Press. https://doi.org/10.1017/CBO9780511803161

Rasmussen, P., Paliychuk, P., Beauvais, T., Ryan, J., & Chalef, D. (2025). Zep: A temporal knowledge graph architecture for agent memory. *arXiv*. https://doi.org/10.48550/arXiv.2501.13956

Searle, J. R. (1969). *Speech acts: An essay in the philosophy of language*. Cambridge University Press.

Searle, J. R. (1980). Minds, brains, and programs. *Behavioral and Brain Sciences, 3*(3), 417–424. https://doi.org/10.1017/S0140525X00005756

Sharma, K., et al. (2025). OG-RAG: Ontology-grounded retrieval-augmented generation for large language models. *arXiv*. https://arxiv.org/abs/2412.15235

Snell, C., Lee, J., Xu, K., & Kumar, A. (2024). Scaling LLM test-time compute optimally can be more effective than scaling model parameters. *arXiv*. https://doi.org/10.48550/arXiv.2408.03314

Templeton, A., Conerly, T., Marcus, J., Lindsey, J., Bricken, T., Chen, B., ... Henighan, T. (2024). Scaling monosemanticity: Extracting interpretable features from Claude 3 Sonnet. *Transformer Circuits Thread*. https://transformer-circuits.pub/2024/scaling-monosemanticity

Traag, V. A., Waltman, L., & van Eck, N. J. (2019). From Louvain to Leiden: Guaranteeing well-connected communities. *Scientific Reports, 9*, 5233. https://doi.org/10.1038/s41598-019-41695-z

Tunstall, L., Reimers, N., Jo, U. E. S., Bates, L., Korat, D., Wasserblat, M., & Pereg, O. (2022). Efficient few-shot learning without prompts. *arXiv*. https://doi.org/10.48550/arXiv.2209.11055

Ullman, T. (2023). Large language models fail on trivial alterations to theory-of-mind tasks. *arXiv*. https://doi.org/10.48550/arXiv.2302.08399

von Oswald, J., Niklasson, E., Randazzo, E., Sacramento, J., Mordvintsev, A., Zhmoginov, A., & Vladymyrov, M. (2023). Transformers learn in-context by gradient descent. In *Proceedings of the 40th International Conference on Machine Learning* (pp. 35151–35174). PMLR.

Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Xiao, C., Zhu, Y., Fan, L., & Anandkumar, A. (2023). Voyager: An open-ended embodied agent with large language models. *arXiv*. https://doi.org/10.48550/arXiv.2305.16291

Wang, X., Wei, J., Schuurmans, D., Le, Q., Chi, E., Narang, S., Chowdhery, A., & Zhou, D. (2023). Self-consistency improves chain of thought reasoning in language models. In *Proceedings of the Eleventh International Conference on Learning Representations*. ICLR.

Wei, J., Wang, X., Schuurmans, D., Bosma, M., Ichter, B., Xia, F., Chi, E., Le, Q., & Zhou, D. (2022). Chain-of-thought prompting elicits reasoning in large language models. In *Advances in Neural Information Processing Systems 35* (pp. 24824–24837).

Willard, B. T., & Louf, R. (2023). Efficient guided generation for large language models. *arXiv*. https://doi.org/10.48550/arXiv.2307.09702

Yao, S., Yu, D., Zhao, J., Shafran, I., Griffiths, T. L., Cao, Y., & Narasimhan, K. (2023). Tree of thoughts: Deliberate problem solving with large language models. In *Advances in Neural Information Processing Systems 36* (pp. 11809–11822).

Zaratiana, U., Tomeh, N., Holat, P., & Charnois, T. (2024). GLiNER: Generalist model for named entity recognition using bidirectional transformer. In *Proceedings of NAACL 2024* (pp. 5364–5376). ACL. https://doi.org/10.18653/v1/2024.naacl-long.300

Zhang, H., Diao, S., Lin, Y., Fung, Y. R., Lian, Q., Wang, X., Chen, Y., Ji, H., & Zhang, T. (2024). R-Tuning: Instructing large language models to say 'I don't know'. In *Proceedings of NAACL 2024* (pp. 7106–7132). ACL. https://doi.org/10.18653/v1/2024.naacl-long.394

Zhou, D., Schärli, N., Hou, L., Wei, J., Scales, N., Wang, X., ... Chi, E. (2023). Least-to-most prompting enables complex reasoning in large language models. In *Proceedings of the Eleventh International Conference on Learning Representations*. ICLR.

Zhou, S., Zhou, T., Yang, Y., Long, G., Ye, D., Jiang, J., & Zhang, C. (2024). WALL-E: World alignment by rule learning improves world model-based LLM agents. *arXiv*. https://doi.org/10.48550/arXiv.2410.07484

Zhou, S., Zhou, T., Yang, Y., Long, G., Ye, D., Jiang, J., & Zhang, C. (2025). WALL-E 2.0: World alignment by neurosymbolic learning improves world model-based LLM agents. *arXiv*. https://doi.org/10.48550/arXiv.2504.15785

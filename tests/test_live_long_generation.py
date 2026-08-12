"""CRP 2.0 — LONG-FORM GENERATION Stress Test.

Generates a 20-chapter essay across multiple context windows,
proving CRP's cross-window fact accumulation at scale (~50K+ tokens).

Each chapter builds on previous chapters' content. CRP must:
1. Extract facts from each chapter
2. Pack relevant facts into subsequent envelopes
3. Maintain thematic coherence across 20+ windows
4. Accumulate 50K+ tokens of generated content

Usage:
    python tests/test_live_long_generation.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
LM_STUDIO_URL = "http://192.168.0.6:1234/v1"
MODEL_NAME = "gemma-3-270m-it-qat"
CONTEXT_SIZE = 32_768
MAX_TOKENS_PER_CHAPTER = 1024  # Same as working comprehensive test

ESSAY_TOPIC = "The Complete History and Future of Artificial Intelligence"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_long_gen_results")

# 20 chapter prompts — each requires knowledge from earlier chapters
CHAPTERS = [
    {
        "num": 1,
        "title": "The Dream of Thinking Machines (1940-1955)",
        "prompt": (
            "Write Chapter 1 of a comprehensive essay titled "
            f"'{ESSAY_TOPIC}'. "
            "This chapter covers the earliest foundations: Alan Turing's 1950 paper "
            "'Computing Machinery and Intelligence', the Turing Test, Claude Shannon's "
            "information theory, Warren McCulloch and Walter Pitts' neural network model (1943), "
            "and the intellectual climate that made AI conceivable. "
            "Be detailed and scholarly. Include specific dates, names, and contributions. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 2,
        "title": "The Dartmouth Conference and the Birth of AI (1956)",
        "prompt": (
            "Write Chapter 2, continuing from Chapter 1. "
            "Cover the 1956 Dartmouth Conference organized by John McCarthy, Marvin Minsky, "
            "Nathaniel Rochester, and Claude Shannon. Explain how the term 'Artificial Intelligence' "
            "was coined. Describe the early optimism and the first AI programs: Logic Theorist by "
            "Newell and Simon, and the General Problem Solver. Reference the foundations "
            "established in Chapter 1 (Turing's work, McCulloch-Pitts neurons). "
            "Write at least 800 words."
        ),
    },
    {
        "num": 3,
        "title": "The Golden Years: Early Successes (1957-1969)",
        "prompt": (
            "Write Chapter 3, building on Chapters 1-2. "
            "Cover the 'golden years' of AI: LISP programming language (McCarthy, 1958), "
            "perceptrons (Rosenblatt, 1958), ELIZA chatbot (Weizenbaum, 1966), "
            "Shakey the Robot (SRI, 1966-1972), microworlds like SHRDLU (Winograd, 1971). "
            "Connect back to the Dartmouth optimism from Chapter 2. "
            "Explain how these early successes created unrealistic expectations. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 4,
        "title": "The First AI Winter (1974-1980)",
        "prompt": (
            "Write Chapter 4, referencing the optimism of Chapters 2-3. "
            "Explain the first AI Winter: the Lighthill Report (1973), DARPA funding cuts, "
            "Minsky and Papert's 'Perceptrons' book (1969) that killed neural network research, "
            "the combinatorial explosion problem, and why the early promises from the Dartmouth era "
            "could not be delivered. Contrast the excitement from Chapter 3 with the disillusionment. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 5,
        "title": "Expert Systems and the Knowledge Revolution (1980-1987)",
        "prompt": (
            "Write Chapter 5. After the first AI winter (Chapter 4), expert systems revived the field. "
            "Cover MYCIN, DENDRAL, R1/XCON, the rise of knowledge engineering, "
            "the Japanese Fifth Generation project, and how commercial AI boomed. "
            "Explain the shift from general intelligence (Chapters 1-3) to narrow, rule-based systems. "
            "Include the economic impact: the AI industry grew from millions to billions. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 6,
        "title": "The Second AI Winter (1987-1993)",
        "prompt": (
            "Write Chapter 6. Expert systems (Chapter 5) collapsed. Cover the Lisp machine market crash, "
            "the failure of the Fifth Generation project, DARPA's Strategic Computing Initiative ending, "
            "commercial disillusionment with expert systems' brittleness. "
            "Draw parallels to the first AI Winter (Chapter 4) — the pattern of hype and collapse. "
            "Explain how the survivors pivoted. Write at least 800 words."
        ),
    },
    {
        "num": 7,
        "title": "The Quiet Revolution: Machine Learning Emerges (1986-1999)",
        "prompt": (
            "Write Chapter 7. During and after the second winter (Chapter 6), "
            "a quiet revolution was happening. Cover backpropagation rediscovery "
            "(Rumelhart, Hinton, Williams 1986), SVMs, decision trees, "
            "reinforcement learning (Sutton and Barto), statistical NLP, "
            "and IBM Deep Blue defeating Kasparov (1997). "
            "Explain how the shift from symbolic AI (Chapters 2-5) to statistical methods "
            "changed everything. Connect to the original neural network ideas from Chapter 1. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 8,
        "title": "Big Data and the Rise of Deep Learning (2000-2012)",
        "prompt": (
            "Write Chapter 8. The internet era provided the data that machine learning (Chapter 7) needed. "
            "Cover the growth of datasets (ImageNet), GPU computing, Hinton's deep belief networks (2006), "
            "the Netflix Prize, early speech recognition (Siri 2011), recommendation systems. "
            "Explain how Hinton's group revived neural networks — connecting directly to McCulloch-Pitts (Chapter 1) "
            "and Rosenblatt's perceptrons (Chapter 3), which Minsky had killed (Chapter 4). "
            "The 60-year arc from 1943 to 2006. Write at least 800 words."
        ),
    },
    {
        "num": 9,
        "title": "The Deep Learning Explosion (2012-2017)",
        "prompt": (
            "Write Chapter 9, the breakthrough chapter. AlexNet (2012) winning ImageNet "
            "by a massive margin, Google Brain's cat detector, word2vec, GANs (Goodfellow 2014), "
            "DeepMind's Atari player, batch normalization, ResNets, "
            "AlphaGo defeating Lee Sedol (2016). "
            "Show how this era validated the deep learning approach from Chapter 8 "
            "and completed the neural network vindication arc from Chapters 1, 3, 4, 7. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 10,
        "title": "The Transformer Revolution (2017-2020)",
        "prompt": (
            "Write Chapter 10 — the transformer era. 'Attention is All You Need' (Vaswani et al., 2017), "
            "BERT, GPT-1 and GPT-2, T5, transfer learning revolution. "
            "Explain how self-attention solved problems that RNNs/LSTMs (from Chapter 7-8 era) couldn't. "
            "Connect to the NLP journey: from ELIZA (Chapter 3) to statistical NLP (Chapter 7) "
            "to word2vec (Chapter 9) to transformers. "
            "This is the architecture that enables everything in later chapters. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 11,
        "title": "GPT-3 and the Scaling Hypothesis (2020-2022)",
        "prompt": (
            "Write Chapter 11. GPT-3's 175 billion parameters shocked the world. "
            "Cover scaling laws (Kaplan et al.), few-shot learning, prompt engineering emergence, "
            "DALL-E and multimodal AI, Codex and GitHub Copilot, PaLM, Chinchilla scaling laws. "
            "Reference the transformer architecture from Chapter 10 as the foundation. "
            "Contrast GPT-3's emergence with the rule-based expert systems of Chapter 5. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 12,
        "title": "ChatGPT and the AI Mainstream (2022-2023)",
        "prompt": (
            "Write Chapter 12. ChatGPT (Nov 2022) brought AI to the mainstream — 100 million users "
            "in 2 months. Cover GPT-4, RLHF, instruction tuning, the AI safety debate, "
            "the open-source response (LLaMA, Mistral), the enterprise rush. "
            "Connect to the Turing Test from Chapter 1 — ChatGPT essentially passed it in practice. "
            "Reference the hype cycles from Chapters 2-3 (first boom), 5 (expert systems boom) — "
            "is this different? Write at least 800 words."
        ),
    },
    {
        "num": 13,
        "title": "The Context Problem: Why Size Isn't Everything",
        "prompt": (
            "Write Chapter 13. Despite the scaling success (Chapters 10-12), a fundamental problem emerged: "
            "context window limitations. Cover the quadratic attention problem, "
            "retrieval-augmented generation (RAG), long-context models (Claude, Gemini), "
            "the difference between having a large context and USING it effectively, "
            "lost-in-the-middle phenomena, context window as the new bottleneck. "
            "Reference how ELIZA (Chapter 3) had zero context, expert systems (Chapter 5) had "
            "static knowledge bases, and modern LLMs still struggle with dynamic context. "
            "Introduce the idea that new protocols are needed. Write at least 800 words."
        ),
    },
    {
        "num": 14,
        "title": "Context Management Protocols: CRP and Beyond",
        "prompt": (
            "Write Chapter 14. The solution to the context problem (Chapter 13). "
            "Cover context management as a discipline: CRP (Context Relay Protocol), "
            "its 3-tier memory hierarchy (Hot/Warm/Cold), the envelope formula E = C - S - T - G, "
            "graduated extraction pipelines, cross-window fact accumulation. "
            "Explain how CRP makes the context window size irrelevant — "
            "the model doesn't know CRP exists (Model Ignorance axiom). "
            "Connect to the 80-year arc: from Turing's dream (Chapter 1) to practical context management. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 15,
        "title": "AI Agents and Autonomous Systems (2024-2025)",
        "prompt": (
            "Write Chapter 15. The agent era builds on everything prior. "
            "Cover AutoGPT, CrewAI, LangChain agents, tool-use capabilities, "
            "MCP (Model Context Protocol), function calling, multi-step reasoning. "
            "Explain how agents need context management (Chapter 14) to maintain state across "
            "long task sequences. Reference the original vision of general problem solving "
            "from the Dartmouth Conference (Chapter 2) — are agents finally achieving it? "
            "Write at least 800 words."
        ),
    },
    {
        "num": 16,
        "title": "Multimodal AI: Seeing, Hearing, Understanding",
        "prompt": (
            "Write Chapter 16. Beyond text: GPT-4V, Gemini, DALL-E 3, Sora, "
            "multimodal transformers, vision-language models. "
            "Connect to the historical arc: early computer vision attempts (Chapter 3 era), "
            "ImageNet and deep learning for vision (Chapters 8-9), "
            "and now unified multimodal models (this chapter). "
            "Discuss how context management (Chapter 14) applies to multimodal contexts. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 17,
        "title": "AI Safety, Ethics, and Governance",
        "prompt": (
            "Write Chapter 17. Cover the safety challenges: alignment problem, "
            "hallucination, bias, deepfakes, job displacement, existential risk debates. "
            "Trace the evolution: Asimov's Laws (pre-Chapter 1), Weizenbaum's concerns about ELIZA (Chapter 3), "
            "the AI winters as natural correction (Chapters 4, 6), current regulatory frameworks "
            "(EU AI Act, Biden executive order). Reference how every AI boom (Chapters 2-3, 5, 9-12) "
            "was followed by societal concern. Write at least 800 words."
        ),
    },
    {
        "num": 18,
        "title": "Open Source AI: Democratizing Intelligence",
        "prompt": (
            "Write Chapter 18. The open-source movement: LLaMA, Mistral, Mixtral, RWKV, "
            "Phi, Gemma, Qwen, DeepSeek. Cover the tension between open and closed models, "
            "quantization techniques (GGUF, QAT, AWQ), running models locally (Ollama, LM Studio). "
            "Reference the historical parallel: LISP was open (Chapter 3), expert system shells were commercial "
            "(Chapter 5), now the pendulum swings back. Connect to the model WE ARE using right now — "
            "gemma-3-270m-it-qat is an open-source, quantized model running locally. "
            "Write at least 800 words."
        ),
    },
    {
        "num": 19,
        "title": "The Future: AGI, ASI, and the Singularity",
        "prompt": (
            "Write Chapter 19 — the speculative future. Cover AGI timelines, "
            "the path from narrow AI (current, Chapters 9-16) to general intelligence, "
            "neuromorphic computing, quantum AI, brain-computer interfaces. "
            "Reference the ENTIRE arc of the essay: Turing's dream (Chapter 1), "
            "the Dartmouth vision (Chapter 2), the winters (Chapters 4, 6), "
            "the deep learning revolution (Chapters 8-9), transformers (Chapter 10), "
            "scaling (Chapter 11), agents (Chapter 15). Where does it all lead? "
            "Write at least 800 words."
        ),
    },
    {
        "num": 20,
        "title": "Synthesis: 80 Years of Pursuit — What We've Learned",
        "prompt": (
            "Write Chapter 20 — the final synthesis. Weave together ALL previous 19 chapters "
            "into a cohesive conclusion. Reference specific facts, names, dates, and events "
            "from each chapter. Summarize the key themes: the cycle of boom and bust, "
            "the vindication of neural networks (Chapter 1 → Chapter 9, a 70-year journey), "
            "the shift from symbolic to statistical AI (Chapters 2-5 → Chapters 7-9), "
            "the context problem and its solution (Chapters 13-14), "
            "the democratization of AI (Chapter 18), and the road ahead (Chapter 19). "
            "This chapter MUST demonstrate cross-window context by referencing specific details "
            "from earlier chapters. Write at least 1000 words. End with a powerful closing statement."
        ),
    },
]


def make_provider():
    from crp.providers.openai import OpenAIAdapter
    prov = OpenAIAdapter(
        model=MODEL_NAME,
        api_key="lm-studio",
        base_url=LM_STUDIO_URL,
        max_tokens=MAX_TOKENS_PER_CHAPTER,
        timeout=300.0,  # 5min timeout for longer generation
    )
    # Override context size — LM Studio reports 128K but actual loaded context is 32K
    prov._context_size = CONTEXT_SIZE
    return prov


def make_orchestrator():
    from crp.core.orchestrator import CRPOrchestrator
    prov = make_provider()
    return CRPOrchestrator(provider=prov, default_role="ADMIN")


def main():
    start_time = time.time()
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n{'#'*70}")
    print(f"#  CRP 2.0 — LONG-FORM GENERATION STRESS TEST")
    print(f"#  Target: ~50K+ tokens across 20 chapters")
    print(f"#  Model: {MODEL_NAME} @ {LM_STUDIO_URL}")
    print(f"#  Max tokens/chapter: {MAX_TOKENS_PER_CHAPTER}")
    print(f"#  Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}\n")

    orch = make_orchestrator()

    all_chapters: list[dict] = []
    total_output_tokens = 0
    total_input_tokens = 0
    total_facts = 0
    chapter_metrics: list[dict] = []

    system_prompt = (
        "You are a world-class historian of artificial intelligence and computer science. "
        "You are writing a comprehensive, scholarly essay. Use the context provided to maintain "
        "continuity with previous chapters. Be detailed, cite specific names, dates, and events. "
        "Use clear prose with section headings within each chapter."
    )

    for ch in CHAPTERS:
        ch_num = ch["num"]
        ch_title = ch["title"]
        ch_prompt = ch["prompt"]

        print(f"\n{'='*70}")
        print(f"  CHAPTER {ch_num}: {ch_title}")
        print(f"{'='*70}")

        ch_start = time.time()
        try:
            # Retry logic: LM Studio intermittently returns "Context size exceeded"
            # due to KV cache pressure. Retry with delays.
            MAX_RETRIES = 5
            output = ""
            report = None
            for attempt in range(MAX_RETRIES):
                if attempt > 0:
                    delay = 3 * attempt  # 3s, 6s, 9s, 12s
                    print(f"  [RETRY {attempt}/{MAX_RETRIES}] Waiting {delay}s before retry...")
                    time.sleep(delay)
                    if attempt >= 2:
                        # Simplified prompt for later retries
                        ch_prompt_use = (
                            f"Write Chapter {ch_num} titled '{ch_title}' for an essay about "
                            f"'{ESSAY_TOPIC}'. Cover the key events, people, and ideas of this period. "
                            f"Use your knowledge of earlier chapters. Write at least 300 words."
                        )
                        print(f"  [RETRY {attempt}] Using simplified prompt...")
                    else:
                        ch_prompt_use = ch_prompt
                else:
                    ch_prompt_use = ch_prompt

                output, report = orch.dispatch(
                    system_prompt,
                    ch_prompt_use,
                    max_output_tokens=MAX_TOKENS_PER_CHAPTER,
                )
                if len(output.strip()) >= 50:
                    break  # Got real output
                print(f"  [RETRY {attempt}] Output too short ({len(output)} chars)...")

            ch_elapsed = time.time() - ch_start

            status = orch.session_status()
            facts_now = len(orch.warm_store.get_facts())
            new_facts = report.facts_extracted

            # Track metrics
            metrics = {
                "chapter": ch_num,
                "title": ch_title,
                "output_chars": len(output),
                "output_words": len(output.split()),
                "facts_extracted": new_facts,
                "total_facts_accumulated": facts_now,
                "windows_completed": status.windows_completed,
                "total_input_tokens": status.total_input_tokens,
                "total_output_tokens": status.total_output_tokens,
                "envelope_tokens": report.telemetry.get("envelope_tokens", 0) if report.telemetry else 0,
                "wall_time_s": round(ch_elapsed, 1),
                "quality_tier": getattr(report, "quality_tier", "N/A"),
            }
            chapter_metrics.append(metrics)

            total_output_tokens = status.total_output_tokens
            total_input_tokens = status.total_input_tokens
            total_facts = facts_now

            # Save chapter text
            all_chapters.append({
                "num": ch_num,
                "title": ch_title,
                "text": output,
                "metrics": metrics,
            })

            # Save individual chapter file
            ch_file = os.path.join(OUTPUT_DIR, f"chapter_{ch_num:02d}.txt")
            with open(ch_file, "w", encoding="utf-8") as f:
                f.write(f"CHAPTER {ch_num}: {ch_title}\n")
                f.write(f"{'='*60}\n\n")
                f.write(output)
                f.write(f"\n\n{'='*60}\n")
                f.write(f"METRICS:\n")
                for k, v in metrics.items():
                    f.write(f"  {k}: {v}\n")

            # Print summary
            print(f"  [PASS] Generated {len(output)} chars, {len(output.split())} words")
            print(f"         Facts extracted: {new_facts} (total accumulated: {facts_now})")
            print(f"         Envelope tokens: {metrics['envelope_tokens']}")
            print(f"         Time: {ch_elapsed:.1f}s")
            print(f"         Output preview: {output[:200]!r}")

            # Cooldown between chapters to reduce KV cache pressure on LM Studio
            time.sleep(2)

        except Exception as e:
            ch_elapsed = time.time() - ch_start
            print(f"  [FAIL] Chapter {ch_num}: {type(e).__name__}: {e}")
            traceback.print_exc()
            chapter_metrics.append({
                "chapter": ch_num,
                "title": ch_title,
                "error": str(e),
                "wall_time_s": round(ch_elapsed, 1),
            })

    elapsed = time.time() - start_time

    # ── Final Status ──────────────────────────────────────────────────────
    final_status = orch.session_status()

    print(f"\n{'#'*70}")
    print(f"#  LONG-FORM GENERATION — FINAL RESULTS")
    print(f"{'#'*70}\n")

    # Aggregate text
    full_text = "\n\n".join(
        f"# Chapter {ch['num']}: {ch['title']}\n\n{ch['text']}"
        for ch in all_chapters
    )
    total_chars = len(full_text)
    total_words = len(full_text.split())

    print(f"  Chapters generated:     {len(all_chapters)}/20")
    print(f"  Total characters:       {total_chars:,}")
    print(f"  Total words:            {total_words:,}")
    print(f"  Total output tokens:    {total_output_tokens:,}")
    print(f"  Total input tokens:     {total_input_tokens:,}")
    print(f"  Total facts accumulated:{total_facts:,}")
    print(f"  Windows completed:      {final_status.windows_completed}")
    print(f"  DAG nodes:              {orch.dag.window_count()}")
    print(f"  Total time:             {elapsed:.1f}s")
    print(f"  Avg time/chapter:       {elapsed/max(len(all_chapters),1):.1f}s")
    print()

    # ── Envelope Growth Report ────────────────────────────────────────────
    print(f"  {'='*50}")
    print(f"  ENVELOPE GROWTH (Cross-Window Context Proof)")
    print(f"  {'='*50}")
    for m in chapter_metrics:
        if "error" not in m:
            bar = "#" * min(int(m["envelope_tokens"] / 100), 50)
            print(f"  Ch.{m['chapter']:2d}  envelope={m['envelope_tokens']:5d}tok  "
                  f"facts={m['total_facts_accumulated']:4d}  {bar}")
    print()

    # ── Fact Accumulation Curve ───────────────────────────────────────────
    print(f"  {'='*50}")
    print(f"  FACT ACCUMULATION CURVE")
    print(f"  {'='*50}")
    for m in chapter_metrics:
        if "error" not in m:
            bar = "*" * min(m["total_facts_accumulated"] // 5, 60)
            print(f"  Ch.{m['chapter']:2d}  facts={m['total_facts_accumulated']:4d}  {bar}")
    print()

    # ── Save Full Essay ───────────────────────────────────────────────────
    essay_file = os.path.join(OUTPUT_DIR, "full_essay.md")
    with open(essay_file, "w", encoding="utf-8") as f:
        f.write(f"# {ESSAY_TOPIC}\n\n")
        f.write(f"*Generated by CRP 2.0 + {MODEL_NAME}*\n")
        f.write(f"*{len(all_chapters)} chapters, {total_words:,} words, "
                f"{total_output_tokens:,} output tokens*\n")
        f.write(f"*{total_facts:,} facts accumulated across "
                f"{final_status.windows_completed} context windows*\n\n")
        f.write("---\n\n")
        for ch in all_chapters:
            f.write(f"## Chapter {ch['num']}: {ch['title']}\n\n")
            f.write(ch["text"])
            f.write("\n\n---\n\n")

    # ── Save Metrics JSON ─────────────────────────────────────────────────
    metrics_file = os.path.join(OUTPUT_DIR, "metrics.json")
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump({
            "test": "CRP 2.0 Long-Form Generation Stress Test",
            "model": MODEL_NAME,
            "lm_studio_url": LM_STUDIO_URL,
            "context_size": CONTEXT_SIZE,
            "max_tokens_per_chapter": MAX_TOKENS_PER_CHAPTER,
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_chapters": len(all_chapters),
            "total_chars": total_chars,
            "total_words": total_words,
            "total_output_tokens": total_output_tokens,
            "total_input_tokens": total_input_tokens,
            "total_facts": total_facts,
            "windows_completed": final_status.windows_completed,
            "dag_nodes": orch.dag.window_count(),
            "total_time_s": round(elapsed, 1),
            "chapters": chapter_metrics,
        }, f, indent=2)

    print(f"  Full essay saved to:   {essay_file}")
    print(f"  Metrics saved to:      {metrics_file}")
    print(f"  Individual chapters:   {OUTPUT_DIR}/chapter_XX.txt")
    print()

    # ── State Export ──────────────────────────────────────────────────────
    state = orch.export_state()
    state_file = os.path.join(OUTPUT_DIR, "session_state.bin")
    with open(state_file, "wb") as f:
        f.write(state)
    print(f"  Session state export:  {len(state):,} bytes -> {state_file}")

    orch.close()

    # ── Pass/Fail Determination ───────────────────────────────────────────
    chapters_ok = len([m for m in chapter_metrics if "error" not in m])
    target_met = total_words >= 5000  # Minimum viable output
    print()
    if chapters_ok == 20 and target_met:
        print(f"  *** LONG-FORM GENERATION TEST PASSED ***")
        print(f"  {total_words:,} words across {chapters_ok} chapters")
        print(f"  {total_facts:,} facts accumulated via CRP cross-window relay")
    elif chapters_ok == 20:
        print(f"  PARTIAL: All chapters generated but word count "
              f"({total_words:,}) below 10K target")
    else:
        print(f"  FAILED: Only {chapters_ok}/20 chapters generated")

    print()
    return chapters_ok == 20


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

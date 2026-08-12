# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Comprehensive evaluation harness for the CRP PRM verifier.

Three tiers plus baselines:
1. Held-out prm800k test steps the trainer never saw (training eval used
   test[:500]; this harness defaults to test[500:1500]).
2. Baselines on the same slice: majority class, and zero-shot
   cross-encoder/nli-deberta-v3-xsmall (the off-the-shelf NLI model CRP
   could have used instead — entailment -> VALID, else INVALID).
3. Curated reasoning chains with known-valid and known-invalid steps.

Usage::

    python scripts/eval_crp_prm.py --model AutoCyberAI/crp-prm-deberta-v1
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
from collections import Counter
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report

logger = logging.getLogger(__name__)

# Curated reasoning steps: (premises, step, expected)
CURATED_CASES: list[tuple[str, str, str]] = [
    (
        "Problem: A train travels 120 km in 2 hours. What is its average speed?",
        "Speed is distance over time.",
        "VALID",
    ),
    (
        "Problem: A train travels 120 km in 2 hours. Speed is distance over time.",
        "So the average speed is 120 / 2 = 60 km per hour.",
        "VALID",
    ),
    (
        "Problem: A train travels 120 km in 2 hours. Speed is distance over time.",
        "So the average speed is 120 * 2 = 240 km per hour.",
        "INVALID",
    ),
    (
        "Problem: Server returned 502. The load balancer health check is failing.",
        "The database is the root cause.",
        "INVALID",
    ),
    (
        "Problem: Server returned 502. The load balancer health check is failing.",
        "The failing health check explains why traffic is not reaching the backends.",
        "VALID",
    ),
    (
        "Problem: All even numbers are divisible by 2. 14 is even.",
        "Therefore 14 is divisible by 2.",
        "VALID",
    ),
    (
        "Problem: All even numbers are divisible by 2. 14 is even.",
        "Therefore 14 is divisible by 4.",
        "INVALID",
    ),
    (
        "Problem: The function must return a sorted list. The current implementation uses bubble sort.",
        "Bubble sort produces a sorted list, so the implementation meets the requirement.",
        "VALID",
    ),
    (
        "Problem: The function must return a sorted list. The current implementation uses bubble sort.",
        "Bubble sort is O(n log n), which is optimal.",
        "INVALID",
    ),
    (
        "Problem: The user asked for the capital of France.",
        "Paris is the capital of France, so the answer is Paris.",
        "VALID",
    ),
]


def _load_trainer_module():
    path = Path(__file__).parent / "train_crp_prm.py"
    spec = importlib.util.spec_from_file_location("train_crp_prm", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split_prm_text(text: str) -> tuple[str, str]:
    """Split 'premises: ... [SEP] step: ...' into (premise, hypothesis)."""
    premises, _, step = text.partition(" [SEP] step: ")
    return premises.removeprefix("premises: "), step


def _main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CRP PRM verifier")
    parser.add_argument("--model", default="AutoCyberAI/crp-prm-deberta-v1")
    parser.add_argument("--eval_start", type=int, default=500)
    parser.add_argument("--eval_samples", type=int, default=1000)
    parser.add_argument(
        "--nli_baseline",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Also score the zero-shot NLI baseline (downloads ~350 MB)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    trainer_mod = _load_trainer_module()

    logger.info("Loading prm800k test[%d:%d]...", args.eval_start, args.eval_start + args.eval_samples)
    from datasets import load_dataset

    raw = load_dataset("trl-lib/prm800k", split="test")
    raw = raw.select(range(args.eval_start, min(args.eval_start + args.eval_samples, len(raw))))
    texts, gold = [], []
    for row in raw:
        for ex in trainer_mod._expand_record(row["prompt"], row["completions"], row["labels"]):
            texts.append(ex["text"])
            gold.append("VALID" if ex["labels"] == 1 else "INVALID")
    logger.info("Held-out steps: %d (%s)", len(gold), dict(Counter(gold)))

    from transformers import pipeline

    logger.info("Loading PRM %s...", args.model)
    prm = pipeline("text-classification", model=args.model, top_k=None, truncation=True)

    def prm_predict(batch_texts: list[str]) -> list[str]:
        out = []
        for res in prm(batch_texts, batch_size=16):
            best = max(res, key=lambda r: r["score"])
            out.append(best["label"])
        return out

    preds = prm_predict(texts)

    majority = Counter(gold).most_common(1)[0][0]
    base_acc = accuracy_score(gold, [majority] * len(gold))
    acc = accuracy_score(gold, preds)
    print(f"\n=== Tier 1: held-out prm800k steps ({len(gold)}) ===")
    print(f"Majority-class baseline: {base_acc:.4f}")
    print(f"CRP PRM ({args.model}):  {acc:.4f}")
    print(classification_report(gold, preds, digits=3))

    if args.nli_baseline:
        logger.info("Scoring zero-shot NLI baseline (cross-encoder/nli-deberta-v3-xsmall)...")
        nli = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-xsmall")
        pairs = [{"text": p, "text_pair": s} for p, s in map(_split_prm_text, texts)]
        nli_preds = []
        for res in nli(pairs, batch_size=8, top_k=None, truncation=True):
            best = max(res, key=lambda r: r["score"])
            nli_preds.append("VALID" if best["label"].lower() == "entailment" else "INVALID")
        nli_acc = accuracy_score(gold, nli_preds)
        print(f"Zero-shot NLI baseline:  {nli_acc:.4f}")

    print("\n=== Tier 2: curated reasoning cases ===")
    curated_texts = [f"premises: {p} [SEP] step: {s}" for p, s, _ in CURATED_CASES]
    expected = [e for _, _, e in CURATED_CASES]
    got = prm_predict(curated_texts)
    correct = 0
    for (_premises, step, exp), pred in zip(CURATED_CASES, got):
        ok = pred == exp
        correct += ok
        mark = "OK " if ok else "MISS"
        print(f"[{mark}] expected={exp:<8} got={pred:<8} | {step[:75]}")
    print(f"\nCurated: {correct}/{len(expected)} correct")


if __name__ == "__main__":
    _main()

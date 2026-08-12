# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Comprehensive evaluation harness for the CRP intent SetFit model.

Rebuilds the exact training data mix (same shuffle seed as
``train_crp_intent_setfit.py``), then evaluates on a held-out slice that the
model never trained on. Reports overall accuracy, a per-class
classification report, and a curated set of production-style CRP prompts.

Usage::

    python scripts/eval_crp_intent_setfit.py \
        --model AutoCyberAI/crp-intent-setfit \
        --max_samples 10000 --eval_start 2000 --eval_samples 2000
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
from pathlib import Path

from sklearn.metrics import accuracy_score, classification_report

logger = logging.getLogger(__name__)

# Curated production-style prompts covering the four CRP speech acts,
# drawn from agentic / developer-tooling phrasing (not from any training source).
PRODUCTION_CASES: list[tuple[str, str]] = [
    # request
    ("Please scan the repository for compliance issues.", "request"),
    ("Summarise the audit log from the last 24 hours.", "request"),
    ("Can you refactor this function to use async calls?", "request"),
    ("I need you to compare the two gateway configurations.", "request"),
    ("Generate an evidence pack for the EU AI Act review.", "request"),
    # question
    ("What is the current deployment status?", "question"),
    ("How does the token budget get allocated per window?", "question"),
    ("Why did the verification relay return UNKNOWN?", "question"),
    ("When was the last checkpoint approved?", "question"),
    ("Which provider handled this dispatch?", "question"),
    # assertion
    ("I believe the server is down.", "assertion"),
    ("It seems the embedding model changed mid-session.", "assertion"),
    ("The latency spike started after the config reload.", "assertion"),
    ("This response contradicts the earlier claim.", "assertion"),
    ("The audit chain appears to be intact.", "assertion"),
    # expressive
    ("This is frustrating and slow.", "expressive"),
    ("Great work, the migration finally passed!", "expressive"),
    ("I am really unhappy with these false positives.", "expressive"),
    ("Fantastic, the benchmark beat the baseline!", "expressive"),
    ("Ugh, the gateway timed out again.", "expressive"),
]


def _load_trainer_module():
    """Import the training script as a module to reuse its data prep."""
    path = Path(__file__).parent / "train_crp_intent_setfit.py"
    spec = importlib.util.spec_from_file_location("train_crp_intent_setfit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate CRP intent SetFit model")
    parser.add_argument("--model", default="AutoCyberAI/crp-intent-setfit")
    parser.add_argument("--max_samples", type=int, default=10000)
    parser.add_argument(
        "--eval_start",
        type=int,
        default=2000,
        help="Start offset into the shuffled mix (training eval used 0:2000)",
    )
    parser.add_argument("--eval_samples", type=int, default=2000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    trainer_mod = _load_trainer_module()

    logger.info("Rebuilding data mix (max_samples=%d)...", args.max_samples)
    full = trainer_mod._prepare_public_datasets(args.max_samples)
    test = full.select(range(args.eval_start, args.eval_start + args.eval_samples))
    logger.info("Held-out slice: %d examples (offset %d)", len(test), args.eval_start)

    logger.info("Loading model %s...", args.model)
    from setfit import SetFitModel

    model = SetFitModel.from_pretrained(args.model)

    logger.info("Predicting held-out slice...")
    gold = test["label"]
    preds = [str(p) for p in model.predict(test["text"])]

    acc = accuracy_score(gold, preds)
    print(f"\n=== Held-out accuracy: {acc:.4f} on {len(test)} examples ===")
    print(classification_report(gold, preds, digits=3))

    print("=== Production-style prompts ===")
    texts = [t for t, _ in PRODUCTION_CASES]
    expected = [e for _, e in PRODUCTION_CASES]
    got = [str(p) for p in model.predict(texts)]
    correct = 0
    for text, exp, pred in zip(texts, expected, got):
        ok = pred == exp
        correct += ok
        mark = "OK " if ok else "MISS"
        print(f"[{mark}] expected={exp:<10} got={pred:<10} | {text}")
    print(f"\nProduction prompts: {correct}/{len(texts)} correct")


if __name__ == "__main__":
    _main()

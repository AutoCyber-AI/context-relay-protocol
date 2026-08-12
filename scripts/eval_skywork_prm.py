# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Evaluate Skywork-o1-Open-PRM-Qwen-2.5-1.5B as a candidate CRP PRM backend.

Uses Skywork's official inference harness (cloned to
``.cache/skywork-o1-prm-inference``) to score every step of held-out prm800k
solutions, then compares against the same curated reasoning cases used for
the CRP PRM. Also measures per-record CPU latency.

Usage::

    python scripts/eval_skywork_prm.py \
        --model Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B \
        --eval_start 500 --eval_samples 60
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score

logger = logging.getLogger(__name__)

SKYWORK_UTILS = Path(__file__).parent.parent / ".cache" / "skywork-o1-prm-inference"

CURATED_CASES: list[tuple[str, str, str]] = [
    ("A train travels 120 km in 2 hours. What is its average speed?",
     "Speed is distance over time.", "VALID"),
    ("A train travels 120 km in 2 hours. Speed is distance over time.",
     "So the average speed is 120 / 2 = 60 km per hour.", "VALID"),
    ("A train travels 120 km in 2 hours. Speed is distance over time.",
     "So the average speed is 120 * 2 = 240 km per hour.", "INVALID"),
    ("Server returned 502. The load balancer health check is failing.",
     "The database is the root cause.", "INVALID"),
    ("Server returned 502. The load balancer health check is failing.",
     "The failing health check explains why traffic is not reaching the backends.", "VALID"),
    ("All even numbers are divisible by 2. 14 is even.",
     "Therefore 14 is divisible by 2.", "VALID"),
    ("All even numbers are divisible by 2. 14 is even.",
     "Therefore 14 is divisible by 4.", "INVALID"),
    ("The function must return a sorted list. The implementation uses bubble sort.",
     "Bubble sort produces a sorted list, so the requirement is met.", "VALID"),
    ("The function must return a sorted list. The implementation uses bubble sort.",
     "Bubble sort is O(n log n), which is optimal.", "INVALID"),
    ("The user asked for the capital of France.",
     "Paris is the capital of France, so the answer is Paris.", "VALID"),
]


def _main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Skywork PRM backend")
    parser.add_argument("--model", default="Skywork/Skywork-o1-Open-PRM-Qwen-2.5-1.5B")
    parser.add_argument("--eval_start", type=int, default=500)
    parser.add_argument("--eval_samples", type=int, default=60)
    parser.add_argument("--batch_size", type=int, default=4)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not SKYWORK_UTILS.exists():
        raise SystemExit(
            f"Skywork inference harness not found at {SKYWORK_UTILS}. "
            "Clone https://github.com/SkyworkAI/skywork-o1-prm-inference there first."
        )
    sys.path.insert(0, str(SKYWORK_UTILS))

    import torch
    from model_utils.io_utils import (
        derive_step_rewards,
        prepare_batch_input_for_model,
        prepare_input,
    )
    from transformers import AutoModel, AutoTokenizer

    logger.info("Loading tokenizer + model %s (CPU, fp32)...", args.model)
    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    # The repo's auto_map resolves AutoModel -> Qwen2ForRewardModel, which owns
    # the per-token value head (v_head). Skywork's separate PRM_MODEL wrapper is
    # broken on modern transformers, so we apply v_head directly at step-token
    # positions (exactly what derive_step_rewards expects).
    model = AutoModel.from_pretrained(
        args.model,
        dtype=torch.float32,
        trust_remote_code=True,
    ).eval()

    def score_records(records: list[dict]) -> tuple[list[list[float]], float]:
        """Score every step of each record; return rewards and total seconds."""
        all_rewards: list[list[float]] = []
        t0 = time.time()
        for i in range(0, len(records), args.batch_size):
            chunk = records[i : i + args.batch_size]
            processed = [
                prepare_input(r["problem"], r["response"], tokenizer=tokenizer, step_token="\n")
                for r in chunk
            ]
            input_ids, _steps, reward_flags = zip(*processed)
            ids, mask, flags = prepare_batch_input_for_model(
                input_ids, reward_flags, tokenizer.pad_token_id
            )
            with torch.no_grad():
                backbone = getattr(model, "model", model)
                out = backbone(input_ids=ids, attention_mask=mask, use_cache=False)
                hidden = out[0] if isinstance(out, tuple) else out.last_hidden_state
                rewards = torch.sigmoid(model.v_head(hidden).squeeze(-1))
            all_rewards.extend(derive_step_rewards(rewards, flags))
        return all_rewards, time.time() - t0

    # --- Tier 1: held-out prm800k solutions ---
    from datasets import load_dataset

    logger.info(
        "Loading prm800k test[%d:%d]...", args.eval_start, args.eval_start + args.eval_samples
    )
    raw = load_dataset("trl-lib/prm800k", split="test")
    raw = raw.select(range(args.eval_start, min(args.eval_start + args.eval_samples, len(raw))))

    records, gold = [], []
    for row in raw:
        steps = [c.replace("\n", " ") for c in row["completions"]]
        records.append({"problem": row["prompt"], "response": "\n".join(steps)})
        gold.extend(1 if lbl else 0 for lbl in row["labels"])  # 1=VALID, 0=INVALID

    logger.info("Scoring %d records...", len(records))
    rewards_per_record, elapsed = score_records(records)
    scores = [s for r in rewards_per_record for s in r]
    if len(scores) != len(gold):
        logger.warning(
            "Step count mismatch: model scored %d steps, labels have %d — truncating to min",
            len(scores), len(gold),
        )
    n = min(len(scores), len(gold))
    scores, gold_arr = np.array(scores[:n]), np.array(gold[:n])

    preds = (scores > 0.5).astype(int)
    print(f"\n=== Tier 1: Skywork PRM on {n} held-out prm800k steps ===")
    print(f"Accuracy: {accuracy_score(gold_arr, preds):.4f}")
    print(f"AUC:      {roc_auc_score(gold_arr == 0, -scores):.4f}")
    print(f"Dist:     {dict(Counter(gold_arr.tolist()))}")
    print(classification_report(gold_arr, preds, target_names=["INVALID", "VALID"], digits=3))
    print(f"Latency: {elapsed:.1f}s total, {elapsed / len(records):.2f}s/record "
          f"({n / max(elapsed, 1e-9):.1f} steps/s)")

    # --- Tier 2: curated cases ---
    curated_records = [
        {"problem": p, "response": s} for p, s, _ in CURATED_CASES
    ]
    curated_rewards, _ = score_records(curated_records)
    print("=== Tier 2: curated reasoning cases ===")
    correct = 0
    for (_p, step, exp), rw in zip(CURATED_CASES, curated_rewards):
        score = rw[-1] if rw else 0.0
        pred = "VALID" if score > 0.5 else "INVALID"
        ok = pred == exp
        correct += ok
        mark = "OK " if ok else "MISS"
        print(f"[{mark}] expected={exp:<8} score={score:.3f} pred={pred:<8} | {step[:60]}")
    print(f"\nCurated: {correct}/{len(CURATED_CASES)} correct")


if __name__ == "__main__":
    _main()

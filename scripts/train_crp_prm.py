# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Train the CRP Process Reward Model (PRM) verifier — v3, multi-dataset.

Fine-tunes a DeBERTa classifier to score whether a reasoning step is entailed
by / consistent with its prior steps and the original problem. v3 changes:

- Multiple data sources, unified to ``premises: ... [SEP] step: ...``:
  * ``trl-lib/prm800k`` — human-labeled math steps (~800k, bool labels)
  * ``peiyi9979/Math-Shepherd`` — GPT-4-labeled math steps (~445k, +/- labels)
  * built-in agentic synthetic generator — devops / compliance / code
    reasoning traces with known-valid and known-invalid steps (covers the
    domain gap that math-only PRMs like Skywork-o1-PRM miss)
- Keep-all-INVALID stratified capping + deterministic oversampling (v2 recipe)
- Optional threshold calibration: sweeps P(INVALID) on a held-out slice and
  stores the best operating point in the saved model config

Usage (CPU, quick)::

    python scripts/train_crp_prm.py \
        --datasets prm800k,math_shepherd,agentic_synth \
        --max_records 3000 --max_train_examples 8000 --num_epochs 1

Usage (RunPod / GPU, full)::

    python scripts/train_crp_prm.py \
        --base_model microsoft/deberta-v3-large \
        --datasets prm800k,math_shepherd,agentic_synth \
        --max_records 50000 --max_train_examples 400000 \
        --num_epochs 2 --batch_size 32 --bf16 \
        --push_to_hub AutoCyberAI/crp-prm-deberta-v1

The resulting model can be loaded by CRP via the env var::

    CRP_PRM_MODEL=AutoCyberAI/crp-prm-deberta-v1

References:
- PRM800K paper: https://arxiv.org/abs/2305.20050
- Math-Shepherd paper: https://arxiv.org/abs/2312.08935
"""

from __future__ import annotations

import argparse
import logging
import os
import random
from typing import Any

from datasets import Dataset, load_dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

logger = logging.getLogger(__name__)

LABEL2ID = {"INVALID": 0, "VALID": 1}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}


def _verify_environment() -> None:
    """Fail fast on the numpy 2.x / pyarrow / datasets version trap."""
    import numpy

    np_major = int(numpy.__version__.split(".")[0])

    try:
        import pyarrow
    except AttributeError as exc:
        msg = str(exc)
        if "_ARRAY_API" in msg or "numpy.core.multiarray" in msg:
            raise SystemExit(
                "Incompatible environment: pyarrow is built against numpy 1.x but numpy 2.x is installed.\n"
                "Do NOT downgrade pyarrow. Recreate .venv-train with the pinned recipe:\n"
                "  docs/CRPv6_PhaseA_Action_Plan.md §2.2 (pyarrow>=15, datasets>=3.2, transformers>=4.46,<5)."
            ) from None
        raise

    pa_major = int(pyarrow.__version__.split(".")[0])
    if np_major >= 2 and pa_major < 15:
        raise SystemExit(
            "Incompatible environment: numpy 2.x requires pyarrow>=15.\n"
            "Do NOT downgrade pyarrow. Recreate .venv-train with the pinned recipe:\n"
            "  docs/CRPv6_PhaseA_Action_Plan.md §2.2."
        )

    import datasets as ds

    ds_major = int(ds.__version__.split(".")[0])
    if np_major >= 2 and ds_major < 3:
        raise SystemExit(
            "Incompatible environment: numpy 2.x requires datasets>=3.2.\n"
            "Recreate .venv-train with the pinned recipe:\n"
            "  docs/CRPv6_PhaseA_Action_Plan.md §2.2."
        )


_verify_environment()


# ---------------------------------------------------------------------------
# Data source 1: trl-lib/prm800k (human labels, bool per step)
# ---------------------------------------------------------------------------

def _load_prm800k_steps(max_records: int | None) -> list[dict[str, Any]]:
    """Return step-level examples from prm800k train."""
    logger.info("Loading trl-lib/prm800k...")
    ds = load_dataset("trl-lib/prm800k", split="train")
    if max_records:
        ds = ds.select(range(min(max_records, len(ds))))
    examples: list[dict[str, Any]] = []
    for row in ds:
        examples.extend(_expand_record(row["prompt"], row["completions"], row["labels"]))
    return examples


def _expand_record(
    problem: str, steps: list[str], labels: list[Any]
) -> list[dict[str, Any]]:
    """Expand one solution into step-level classification examples."""
    out = []
    prior: list[str] = []
    for step, is_valid in zip(steps, labels):
        step_text = step if isinstance(step, str) else step.get("text", "")
        premises = " ".join([problem] + prior)
        out.append({
            "text": f"premises: {premises} [SEP] step: {step_text}",
            "labels": LABEL2ID["VALID"] if bool(is_valid) else LABEL2ID["INVALID"],
        })
        prior.append(step_text)
    return out


# ---------------------------------------------------------------------------
# Data source 2: peiyi9979/Math-Shepherd (GPT-4 labels, +/- per step)
# ---------------------------------------------------------------------------

def _parse_math_shepherd(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse one Math-Shepherd record into step-level examples.

    ``input`` carries the problem followed by ``Step N: ...`` segments joined
    by ``ки``; ``label`` carries the same steps each terminated by ``+`` (good)
    or ``-`` (bad). Records whose steps and labels do not align are skipped.
    """
    inp, lab = row["input"], row["label"]
    if "Step 1:" not in inp:
        return []
    problem = inp.split("Step 1:", 1)[0].strip()
    steps_blob = "Step 1:" + inp.split("Step 1:", 1)[1]
    steps = []
    for seg in steps_blob.split("ки"):
        seg = seg.strip()
        if not seg:
            continue
        # Strip the leading "Step N:" prefix.
        if seg.startswith("Step") and ":" in seg[:10]:
            seg = seg.split(":", 1)[1].strip()
        steps.append(seg)
    labels = []
    for seg in (s.strip() for s in lab.split("\n") if s.strip()):
        if seg.endswith("+"):
            labels.append(1)
        elif seg.endswith("-"):
            labels.append(0)
        else:
            return []  # unparseable label row — skip the record
    if len(steps) != len(labels):
        return []
    return _expand_record(problem, steps, labels)


def _load_math_shepherd_steps(max_records: int | None) -> list[dict[str, Any]]:
    logger.info("Loading peiyi9979/Math-Shepherd...")
    ds = load_dataset("peiyi9979/Math-Shepherd", split="train")
    if max_records:
        ds = ds.select(range(min(max_records, len(ds))))
    examples: list[dict[str, Any]] = []
    for row in ds:
        examples.extend(_parse_math_shepherd(row))
    return examples


# ---------------------------------------------------------------------------
# Data source 3: UW-Madison-Lee-Lab/MMLU-Pro-CoT-Train-Labeled (VersaPRM)
# ---------------------------------------------------------------------------

def _load_mmlu_pro_steps(max_records: int | None) -> list[dict[str, Any]]:
    """Step-labeled CoT traces across 14 MMLU-Pro domains (MIT license).

    The only large public step-labeled corpus outside math (law, business,
    health, engineering, CS, ...). ``chain_of_thoughts`` and ``labels`` are
    string reprs of Python lists; labels are 1 (correct) / -1 (incorrect).
    """
    import ast

    logger.info("Loading UW-Madison-Lee-Lab/MMLU-Pro-CoT-Train-Labeled...")
    ds = load_dataset("UW-Madison-Lee-Lab/MMLU-Pro-CoT-Train-Labeled", split="train")
    if max_records:
        ds = ds.select(range(min(max_records, len(ds))))
    examples: list[dict[str, Any]] = []
    skipped = 0
    for row in ds:
        try:
            steps = ast.literal_eval(row["chain_of_thoughts"])
            raw_labels = ast.literal_eval(row["labels"])
            labels = [1 if lbl == 1 else 0 for lbl in raw_labels]
            if not steps or len(steps) != len(labels):
                skipped += 1
                continue
            examples.extend(
                _expand_record(row["question"], [str(s) for s in steps], labels)
            )
        except (ValueError, SyntaxError):
            skipped += 1
    if skipped:
        logger.info("MMLU-Pro: skipped %d unparseable records", skipped)
    return examples


# ---------------------------------------------------------------------------
# Data source 4: RLHFlow/Mistral-PRM-Data (MC-labeled, +/- per step)
# ---------------------------------------------------------------------------

def _load_rlhflow_steps(max_records: int | None) -> list[dict[str, Any]]:
    """RLHFlow PRM data: multi-turn conversations, user=step, assistant=+/-.

    Math-only (GSM8K+MATH rollouts) but adds 273k step labels from a
    different generator than Math-Shepherd. No license declared — fine for
    research; flag for commercial redistribution.
    """
    logger.info("Loading RLHFlow/Mistral-PRM-Data...")
    ds = load_dataset("RLHFlow/Mistral-PRM-Data", split="train")
    if max_records:
        ds = ds.select(range(min(max_records, len(ds))))
    examples: list[dict[str, Any]] = []
    skipped = 0
    for row in ds:
        conv = row["conversations"]
        user_turns = [c["content"] for c in conv if c.get("role") == "user"]
        labels = []
        for c in conv:
            if c.get("role") == "assistant":
                content = c["content"].strip()
                if content == "+":
                    labels.append(1)
                elif content == "-":
                    labels.append(0)
        if not user_turns or len(labels) != len(user_turns):
            skipped += 1
            continue
        first = user_turns[0]
        if "Step 1:" in first:
            problem, step1 = first.split("Step 1:", 1)
            steps = [step1.strip()]
        else:
            problem, steps = first, []
        for turn in user_turns[1:]:
            turn = turn.strip()
            if turn.startswith("Step") and ":" in turn[:10]:
                turn = turn.split(":", 1)[1].strip()
            steps.append(turn)
        if len(steps) != len(labels):
            skipped += 1
            continue
        examples.extend(_expand_record(problem.strip(), steps, labels))
    if skipped:
        logger.info("RLHFlow: skipped %d misaligned records", skipped)
    return examples


# ---------------------------------------------------------------------------
# Data source 5: agentic synthetic generator (devops / compliance / code)
# ---------------------------------------------------------------------------

_SCENARIOS: list[dict[str, Any]] = [
    {
        "problem": "The {service} returned {error} after the {trigger}.",
        "valid": [
            "The {trigger} coincides with the onset of the errors, so it is the first thing to inspect.",
            "Because the {service} depends on the {dependency}, its failure can produce {error} responses.",
            "Rolling back the {trigger} would test whether it caused the regression.",
        ],
        "invalid": [
            "The database is definitely the root cause.",
            "Therefore the {service} codebase must be rewritten.",
            "This proves the network hardware is faulty.",
        ],
    },
    {
        "problem": "The audit trail shows a gap between windows {n1} and {n2} in the {service} logs.",
        "valid": [
            "A gap in the HMAC chain means the events between {n1} and {n2} cannot be trusted as-is.",
            "We should quarantine the affected window range before drawing conclusions.",
            "The retention policy may have compacted those windows, which would explain the gap.",
        ],
        "invalid": [
            "Gaps in logs are always caused by attackers.",
            "So the entire audit trail is worthless and compliance is impossible.",
            "Therefore we can ignore the gap.",
        ],
    },
    {
        "problem": "The function must return a sorted list, but the {service} returns items out of order.",
        "valid": [
            "The comparator likely ignores the secondary key, which would scramble equal elements.",
            "Adding a failing test that asserts ordering would confirm the bug before fixing it.",
            "The implementation sorts by the wrong field, so the fix is to sort by the requested one.",
        ],
        "invalid": [
            "Sorting is O(n log n), which is optimal, so nothing is wrong.",
            "The compiler is at fault.",
            "Therefore the list should not be sorted at all.",
        ],
    },
    {
        "problem": "The {service} latency doubled after the config change to {component}.",
        "valid": [
            "The timing correlation makes {component} the prime suspect, so measure it first.",
            "Reverting the change and re-measuring isolates whether {component} caused the regression.",
            "The new {component} setting may disable caching, which would explain the extra latency.",
        ],
        "invalid": [
            "Latency always doubles when traffic increases, so no action is needed.",
            "The CPU must be replaced.",
            "Therefore the monitoring dashboard is lying.",
        ],
    },
    {
        "problem": "A user turn was flagged as a possible prompt injection by the safety layer.",
        "valid": [
            "The flagged text contains instruction-like imperatives, which matches known injection phrasing.",
            "Routing the turn to quarantine preserves the audit trail while blocking execution.",
            "We should check whether the text tries to override prior instructions before acting on it.",
        ],
        "invalid": [
            "All user input is safe, so the flag can be ignored.",
            "Therefore the user is a criminal.",
            "The model itself must be compromised.",
        ],
    },
]

_SCENARIO_WORDS: dict[str, list[str]] = {
    "service": ["gateway", "API server", "worker pool", "scheduler", "proxy"],
    "error": ["502 errors", "timeouts", "HTTP 429 responses", "connection resets"],
    "trigger": ["deploy", "config reload", "certificate rotation", "dependency upgrade"],
    "dependency": ["database", "cache layer", "message queue", "identity provider"],
    "component": ["connection pooling", "TLS termination", "query caching", "rate limiting"],
    "n1": ["12", "41", "128", "1024"],
    "n2": ["17", "42", "133", "1050"],
}


def _fill(text: str, rng: random.Random) -> str:
    for key, words in _SCENARIO_WORDS.items():
        while f"{{{key}}}" in text:
            text = text.replace(f"{{{key}}}", rng.choice(words), 1)
    return text


def _make_agentic_synthetic(n: int = 4000, seed: int = 13) -> list[dict[str, Any]]:
    """Generate step-level examples for agentic (non-math) reasoning domains.

    Each example chains 1–2 valid prior steps as premises, then labels the
    current step VALID (drawn from the valid pool) or INVALID (drawn from the
    invalid pool: non-sequiturs, overclaims, false dismissals).
    """
    rng = random.Random(seed)
    out: list[dict[str, Any]] = []
    for _ in range(n):
        scenario = rng.choice(_SCENARIOS)
        problem = _fill(scenario["problem"], rng)
        valid_steps = [_fill(s, rng) for s in scenario["valid"]]
        invalid_steps = [_fill(s, rng) for s in scenario["invalid"]]
        n_prior = rng.randint(0, 2)
        prior = rng.sample(valid_steps, k=min(n_prior, len(valid_steps)))
        is_valid = rng.random() < 0.5
        pool = valid_steps if is_valid else invalid_steps
        step = rng.choice(pool)
        premises = " ".join([problem] + prior)
        out.append({
            "text": f"premises: {premises} [SEP] step: {step}",
            "labels": LABEL2ID["VALID"] if is_valid else LABEL2ID["INVALID"],
        })
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

_LOADERS = {
    "prm800k": _load_prm800k_steps,
    "math_shepherd": _load_math_shepherd_steps,
    "mmlu_pro": _load_mmlu_pro_steps,
    "rlhflow_mistral": _load_rlhflow_steps,
}


def _rebalance_labels(
    examples: list[dict[str, Any]],
    target_minority_share: float = 0.40,
    minority_label: int = 0,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Oversample INVALID examples to ``target_minority_share`` (deterministic)."""
    minority = [e for e in examples if e["labels"] == minority_label]
    target = int(target_minority_share * len(examples))
    if not minority or len(minority) >= target:
        return examples
    rng = random.Random(seed)
    extras = [rng.choice(minority) for _ in range(target - len(minority))]
    logger.info(
        "Rebalancing: INVALID %d -> %d of %d (target share %.2f)",
        len(minority), target, len(examples) + len(extras), target_minority_share,
    )
    return examples + extras


def _build_dataset(args: argparse.Namespace) -> tuple[Dataset, Dataset]:
    """Build (train, eval) step-level datasets from the selected sources."""
    train_examples: list[dict[str, Any]] = []
    eval_examples: list[dict[str, Any]] = []

    for name in args.datasets.split(","):
        name = name.strip()
        if name == "agentic_synth":
            synth = _make_agentic_synthetic(n=args.agentic_samples)
            train_examples.extend(synth)
            eval_examples.extend(_make_agentic_synthetic(n=args.agentic_samples // 10, seed=99))
            logger.info("agentic_synth: %d train examples", len(synth))
        elif name in _LOADERS:
            train_examples.extend(_LOADERS[name](args.max_records))
            logger.info("%s: running total %d", name, len(train_examples))
        else:
            raise SystemExit(f"Unknown dataset source: {name!r} (choose from {list(_LOADERS)} + agentic_synth)")

    # Held-out eval slice from prm800k test (never used in training).
    logger.info("Loading prm800k test slice for eval...")
    test = load_dataset("trl-lib/prm800k", split="test")
    test = test.select(range(min(args.eval_samples, len(test))))
    for row in test:
        eval_examples.extend(_expand_record(row["prompt"], row["completions"], row["labels"]))

    rng = random.Random(42)
    rng.shuffle(train_examples)

    # Stratified cap: keep as many INVALID as possible without crowding out
    # VALID (at most half the cap), fill the rest with VALID.
    if args.max_train_examples and len(train_examples) > args.max_train_examples:
        invalid = [e for e in train_examples if e["labels"] == 0]
        valid = [e for e in train_examples if e["labels"] == 1]
        rng.shuffle(invalid)
        rng.shuffle(valid)
        n_inv = min(len(invalid), args.max_train_examples // 2)
        train_examples = invalid[:n_inv] + valid[: args.max_train_examples - n_inv]

    train_examples = _rebalance_labels(train_examples, args.target_invalid_share)
    rng.shuffle(train_examples)

    if args.max_eval_examples and len(eval_examples) > args.max_eval_examples:
        rng.shuffle(eval_examples)
        eval_examples = eval_examples[: args.max_eval_examples]

    logger.info("Step-level examples: train=%d, eval=%d", len(train_examples), len(eval_examples))
    return Dataset.from_list(train_examples), Dataset.from_list(eval_examples)


def _tokenize(
    batch: dict[str, Any], tokenizer: Any, max_length: int = 512
) -> dict[str, Any]:
    return tokenizer(batch["text"], truncation=True, padding=False, max_length=max_length)


def _calibrate_threshold(model: Any, eval_tok: Dataset, tokenizer: Any) -> float:
    """Sweep P(INVALID) thresholds on the eval set; return the best F1 point."""
    import numpy as np
    import torch

    logger.info("Calibrating decision threshold on the eval set...")
    model.eval()
    device = next(model.parameters()).device
    scores, gold = [], []
    for i in range(0, len(eval_tok), 64):
        batch = eval_tok[i : i + 64]
        padded = tokenizer.pad(
            {"input_ids": batch["input_ids"], "attention_mask": batch["attention_mask"]},
            padding=True,
            return_tensors="pt",
        ).to(device)
        with torch.no_grad():
            logits = model(**padded).logits
        probs = torch.softmax(logits, dim=-1)[:, 0]  # P(INVALID)
        scores.extend(probs.cpu().tolist())
        gold.extend(batch["labels"])
    scores_arr, gold_arr = np.array(scores), np.array(gold)
    best_t, best_f1 = 0.5, 0.0
    for t in np.arange(0.05, 0.95, 0.025):
        pred = scores_arr > t
        tp = int(((pred == 1) & (gold_arr == 0)).sum())
        fp = int(((pred == 1) & (gold_arr == 1)).sum())
        fn = int(((pred == 0) & (gold_arr == 0)).sum())
        f1 = 2 * tp / max(2 * tp + fp + fn, 1)
        if f1 > best_f1:
            best_f1, best_t = f1, float(t)
    inv_rec = float((scores_arr[gold_arr == 0] > best_t).mean()) if (gold_arr == 0).any() else 0.0
    val_rec = float((scores_arr[gold_arr == 1] <= best_t).mean()) if (gold_arr == 1).any() else 0.0
    logger.info(
        "Calibrated threshold %.3f (INVALID F1 %.3f, INVALID recall %.3f, VALID recall %.3f)",
        best_t, best_f1, inv_rec, val_rec,
    )
    return best_t


def _main() -> None:
    parser = argparse.ArgumentParser(description="Train CRP PRM verifier (v3)")
    parser.add_argument("--base_model", default="microsoft/deberta-v3-small")
    parser.add_argument("--output_dir", default="./crp-prm-deberta-v1")
    parser.add_argument("--push_to_hub", default="")
    parser.add_argument(
        "--datasets",
        default="prm800k,math_shepherd,mmlu_pro,agentic_synth",
        help="Comma-separated sources: prm800k, math_shepherd, mmlu_pro, "
        "rlhflow_mistral, agentic_synth",
    )
    parser.add_argument(
        "--max_records",
        type=int,
        default=None,
        help="Cap RECORDS per public dataset (records expand ~20x into steps)",
    )
    parser.add_argument(
        "--max_train_examples",
        type=int,
        default=None,
        help="Cap EXPANDED step-level training examples (keep-all-INVALID)",
    )
    parser.add_argument(
        "--agentic_samples",
        type=int,
        default=4000,
        help="Number of synthetic agentic reasoning examples to generate",
    )
    parser.add_argument(
        "--target_invalid_share",
        type=float,
        default=0.40,
        help="Oversample INVALID steps to this share of the train set",
    )
    parser.add_argument("--eval_samples", type=int, default=60, help="prm800k test records for eval")
    parser.add_argument("--max_eval_examples", type=int, default=2000)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--num_epochs", type=int, default=2)
    parser.add_argument("--learning_rate", type=float, default=5e-5)
    parser.add_argument("--bf16", action="store_true", help="Use bf16 (GPU only)")
    parser.add_argument("--gradient_checkpointing", action="store_true")
    parser.add_argument(
        "--max_length",
        type=int,
        default=512,
        help="Token truncation length (384 is ~25%% faster with minimal loss)",
    )
    parser.add_argument(
        "--num_workers",
        type=int,
        default=0,
        help="Dataloader workers (use 4-8 on Linux GPU pods; 0 on Windows)",
    )
    parser.add_argument(
        "--tokenize_workers",
        type=int,
        default=1,
        help="Parallel processes for dataset tokenization (use 8-16 on pods)",
    )
    parser.add_argument(
        "--calibrate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Calibrate the INVALID threshold on the eval set after training",
    )
    parser.add_argument(
        "--resume_from_checkpoint",
        default=None,
        help="Path to a checkpoint to resume from, or 'auto' to resume the latest checkpoint-* in output_dir",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    train_ds, eval_ds = _build_dataset(args)

    logger.info("Loading tokenizer and model %s...", args.base_model)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=len(LABEL2ID),
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )

    logger.info("Tokenizing...")
    tokenize_kwargs: dict[str, Any] = {}
    if args.tokenize_workers > 1:
        tokenize_kwargs["num_proc"] = args.tokenize_workers
    train_tok = train_ds.map(
        lambda batch: _tokenize(batch, tokenizer, args.max_length),
        batched=True,
        remove_columns=["text"],
        **tokenize_kwargs,
    )
    eval_tok = eval_ds.map(
        lambda batch: _tokenize(batch, tokenizer, args.max_length),
        batched=True,
        remove_columns=["text"],
        **tokenize_kwargs,
    )

    data_collator = DataCollatorWithPadding(tokenizer)

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        num_train_epochs=args.num_epochs,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        logging_strategy="steps",
        logging_steps=50,
        fp16=(os.environ.get("CRP_TRAIN_FP16", "0") == "1"),
        bf16=args.bf16,
        gradient_checkpointing=args.gradient_checkpointing,
        dataloader_num_workers=args.num_workers,
        push_to_hub=bool(args.push_to_hub),
        hub_model_id=args.push_to_hub or None,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_tok,
        eval_dataset=eval_tok,
        processing_class=tokenizer,
        data_collator=data_collator,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    resume_arg = args.resume_from_checkpoint
    if resume_arg == "auto":
        from pathlib import Path

        checkpoint_dirs = sorted(Path(args.output_dir).glob("checkpoint-*"))
        if checkpoint_dirs:
            resume_arg = str(checkpoint_dirs[-1])
            logger.info("Resuming from latest checkpoint: %s", resume_arg)
        else:
            logger.info("No existing checkpoint in %s — starting fresh.", args.output_dir)
            resume_arg = None

    logger.info("Training...")
    trainer.train(resume_from_checkpoint=resume_arg)
    logger.info("Final eval: %s", trainer.evaluate())

    if args.calibrate:
        threshold = _calibrate_threshold(model, eval_tok, tokenizer)
        model.config.prm_threshold = threshold  # type: ignore[attr-defined]

    logger.info("Saving to %s...", args.output_dir)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)

    if args.push_to_hub:
        logger.info("Pushing to %s...", args.push_to_hub)
        trainer.push_to_hub()

    logger.info(
        "Done. Set CRP_PRM_MODEL=%s to use the trained model.",
        args.push_to_hub or args.output_dir,
    )


if __name__ == "__main__":
    _main()

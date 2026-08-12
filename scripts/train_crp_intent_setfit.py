# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Train the CRP speech-act / intent SetFit model.

This script fine-tunes a small sentence-transformer encoder on a mixture of:
- Banking77 customer-service intents (mapped to CRP speech acts)
- SNIPS voice-assistant intents (mapped to CRP speech acts)
- Synthetic templated examples for the four CRP speech acts

Usage (tested stack: setfit 1.1.3, sentence-transformers 5.6.x,
transformers 4.57.x, datasets 5.x, torch 2.x)::

    pip install setfit sentence-transformers transformers datasets huggingface_hub
    python scripts/train_crp_intent_setfit.py \
        --output_dir ./crp-intent-setfit \
        --push_to_hub AutoCyberAI/crp-intent-setfit \
        --max_samples 10000

The resulting model can be loaded by CRP via the env var::

    CRP_INTENT_MODEL=AutoCyberAI/crp-intent-setfit

References:
- SetFit: https://github.com/huggingface/setfit
- Banking77: https://huggingface.co/datasets/banking77
- SNIPS: https://huggingface.co/datasets/snips_built_in_intents
- Base encoder: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
"""

from __future__ import annotations

import argparse
import logging
import random
from collections.abc import Callable

from datasets import Dataset, Features, Value, concatenate_datasets, load_dataset
from setfit import SetFitModel, Trainer, TrainingArguments, sample_dataset
from sklearn.metrics import accuracy_score, classification_report

logger = logging.getLogger(__name__)

CRP_SPEECH_ACTS = ["request", "question", "assertion", "expressive"]


def _verify_environment() -> None:
    """Fail fast on the numpy 2.x / pyarrow / datasets / setfit version trap."""
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
                "  docs/CRPv6_PhaseA_Action_Plan.md §2.2 (pyarrow>=15, datasets>=3.2, setfit>=1.1.3)."
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

    import setfit

    sf_major, sf_minor = map(int, setfit.__version__.split(".")[:2])
    if sf_major == 1 and sf_minor < 1:
        raise SystemExit(
            "Incompatible environment: setfit>=1.1.3 is required.\n"
            "Recreate .venv-train with the pinned recipe:\n"
            "  docs/CRPv6_PhaseA_Action_Plan.md §2.2."
        )


_verify_environment()


# Heuristic mapping from Banking77 intent names to CRP speech acts.
# Banking77 labels are strings like "card_payment_wrong_amount".
_BANKING77_REQUEST_KEYWORDS = [
    "change", "update", "cancel", "request", "activate", "block",
    "order", "transfer", "withdraw", "deposit", "pay", "top_up",
]
_BANKING77_QUESTION_KEYWORDS = [
    "what", "how", "when", "why", "amount", "balance", "limit",
    "exchange_rate", "transaction", "fee", "charge",
]
_BANKING77_EXPRESSIVE_KEYWORDS = [
    "complain", "frustrated", "angry", "happy", "thank", "appreciate",
]


def _banking77_to_speech_act(label: str) -> str:
    lower = label.lower()
    if any(kw in lower for kw in _BANKING77_EXPRESSIVE_KEYWORDS):
        return "expressive"
    if any(kw in lower for kw in _BANKING77_QUESTION_KEYWORDS):
        return "question"
    return "request"


# SNIPS intent names map cleanly to request/question/assertion.
_SNIPS_QUESTION_KEYWORDS = ["question", "query", "ask"]
_SNIPS_ASSERTIVE_KEYWORDS = ["weather", "fact", "news", "definition"]


def _snips_to_speech_act(label: str) -> str:
    lower = label.lower()
    if any(kw in lower for kw in _SNIPS_QUESTION_KEYWORDS):
        return "question"
    if any(kw in lower for kw in _SNIPS_ASSERTIVE_KEYWORDS):
        return "assertion"
    return "request"


_TEMPLATES: dict[str, list[str]] = {
    "request": [
        "Please {verb} {object}.",
        "I need you to {verb} {object}.",
        "{verb} {object} for me.",
        "Can you {verb} {object}?",
        "I want to {verb} {object}.",
    ],
    "question": [
        "What is {object}?",
        "How do I {verb} {object}?",
        "Can you tell me about {object}?",
        "Why is {object} {adjective}?",
        "When should I {verb} {object}?",
    ],
    "assertion": [
        "I think {object} is {adjective}.",
        "It seems that {object} {verb}.",
        "This is {object}.",
        "I believe {object} is {adjective}.",
        "{object} appears to be {adjective}.",
    ],
    "expressive": [
        "I am frustrated with {object}.",
        "Great, {object} is working!",
        "This is terrible: {object}.",
        "I feel {adjective} about {object}.",
        "Amazing, {object} is fixed!",
    ],
}

_WORD_BANK: dict[str, list[str]] = {
    "verb": [
        "check", "show", "find", "update", "change", "transfer", "scan",
        "verify", "compare", "summarise", "cancel", "book", "schedule",
    ],
    "object": [
        "the balance", "my account", "the report", "the server", "the policy",
        "the invoice", "the host", "the port", "the compliance posture",
    ],
    "adjective": [
        "correct", "wrong", "slow", "secure", "open", "closed", "updated",
        "missing", "complete", "high", "low",
    ],
}


def _fill_template(template: str, rng: random.Random) -> str:
    out = template
    for key, words in _WORD_BANK.items():
        out = out.replace(f"{{{key}}}", rng.choice(words))
    return out


def _make_synthetic(n_per_class: int = 256, seed: int = 42) -> Dataset:
    rng = random.Random(seed)
    texts, labels = [], []
    for act in CRP_SPEECH_ACTS:
        for _ in range(n_per_class):
            template = rng.choice(_TEMPLATES[act])
            texts.append(_fill_template(template, rng))
            labels.append(act)
    return Dataset.from_dict({"text": texts, "label": labels})


def _map_labels(dataset: Dataset, label_to_act: Callable[[str], str]) -> Dataset:
    """Map a ClassLabel-int dataset to CRP speech-act string labels."""
    class_label = dataset.features["label"]
    new_features = Features({"text": Value("string"), "label": Value("string")})
    return dataset.map(
        lambda row: {
            "text": row["text"],
            "label": label_to_act(class_label.int2str(row["label"])),
        },
        remove_columns=dataset.column_names,
        features=new_features,
    )


def _prepare_public_datasets(max_samples: int | None) -> Dataset:
    logger.info("Loading Banking77...")
    banking_train = load_dataset("banking77", split="train")
    if max_samples:
        banking_train = banking_train.select(range(min(max_samples, len(banking_train))))
    banking_train = _map_labels(banking_train, _banking77_to_speech_act)

    logger.info("Loading SNIPS...")
    snips_train = load_dataset("snips_built_in_intents", split="train")
    if max_samples:
        snips_train = snips_train.select(range(min(max_samples, len(snips_train))))
    snips_train = _map_labels(snips_train, _snips_to_speech_act)

    logger.info("Generating synthetic examples...")
    synthetic = _make_synthetic(n_per_class=max_samples // 4 if max_samples else 256)

    combined = concatenate_datasets([banking_train, snips_train, synthetic])
    return combined.shuffle(seed=42)


def _main() -> None:
    parser = argparse.ArgumentParser(description="Train CRP intent SetFit model")
    parser.add_argument(
        "--base_model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-transformer checkpoint to fine-tune",
    )
    parser.add_argument(
        "--output_dir",
        default="./crp-intent-setfit",
        help="Local directory to save the model",
    )
    parser.add_argument(
        "--push_to_hub",
        default="",
        help="Optional Hugging Face repo id to push to",
    )
    parser.add_argument(
        "--max_samples",
        type=int,
        default=None,
        help="Cap public dataset sizes for quick experiments",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=16,
        help="Training batch size",
    )
    parser.add_argument(
        "--num_epochs",
        type=int,
        default=1,
        help="SetFit num_epochs",
    )
    parser.add_argument(
        "--eval_samples",
        type=int,
        default=2000,
        help="Cap the evaluation set size (CPU eval on the full mix is slow)",
    )
    parser.add_argument(
        "--num_samples",
        type=int,
        default=64,
        help="Few-shot samples per class for SetFit contrastive body training",
    )
    parser.add_argument(
        "--fit_head_full",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Fit the classifier head on the full training set after body tuning",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Preparing dataset...")
    train_full = _prepare_public_datasets(args.max_samples)
    eval_set = train_full.select(range(min(args.eval_samples, len(train_full))))

    # Sample a few-shot subset per class for SetFit contrastive body tuning.
    train_sampled = sample_dataset(
        train_full, label_column="label", num_samples=args.num_samples
    )

    logger.info("Loading base model %s...", args.base_model)
    model = SetFitModel.from_pretrained(args.base_model)

    logger.info(
        "Contrastive body training on %d few-shot examples...", len(train_sampled)
    )
    args_fit = TrainingArguments(
        batch_size=args.batch_size,
        num_epochs=args.num_epochs,
        # NOTE: do NOT enable epoch evaluation here. SetFit's embedding eval
        # generates O(n^2) contrastive pairs from the eval set — a 2000-example
        # eval slice cost ~11.5 h on CPU for zero benefit on a 1-epoch run.
        # The classifier head is evaluated below in seconds instead.
        eval_strategy="no",
        save_strategy="no",
    )
    trainer = Trainer(
        model=model,
        args=args_fit,
        train_dataset=train_sampled,
        column_mapping={"text": "text", "label": "label"},
    )
    trainer.train()

    if args.fit_head_full:
        logger.info(
            "Fitting classifier head on the full %d-example training set...",
            len(train_full),
        )
        model.fit(
            train_full["text"],
            train_full["label"],
            num_epochs=1,
            show_progress_bar=True,
        )

    logger.info("Evaluating on %d held-out examples...", len(eval_set))
    preds = [str(p) for p in model.predict(eval_set["text"])]
    gold = eval_set["label"]
    accuracy = accuracy_score(gold, preds)
    logger.info("Held-out accuracy: %.4f", accuracy)
    print(classification_report(gold, preds, digits=3))

    logger.info("Saving to %s...", args.output_dir)
    model.save_pretrained(args.output_dir)

    if args.push_to_hub:
        logger.info("Pushing to %s...", args.push_to_hub)
        model.push_to_hub(args.push_to_hub)

    logger.info(
        "Done. Set CRP_INTENT_MODEL=%s to use the trained model.",
        args.push_to_hub or args.output_dir,
    )


if __name__ == "__main__":
    _main()

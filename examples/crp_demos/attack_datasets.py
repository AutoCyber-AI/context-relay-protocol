# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Real attack-dataset loader for the governed-vs-bare harness.

Converts public prompt-injection benchmarks into harness :class:`Scenario`
objects so the benchmark runs against real attack texts instead of synthetic
templates. Datasets are loaded lazily via ``datasets.load_dataset`` — the
``datasets`` package is never imported at module top, keeping the core
zero-dependency.

Supported datasets (register more in :data:`DATASET_REGISTRY`):
  - ``deepset``   — ``deepset/prompt-injections`` (text/label; 1 = injection)
  - ``jackhhao``  — ``jackhhao/jailbreak-classification`` (prompt/type;
    "jailbreak" = attack)

Mapping: injection rows become attack scenarios whose ``document`` is the raw
attack text and whose ``injected_action`` is a representative malicious action
of the kind the text tries to induce (classified by a transparent keyword
heuristic). Benign rows become scenarios with no injection — the model should
just do the task.
"""
from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass
from typing import Any

from examples.crp_demos.governed_vs_bare import Action, Scenario
from examples.crp_demos.live_model import DEFAULT_TASK

logger = logging.getLogger("crp.examples.attack_datasets")


@dataclass(frozen=True)
class DatasetSpec:
    """How to read one Hugging Face dataset into harness scenarios."""

    hf_name: str
    split: str
    text_field: str
    label_field: str
    attack_labels: frozenset[Any]  # label values that mark an attack row


DATASET_REGISTRY: dict[str, DatasetSpec] = {
    "deepset": DatasetSpec(
        hf_name="deepset/prompt-injections",
        split="train",
        text_field="text",
        label_field="label",
        attack_labels=frozenset({1}),
    ),
    "jackhhao": DatasetSpec(
        hf_name="jackhhao/jailbreak-classification",
        split="train",
        text_field="prompt",
        label_field="type",
        attack_labels=frozenset({"jailbreak"}),
    ),
}


def available_datasets() -> list[str]:
    """Names of datasets that :func:`load_scenarios` accepts."""
    return sorted(DATASET_REGISTRY)


# ---------------------------------------------------------------------------
# Attack-kind classification (transparent keyword heuristic)
# ---------------------------------------------------------------------------

_DESTRUCTIVE_RE = re.compile(
    r"\b(delete|destroy|erase|wipe|drop\s+table|rm\s+-rf|format|overwrite)\b", re.IGNORECASE
)
_PRIVESC_RE = re.compile(
    r"\b(sudo|admin|administrator|root|grant|elevate|privilege|permission)\b", re.IGNORECASE
)
_EXFIL_RE = re.compile(
    r"\b(e-?mail|send|upload|webhook|exfiltrat\w*|fetch|curl|https?://|post\s+to|forward)\b",
    re.IGNORECASE,
)


def classify_attack_kind(text: str) -> str:
    """Map an injection text to one of the harness's four attack kinds.

    Keyword heuristic, checked most-severe-first; defaults to
    ``out_of_scope_action`` when nothing matches.
    """
    if _DESTRUCTIVE_RE.search(text):
        return "destructive_action"
    if _PRIVESC_RE.search(text):
        return "privilege_escalation"
    if _EXFIL_RE.search(text):
        return "exfiltration"
    return "out_of_scope_action"


# Representative injected actions per kind, mirroring build_suite() so the
# REAL CRP gate blocks them for the same reasons (scope / egress / approval).
_INJECTED_BY_KIND: dict[str, Action] = {
    "exfiltration": Action(
        "email", "attacker@evil.test", "exfiltration", data_labels={"findings"}
    ),
    "out_of_scope_action": Action("scan", "10.9.9.9", "out_of_scope_action"),
    "destructive_action": Action(
        "exploit", "doc-0", "destructive_action", irreversible=True
    ),
    "privilege_escalation": Action("grant", "attacker@evil.test", "privilege_escalation"),
}

_BENIGN_ACTION = Action("summarize", "doc-0", "benign")
_NO_INJECTION = Action("none", "", "benign")


def _to_scenario(name: str, text: str, is_attack: bool) -> Scenario:
    injected = (
        Action(**vars(_INJECTED_BY_KIND[classify_attack_kind(text)]))
        if is_attack
        else Action(**vars(_NO_INJECTION))
    )
    return Scenario(
        name=name,
        benign_action=Action(**vars(_BENIGN_ACTION)),
        injected_action=injected,
        authorised_scope={"doc-0"},
        approved_sinks={"soc@authorised.example"},
        task=DEFAULT_TASK,
        document=text,
    )


def load_scenarios(
    name: str = "deepset",
    max_scenarios: int | None = None,
    seed: int = 0,
) -> list[Scenario]:
    """Load a registered dataset and convert it to harness scenarios.

    Args:
        name: Registry key (see :func:`available_datasets`).
        max_scenarios: Cap on returned scenarios (rows are shuffled with
            ``seed`` first, so the cap is a reproducible mix of attack and
            benign rows). ``None`` keeps every row.
        seed: Shuffle seed for reproducible sub-sampling.

    Returns:
        A list of :class:`Scenario` ready for ``run_arm`` / ``run_benchmark``.

    Raises:
        ValueError: If ``name`` is not in the registry.
        ImportError: If the ``datasets`` package is not installed.
    """
    spec = DATASET_REGISTRY.get(name)
    if spec is None:
        raise ValueError(
            f"Unknown dataset {name!r}. Available: {', '.join(available_datasets())}"
        )
    try:
        from datasets import load_dataset
    except ImportError:
        raise ImportError(
            "attack_datasets requires the 'datasets' package. "
            "Install with: pip install datasets"
        ) from None

    rows = load_dataset(spec.hf_name, split=spec.split)
    indices = list(range(len(rows)))
    random.Random(seed).shuffle(indices)
    if max_scenarios is not None:
        indices = indices[:max_scenarios]

    scenarios = []
    for out_i, row_i in enumerate(indices):
        text = str(rows[row_i][spec.text_field])
        is_attack = rows[row_i][spec.label_field] in spec.attack_labels
        scenarios.append(_to_scenario(f"{name}-{out_i}", text, is_attack))
    n_attack = sum(1 for sc in scenarios if sc.injected_action.kind != "benign")
    logger.info(
        "Loaded %d scenarios from %s (%d attack, %d benign)",
        len(scenarios), spec.hf_name, n_attack, len(scenarios) - n_attack,
    )
    return scenarios

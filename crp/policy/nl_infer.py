# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Natural-language safety policy inference (CRP-SPEC-033/034 extension).

Safety in CRP was only declarable through the CSP-like ``CRP-Safety-Policy``
directive grammar (:mod:`crp.policy.grammar`) or raw ``SafetyControlPlane``
capability tuning (:func:`crp.security.control_plane.SafetyControlPlane.tune`).
Neither accepts a plain English instruction such as ``"never let it delete
files without asking me first"``. This module bridges that gap:

  1. A deterministic keyword/pattern layer (:func:`infer_from_text`) — zero
     cost, always available, covers the common safety intents a user is
     likely to write.
  2. An optional LLM-assisted layer (pass ``model_call``) that asks the
     *already-resolved* model itself to classify the sentence against the
     Safety Control Plane's known tunable capabilities, for phrasing the
     deterministic layer does not recognise.

Both layers return the SAME shape: a dict of ``SafetyControlPlane`` capability
names to values, plus an ``oversight_required`` set of :class:`SafetyClass`
names when the text implies gating specific action classes, and a
``matched_rules`` list for auditability (never apply an inferred policy the
user cannot inspect).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("crp.policy.nl_infer")


@dataclass
class InferredPolicy:
    """Result of inferring safety settings from natural language.

    Attributes:
        settings: SafetyControlPlane capability name -> value.
        oversight_required: Safety-class tokens (e.g. ``"destructive"``) that
            should require human approval before executing.
        matched_rules: Human-readable description of every rule that fired —
            always surfaced so an inferred policy is auditable, never a black
            box (mirrors the Coverage Map's "honesty is a feature" design).
        source: ``"keyword"``, ``"llm"``, or ``"keyword+llm"``.
    """

    settings: dict[str, Any] = field(default_factory=dict)
    oversight_required: set[str] = field(default_factory=set)
    matched_rules: list[str] = field(default_factory=list)
    source: str = "keyword"

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict."""
        return {
            "settings": dict(self.settings),
            "oversight_required": sorted(self.oversight_required),
            "matched_rules": list(self.matched_rules),
            "source": self.source,
        }


# ── Deterministic keyword layer ─────────────────────────────────────────────

# Each rule: (pattern, capability settings, oversight safety-classes, label).
# Ordered by specificity — later rules may refine earlier ones since all
# matching rules apply (dict.update semantics), not just the first hit.
_RULES: list[tuple[re.Pattern[str], dict[str, Any], set[str], str]] = [
    (
        re.compile(
            r"\b(never|don'?t|do not|without asking|without permission)\b"
            r".{0,40}\b(delete|remove|destroy|wipe|drop|erase)\b",
            re.IGNORECASE,
        ),
        {"human_oversight": "automatic"},
        {"destructive"},
        "destructive actions require approval",
    ),
    (
        re.compile(
            r"\b(ask|approv|confirm|review|check with me|check in)\b.{0,40}"
            r"\b(before|first|prior)\b",
            re.IGNORECASE,
        ),
        {"human_oversight": "automatic"},
        {"destructive"},
        "ask-before-acting -> human oversight",
    ),
    (
        re.compile(
            r"\brequire\b.{0,20}\b(human|manual)\b.{0,20}\b(review|approval|oversight)\b",
            re.IGNORECASE,
        ),
        {"human_oversight": "automatic"},
        set(),
        "explicit human-review requirement",
    ),
    (
        re.compile(
            r"\b(block|redact|never (send|leak|expose|share))\b.{0,25}"
            r"\b(pii|personal (data|information)|ssn|credit card)\b",
            re.IGNORECASE,
        ),
        {"pii_detection": "block"},
        set(),
        "block PII",
    ),
    (
        re.compile(r"\bpii\b|\bpersonal (data|information)\b", re.IGNORECASE),
        {"pii_detection": "flag"},
        set(),
        "flag PII (no explicit block/redact instruction)",
    ),
    (
        re.compile(
            r"\b(strict|careful|cautious|conservative|rigorous|paranoid)\b",
            re.IGNORECASE,
        ),
        {"grounding_verification": 0.85, "prompt_injection_shield": True},
        set(),
        "strict tone -> raise grounding bar",
    ),
    (
        re.compile(
            r"\b(loose|relaxed|permissive|lenient|casual)\b", re.IGNORECASE,
        ),
        {"grounding_verification": 0.5},
        set(),
        "permissive tone -> lower grounding bar",
    ),
    (
        re.compile(
            r"\b(block|prevent|stop|guard against)\b.{0,25}"
            r"\b(injection|jailbreak|prompt override)\b",
            re.IGNORECASE,
        ),
        {"prompt_injection_shield": True},
        set(),
        "explicit injection-shield request",
    ),
    (
        re.compile(
            r"\bnever\b.{0,25}\b(guess|make up|invent|fabricate|hallucinat)\b",
            re.IGNORECASE,
        ),
        {"grounding_verification": 0.8},
        set(),
        "no fabrication -> raise grounding bar",
    ),
    (
        re.compile(
            r"\b(don'?t|never|do not)\b.{0,25}\b(send|email|post|publish|upload)\b"
            r".{0,25}\b(without|unless)\b",
            re.IGNORECASE,
        ),
        {"human_oversight": "automatic"},
        {"network"},
        "network/outbound actions require approval",
    ),
]


def infer_from_text(text: str) -> InferredPolicy:
    """Infer SafetyControlPlane settings from a plain-English instruction.

    Zero-cost, deterministic, always available — no model call. Every
    matching rule contributes its settings (later matches can add to, but
    never silently replace, earlier ones for different keys).

    Args:
        text: A natural-language safety instruction, e.g. ``"never let it
            delete files without asking me"``.

    Returns:
        An :class:`InferredPolicy` with ``source="keyword"``. Empty
        ``settings``/``oversight_required`` (with ``matched_rules == []``)
        means no known pattern matched — callers should fall back to a
        named profile (``"balanced"``) rather than silently applying nothing.
    """
    result = InferredPolicy(source="keyword")
    for pattern, settings, safety_classes, label in _RULES:
        if pattern.search(text):
            # First match wins per key: rules are ordered specific -> generic
            # (e.g. an explicit "block PII" rule before a bare "PII mention"
            # rule), so a later, weaker rule must not downgrade an earlier,
            # stronger one that already set the same key.
            for key, value in settings.items():
                result.settings.setdefault(key, value)
            result.oversight_required |= safety_classes
            result.matched_rules.append(label)
    return result


# ── Optional LLM-assisted layer ─────────────────────────────────────────────

_LLM_CAPABILITY_KEYS = (
    "grounding_verification (0.0-1.0)",
    "pii_detection (flag|redact|block)",
    "prompt_injection_shield (true|false)",
    "human_oversight (manual|automatic)",
    "repetition_detection (warn|off)",
)

_LLM_PROMPT_TEMPLATE = (
    "You translate a plain-English AI-safety instruction into settings for "
    "an AI governance control plane. The only valid setting keys are:\n"
    "{keys}\n\n"
    "Respond with ONLY a JSON object mapping zero or more of these keys to "
    "a valid value for that key. Use no other keys. If the instruction "
    "implies destructive actions (delete/remove/destroy) need approval, "
    'also include "oversight_required": ["destructive"] (valid tokens: '
    "read-only, mutating, destructive, network, human-oversight).\n\n"
    "Instruction: {text}\n\n"
    "JSON:"
)


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    """Best-effort extraction of a single JSON object from free model text."""
    raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(raw[start : end + 1])
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


_KNOWN_KEYS = {
    "grounding_verification",
    "pii_detection",
    "prompt_injection_shield",
    "human_oversight",
    "repetition_detection",
}
_KNOWN_SAFETY_CLASSES = {
    "read-only", "mutating", "destructive", "network", "human-oversight",
}


def infer_from_text_with_llm(
    text: str, model_call: Callable[[str], str],
) -> InferredPolicy:
    """Infer settings using both the keyword layer and an LLM classifier.

    Args:
        text: The natural-language safety instruction.
        model_call: A single-argument callable ``(prompt) -> raw_text``,
            typically the caller's already-resolved provider (no separate
            model load — reuses whatever LLM the agent is already using).

    Returns:
        An :class:`InferredPolicy` merging both layers. If the model call
        raises or returns unparsable output, the keyword-only result is
        returned unchanged (never raises — this is advisory enrichment,
        not a required step).
    """
    result = infer_from_text(text)
    prompt = _LLM_PROMPT_TEMPLATE.format(
        keys="\n".join(f"  - {k}" for k in _LLM_CAPABILITY_KEYS), text=text,
    )
    try:
        raw = model_call(prompt)
    except Exception:  # noqa: BLE001 — advisory enrichment must never break policy setup
        logger.debug("LLM-assisted policy inference call failed", exc_info=True)
        return result

    parsed = _extract_json_object(raw)
    if not parsed:
        return result

    llm_settings = {k: v for k, v in parsed.items() if k in _KNOWN_KEYS}
    result.settings.update(llm_settings)
    if llm_settings:
        result.matched_rules.append("llm-inferred: " + ", ".join(sorted(llm_settings)))

    raw_classes = parsed.get("oversight_required")
    if isinstance(raw_classes, list):
        valid = {c for c in raw_classes if isinstance(c, str) and c in _KNOWN_SAFETY_CLASSES}
        if valid:
            result.oversight_required |= valid
            result.matched_rules.append("llm-inferred oversight: " + ", ".join(sorted(valid)))

    result.source = "keyword+llm" if llm_settings or raw_classes else "keyword"
    return result


def looks_like_natural_language(value: str) -> bool:
    """Heuristic: is *value* a free-text safety instruction, not a known
    profile name (``"strict"``/``"balanced"``/``"permissive"``) or a
    ``CRP-Safety-Policy`` directive string (``"default-src ..."``)?

    Used by callers (e.g. ``crp.Agent(safety=...)``) to decide whether a
    string argument should be parsed as a profile name or run through
    :func:`infer_from_text`.
    """
    stripped = value.strip()
    if not stripped:
        return False
    known_profiles = {"strict", "balanced", "permissive", "research"}
    if stripped.lower() in known_profiles:
        return False
    # A CSP-style directive string always contains a directive keyword and
    # a semicolon-or-space token shape ("default-src context; halt-on ...").
    if re.match(r"^[a-z][a-z-]*(\s|;)", stripped.lower()) and "-" in stripped.split()[0]:
        return False
    # Multiple words with everyday language markers (articles, pronouns,
    # negation) is the strongest signal of a natural-language sentence.
    return bool(re.search(r"\b(never|don'?t|always|please|it|me|before|without)\b", stripped, re.IGNORECASE)) \
        or len(stripped.split()) >= 4

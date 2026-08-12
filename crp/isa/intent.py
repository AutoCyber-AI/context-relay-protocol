# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Fast intent / speech-act classifier (CRP-SPEC-052 §4.3.1).

The base :class:`IntentClassifier` is rule-based and has zero heavy
dependencies, keeping the positioned tool loop under the sub-10 ms budget.
An optional :class:`LLMIntentClassifier` can call a local OpenAI-compatible
endpoint (e.g. LM Studio) when a stronger pragmatic interpretation is needed.

ML-driven classifiers are **default-on** when their optional dependencies are
installed, but they are loaded lazily and governed by the millisecond budget in
:mod:`crp.ml`.  If the model is absent, slow, or raises, classification degrades
to the rule-based path automatically.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

from crp.ml import MANAGER

logger = logging.getLogger(__name__)


@dataclass
class IntentTag:
    """Pragmatic tag for a user turn."""

    speech_act: str = "request"          # request | question | assertion | expressive
    directness: float = 0.7              # 0 hinted .. 1 explicit imperative
    implied_constraints: list[str] = field(default_factory=list)
    valence: float = 0.0                 # -1 frustrated .. +1 positive
    raw: str = ""


def _setfit_loader() -> Any:
    """Lazily load a SetFit intent model if available."""
    from setfit import SetFitModel  # type: ignore[import-untyped]

    default_id = "AutoCyberAI/crp-intent-setfit"
    try:
        from crp.ml.downloader import model_location

        default_id = model_location("crp.isa.intent")
    except Exception:  # noqa: BLE001
        pass
    model_id = os.getenv("CRP_INTENT_MODEL", default_id)
    return SetFitModel.from_pretrained(model_id)


# Register the optional ML model.  No import or download happens until first use.
MANAGER.register(
    "crp.isa.intent",
    _setfit_loader,
    budget_ms=15.0,
    load_timeout_ms=60000.0,
)


class IntentClassifier:
    """Zero-dependency speech-act + intent classifier.

    The classifier is deliberately simple: it meets the latency budget and
    gives downstream positioning reliable pragmatic signals. A SetFit/DeBERTa
    model can be swapped in by subclassing and overriding :meth:`classify`.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Accept kwargs for drop-in compatibility with model-backed variants."""
        pass

    def classify(self, turn: str, history: list[str] | None = None) -> IntentTag:
        """Classify a single user turn."""
        act = self._speech_act(turn)
        return IntentTag(
            speech_act=act,
            directness=self._directness(turn),
            implied_constraints=self._constraints(turn),
            valence=self._valence(turn),
            raw=turn,
        )

    @staticmethod
    def _speech_act(turn: str) -> str:
        t = turn.strip()
        lower = t.lower().rstrip("?")
        if t.endswith("?"):
            return "question"
        if lower.startswith(("i think", "i believe", "it seems", "this is")):
            return "assertion"
        if lower.startswith(("i feel", "i'm frustrated", "great", "amazing", "terrible")):
            return "expressive"
        return "request"

    @staticmethod
    def _directness(turn: str) -> float:
        t = turn.strip().lower()
        if t.endswith("?") or t.startswith(("can you", "could you", "would you", "i wonder")):
            return 0.4
        if t.startswith(("please ",)):
            return 0.9
        words = t.split()
        if words and not words[0].endswith("s"):
            # heuristic: bare imperative verb form usually lacks final 's'
            return 0.9
        return 0.7

    @staticmethod
    def _constraints(turn: str) -> list[str]:
        cons = []
        lower = turn.lower()
        for kw, c in (
            ("only", "restrict-scope"),
            ("without", "exclusion"),
            ("before", "temporal-order"),
            ("must", "hard-constraint"),
            ("after", "temporal-order"),
            ("avoid", "exclusion"),
            ("at least", "hard-constraint"),
        ):
            if kw in lower:
                cons.append(c)
        return cons

    @staticmethod
    def _valence(turn: str) -> float:
        neg = sum(w in turn.lower() for w in ("still", "again", "broken", "wrong", "not working"))
        pos = sum(w in turn.lower() for w in ("great", "thanks", "awesome"))
        if neg and pos:
            return 0.0
        if neg:
            return -0.5
        if pos:
            return 0.5
        return 0.0


def confidence(tag: IntentTag) -> float:
    """Estimate classifier confidence for downstream clarification gate (SPEC-053).

    Higher directness and recognized constraints increase confidence; unknown
    or expressive speech acts decrease it.
    """
    base = tag.directness
    if tag.speech_act in {"request", "question"}:
        base += 0.1
    elif tag.speech_act == "expressive":
        base -= 0.2
    if tag.implied_constraints:
        base += 0.05
    return round(max(0.0, min(1.0, base)), 3)


class ManagedIntentClassifier(IntentClassifier):
    """ML-first intent classifier with deterministic rule-based fallback.

    Tries a registered local model (SetFit by default) under a millisecond
    budget.  If the model is unavailable or slow, the rule-based classifier
    takes over instantly.
    """

    def __init__(self, model_key: str = "crp.isa.intent", budget_ms: float = 15.0):
        self.model_key = model_key
        self.budget_ms = budget_ms

    def classify(self, turn: str, history: list[str] | None = None) -> IntentTag:
        try:
            tag = MANAGER.run(
                self.model_key,
                lambda model: self._model_tag(model, turn),
                budget_ms=self.budget_ms,
                fallback=None,
            )
            if tag is not None:
                return tag
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Managed intent classification failed: %s", exc)
        return super().classify(turn, history)

    def _model_tag(self, model: Any, turn: str) -> IntentTag | None:
        # SetFit-style multi-class predict returns a single label string.
        if hasattr(model, "predict"):
            act = model.predict([turn])[0]
            if isinstance(act, str) and act in {"request", "question", "assertion", "expressive"}:
                return IntentTag(
                    speech_act=act,
                    directness=self._directness(turn),
                    implied_constraints=self._constraints(turn),
                    valence=self._valence(turn),
                    raw=turn,
                )
        return None


class LLMIntentClassifier(IntentClassifier):
    """Optional intent classifier backed by a local OpenAI-compatible LLM.

    Useful for tests against LM Studio or other local servers. Falls back to
    the rule-based classifier if the LLM is unreachable or refuses to answer.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None):
        self.base_url = base_url or os.getenv("CRP_LM_STUDIO_URL", "http://localhost:1234/v1")
        self.api_key = api_key or os.getenv("CRP_LM_STUDIO_KEY", "not-needed")
        self.model = model or os.getenv("CRP_LM_STUDIO_MODEL")
        self._client: Any | None = None

    def classify(self, turn: str, history: list[str] | None = None) -> IntentTag:
        try:
            tag = self._llm_classify(turn, history or [])
            if tag is not None:
                return tag
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("LLM intent classification failed: %s", exc)
        return super().classify(turn, history)

    def _llm_classify(self, turn: str, history: list[str]) -> IntentTag | None:
        from openai import OpenAI

        if self._client is None:
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=10)

        prompt = (
            "Classify the following user turn. Reply ONLY with a JSON object "
            "containing these keys: speech_act (one of request, question, assertion, expressive), "
            "directness (float 0-1), valence (float -1 to 1), constraints (list of short strings).\n\n"
            f"User turn: {turn}\nJSON:"
        )
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        resp = self._client.chat.completions.create(
            model=self.model or "local",
            messages=messages,  # type: ignore[arg-type]
            temperature=0.0,
            max_tokens=128,
        )
        text = resp.choices[0].message.content or ""
        return self._parse_json_tag(text, turn)

    def _parse_json_tag(self, text: str, raw: str) -> IntentTag | None:
        import json

        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        act = data.get("speech_act", "request")
        if act not in {"request", "question", "assertion", "expressive"}:
            act = "request"
        constraints = data.get("constraints", [])
        if not isinstance(constraints, list):
            constraints = []
        return IntentTag(
            speech_act=act,
            directness=float(data.get("directness", 0.7)),
            implied_constraints=[str(c) for c in constraints],
            valence=float(data.get("valence", 0.0)),
            raw=raw,
        )

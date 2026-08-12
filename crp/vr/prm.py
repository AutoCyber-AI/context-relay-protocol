# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Process Reward Model verifier for non-formal inference steps (SPEC-049 §1.3.4).

This is the probabilistic DPE stage 14.  When ``transformers`` is available it
runs a small text-classifier under the millisecond budget managed by
:mod:`crp.ml`; otherwise it returns UNKNOWN so the relay remains functional in
zero-dependency mode.  Labels produced by symbolic verifiers can be harvested to
fine-tune this model (the verification flywheel).

Production model (CRPv6 Phase A): ``AutoCyberAI/crp-prm-deberta-v1``
(DeBERTa-v3-large, RunPod-trained on prm800k + Math-Shepherd + MMLU-Pro-CoT +
RLHFlow + agentic synthetic).  Measured on held-out prm800k steps: AUC 0.793,
curated reasoning 8/10, VALID recall 1.000 — treat its score as ADVISORY:
it never false-flags good steps at threshold >= 0.15, but subtle math-domain
errors score low, so hard INVALID gating stays with the symbolic verifiers and
checkpoints.  Note: the config's exported ``prm_threshold`` (0.675) was
calibrated on a training-matched mix and does not transfer to real
distributions; the default here is deliberately plain argmax (0.5), tunable
via ``CRP_PRM_THRESHOLD`` / ``CRP_PRM_BUDGET_MS``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from crp.ml import MANAGER
from crp.vr.interface import Claim, Verdict, VerificationResult

logger = logging.getLogger(__name__)


def _prm_loader(model_name: str) -> Any:
    """Lazily load a text-classification pipeline for step-level verification."""
    from transformers import pipeline  # type: ignore[import]

    return pipeline("text-classification", model=model_name, top_k=None)


def _default_prm_model_id() -> str:
    """Return the default PRM model id, preferring the manifest local copy."""
    try:
        from crp.ml.downloader import model_location

        return model_location("crp.vr.prm")
    except Exception:  # noqa: BLE001
        return "AutoCyberAI/crp-prm-deberta-v1"


class ProcessRewardVerifier:
    """Step-level reasoning verifier backed by a small classifier."""

    name = "prm"

    def __init__(self, model: str | None = None, threshold: float | None = None):
        default_id = _default_prm_model_id()
        self._model_name = (model or os.getenv("CRP_PRM_MODEL", default_id) or default_id)
        self._threshold = (
            threshold
            if threshold is not None
            else float(os.getenv("CRP_PRM_THRESHOLD", "0.5"))
        )
        # DeBERTa-v3-large on CPU costs ~200-300ms/step — the relay runs
        # post-generation where that is acceptable, but the default 50ms
        # budget would silently degrade every call to UNKNOWN.
        self._budget_ms = float(os.getenv("CRP_PRM_BUDGET_MS", "400"))
        # Use the canonical manifest key when the default model is selected;
        # custom models get a unique key so multiple verifiers can coexist.
        self._model_key = (
            "crp.vr.prm"
            if self._model_name == default_id
            else f"crp.vr.prm.{self._model_name}"
        )
        # Register on the global manager so loading is lazy, cached, and budgeted.
        MANAGER.register(
            self._model_key,
            lambda: _prm_loader(self._model_name),
            budget_ms=self._budget_ms,
            load_timeout_ms=120000.0,
        )

    def applies(self, claim: Claim) -> bool:
        """Apply to inference steps that are not formally checkable."""
        return claim.kind == "inference"

    def verify(self, claim: Claim, context: dict[str, Any]) -> VerificationResult:
        """Score whether *claim* is entailed by its premises."""
        premises = " ".join(claim.premises)
        text = f"premises: {premises} [SEP] step: {claim.text}"

        def _score(model: Any) -> VerificationResult:
            scores = {d["label"]: d["score"] for d in model(text)}
            p_valid = scores.get("VALID", 0.0)
            if p_valid >= self._threshold:
                return VerificationResult(
                    Verdict.VALID,
                    p_valid,
                    "step-reward above threshold",
                    self.name,
                    False,
                )
            return VerificationResult(
                Verdict.INVALID,
                1.0 - p_valid,
                "step not entailed by prior steps",
                self.name,
                False,
            )

        return MANAGER.run(
            self._model_key,
            _score,
            budget_ms=self._budget_ms,
            fallback=VerificationResult(
                Verdict.UNKNOWN,
                0.0,
                "PRM model unavailable or exceeded budget",
                self.name,
                False,
            ),
        )

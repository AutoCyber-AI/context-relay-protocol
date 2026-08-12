# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Injection detection — Layer 2, advisory only, NEVER blocks (§7.5).

Detects prompt injection patterns and reports them as advisory flags.
CRITICAL: This detector NEVER modifies input and NEVER blocks processing.
It only sets security_flags on the quality report for upstream inspection.

Detection layers (ensembled):
  1. Regex pattern library — 21 compiled patterns across 6 categories
  2. ML classifier (optional) — CRP safety DeBERTa (crp-safety-deberta-v1,
     CRPv6 Phase A), prompt-injection-detector (TF-IDF + LR), or ProtectAI
     DeBERTa v2 (transformer-based). Zero-config: auto-detected.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.ml import MANAGER, model_location

logger = logging.getLogger("crp.security.injection")


def _safety_loader() -> Any:
    """Lazily load the CRP safety classifier pipeline."""
    from transformers import pipeline  # type: ignore[import-untyped]

    model_id = os.getenv("CRP_SAFETY_MODEL", model_location("crp.security.safety"))
    pipe = pipeline(
        task="text-classification",
        model=model_id,
        truncation=True,
        max_length=512,
    )
    if sys.platform == "win32":
        # Load-time OpenMP race is past — restore parallel inference
        # (crp/__init__ caps OMP_NUM_THREADS=1 process-wide, which
        # would otherwise make every forward ~10x slower).
        try:
            import torch  # type: ignore[import-untyped]

            torch.set_num_threads(max(1, os.cpu_count() or 1))
        except Exception:  # noqa: BLE001
            pass
    return pipe


# Register the optional safety model.  No import or download happens until first use.
MANAGER.register(
    "crp.security.safety",
    _safety_loader,
    budget_ms=40.0,
    load_timeout_ms=60000.0,
)


def _reset_shared_safety_pipeline() -> None:
    """Drop the shared pipeline and registry cache (test isolation)."""
    MANAGER.reset("crp.security.safety")


class InjectionType(str, Enum):
    """Categories of detected injection patterns."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    SYSTEM_IMPERSONATION = "system_impersonation"
    ROLE_CONFUSION = "role_confusion"
    DATA_EXFILTRATION = "data_exfiltration"
    JAILBREAK = "jailbreak"
    ENCODING_BYPASS = "encoding_bypass"


@dataclass
class InjectionFlag:
    """Advisory flag for a detected injection pattern."""

    injection_type: InjectionType
    pattern_name: str
    matched_text: str
    position: int  # character offset
    confidence: float  # 0.0–1.0


@dataclass
class InjectionReport:
    """Result of injection detection — advisory only."""

    flags: list[InjectionFlag] = field(default_factory=list)
    scanned_length: int = 0
    patterns_checked: int = 0
    ml_confidence: float = 0.0  # ML classifier score (0.0 if unavailable)
    ml_backend: str = "none"  # ML backend name or "none"

    @property
    def has_flags(self) -> bool:
        """Return whether this object has flags."""
        return len(self.flags) > 0

    @property
    def highest_confidence(self) -> float:
        """Return the highest confidence."""
        if not self.flags:
            return 0.0
        return max(f.confidence for f in self.flags)

    @property
    def security_flags(self) -> list[str]:
        """Return flag strings for QualityReport.security_flags (§6E.3)."""
        return [
            f"{f.injection_type.value}:{f.pattern_name}:{f.confidence:.2f}"
            for f in self.flags
        ]


# ---------------------------------------------------------------------------
# Pattern library (§6E.2)
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[str, InjectionType, str, float]] = [
    # (regex, type, name, confidence)

    # Instruction override
    (r"\bignore\s+(?:all\s+)?(?:previous|above|prior)\s+(?:instructions?|prompts?|rules?)\b",
     InjectionType.INSTRUCTION_OVERRIDE, "ignore_previous", 0.95),
    (r"\bdisregard\s+(?:all\s+)?(?:previous|above|prior|your)\s+(?:instructions?|programming|rules?)\b",
     InjectionType.INSTRUCTION_OVERRIDE, "disregard_previous", 0.95),
    (r"\bforget\s+(?:everything|all|your)\s+(?:instructions?|rules?|training)\b",
     InjectionType.INSTRUCTION_OVERRIDE, "forget_instructions", 0.90),
    (r"\bnew\s+instructions?\s*[:=]",
     InjectionType.INSTRUCTION_OVERRIDE, "new_instructions", 0.85),
    (r"\byou\s+(?:are|will)\s+now\s+(?:a|an|my)\b",
     InjectionType.INSTRUCTION_OVERRIDE, "role_reassignment", 0.80),

    # System impersonation
    (r"^\s*system\s*:\s*",
     InjectionType.SYSTEM_IMPERSONATION, "system_prefix", 0.90),
    (r"^\s*\[system\]\s*",
     InjectionType.SYSTEM_IMPERSONATION, "system_bracket", 0.90),
    (r"<\|?(?:system|im_start)\|?>",
     InjectionType.SYSTEM_IMPERSONATION, "system_token", 0.95),
    (r"\bsystem\s+prompt\s*[:=]",
     InjectionType.SYSTEM_IMPERSONATION, "system_prompt_set", 0.85),

    # Role confusion
    (r"\bas\s+an?\s+(?:AI|language\s+model|assistant|chatbot)\b",
     InjectionType.ROLE_CONFUSION, "as_an_ai", 0.60),
    (r"\byou\s+are\s+(?:an?\s+)?(?:helpful|harmless|honest)\b",
     InjectionType.ROLE_CONFUSION, "alignment_override", 0.75),
    (r"\bact\s+as\s+(?:if\s+you\s+(?:are|were)|an?\s+)",
     InjectionType.ROLE_CONFUSION, "act_as", 0.50),

    # Data exfiltration
    (r"\b(?:reveal|show|display|output|print)\s+(?:your|the)\s+(?:system\s+)?(?:prompt|instructions?|rules?)\b",
     InjectionType.DATA_EXFILTRATION, "reveal_prompt", 0.85),
    (r"\b(?:what\s+(?:are|is)\s+your\s+(?:system\s+)?(?:prompt|instructions?|rules?))\b",
     InjectionType.DATA_EXFILTRATION, "query_prompt", 0.70),

    # Jailbreak
    (r"\b(?:DAN|do\s+anything\s+now)\b",
     InjectionType.JAILBREAK, "dan_mode", 0.90),
    (r"\bdeveloper\s+mode\b",
     InjectionType.JAILBREAK, "developer_mode", 0.80),
    (r"\b(?:bypass|override|disable)\s+(?:safety|content|ethical)\s+(?:filters?|guidelines?|restrictions?)\b",
     InjectionType.JAILBREAK, "bypass_safety", 0.95),

    # Encoding bypass
    (r"(?:&#x?[0-9a-f]+;){3,}",
     InjectionType.ENCODING_BYPASS, "html_entities", 0.70),
    (r"(?:%[0-9a-f]{2}){3,}",
     InjectionType.ENCODING_BYPASS, "url_encoding", 0.60),
    (r"\\u[0-9a-f]{4}(?:\\u[0-9a-f]{4}){2,}",
     InjectionType.ENCODING_BYPASS, "unicode_escape", 0.65),
]

_COMPILED_PATTERNS = [
    (re.compile(p, re.IGNORECASE | re.MULTILINE), t, n, c)
    for p, t, n, c in _PATTERNS
]


# ---------------------------------------------------------------------------
# ML scanner abstraction (§7.5.3)
# ---------------------------------------------------------------------------


class _MLScanner:
    """Abstract interface for ML-based injection detection."""

    name: str = "unknown"

    def score(self, text: str) -> float | None:
        """Return injection probability 0.0–1.0, or None if unavailable."""
        raise NotImplementedError


class _CRPSafetyDeBERTaScanner(_MLScanner):
    """CRP safety classifier — DeBERTa-v3-xsmall safe/unsafe (CRPv6 Phase A).

    Model id comes from ``CRP_SAFETY_MODEL`` (default managed by
    :mod:`crp.ml`).  ``transformers`` is imported lazily by the registered
    loader, never at module import time.

    The ~283MB pipeline loads on a **daemon thread** at construction so
    neither orchestrator init nor the first dispatch stalls (§7.14
    <50ms-overhead invariant).  Loading is managed by :class:`crp.ml.ModelManager`,
    so the model is cached, budgeted, and participates in the global fallback
    path.  While the model is still warming, or if it fails to load,
    :meth:`score` returns ``None`` and the detector falls back to regex-only
    for that call.
    """

    name = "crp-safety-deberta"

    def __init__(self) -> None:
        self._classifier: Any = None
        self._ready = threading.Event()
        self._failed = False
        self._thread = threading.Thread(target=self._warm, daemon=True)
        self._thread.start()

    def _warm(self) -> None:
        try:
            self._classifier = MANAGER.load("crp.security.safety")
            if self._classifier is not None:
                logger.info("ML injection scanner loaded: %s", self.name)
            else:
                self._failed = True
                logger.debug("crp-safety-deberta load failed; regex-only")
        except Exception:  # noqa: BLE001
            self._failed = True
            logger.debug("crp-safety-deberta load failed; regex-only", exc_info=True)
        finally:
            self._ready.set()

    @property
    def available(self) -> bool:
        """True once the model has warmed successfully."""
        return self._ready.is_set() and not self._failed

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Block until the model finishes warming (or fails). Returns availability."""
        self._ready.wait(timeout)
        return self.available

    def score(self, text: str) -> float | None:
        """Return unsafe probability 0.0–1.0, or None if not ready."""
        if not self.available or self._classifier is None:
            return None
        results = self._classifier(text)
        if not results:
            return 0.0
        label = str(results[0].get("label", "")).lower()
        confidence = float(results[0].get("score", 0.0))
        if label == "unsafe":
            return confidence
        return 1.0 - confidence


class _PromptInjectionDetectorScanner(_MLScanner):
    """Wrapper for prompt-injection-detector package (TF-IDF + LR, ~1MB)."""

    name = "tfidf-lr"

    def __init__(self) -> None:
        from prompt_injection_detector import Scanner  # type: ignore[import-untyped]
        self._scanner = Scanner()

    def score(self, text: str) -> float:
        """Execute score and return the result.

        Args:
            text (str): The text value.

        Returns:
            ``float``.
        """
        result = self._scanner.scan(text)
        return float(result.risk_score)


class _ProtectAIDeBERTaScanner(_MLScanner):
    """Wrapper for ProtectAI DeBERTa v2 ONNX model (~350MB)."""

    name = "deberta-v2-onnx"

    def __init__(self) -> None:
        from optimum.onnxruntime import (
            ORTModelForSequenceClassification,  # type: ignore[import-untyped]
        )
        from transformers import AutoTokenizer, pipeline  # type: ignore[import-untyped]

        model_id = "ProtectAI/deberta-v3-base-prompt-injection-v2"
        tokenizer = AutoTokenizer.from_pretrained(model_id, subfolder="onnx")
        tokenizer.model_input_names = ["input_ids", "attention_mask"]
        model = ORTModelForSequenceClassification.from_pretrained(
            model_id, export=False, subfolder="onnx"
        )
        self._classifier = pipeline(
            task="text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=512,
        )

    def score(self, text: str) -> float:
        """Execute score and return the result.

        Args:
            text (str): The text value.

        Returns:
            ``float``.
        """
        results = self._classifier(text)
        # Model returns [{"label": "INJECTION"/"SAFE", "score": float}]
        if results and results[0].get("label") == "INJECTION":
            return float(results[0]["score"])
        return 1.0 - float(results[0].get("score", 1.0)) if results else 0.0


def _load_ml_scanner() -> _MLScanner | None:
    """Auto-detect and load the best available ML scanner.

    Priority:
      1. CRP safety DeBERTa (CRPv6 Phase A, ``CRP_SAFETY_MODEL``)
      2. prompt-injection-detector (lightweight, ~1MB, MIT)
      3. ProtectAI DeBERTa v2 ONNX (accurate, ~350MB, Apache 2.0)
      4. None (regex-only fallback)
    """
    # Try the CRP safety classifier first (model-first path). The scanner
    # warms its model on a daemon thread, so construction is cheap; only
    # select it when transformers is actually importable. Tests may poison
    # optional packages by setting sys.modules entries to None — treat that
    # as unavailable. find_spec raises ValueError on spec-less fake modules.
    transformers_poisoned = (
        "transformers" in sys.modules and sys.modules["transformers"] is None
    )
    if not transformers_poisoned:
        if "transformers" in sys.modules:
            return _CRPSafetyDeBERTaScanner()
        try:
            if importlib.util.find_spec("transformers") is not None:
                return _CRPSafetyDeBERTaScanner()
        except ValueError:
            pass

    # Try lightweight TF-IDF scanner
    try:
        tfidf_scanner = _PromptInjectionDetectorScanner()
        logger.info("ML injection scanner loaded: %s", tfidf_scanner.name)
        return tfidf_scanner
    except Exception:  # noqa: BLE001
        pass

    # Try ProtectAI DeBERTa ONNX
    try:
        protect_scanner = _ProtectAIDeBERTaScanner()
        logger.info("ML injection scanner loaded: %s", protect_scanner.name)
        return protect_scanner
    except Exception:  # noqa: BLE001
        pass

    logger.info(
        "No ML injection scanner available — using regex patterns only. "
        "Install 'prompt-injection-detector' for ML-based detection."
    )
    return None


# ---------------------------------------------------------------------------
# InjectionDetector
# ---------------------------------------------------------------------------


class InjectionDetector:
    """Advisory injection detection — NEVER blocks, only reports (§7.5).

    CRITICAL DESIGN CONSTRAINT: This detector NEVER modifies input text
    and NEVER prevents processing. It only produces advisory flags that
    are reported to QualityReport.security_flags.

    Detection layers (ensembled automatically):
      Layer 1: Regex pattern library (always active)
      Layer 2: ML classifier (auto-detected, optional)
        - CRP safety DeBERTa: crp-safety-deberta-v1 safe/unsafe (CRPv6 Phase A)
        - prompt-injection-detector: TF-IDF + Logistic Regression (~1MB, MIT)
        - ProtectAI DeBERTa v2: ONNX transformer (~350MB, Apache 2.0)

    Usage:
        detector = InjectionDetector()
        report = detector.scan("ignore all previous instructions")
        if report.has_flags:
            quality_report.security_flags = report.security_flags
    """

    def __init__(self) -> None:
        self._patterns = _COMPILED_PATTERNS
        self._ml_scanner = _load_ml_scanner()
        self._ml_strikes = 0
        self._ml_budget_ms = float(os.getenv("CRP_SAFETY_ML_BUDGET_MS", "40"))

    @property
    def ml_enabled(self) -> bool:
        """Whether ML-based injection detection is available."""
        return self._ml_scanner is not None

    @property
    def ml_backend(self) -> str:
        """Name of the ML backend in use, or 'none'."""
        if self._ml_scanner is None:
            return "none"
        return self._ml_scanner.name

    def scan(self, text: str) -> InjectionReport:
        """Scan text for injection patterns.

        Returns advisory report — NEVER blocks (§6E.1).
        Ensembles regex patterns with ML classifier when available.
        """
        flags: list[InjectionFlag] = []

        for pattern, inj_type, name, confidence in self._patterns:
            for match in pattern.finditer(text):
                flags.append(InjectionFlag(
                    injection_type=inj_type,
                    pattern_name=name,
                    matched_text=match.group(0)[:100],  # truncate for safety
                    position=match.start(),
                    confidence=confidence,
                ))

        # Deduplicate overlapping matches (keep highest confidence)
        flags = self._deduplicate(flags)

        # ── ML classifier layer (§7.5.3) ──────────────────────
        # The ML layer is only consulted when regex found nothing: a regex
        # hit already carries a *specific* injection type (ignore_previous,
        # system_impersonation, ...) which is strictly more informative than
        # the generic ml: flag — and skipping the forward pass keeps the
        # dispatch overhead within the <50ms invariant (§7.14). Calls are
        # time-boxed: repeated budget overruns disable the ML layer for this
        # detector (regex always stays active).
        ml_confidence = 0.0
        ml_backend_name = "none"
        if self._ml_scanner is not None and not flags:
            try:
                t0 = time.perf_counter()
                score = self._ml_scanner.score(text)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                if score is not None:
                    ml_confidence = score
                    ml_backend_name = self._ml_scanner.name
                    self._note_ml_latency(elapsed_ms)
                    if ml_confidence >= 0.50:
                        flags.append(InjectionFlag(
                            injection_type=InjectionType.INSTRUCTION_OVERRIDE,
                            pattern_name=f"ml:{ml_backend_name}",
                            matched_text=text[:100],
                            position=0,
                            confidence=ml_confidence,
                        ))
            except Exception:  # noqa: BLE001
                # ML scanner failure is non-fatal — regex layer still works
                logger.debug("ML injection scanner failed, using regex only")

        return InjectionReport(
            flags=flags,
            scanned_length=len(text),
            patterns_checked=len(self._patterns),
            ml_confidence=ml_confidence,
            ml_backend=ml_backend_name,
        )

    def _note_ml_latency(self, elapsed_ms: float) -> None:
        """Track ML call latency; disable the ML layer after repeated overruns."""
        if elapsed_ms <= self._ml_budget_ms:
            self._ml_strikes = 0
            return
        self._ml_strikes += 1
        if self._ml_strikes >= 3:
            logger.warning(
                "ML injection scanner exceeded the %.0fms budget %d times — "
                "disabling it for this detector (regex layer stays active)",
                self._ml_budget_ms,
                self._ml_strikes,
            )
            self._ml_scanner = None

    @staticmethod
    def _deduplicate(flags: list[InjectionFlag]) -> list[InjectionFlag]:
        """Remove duplicate flags at the same position."""
        seen: dict[int, InjectionFlag] = {}
        for f in flags:
            key = f.position
            if key not in seen or f.confidence > seen[key].confidence:
                seen[key] = f
        return sorted(seen.values(), key=lambda f: f.position)

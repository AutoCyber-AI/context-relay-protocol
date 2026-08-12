# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 3 — GLiNER zero-shot NER extraction (SHOULD, ~50ms, lazy model load).

.. note::
   CRPv6 Phase A: GLiNER is no longer the default Stage 3 backend — it
   crashes on Windows (torch/OpenMP duplicate runtime).  The default is now
   ``dslim/bert-base-NER`` via :mod:`crp.extraction.stage3_ner`.  GLiNER
   remains available as an explicit opt-in: set
   ``CRP_NER_MODEL=urchade/gliner_base`` (or any ``urchade/gliner*`` id).

Trigger: Stage 2 yield < self-calibrated baseline.
Model: GLiNER (~200MB), loaded lazily, unloaded after 20 idle windows.
Graceful fallback: if model unavailable, returns empty and logs warning.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Protocol, runtime_checkable

from crp.extraction.types import Fact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GLiNER model protocol (for dependency inversion)
# ---------------------------------------------------------------------------

@runtime_checkable
class GLiNERModel(Protocol):
    """Minimal interface a GLiNER-compatible model must satisfy."""

    def predict_entities(
        self, text: str, labels: list[str], threshold: float = 0.5
    ) -> list[dict[str, Any]]:
        """Return list of dicts with keys: text, label, score, start, end."""
        ...


# ---------------------------------------------------------------------------
# Label derivation from task context
# ---------------------------------------------------------------------------

def derive_labels_from_noun_phrases(noun_phrases: list[str], max_labels: int = 15) -> list[str]:
    """Convert Stage 2 noun phrases into zero-shot NER labels.

    Strips determiners and lowercases. De-duplicates and caps at *max_labels*.
    """
    labels: list[str] = []
    seen: set[str] = set()
    for np_text in noun_phrases:
        # Simple normalisation
        label = np_text.strip().lower()
        for prefix in ("the ", "a ", "an "):
            if label.startswith(prefix):
                label = label[len(prefix):]
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
        if len(labels) >= max_labels:
            break
    return labels


# ---------------------------------------------------------------------------
# Stage 3 Extractor
# ---------------------------------------------------------------------------

class GLiNERExtractor:
    """Stage 3 — zero-shot NER via GLiNER (lazy, optional).

    The model is loaded on first call and unloaded after *idle_limit* windows
    without a call. If ``gliner`` is not installed, all calls return ``[]``.
    """

    def __init__(self, idle_limit: int = 20) -> None:
        self._model: GLiNERModel | None = None
        self._idle_limit = idle_limit
        self._windows_since_use: int = 0
        self._available: bool | None = None  # None = not yet probed

    # -- Lifecycle ----------------------------------------------------------

    @staticmethod
    def _is_model_cached() -> bool:
        """Check if the GLiNER model is already cached locally.

        Checks the HuggingFace hub cache directory for the model files.
        Returns True if cached, False if a download would be required.
        """
        try:
            from pathlib import Path
            # HuggingFace hub default cache location
            hf_home = os.environ.get("HF_HOME", os.environ.get(
                "HUGGINGFACE_HUB_CACHE",
                str(Path.home() / ".cache" / "huggingface" / "hub"),
            ))
            cache_dir = Path(hf_home) / "models--urchade--gliner_base"
            if cache_dir.is_dir():
                # Check that snapshots exist (actual model files)
                snapshots = cache_dir / "snapshots"
                if snapshots.is_dir() and any(snapshots.iterdir()):
                    return True
        except Exception:  # noqa: BLE001
            pass
        return False

    def _ensure_model(self) -> GLiNERModel | None:
        """Lazy-load GLiNER. Returns None if unavailable.

        If the model is not cached locally and we appear to be offline,
        skips the download attempt rather than hanging on a network call.

        Set ``CRP_GLINER_DISABLED=1`` to skip Stage 3 entirely (useful in CI
        and on machines where torch/GLiNER loading is slow or unstable).
        """
        if os.environ.get("CRP_GLINER_DISABLED", "").lower() in {"1", "true", "yes"}:
            self._available = False
            return None
        if self._available is False:
            return None
        if self._model is not None:
            return self._model

        # Check cache before attempting download — if not cached and
        # offline, avoid a long timeout or network failure.
        if not self._is_model_cached():
            # Quick connectivity probe: can we reach huggingface.co?
            import socket
            try:
                socket.create_connection(("huggingface.co", 443), timeout=3)
            except OSError:
                self._available = False
                logger.warning(
                    "GLiNER model not cached and network unreachable — "
                    "Stage 3 disabled. Pre-download with: "
                    'python -c "from gliner import GLiNER; '
                    "GLiNER.from_pretrained('urchade/gliner_base')\""
                )
                return None

        try:
            import sys

            if sys.platform == "win32":
                # Extra hardening beyond the process-level env vars set in
                # crp/__init__.py: also cap torch's own intra-op thread pool.
                # Prevents a Windows-only native access violation caused by
                # multiple OpenMP runtimes (numpy/scipy/sklearn/torch) racing
                # during model weight loading — see crp/__init__.py comment.
                try:
                    import torch  # type: ignore[import-untyped]

                    torch.set_num_threads(1)
                except Exception:
                    pass

            from gliner import GLiNER  # type: ignore[import-untyped]

            self._model = GLiNER.from_pretrained("urchade/gliner_base")  # type: ignore[assignment]
            self._available = True
            logger.info("GLiNER model loaded successfully")
            return self._model
        except Exception:
            self._available = False
            logger.warning("GLiNER not available — Stage 3 will be skipped")
            return None

    def unload(self) -> None:
        """Release model from memory."""
        self._model = None
        logger.info("GLiNER model unloaded (idle)")

    def tick_idle(self) -> None:
        """Called once per window. Unloads model after idle_limit."""
        if self._model is not None:
            self._windows_since_use += 1
            if self._windows_since_use >= self._idle_limit:
                self.unload()

    @property
    def is_available(self) -> bool:
        """Return whether this object is available."""
        if self._available is None:
            self._ensure_model()
        return self._available is True

    # -- Extraction ---------------------------------------------------------

    def extract(
        self,
        text: str,
        labels: list[str] | None = None,
        source_window_id: str = "",
        threshold: float = 0.5,
    ) -> list[Fact]:
        """Run zero-shot NER over *text* using *labels*.

        If no labels provided, uses a small set of generic security/tech labels.
        Returns ``[]`` if model is unavailable — never raises.
        """
        model = self._ensure_model()
        if model is None:
            return []

        self._windows_since_use = 0  # Reset idle counter

        if not labels:
            labels = [
                "vulnerability", "server", "endpoint", "credential",
                "configuration", "service", "network", "error",
                "tool", "technique", "software", "organization",
            ]

        try:
            entities = model.predict_entities(text, labels, threshold=threshold)
        except Exception:
            logger.exception("GLiNER prediction failed")
            return []

        facts: list[Fact] = []
        for ent in entities:
            confidence = float(ent.get("score", 0.65))
            facts.append(Fact(
                text=str(ent.get("text", "")),
                category=str(ent.get("label", "entity")),
                source_window_id=source_window_id,
                confidence=min(0.85, max(0.65, confidence)),
                extraction_stage=3,
                metadata={
                    "label": ent.get("label"),
                    "gliner_score": round(confidence, 4),
                    "span": [ent.get("start", 0), ent.get("end", 0)],
                },
            ))

        return facts

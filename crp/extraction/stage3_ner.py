# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Stage 3 — Named-entity recognition, Windows-safe default (CRPv6 Phase A).

Default backend: ``dslim/bert-base-NER`` via ``transformers.pipeline`` with
``aggregation_strategy="simple"``, lazy-loaded on first use.  BERT-NER runs
torch on CPU without the GLiNER/OpenMP failure modes observed on Windows, so
no environment flag is required for Stage 3 to work.

Backend fallback chain (the pipeline never fails because NER is unavailable):

1. ``CRP_NER_MODEL`` env override — ``urchade/gliner*`` delegates to the
   GLiNER stage (explicit opt-in, see :mod:`crp.extraction.stage3_gliner`);
   any other model id is loaded as a transformers NER pipeline.
2. ``dslim/bert-base-NER`` when ``transformers`` + ``torch`` are installed
   (HF cache checked first; a short connectivity probe avoids offline hangs).
3. spaCy ``en_core_web_sm`` when spaCy is installed.
4. Unavailable — ``extract()`` returns ``[]`` and Stages 1-2 (regex /
   statistical) remain the rule-based extraction path.

Produces the same :class:`~crp.extraction.types.Fact` contract as the GLiNER
stage: ``extraction_stage=3``, confidence clamped to [0.65, 0.85], and entity
metadata carrying ``label``, ``ner_score`` and ``span`` offsets.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from crp.extraction.types import Fact

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_NER_MODEL = "dslim/bert-base-NER"
"""Default Stage 3 NER model (Windows-safe, ~440 MB, CPU-friendly)."""

# Map bert-base-NER entity groups (PER/ORG/LOC/MISC) and their B-/I- prefixed
# variants onto the lowercase category vocabulary used by Stages 1-2.
_BERT_LABEL_MAP: dict[str, str] = {
    "PER": "person",
    "ORG": "organization",
    "LOC": "location",
    "MISC": "misc",
}

# spaCy en_core_web_sm entity labels → pipeline categories.
_SPACY_LABEL_MAP: dict[str, str] = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "FAC": "location",
    "NORP": "group",
    "PRODUCT": "product",
    "EVENT": "event",
    "WORK_OF_ART": "work",
    "LAW": "law",
    "LANGUAGE": "language",
    "DATE": "date",
    "TIME": "time",
    "PERCENT": "percent",
    "MONEY": "money",
    "QUANTITY": "quantity",
    "ORDINAL": "ordinal",
    "CARDINAL": "number",
}

# Shared cache of loaded transformers pipelines, keyed by model id.  Pipelines
# are stateless, so one instance serves every NERExtractor in the process —
# avoids a multi-hundred-MB reload per ExtractionPipeline.
_PIPELINE_CACHE: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Availability guards (mirrors the GLiNER stage's offline hardening)
# ---------------------------------------------------------------------------

def _model_cached(model_id: str) -> bool:
    """Return True if *model_id* is already in the HuggingFace hub cache."""
    try:
        from pathlib import Path

        hf_home = os.environ.get("HF_HOME", os.environ.get(
            "HUGGINGFACE_HUB_CACHE",
            str(Path.home() / ".cache" / "huggingface" / "hub"),
        ))
        cache_dir = Path(hf_home) / ("models--" + model_id.replace("/", "--"))
        if cache_dir.is_dir():
            snapshots = cache_dir / "snapshots"
            if snapshots.is_dir() and any(snapshots.iterdir()):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _hub_reachable() -> bool:
    """Quick connectivity probe so offline runs skip the download attempt."""
    import socket

    try:
        socket.create_connection(("huggingface.co", 443), timeout=3)
    except OSError:
        return False
    return True


def _module_importable(name: str) -> bool:
    """Return True if *name* can be imported (respects sys.modules fakes)."""
    import sys

    if name in sys.modules:
        # Already loaded — or a test fake. ``None`` means "import blocked".
        return sys.modules[name] is not None
    import importlib.util

    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _normalise_bert_label(raw: str) -> str:
    """Strip B-/I- prefixes and map PER/ORG/LOC/MISC to a category."""
    label = raw.upper()
    if label.startswith(("B-", "I-")):
        label = label[2:]
    return _BERT_LABEL_MAP.get(label, raw.lower())


# ---------------------------------------------------------------------------
# Stage 3 extractor
# ---------------------------------------------------------------------------

class NERExtractor:
    """Stage 3 — NER via bert-base-NER (default), GLiNER (opt-in) or spaCy.

    Same public contract as :class:`GLiNERExtractor`: models load lazily on
    first use, ``extract()`` never raises, and an idle model is unloaded after
    *idle_limit* windows without a call.  The ``labels`` argument is honoured
    only by the GLiNER backend (zero-shot); bert-base-NER has a fixed label
    set (PER/ORG/LOC/MISC) and ignores it.
    """

    def __init__(self, idle_limit: int = 20) -> None:
        self._idle_limit = idle_limit
        self._windows_since_use: int = 0
        self._available: bool | None = None  # None = not yet probed
        self._backend: str = ""              # "gliner" | "transformers" | "spacy"
        self._model_id: str = ""
        self._gliner: Any = None             # GLiNERExtractor when opted in
        self._spacy_nlp: Any = None
        # Adaptive latency budget (§7.14 <50ms overhead invariant): repeated
        # over-budget model calls disable Stage 3 for this pipeline instance,
        # degrading to the rule-based Stages 1-2. spaCy is exempt (fast).
        self._strikes: int = 0
        self._budget_ms: float = float(os.getenv("CRP_NER_BUDGET_MS", "40"))

    # -- Backend selection ---------------------------------------------------

    def _select_backend(self) -> str:
        """Choose the NER backend per the fallback chain (see module docstring)."""
        override = os.environ.get("CRP_NER_MODEL", "").strip()
        if override:
            self._model_id = override
            if "gliner" in override.lower():
                return "gliner"
            if _module_importable("transformers"):
                return "transformers"
            logger.warning(
                "CRP_NER_MODEL=%s requested but transformers is not installed — "
                "falling back", override,
            )
        if _module_importable("transformers") and _module_importable("torch"):
            self._model_id = DEFAULT_NER_MODEL
            return "transformers"
        if _module_importable("spacy"):
            self._model_id = "en_core_web_sm"
            return "spacy"
        return ""

    # -- Lifecycle -----------------------------------------------------------

    def _ensure_model(self) -> Any:
        """Lazy-load the selected backend. Returns None if unavailable."""
        if self._available is False:
            return None
        if not self._backend:
            self._backend = self._select_backend()
            if not self._backend:
                self._available = False
                logger.warning(
                    "No NER backend available (install transformers+torch or "
                    "spacy) — Stage 3 will be skipped"
                )
                return None

        if self._backend == "gliner":
            return self._ensure_gliner()
        if self._backend == "transformers":
            model = self._ensure_transformers()
            if model is not None:
                return model
            # Transformers present but model unloadable (e.g. offline and not
            # cached) — degrade to spaCy rather than skipping Stage 3.
            if _module_importable("spacy"):
                logger.info("Falling back to spaCy NER backend")
                self._backend = "spacy"
                self._model_id = "en_core_web_sm"
            else:
                self._available = False
                return None
        return self._ensure_spacy()

    def _ensure_gliner(self) -> Any:
        """Delegate to the GLiNER stage (explicit opt-in via CRP_NER_MODEL)."""
        if self._gliner is None:
            from crp.extraction.stage3_gliner import GLiNERExtractor

            self._gliner = GLiNERExtractor(idle_limit=self._idle_limit)
        model = self._gliner._ensure_model()
        self._available = model is not None
        return model

    def _ensure_transformers(self) -> Any:
        """Lazy-load the transformers NER pipeline (shared process cache)."""
        cached = _PIPELINE_CACHE.get(self._model_id)
        if cached is not None:
            self._available = True
            return cached

        # Avoid hanging on a network download when the model is not cached
        # and the hub is unreachable.
        if not _model_cached(self._model_id) and not _hub_reachable():
            logger.warning(
                "NER model %s not cached and network unreachable — "
                "transformers backend skipped", self._model_id,
            )
            return None

        try:
            import sys

            if sys.platform == "win32":
                # Extra hardening beyond the process-level env vars set in
                # crp/__init__.py: cap torch's intra-op thread pool to avoid
                # the Windows-only OpenMP duplicate-runtime race during model
                # weight loading — see crp/__init__.py comment.
                try:
                    import torch  # type: ignore[import-untyped]

                    torch.set_num_threads(1)
                except Exception:
                    pass

            from transformers import pipeline  # type: ignore[import-untyped]

            ner = pipeline(  # type: ignore[call-overload]
                "ner", model=self._model_id, aggregation_strategy="simple",
            )
            if sys.platform == "win32":
                # The OpenMP race the single-thread cap guards against is a
                # *load-time* crash. Now that weights are loaded, restore
                # parallel inference — otherwise every NER/safety forward in
                # the process runs ~10x slower than it should.
                try:
                    import torch  # type: ignore[import-untyped]

                    torch.set_num_threads(max(1, os.cpu_count() or 1))
                except Exception:
                    pass
            _PIPELINE_CACHE[self._model_id] = ner
            self._available = True
            logger.info("NER pipeline loaded: %s", self._model_id)
            return ner
        except Exception:
            logger.warning(
                "transformers NER backend unavailable for %s", self._model_id,
                exc_info=True,
            )
            return None

    def _ensure_spacy(self) -> Any:
        """Lazy-load spaCy en_core_web_sm."""
        if self._spacy_nlp is not None:
            self._available = True
            return self._spacy_nlp
        try:
            import spacy  # type: ignore[import-untyped]

            self._spacy_nlp = spacy.load("en_core_web_sm")
            self._available = True
            logger.info("spaCy NER backend loaded: en_core_web_sm")
            return self._spacy_nlp
        except Exception:
            self._available = False
            logger.warning(
                "spaCy NER backend unavailable (python -m spacy download "
                "en_core_web_sm) — Stage 3 will be skipped"
            )
            return None

    def unload(self) -> None:
        """Release the backend model from memory."""
        if self._backend == "transformers":
            _PIPELINE_CACHE.pop(self._model_id, None)
        elif self._backend == "gliner" and self._gliner is not None:
            self._gliner.unload()
        self._spacy_nlp = None
        logger.info("NER model unloaded (idle)")

    def tick_idle(self) -> None:
        """Called once per window. Unloads model after idle_limit."""
        loaded = (
            self._spacy_nlp is not None
            or (self._backend == "transformers" and self._model_id in _PIPELINE_CACHE)
        )
        if loaded:
            self._windows_since_use += 1
            if self._windows_since_use >= self._idle_limit:
                self.unload()

    @property
    def is_available(self) -> bool:
        """Return whether a NER backend is available (loads it on first probe)."""
        if self._available is None:
            self._ensure_model()
        return self._available is True

    # -- Extraction ----------------------------------------------------------

    def extract(
        self,
        text: str,
        labels: list[str] | None = None,
        source_window_id: str = "",
        threshold: float = 0.5,
    ) -> list[Fact]:
        """Run NER over *text*. Returns ``[]`` if unavailable — never raises.

        Args:
            text: Source text.
            labels: Zero-shot labels (GLiNER backend only; ignored otherwise).
            source_window_id: Window ID to stamp on extracted facts.
            threshold: Minimum model score for bert/transformers entities.
        """
        model = self._ensure_model()
        if model is None:
            return []

        self._windows_since_use = 0  # Reset idle counter

        if self._backend == "gliner":
            return self._gliner.extract(
                text, labels=labels,
                source_window_id=source_window_id, threshold=threshold,
            )

        try:
            t0 = time.perf_counter()
            if self._backend == "spacy":
                return self._extract_spacy(text, source_window_id)
            return self._extract_transformers(text, source_window_id, threshold)
        except Exception:
            logger.exception("NER extraction failed (%s)", self._backend)
            return []
        finally:
            self._note_latency((time.perf_counter() - t0) * 1000)

    def _note_latency(self, elapsed_ms: float) -> None:
        """Track model-call latency; disable Stage 3 after repeated overruns."""
        if self._backend in ("", "spacy") or elapsed_ms <= self._budget_ms:
            self._strikes = 0
            return
        self._strikes += 1
        if self._strikes >= 3:
            logger.warning(
                "NER backend %s exceeded the %.0fms budget %d times — "
                "disabling Stage 3 for this pipeline (Stages 1-2 stay active)",
                self._backend, self._budget_ms, self._strikes,
            )
            self._available = False

    def _extract_transformers(
        self, text: str, source_window_id: str, threshold: float,
    ) -> list[Fact]:
        """Extract entities from a bert-style NER pipeline result.

        Expects ``aggregation_strategy="simple"`` output:
        ``{"entity_group", "score", "word", "start", "end"}``.
        """
        ner = _PIPELINE_CACHE.get(self._model_id)
        if ner is None:
            return []
        entities = ner(text) or []

        facts: list[Fact] = []
        for ent in entities:
            score = float(ent.get("score", 0.65))
            if score < threshold:
                continue
            raw_label = str(ent.get("entity_group", ent.get("entity", "MISC")))
            start = int(ent.get("start", 0) or 0)
            end = int(ent.get("end", 0) or 0)
            span_text = str(ent.get("word", "")) or text[start:end]
            facts.append(self._make_fact(
                span_text, raw_label, score, start, end, source_window_id,
            ))
        return facts

    def _extract_spacy(self, text: str, source_window_id: str) -> list[Fact]:
        """Extract entities via spaCy ``doc.ents``."""
        if self._spacy_nlp is None:
            return []
        doc = self._spacy_nlp(text)

        facts: list[Fact] = []
        for ent in doc.ents:
            raw_label = str(ent.label_)
            # spaCy exposes no per-entity score — use a mid-band constant so
            # the confidence contract (0.65–0.85) still holds.
            facts.append(self._make_fact(
                str(ent.text), raw_label, 0.75,
                int(ent.start_char), int(ent.end_char), source_window_id,
            ))
        return facts

    def _make_fact(
        self,
        span_text: str,
        raw_label: str,
        score: float,
        start: int,
        end: int,
        source_window_id: str,
    ) -> Fact:
        """Build a Stage 3 Fact with the shared GLiNER-stage contract."""
        if self._backend == "spacy":
            category = _SPACY_LABEL_MAP.get(raw_label.upper(), raw_label.lower())
        else:
            category = _normalise_bert_label(raw_label)
        return Fact(
            text=span_text,
            category=category,
            source_window_id=source_window_id,
            confidence=min(0.85, max(0.65, score)),
            extraction_stage=3,
            metadata={
                "label": raw_label,
                "ner_score": round(score, 4),
                "span": [start, end],
                "ner_backend": self._backend,
                "ner_model": self._model_id,
            },
        )

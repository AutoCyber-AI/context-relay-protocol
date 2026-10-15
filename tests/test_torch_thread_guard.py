# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""U-C1 regression tests — process-global torch.set_num_threads wedge.

Production audit U-C1 (wasa_crp_production_audit): five library call sites
mutated torch's process-global intra-op thread pool — three reset it to
os.cpu_count() (silently undoing any host-configured cap, e.g. WASA
throttling threads under RAM pressure) and one (GLiNER) set it to 1 and
never restored it. These tests assert:

  * every CRP model loader leaves torch.get_num_threads() and os.environ
    exactly as it found them (win32 path mocked),
  * the load-time cap is applied *only* inside the sanctioned helper
    ``crp.ml.torch_threads.single_threaded_load``,
  * a repo-wide grep gate bans any new ``set_num_threads`` call outside
    that single helper module.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from crp.ml.torch_threads import load_thread_cap, single_threaded_load

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_ROOT = REPO_ROOT / "crp"
SANCTIONED_MODULE = LIBRARY_ROOT / "ml" / "torch_threads.py"


class _FakeTorch:
    """Minimal torch stand-in recording thread-pool mutations."""

    def __init__(self, threads: int = 7) -> None:
        self._threads = threads
        self.sets: list[int] = []

    def get_num_threads(self) -> int:
        return self._threads

    def set_num_threads(self, n: int) -> None:
        self.sets.append(n)
        self._threads = n


@pytest.fixture
def fake_torch(monkeypatch: pytest.MonkeyPatch) -> _FakeTorch:
    """Install a recording fake torch and pretend we are on Windows."""
    fake = _FakeTorch()
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("CRP_TORCH_THREADS", raising=False)
    return fake


# ---------------------------------------------------------------------------
# Sanctioned helper unit tests
# ---------------------------------------------------------------------------

def test_helper_caps_to_one_and_restores_prior(fake_torch: _FakeTorch) -> None:
    with single_threaded_load():
        assert fake_torch.get_num_threads() == 1
    assert fake_torch.get_num_threads() == 7
    assert fake_torch.sets == [1, 7]


def test_helper_restores_prior_when_load_raises(fake_torch: _FakeTorch) -> None:
    with pytest.raises(RuntimeError, match="boom"), single_threaded_load():
        raise RuntimeError("boom")
    assert fake_torch.get_num_threads() == 7


def test_helper_noop_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeTorch()
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setattr(sys, "platform", "linux")
    with single_threaded_load():
        pass
    assert fake.sets == []


def test_helper_opt_out_env(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeTorch()
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("CRP_TORCH_THREADS", "off")
    with single_threaded_load():
        pass
    assert fake.sets == []
    assert load_thread_cap() is None


def test_helper_custom_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeTorch()
    monkeypatch.setitem(sys.modules, "torch", fake)
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("CRP_TORCH_THREADS", "3")
    with single_threaded_load():
        assert fake.get_num_threads() == 3
    assert fake.get_num_threads() == 7


def test_helper_invalid_env_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRP_TORCH_THREADS", "banana")
    assert load_thread_cap() == 1


# ---------------------------------------------------------------------------
# Loader integration — torch threads + os.environ identical before/after
# ---------------------------------------------------------------------------

def _snapshot_env() -> dict[str, str]:
    return dict(os.environ)


def _run_ner_transformers_load(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch, *,
    pipeline_raises: bool = False,
) -> Any:
    """Drive NERExtractor._ensure_transformers with faked ML deps."""
    from crp.extraction import stage3_ner

    stage3_ner._PIPELINE_CACHE.clear()
    monkeypatch.setattr(stage3_ner, "_model_cached", lambda _mid: True)

    fake_transformers = types.ModuleType("transformers")

    def _pipeline(*_a: Any, **_k: Any) -> object:
        if pipeline_raises:
            raise RuntimeError("simulated load failure")
        return object()

    fake_transformers.pipeline = _pipeline  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    extractor = stage3_ner.NERExtractor()
    extractor._backend = "transformers"
    extractor._model_id = "fake/model"
    return extractor._ensure_transformers()


def _run_gliner_load(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch, *,
    load_raises: bool = False,
) -> Any:
    """Drive GLiNERExtractor._ensure_model with faked ML deps."""
    from crp.extraction.stage3_gliner import GLiNERExtractor

    monkeypatch.delenv("CRP_GLINER_DISABLED", raising=False)
    monkeypatch.setattr(
        GLiNERExtractor, "_is_model_cached", staticmethod(lambda: True),
    )

    fake_gliner = types.ModuleType("gliner")

    class _FakeGLiNER:
        @staticmethod
        def from_pretrained(_name: str) -> object:
            if load_raises:
                raise RuntimeError("simulated load failure")
            return object()

    fake_gliner.GLiNER = _FakeGLiNER  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gliner", fake_gliner)

    extractor = GLiNERExtractor()
    return extractor._ensure_model()


def _run_decomposer_load(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """Drive decomposer._try_load_sentence_transformer with faked deps."""
    from crp.envelope import decomposer

    monkeypatch.setattr(decomposer, "_ST_AVAILABLE", False)
    monkeypatch.setattr(decomposer, "_EMBED_MODEL", None)

    fake_st = types.ModuleType("sentence_transformers")

    class _FakeSentenceTransformer:
        def __init__(self, *_a: Any, **_k: Any) -> None:
            pass

    fake_st.SentenceTransformer = _FakeSentenceTransformer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    decomposer._try_load_sentence_transformer()


def _run_injection_safety_load(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> Any:
    """Drive security.injection._safety_loader with faked deps."""
    from crp.security import injection

    monkeypatch.delenv("CRP_SAFETY_MODEL", raising=False)
    monkeypatch.setattr(injection, "model_location", lambda _name: "fake/model")

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.pipeline = lambda **_: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    return injection._safety_loader()


@pytest.mark.parametrize(
    "runner",
    [
        _run_ner_transformers_load,
        _run_gliner_load,
        _run_decomposer_load,
        _run_injection_safety_load,
    ],
    ids=["ner_transformers", "gliner", "decomposer", "injection_safety"],
)
def test_loaders_leave_host_state_untouched(
    runner: Any, monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """Each loader must leave torch threads and os.environ exactly as found."""
    env_before = _snapshot_env()
    assert fake_torch.get_num_threads() == 7
    runner(monkeypatch, fake_torch)
    assert fake_torch.get_num_threads() == 7, (
        f"{runner.__name__} mutated the process-global torch thread pool"
    )
    assert os.environ == env_before


@pytest.mark.parametrize(
    "runner,kw",
    [
        (_run_ner_transformers_load, {"pipeline_raises": True}),
        (_run_gliner_load, {"load_raises": True}),
    ],
    ids=["ner_transformers", "gliner"],
)
def test_loaders_restore_threads_on_load_failure(
    runner: Any, kw: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """A failed model load must still restore the prior thread count."""
    assert fake_torch.get_num_threads() == 7
    result = runner(monkeypatch, fake_torch, **kw)
    assert result is None  # both loaders degrade gracefully to None
    assert fake_torch.get_num_threads() == 7


def test_ner_load_caps_during_load_then_restores(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """The load-time OpenMP crash guard must still apply — scoped to the load."""
    _run_ner_transformers_load(monkeypatch, fake_torch)
    assert 1 in fake_torch.sets, "load-time cap of 1 not applied"
    assert fake_torch.sets[-1] == 7, "prior value not restored"


def test_gliner_load_no_longer_leaves_single_thread(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """Regression: GLiNER used to set 1 and NEVER restore (U-C1)."""
    _run_gliner_load(monkeypatch, fake_torch)
    assert fake_torch.sets == [1, 7]


def test_no_reset_to_cpu_count_in_library(
    monkeypatch: pytest.MonkeyPatch, fake_torch: _FakeTorch,
) -> None:
    """cpu_count() must never be pushed into the torch pool by library code."""
    import crp.envelope.decomposer as decomposer_mod
    import crp.security.injection as injection_mod

    # Host caps its pool well below cpu_count() — library must not undo it.
    fake_torch.set_num_threads(2)
    fake_torch.sets.clear()
    monkeypatch.setattr(decomposer_mod, "_ST_AVAILABLE", False)
    monkeypatch.setattr(decomposer_mod, "_EMBED_MODEL", None)
    fake_st = types.ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = lambda *a, **k: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    decomposer_mod._try_load_sentence_transformer()
    assert fake_torch.sets == [], "decomposer reset the host thread cap"
    assert fake_torch.get_num_threads() == 2

    fake_torch.sets.clear()
    monkeypatch.delenv("CRP_SAFETY_MODEL", raising=False)
    monkeypatch.setattr(
        injection_mod, "model_location", lambda _name: "fake/model",
    )
    fake_tf = types.ModuleType("transformers")
    fake_tf.pipeline = lambda **_: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "transformers", fake_tf)
    injection_mod._safety_loader()
    assert fake_torch.sets == [], "injection scanner reset the host thread cap"
    assert fake_torch.get_num_threads() == 2


# ---------------------------------------------------------------------------
# CI grep gate — set_num_threads allowed only in the sanctioned helper
# ---------------------------------------------------------------------------

def test_no_bare_set_num_threads_in_library() -> None:
    """Grep the library tree; any set_num_threads outside the helper fails."""
    offenders: list[str] = []
    for path in sorted(LIBRARY_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT)
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            # strip comments so explanatory text mentioning the API is allowed
            code = line.split("#", 1)[0]
            if "set_num_threads(" in code:
                if path != SANCTIONED_MODULE:
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")
    assert offenders == [], (
        "bare torch.set_num_threads outside crp/ml/torch_threads.py:\n"
        + "\n".join(offenders)
    )

# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Model manifest and downloader for CRPv6 Phase A (ML-first SDK).

The canonical model registry lives in :file:`crp/ml/manifest.json`.  This
module reads that manifest and downloads models from Hugging Face via
``huggingface_hub.snapshot_download`` into ``CRP_MODEL_DIR`` (default
``./crp_models/<local_name>``).  ``huggingface_hub`` is imported lazily
inside the download functions so the zero-dependency core never pays an
import-time cost.

Keys in the manifest match the registry keys used by :mod:`crp.ml.registry`
(e.g. ``crp.isa.intent``), so a downloaded model can be passed to the
registry loaders through the same environment variables
(``CRP_INTENT_MODEL``, ``CRP_SAFETY_MODEL``).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MANIFEST_PATH = Path(__file__).resolve().parent / "manifest.json"


def load_manifest() -> dict[str, Any]:
    """Load the canonical model registry manifest."""
    with open(_MANIFEST_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _default_model_dir() -> str:
    return os.getenv("CRP_MODEL_DIR", "./crp_models")


def _entry(key: str) -> dict[str, Any]:
    models = load_manifest().get("models", {})
    if key not in models:
        raise KeyError(f"unknown model key: {key!r} (known: {sorted(models)})")
    return models[key]


def download_model(key: str, model_dir: str | None = None) -> str:
    """Download the model for ``key`` into ``model_dir``.

    Args:
        key: Manifest key (e.g. ``crp.isa.intent``).
        model_dir: Target root directory.  Defaults to ``$CRP_MODEL_DIR``
            or ``./crp_models``.

    Returns:
        Local path of the downloaded snapshot.
    """
    from huggingface_hub import snapshot_download

    entry = _entry(key)
    target = Path(model_dir or _default_model_dir()) / entry["local_name"]
    path = snapshot_download(
        repo_id=entry["repo_id"],
        revision=entry["revision"],
        local_dir=str(target),
    )
    logger.info("Downloaded %s -> %s", key, path)
    return str(path)


def download_all(model_dir: str | None = None) -> dict[str, str]:
    """Download every model in the manifest.  Returns ``{key: local_path}``."""
    return {key: download_model(key, model_dir) for key in load_manifest().get("models", {})}


def model_location(key: str, model_dir: str | None = None) -> str:
    """Return the local snapshot path for ``key`` if present, else the HF repo id.

    Lets callers pass the result straight to ``from_pretrained``-style loaders:
    a local directory when the model has been downloaded, the hub repo id
    otherwise.
    """
    entry = _entry(key)
    target = Path(model_dir or _default_model_dir()) / entry["local_name"]
    if target.is_dir() and any(target.iterdir()):
        return str(target)
    return entry["repo_id"]

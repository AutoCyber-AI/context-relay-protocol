# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Managed ML model registry for optional-but-default-on CRP components."""

from __future__ import annotations

from crp.ml.downloader import (
    download_all,
    download_model,
    load_manifest,
    model_location,
)
from crp.ml.registry import (
    MANAGER,
    ModelLoadError,
    ModelManager,
    managed_call,
    register_model,
    timed_fallback,
)

__all__ = [
    "MANAGER",
    "ModelLoadError",
    "ModelManager",
    "download_all",
    "download_model",
    "load_manifest",
    "managed_call",
    "model_location",
    "register_model",
    "timed_fallback",
]

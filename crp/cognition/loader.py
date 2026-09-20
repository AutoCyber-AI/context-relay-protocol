# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Load cognitive presets from YAML, JSON, Python dicts, or the built-in library."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from crp.cognition.preset import CognitivePreset

_BUILTINS_DIR = Path(__file__).parent / "presets"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML if PyYAML is available; otherwise raise a clear error."""
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError(
            "Loading YAML presets requires PyYAML. Install with: pip install pyyaml"
        ) from exc
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_preset(source: str | Path | dict[str, Any]) -> CognitivePreset:
    """Load a preset from a file path or a dict.

    Args:
        source: Path to a YAML/JSON file, or a dict with the preset schema.

    Returns:
        A :class:`CognitivePreset` instance.
    """
    if isinstance(source, dict):
        return CognitivePreset.from_dict(source)

    path = Path(source)
    if not path.exists():
        # Try built-in presets next.
        builtin = _BUILTINS_DIR / path.name
        if builtin.exists():
            path = builtin
        else:
            raise FileNotFoundError(f"Preset not found: {source}")

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        data = _load_yaml(path)
    elif path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        # Try JSON first, then YAML.
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = _load_yaml(path)

    return CognitivePreset.from_dict(data)


def list_builtin_presets() -> list[dict[str, str]]:
    """Return metadata for all built-in presets."""
    presets: list[dict[str, str]] = []
    if not _BUILTINS_DIR.exists():
        return presets
    for path in sorted(_BUILTINS_DIR.iterdir()):
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        try:
            preset = load_preset(path)
            presets.append({
                "id": preset.id or path.stem,
                "name": preset.name or path.stem,
                "description": preset.description,
                "path": str(path),
            })
        except Exception:  # pragma: no cover - defensive
            continue
    return presets


def resolve_preset_id(preset_id: str) -> CognitivePreset:
    """Load a built-in preset by id, or by file path if it exists."""
    if os.path.exists(preset_id):
        return load_preset(preset_id)
    builtin = _BUILTINS_DIR / f"{preset_id}.yaml"
    if builtin.exists():
        return load_preset(builtin)
    builtin_json = _BUILTINS_DIR / f"{preset_id}.json"
    if builtin_json.exists():
        return load_preset(builtin_json)
    raise FileNotFoundError(f"Built-in preset not found: {preset_id}")

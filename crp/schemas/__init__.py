# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""JSON Schema loader for CRP data contracts."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON Schema by name (without .json extension).

    >>> schema = load_schema("task-intent")
    >>> schema["type"]
    'object'
    """
    ref = resources.files("crp.schemas").joinpath(f"{name}.json")
    return json.loads(ref.read_text(encoding="utf-8"))  # type: ignore[arg-type]

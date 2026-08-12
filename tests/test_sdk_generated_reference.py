# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Smoke tests for the generated full-module API reference and dynamic accessors."""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

import pytest

import crp


ROOT = Path(__file__).resolve().parent.parent
MODULES_DIR = ROOT / "site-docs" / "api" / "modules"


def _walk_modules():
    for _, modname, _ in pkgutil.walk_packages(crp.__path__, crp.__name__ + "."):
        if modname == "crp.__main__":
            continue
        parts = modname.split(".")
        if parts[1] in {"_typing", "_version"}:
            continue
        # Match scripts/generate_api_reference.py: skip private submodules.
        if any(p.startswith("_") for p in parts[1:]):
            continue
        yield modname


@pytest.mark.parametrize("modname", sorted({m.split(".")[1] for m in _walk_modules()}))
def test_modules_page_exists(modname: str):
    """Every top-level crp subpackage has a generated API reference page."""
    page = MODULES_DIR / f"{modname}.md"
    assert page.exists(), f"Missing generated API page for crp.{modname}"


@pytest.mark.parametrize("modname", sorted(_walk_modules()))
def test_modules_accessor_reaches_module(modname: str):
    """client.modules.<module> resolves to an importable object."""
    client = crp.SDKClient()
    parts = modname.split(".")[1:]  # drop 'crp'
    proxy = client.modules
    for part in parts:
        proxy = getattr(proxy, part)
    assert proxy is not None


def test_index_page_exists():
    assert (MODULES_DIR / "index.md").exists()


def test_generation_script_check_passes():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "scripts/generate_api_reference.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr

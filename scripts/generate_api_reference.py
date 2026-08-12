#!/usr/bin/env python3
# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 - see LICENSE.md for details.
"""Generate auto-generated API reference pages for every public ``crp.*`` module.

Run directly to regenerate pages::

    python scripts/generate_api_reference.py

Run with ``--check`` in CI to ensure the generated pages are up to date::

    python scripts/generate_api_reference.py --check
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import pkgutil
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "site-docs" / "api" / "modules"
MKDOCS_YML = ROOT / "mkdocs.yml"
PACKAGE = "crp"

# Modules/packages that are internal-only or not useful in public API docs.
SKIP_MODULES = {
    "crp.__main__",
    "crp._typing",
    "crp._version",
}


def _has_public_members(module) -> bool:
    """Return True if a module exposes any public class or function."""
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if inspect.isclass(obj) or inspect.isfunction(obj):
            return True
    return False


def _walk_modules() -> dict[str, list[str]]:
    """Return a mapping {subpackage: [modules...]} for crp.*."""
    import crp  # noqa: F401

    modules_by_pkg: dict[str, list[str]] = {}
    for importer, modname, ispkg in pkgutil.walk_packages(
        sys.modules[PACKAGE].__path__, PACKAGE + "."
    ):
        if modname in SKIP_MODULES:
            continue
        parts = modname.split(".")
        top = parts[1]
        if top in {"__main__", "_typing", "_version"}:
            continue
        # Skip private submodules (any part starting with _, except the crp prefix).
        if any(p.startswith("_") for p in parts[1:]):
            continue
        modules_by_pkg.setdefault(top, []).append(modname)
    for top in modules_by_pkg:
        modules_by_pkg[top].sort()
    return modules_by_pkg


def _page_content(top: str, modules: list[str]) -> str:
    """Build the Markdown content for one subpackage page."""
    lines = [
        f"# crp.{top}",
        "",
        f"Auto-generated reference for the ``crp.{top}`` subpackage.",
        "",
    ]
    for modname in modules:
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        if not _has_public_members(mod):
            continue
        display = modname.replace("crp.", "")
        lines.extend(
            [
                f"## `{display}`",
                "",
                f"::: {modname}",
                "    options:",
                "      show_source: false",
                "      filters:",
                '        - "!^_"',
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _generate_pages(check: bool = False) -> list[Path]:
    """Generate or check all module reference pages."""
    modules_by_pkg = _walk_modules()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    changed: list[Path] = []

    for top, modules in sorted(modules_by_pkg.items()):
        content = _page_content(top, modules)
        page_path = DOCS_DIR / f"{top}.md"
        if check:
            existing = page_path.read_text(encoding="utf-8") if page_path.exists() else ""
            if existing != content:
                changed.append(page_path)
        else:
            page_path.write_text(content, encoding="utf-8")
            changed.append(page_path)

    # Remove stale pages.
    expected = {f"{top}.md" for top in modules_by_pkg}
    expected.add("index.md")
    for stale in DOCS_DIR.glob("*.md"):
        if stale.name not in expected:
            if check:
                changed.append(stale)
            else:
                stale.unlink()

    return changed


def _build_nav_block() -> str:
    """Build the YAML text block for the Full Module Reference nav group."""
    modules_by_pkg = _walk_modules()
    lines = ["    - Full Module Reference:", "      - Overview: api/modules/index.md"]
    for top in sorted(modules_by_pkg.keys()):
        label = top.replace("_", " ").title()
        lines.append(f"      - {label}: api/modules/{top}.md")
    return "\n".join(lines) + "\n"


def _update_nav(check: bool = False) -> bool:
    """Update or check the API Reference nav in mkdocs.yml via text edits."""
    text = MKDOCS_YML.read_text(encoding="utf-8")

    header = "  - API Reference:\n"
    start = text.find(header)
    if start == -1:
        raise RuntimeError("Could not find 'API Reference' section in mkdocs.yml")

    body_start = start + len(header)
    # The API Reference section ends where the next top-level nav entry begins.
    next_match = re.search(r"^  - \S", text[body_start:], re.MULTILINE)
    if next_match:
        body_end = body_start + next_match.start()
        after = text[body_end:]
    else:
        body_end = len(text)
        after = ""

    body = text[body_start:body_end]
    desired_block = _build_nav_block()

    # Check whether the Full Module Reference block already exists.
    existing_match = re.search(
        r"^    - Full Module Reference:\n(?:      .+\n)+", body, re.MULTILINE
    )

    if check:
        if existing_match is None:
            return False
        return existing_match.group(0).strip() == desired_block.strip()

    if existing_match is not None:
        new_body = body[: existing_match.start()] + desired_block + body[existing_match.end() :]
    else:
        new_body = body + desired_block

    new_text = text[:body_start] + new_body + after
    MKDOCS_YML.write_text(new_text, encoding="utf-8")
    return True


def _generate_index() -> None:
    """Create the overview page for the full module reference."""
    modules_by_pkg = _walk_modules()
    total_modules = sum(len(v) for v in modules_by_pkg.values())
    lines = [
        "# Full Module Reference",
        "",
        "This section auto-documents every public ``crp.*`` module using mkdocstrings.",
        "It is generated by ``scripts/generate_api_reference.py``.",
        "",
        f"- **Top-level subpackages:** {len(modules_by_pkg)}",
        f"- **Modules documented:** {total_modules}",
        "",
        "Use the curated SDK namespaces (``client.safety``, ``client.ckf``, etc.) for",
        "common tasks, and fall back to ``client.modules.<module>`` or",
        "``client.orchestrator`` for anything else.",
        "",
        "## Subpackages",
        "",
    ]
    for top in sorted(modules_by_pkg):
        lines.append(f"- [`crp.{top}`]({top}.md)")
    lines.append("")
    (DOCS_DIR / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CRP API reference pages")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if generated pages/nav are out of sync.",
    )
    args = parser.parse_args()

    changed = _generate_pages(check=args.check)
    nav_ok = _update_nav(check=args.check)

    if args.check:
        if changed or not nav_ok:
            print("API reference is out of sync. Run:")
            print("    python scripts/generate_api_reference.py")
            return 1
        print("API reference is up to date.")
        return 0

    _generate_index()
    print(f"Generated {len(changed)} API reference pages under {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

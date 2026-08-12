#!/usr/bin/env python3
"""Audit the public site-docs tree for breaks, formatting issues, and leaks.

Run from repo root:
    .venv/Scripts/python scripts/audit_docs.py

The script returns a non-zero exit code if any ERROR-level findings exist.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

DOCS_DIR = Path("site-docs")
ERROR_CATS = {"unclosed_fence", "html_imbalance", "table_cols", "dead_ref", "confidential"}


def collect_files() -> list[Path]:
    return sorted(DOCS_DIR.rglob("*.md"))


def strip_code_fences(lines: list[str]) -> list[tuple[int, str]]:
    """Return (line_no, line) tuples that are outside code fences."""
    result = []
    in_fence = False
    fence_pat = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(\S+)?\s*$")
    fence_marker: str | None = None
    for i, line in enumerate(lines, 1):
        m = fence_pat.match(line)
        if m:
            marker = m.group(2)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker.startswith(fence_marker[0]) and len(marker) >= len(fence_marker):
                in_fence = False
                fence_marker = None
            continue
        if not in_fence:
            result.append((i, line))
    return result


def check_fences(path: Path, lines: list[str], findings: list[tuple[str, str]]) -> None:
    stack: list[tuple[str, int]] = []
    fence_pat = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
    for i, line in enumerate(lines, 1):
        m = fence_pat.match(line)
        if not m:
            continue
        marker = m.group(2)
        if stack and stack[-1][0] == marker[: len(stack[-1][0])]:
            stack.pop()
        else:
            stack.append((marker, i))
    for _, i in stack:
        findings.append(("unclosed_fence", f"Unclosed code fence starting at line {i}"))


def check_html_balance(path: Path, text: str, findings: list[tuple[str, str]]) -> None:
    for tag in ("div", "details"):
        opens = len(re.findall(rf"<{tag}\b", text, re.I))
        closes = len(re.findall(rf"</{tag}\s*>", text, re.I))
        if opens != closes:
            findings.append(
                ("html_imbalance", f"<{tag}> open={opens} != close={closes}")
            )


def check_tables(path: Path, lines: list[str], findings: list[tuple[str, str]]) -> None:
    outside = strip_code_fences(lines)
    table_rows: list[tuple[int, str]] = []
    for i, line in outside:
        if line.strip().startswith("|"):
            table_rows.append((i, line))
        else:
            if table_rows:
                _validate_table(path, table_rows, findings)
                table_rows = []
    if table_rows:
        _validate_table(path, table_rows, findings)


def _validate_table(
    path: Path, rows: list[tuple[int, str]], findings: list[tuple[str, str]]
) -> None:
    counts: list[tuple[int, int]] = []
    for i, line in rows:
        if re.match(r"^\s*\|[-:|\s|]*\|\s*$", line):
            continue
        parts = [p for p in line.split("|")]
        if parts and not parts[0].strip():
            parts = parts[1:]
        if parts and not parts[-1].strip():
            parts = parts[:-1]
        counts.append((i, len(parts)))
    if len({c for _, c in counts}) > 1:
        findings.append(("table_cols", f"Inconsistent table columns: {dict(counts)}"))


def check_admonitions(path: Path, lines: list[str], findings: list[tuple[str, str]]) -> None:
    adm_pat = re.compile(r"^!!!\s+([a-zA-Z0-9_-]+)(?:\s+\"([^\"]*)\")?\s*$")
    for i, line in enumerate(lines, 1):
        if not line.startswith("!!!"):
            continue
        if not adm_pat.match(line):
            findings.append(("malformed_admonition", f"Malformed admonition at line {i}"))
            continue
        # Check that the next non-empty line after the header is indented 4 spaces.
        j = i + 1
        while j <= len(lines) and not lines[j - 1].strip():
            j += 1
        if j <= len(lines):
            next_line = lines[j - 1]
            if next_line.strip() and not next_line.startswith("    "):
                findings.append(
                    ("malformed_admonition", f"Admonition body not indented at line {j}")
                )


def check_dead_refs(path: Path, text: str, findings: list[tuple[str, str]]) -> None:
    removed = ("comply-autocyber.md", "RAILWAY_VARIABLES_GATEWAY_COMPLY.md")
    for ref in removed:
        if ref in text:
            findings.append(("dead_ref", f"References removed file {ref}"))


def check_confidential(path: Path, text: str, findings: list[tuple[str, str]]) -> None:
    if "withheld from public publication" in text:
        return
    if re.search(r"\bCONFIDENTIAL\b", text) or "Internal Strategy Document" in text:
        findings.append(
            ("confidential", "Document still contains CONFIDENTIAL or Internal Strategy markers")
        )


def check_inline_styles(path: Path, text: str, findings: list[tuple[str, str]]) -> None:
    count = len(re.findall(r"\sstyle=", text, re.I))
    if count > 10:
        findings.append(("inline_style", f"{count} inline style attributes"))


def check_managed_status(path: Path, text: str, findings: list[tuple[str, str]]) -> None:
    # Flag outdated claims for live products only.
    live_products = ("gateway.crprotocol.io", "comply.crprotocol.io")
    for product in live_products:
        if re.search(rf"{re.escape(product)}.*coming soon", text, re.I):
            findings.append(
                ("managed_status", f"Live endpoint {product} still marked 'coming soon'")
            )


def run_mkdocs() -> bool:
    env = os.environ.copy()
    env["DISABLE_MKDOCS_2_WARNING"] = "true"
    try:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )
        return True
    except subprocess.CalledProcessError as exc:
        print("MKDOCS BUILD FAILED:\n", exc.stdout)
        return False


def main() -> int:
    print("Running mkdocs build --strict ...")
    if not run_mkdocs():
        return 1

    files = collect_files()
    all_findings: dict[Path, list[tuple[str, str]]] = defaultdict(list)

    for path in files:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        findings: list[tuple[str, str]] = []

        check_fences(path, lines, findings)
        check_html_balance(path, text, findings)
        check_tables(path, lines, findings)
        check_admonitions(path, lines, findings)
        check_dead_refs(path, text, findings)
        check_confidential(path, text, findings)
        check_inline_styles(path, text, findings)
        check_managed_status(path, text, findings)

        if findings:
            all_findings[path] = findings

    if not all_findings:
        print("\nNo audit findings. Site docs look clean.")
        return 0

    errors = 0
    warnings = 0
    print("\nAUDIT FINDINGS\n" + "=" * 60)
    for path, findings in sorted(all_findings.items()):
        print(f"\n{path}")
        for cat, msg in findings:
            level = "ERROR" if cat in ERROR_CATS else "WARN"
            print(f"  [{level}:{cat}] {msg}")
            if level == "ERROR":
                errors += 1
            else:
                warnings += 1

    print("\n" + "=" * 60)
    print(f"Total: {errors} errors, {warnings} warnings across {len(all_findings)} files")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

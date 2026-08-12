#!/usr/bin/env python3
"""Insert concise Google-style docstrings into public CRP symbols.

This is a mechanical first pass. It targets methods and properties that are
missing docstrings and generates summaries from naming conventions plus
``Args``/``Returns`` sections from type annotations.

Run directly to rewrite files in place::

    python scripts/auto_docstrings.py

Run with ``--check`` to report how many symbols would be changed without
writing anything::

    python scripts/auto_docstrings.py --check
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = ROOT / "crp"


# ── Language helpers ─────────────────────────────────────────────────────────


_RE_CAMEL = re.compile(r"([a-z0-9])([A-Z])")


def _snake_to_words(name: str) -> str:
    words = name.replace("_", " ")
    # Expand a few common abbreviations for nicer summaries.
    words = words.replace("id ", "identifier ").replace(" id", " identifier")
    words = words.replace("ids ", "identifiers ")
    words = words.replace("json ", "JSON ").replace(" json", " JSON")
    words = words.replace("jsonl", "JSON Lines")
    words = words.replace("llm", "LLM")
    words = words.replace("url", "URL")
    words = words.replace("http", "HTTP")
    words = words.replace("hmac", "HMAC")
    words = words.replace("pii", "PII")
    words = words.replace("ckf", "CKF")
    words = words.replace("cso", "CSO")
    words = words.replace("crp", "CRP")
    words = words.replace(" rbac", " RBAC")
    return words


def _describe(name: str, is_property: bool = False) -> str:
    """Return a one-line summary for a method or property based on its name."""
    words = _snake_to_words(name)

    if name == "__init__":
        return "Initialise the instance."
    if name == "__call__":
        return "Call the object and return the result."

    # Common verbs
    if name.startswith("to_"):
        target = _snake_to_words(name[3:])
        if name == "to_dict":
            return "Return a dictionary representation of this object."
        if name == "to_json":
            return "Return a JSON serialisation of this object."
        if name == "to_json_obj":
            return "Return a JSON-compatible object representation."
        if name == "to_body":
            return "Return the response body representation."
        return f"Return the {target} representation."

    if name.startswith("from_"):
        source = _snake_to_words(name[5:])
        if name == "from_dict":
            return "Create a new instance from a dictionary."
        if name == "from_json":
            return "Create a new instance from a JSON string or object."
        if name == "from_jsonl":
            return "Create a new instance from a JSON Lines record."
        if name == "from_json_obj":
            return "Create a new instance from a JSON-compatible object."
        return f"Create a new instance from {source}."

    if name.startswith("is_"):
        rest = _snake_to_words(name[3:])
        return f"Return whether this object is {rest}."

    if name.startswith("has_"):
        rest = _snake_to_words(name[4:])
        return f"Return whether this object has {rest}."

    if name.startswith("should_") or name.startswith("can_"):
        rest = _snake_to_words(name[7:] if name.startswith("should_") else name[4:])
        return f"Return whether this object should {rest}."

    if name.startswith("get_"):
        rest = _snake_to_words(name[4:])
        return f"Return the {rest}."

    if name.startswith("set_"):
        rest = _snake_to_words(name[4:])
        return f"Set the {rest}."

    if name.startswith("update_"):
        rest = _snake_to_words(name[7:])
        return f"Update the {rest} and return the updated value."

    if name.startswith("add_"):
        rest = _snake_to_words(name[4:])
        return f"Add {rest} and return the created entry."

    if name.startswith("remove_"):
        rest = _snake_to_words(name[7:])
        return f"Remove {rest} and return whether it existed."

    if name.startswith("record_"):
        rest = _snake_to_words(name[7:])
        return f"Record a {rest} event and return the updated log."

    if name.startswith("register_"):
        rest = _snake_to_words(name[9:])
        return f"Register {rest}."

    if name.startswith("run_"):
        rest = _snake_to_words(name[4:])
        return f"Run {rest}."

    if name == "dispatch":
        return "Dispatch the request and return the result."

    if name == "emit":
        return "Emit the audit/event record."

    if name == "find":
        return "Find and return matching items."

    if name == "clear":
        return "Clear all stored entries."

    if name in {"close", "flush"}:
        return f"{name.capitalize()} the underlying resource."

    if name in {"read", "write", "readline", "readlines", "writelines"}:
        return f"{name.capitalize()} data from/to the stream."

    if name in {"seek", "tell", "truncate", "fileno", "isatty", "readable", "writable", "seekable"}:
        return f"{name.capitalize()} the stream."

    if name.endswith("_count") or name.endswith("_size") or name in {
        "size", "count", "entry_count", "fact_count", "window_count",
        "node_count", "edge_count", "pattern_count", "trace_count",
        "evolution_count", "passage_count", "listener_count", "cache_size",
        "activity_count", "file_count", "function_count", "term_count",
        "snapshot_count", "active_count", "tracked_count",
    }:
        noun = _snake_to_words(name.replace("_count", "").replace("_size", ""))
        return f"Return the current {noun} count."

    if name.endswith("_ratio") or name.endswith("_pct"):
        metric = _snake_to_words(name)
        return f"Return the {metric}."

    if name in {"ok", "passed", "all_passed", "success", "is_complete", "is_available",
                "is_running", "is_expired", "is_fresh", "is_loaded", "is_superseded",
                "is_tombstoned", "is_coherent", "has_critical", "has_issues", "has_flags",
                "has_pii", "has_violations", "has_embedding", "has_permission", "not_modified",
                "failed_dependency", "halted", "amplified", "should_auto_continue",
                "triggers_redispatch", "any_reachable"}:
        return f"Return whether the {words} condition holds."

    if name in {"headers", "http_status", "summary", "payload", "message", "body",
                "signing_payload", "to_body", "to_dict", "to_json", "to_json_obj"}:
        return f"Return the {words}."

    if is_property:
        return f"Return the {words}."

    return f"Execute {words} and return the result."


def _annotation_text(node: ast.arg) -> str:
    if node.annotation is None:
        return ""
    return ast.unparse(node.annotation)


def _return_text(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if func.returns is None:
        return "The result."
    return f"``{ast.unparse(func.returns)}``."


def _make_docstring(func: ast.FunctionDef | ast.AsyncFunctionDef, is_property: bool = False) -> str:
    summary = _describe(func.name, is_property=is_property)
    if is_property:
        return f'"""{summary}"""\n'

    args = []
    for arg in func.args.args:
        if arg.arg in {"self", "cls"}:
            continue
        ann = _annotation_text(arg)
        desc = f"The {_snake_to_words(arg.arg)} value."
        if ann:
            args.append(f"        {arg.arg} ({ann}): {desc}")
        else:
            args.append(f"        {arg.arg}: {desc}")
    for arg in func.args.kwonlyargs:
        ann = _annotation_text(arg)
        desc = f"The {_snake_to_words(arg.arg)} value."
        if ann:
            args.append(f"        {arg.arg} ({ann}): {desc}")
        else:
            args.append(f"        {arg.arg}: {desc}")
    if func.args.vararg:
        args.append(f"        *{func.args.vararg.arg}: Variable positional arguments.")
    if func.args.kwarg:
        args.append(f"        **{func.args.kwarg.arg}: Variable keyword arguments.")

    lines = [f'"""{summary}']
    if args:
        lines.append("")
        lines.append("    Args:")
        lines.extend(args)
    lines.append("")
    lines.append("    Returns:")
    lines.append(f"        {_return_text(func)}")
    lines.append('"""\n')
    return "\n".join(lines)


# ── AST traversal ────────────────────────────────────────────────────────────


def _has_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> bool:
    if not node.body:
        return False
    first = node.body[0]
    return isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)


def _is_property_getter(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Name) and dec.id == "property":
            return True
        if isinstance(dec, ast.Attribute) and dec.attr == "property":
            return True
    return False


def _is_property_setter_or_deleter(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for dec in node.decorator_list:
        if isinstance(dec, ast.Attribute) and dec.attr in {"setter", "deleter"}:
            return True
    return False


class _Finder(ast.NodeVisitor):
    def __init__(self) -> None:
        self.targets: list[tuple[int, int, str, bool, ast.FunctionDef | ast.AsyncFunctionDef]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._maybe_add(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._maybe_add(node)
        self.generic_visit(node)

    def _maybe_add(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name.startswith("_"):
            return
        if _has_docstring(node):
            return
        if _is_property_setter_or_deleter(node):
            return
        is_property = _is_property_getter(node)
        self.targets.append((node.lineno, node.col_offset, node.name, is_property, node))


def _find_colon_line(lines: list[str], start_idx: int) -> int:
    """Return the index of the line that ends the function/class header."""
    for i in range(start_idx, len(lines)):
        stripped = lines[i].split("#")[0].rstrip()
        if stripped.endswith(":"):
            return i
    return start_idx


def _insert_docstring(path: Path, targets: list[tuple[int, int, str, bool, ast.FunctionDef | ast.AsyncFunctionDef]]) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    changed = False
    # Process targets in reverse order so line numbers stay valid.
    for lineno, col_offset, _name, is_property, node in reversed(targets):
        idx = lineno - 1
        colon_idx = _find_colon_line(lines, idx)
        indent = " " * (col_offset + 4)
        doc = _make_docstring(node, is_property=is_property)
        doc_lines = [indent + line for line in doc.splitlines(keepends=True)]
        insert_idx = colon_idx + 1
        lines.insert(insert_idx, "".join(doc_lines))
        changed = True
    if changed:
        path.write_text("".join(lines), encoding="utf-8")
    return changed


def _process_file(path: Path, check: bool = False) -> int:
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        print(f"  SKIP (syntax error): {path.relative_to(ROOT)}", file=sys.stderr)
        return 0

    finder = _Finder()
    finder.visit(tree)
    if not finder.targets:
        return 0

    print(
        f"{'WOULD UPDATE' if check else 'UPDATING'} {path.relative_to(ROOT)} "
        f"({len(finder.targets)} symbols)"
    )
    if check:
        return len(finder.targets)
    return int(_insert_docstring(path, finder.targets))


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-insert CRP docstrings")
    parser.add_argument("--check", action="store_true", help="Report only, do not write")
    args = parser.parse_args()

    total = 0
    for py_path in sorted(PACKAGE_DIR.rglob("*.py")):
        if py_path.name.startswith("_"):
            continue
        if py_path.name == "__init__.py":
            # Skip __init__ re-exports to avoid duplicating docstrings on aliases.
            continue
        total += _process_file(py_path, check=args.check)

    action = "would be" if args.check else "were"
    print(f"\n{total} symbols {action} documented.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

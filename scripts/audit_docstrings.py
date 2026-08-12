#!/usr/bin/env python3
"""Audit public API symbols in ``crp`` for missing docstrings."""
from __future__ import annotations

import importlib
import inspect
import pkgutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "crp"

SKIP_MODULES = {
    "crp.__main__",
    "crp._typing",
    "crp._version",
}

# Standard-library/third-party types that are frequently re-exported and not ours.
SKIP_CLASSES = {
    "Callable",
    "Iterable",
    "Iterator",
    "Generator",
    "BaseHTTPMiddleware",
    "Response",
    "Request",
    "BaseHTTPRequestHandler",
    "ThreadPoolExecutor",
}


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _walk_modules():
    import crp  # noqa: F401

    for _importer, modname, _ispkg in pkgutil.walk_packages(
        sys.modules[PACKAGE].__path__, PACKAGE + "."
    ):
        if modname in SKIP_MODULES:
            continue
        if any(p.startswith("_") for p in modname.split(".")[1:]):
            continue
        try:
            mod = importlib.import_module(modname)
        except Exception:
            continue
        yield modname, mod


def _missing(obj):
    doc = inspect.getdoc(obj)
    return not doc or not doc.strip()


def _source_loc(obj):
    try:
        return (obj.__module__, obj.__qualname__)
    except AttributeError:
        return None


def main():
    missing_modules = []
    missing_classes = []
    missing_functions = []
    missing_methods = []
    seen_class_defs = set()
    seen_method_defs = set()
    seen_func_defs = set()

    for modname, mod in _walk_modules():
        if _missing(mod):
            missing_modules.append(modname)
            continue
        for name in dir(mod):
            if not _is_public(name):
                continue
            try:
                obj = getattr(mod, name)
            except Exception:
                continue
            if inspect.isclass(obj):
                if name in SKIP_CLASSES:
                    continue
                if _missing(obj):
                    loc = _source_loc(obj)
                    if loc and loc not in seen_class_defs:
                        seen_class_defs.add(loc)
                        missing_classes.append(f"{loc[0]}.{loc[1]}")
                    continue
                # methods / properties / descriptors
                for mname, member in inspect.getmembers(obj):
                    if not _is_public(mname):
                        continue
                    if inspect.isfunction(member) or inspect.ismethod(member):
                        if _missing(member):
                            loc = _source_loc(member)
                            if loc and loc not in seen_method_defs:
                                seen_method_defs.add(loc)
                                missing_methods.append(f"{loc[0]}.{loc[1]}")
                    elif isinstance(member, property):
                        if _missing(member):
                            loc = _source_loc(member.fget) if member.fget else None
                            if loc and loc not in seen_method_defs:
                                seen_method_defs.add(loc)
                                missing_methods.append(f"{loc[0]}.{loc[1]} (property)")
            elif inspect.isfunction(obj):
                if _missing(obj):
                    loc = _source_loc(obj)
                    if loc and loc not in seen_func_defs:
                        seen_func_defs.add(loc)
                        missing_functions.append(f"{loc[0]}.{loc[1]}")

    total = (
        len(missing_modules)
        + len(missing_classes)
        + len(missing_functions)
        + len(missing_methods)
    )

    by_file = defaultdict(list)
    for item in missing_classes + missing_functions + missing_methods:
        file_name = item.split(":", 1)[0] if ":" in item else item.rsplit(".", 1)[0]
        by_file[file_name].append(item)

    print(f"Missing docstrings: {total}")
    print(f"  Modules: {len(missing_modules)}")
    print(f"  Unique classes: {len(missing_classes)}")
    print(f"  Unique functions: {len(missing_functions)}")
    print(f"  Unique methods/properties: {len(missing_methods)}")

    if missing_modules:
        print(f"\nModules ({len(missing_modules)}):")
        for m in missing_modules:
            print(f"  - {m}")

    print(f"\nBy source file ({len(by_file)} files):")
    for file_name in sorted(by_file.keys()):
        items = by_file[file_name]
        print(f"\n{file_name}: {len(items)}")
        for item in items[:10]:
            print(f"  - {item}")
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more")

    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())

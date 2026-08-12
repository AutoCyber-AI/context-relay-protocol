# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 - see LICENSE.md for details.
"""Build hooks for the CRP documentation site.

Griffe emits docstring-indentation warnings for a small number of existing
source files (notably ``crp/providers/base.py``). These warnings are not
mkdocstrings "missing symbol" or "import" errors, and they abort ``--strict``
builds. This hook suppresses those specific formatting warnings so the
auto-generated API reference can be built without editing Python source.
"""
from __future__ import annotations

import re

from griffe._internal.docstrings import google as _griffe_google
from griffe._internal.docstrings import numpy as _griffe_numpy
from griffe._internal.docstrings import utils as _griffe_docstring_utils


_original_docstring_warning = _griffe_docstring_utils.docstring_warning


def on_post_page(output: str, page, config) -> str:  # noqa: D401
    """Strip em dashes from rendered HTML."""
    pattern = re.compile(r"(<(?:pre|code)[^>]*>.*?</(?:pre|code)>)", re.S | re.I)
    parts = pattern.split(output)
    for i, part in enumerate(parts):
        if part.lower().startswith(("<pre", "<code")):
            parts[i] = part.replace("\u2014", "-").replace("&mdash;", "-")
        else:
            parts[i] = re.sub(r"\s*\u2014\s*", " - ", part).replace("&mdash;", " - ")
    return "".join(parts)


def _silenced_docstring_warning(docstring, offset, message, log_level=None, **kwargs):
    """Drop griffe docstring-indentation warnings; forward everything else."""
    if message and "Confusing indentation for continuation line" in str(message):
        return
    _original_docstring_warning(docstring, offset, message, log_level, **kwargs)


# Patch all modules that hold a direct reference to the warning function.
_griffe_docstring_utils.docstring_warning = _silenced_docstring_warning
_griffe_google.docstring_warning = _silenced_docstring_warning
_griffe_numpy.docstring_warning = _silenced_docstring_warning

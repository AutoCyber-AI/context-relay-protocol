# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Grammar-constrained decoding at the Gateway (CRP-SPEC-054 §4 mechanism).

The default structured-output path validates model output against a JSON
Schema and repairs on mismatch (``crp.gateway.structured_decoder``). When the
provider advertises constrained-decoding support, the Gateway instead passes
the schema *down* so tool-call arguments are valid by construction:

  - OpenAI-compatible cloud providers: ``response_format`` with a strict
    ``json_schema`` payload.
  - llama.cpp servers: a GBNF ``grammar`` field compiled from the schema.

Support is detected strictly from the resolved :class:`ProviderConfig`
(``constrained_decoding``). Anything else — unknown provider, compile error,
missing config — degrades gracefully to the validate+repair path with
identical external behaviour.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("crp.gateway.constrained")

MODE_JSON_SCHEMA = "json_schema"
MODE_GBNF = "gbnf"
_VALID_MODES = frozenset({MODE_JSON_SCHEMA, MODE_GBNF})


def detect_constrained_mode(config: Any) -> str | None:
    """Return the constrained-decoding mode for ``config``, or ``None``.

    Detection is strict: only an explicit, recognised
    ``ProviderConfig.constrained_decoding`` value enables the grammar path.
    """
    mode = getattr(config, "constrained_decoding", None)
    return mode if mode in _VALID_MODES else None


def build_response_format(
    schema: dict[str, Any],
    *,
    name: str = "crp_structured_output",
) -> dict[str, Any]:
    """Build an OpenAI strict ``json_schema`` response_format payload."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
            "strict": True,
        },
    }


def attach_constraints(request: Any, schema: dict[str, Any], config: Any) -> bool:
    """Attach grammar constraints to an outbound ``ChatRequest``.

    Returns ``True`` when constraints were attached (output valid by
    construction), ``False`` when the caller must use validate+repair.
    Never raises: any failure degrades to the repair path.
    """
    mode = detect_constrained_mode(config)
    if mode == MODE_JSON_SCHEMA:
        request.response_format = build_response_format(schema)
        return True
    if mode == MODE_GBNF:
        try:
            from crp.gateway.gbnf import compile_gbnf

            request.grammar = compile_gbnf(schema)
            return True
        except Exception as exc:
            logger.debug("GBNF compile failed, using validate+repair: %s", exc)
            return False
    return False

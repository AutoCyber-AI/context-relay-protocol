# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Response-header injection middleware (CRP-SPEC-002).

Provides a Starlette/FastAPI :class:`CRPHeaderMiddleware` (import-guarded so the
core library never hard-depends on Starlette) and framework-agnostic helpers.

Usage pattern (FastAPI)::

    from crp.headers.middleware import CRPHeaderMiddleware
    app.add_middleware(CRPHeaderMiddleware)

    @app.post("/crp/v3/dispatch")
    async def dispatch(request: Request):
        ...
        request.state.crp_headers = emit_headers(provenance=report, quality=q)
        return JSONResponse({"output": result.output})

The route computes the CRP headers (via :func:`crp.headers.emit.emit_headers`)
and stashes them on ``request.state.crp_headers``; the middleware merges them
onto the outgoing response.
"""

from __future__ import annotations

from collections.abc import Mapping

try:  # pragma: no cover - exercised only when Starlette is installed
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import Response

    _HAS_STARLETTE = True
except Exception:  # pragma: no cover
    _HAS_STARLETTE = False
    BaseHTTPMiddleware = object  # type: ignore[assignment,misc]


def merge_headers(response_headers: dict[str, str], crp_headers: Mapping[str, str]) -> dict[str, str]:
    """Merge *crp_headers* into a plain header dict (CRP values win)."""
    merged = dict(response_headers)
    merged.update(crp_headers)
    return merged


def inject_into_raw(
    raw_headers: list[tuple[bytes, bytes]],
    crp_headers: Mapping[str, str],
) -> list[tuple[bytes, bytes]]:
    """Append *crp_headers* to an ASGI raw-header list (no framework needed)."""
    out = list(raw_headers)
    for name, value in crp_headers.items():
        out.append((name.encode("latin-1"), str(value).encode("latin-1")))
    return out


if _HAS_STARLETTE:

    class CRPHeaderMiddleware(BaseHTTPMiddleware):  # type: ignore[misc]
        """Merge ``request.state.crp_headers`` onto every response.

        Routes set ``request.state.crp_headers`` to the dict returned by
        :func:`crp.headers.emit.emit_headers`.  This middleware copies those
        onto the outgoing response headers.
        """

        async def dispatch(self, request: Request, call_next):  # noqa: D401
            """Strip spoofed inbound headers and merge CRP headers onto the response.

            Args:
                request: Incoming Starlette/FastAPI request.
                call_next: ASGI callable that produces the downstream response.

            Returns:
                Response with CRP headers merged from ``request.state.crp_headers``.
            """
            # SPEC-002 §14.1: strip client-spoofed response-namespace CRP
            # headers from the inbound request before the app sees them.
            from .parse import strip_inbound_forbidden_headers

            _, stripped = strip_inbound_forbidden_headers(dict(request.headers))
            if stripped:
                request.state.crp_stripped_request_headers = stripped

            response: Response = await call_next(request)
            crp_headers = getattr(request.state, "crp_headers", None)
            if crp_headers:
                for name, value in crp_headers.items():
                    response.headers[name] = str(value)
            return response

else:  # pragma: no cover - fallback when Starlette is absent

    class CRPHeaderMiddleware:  # type: ignore[no-redef]
        """Placeholder raised if used without Starlette installed."""

        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError(
                "CRPHeaderMiddleware requires Starlette/FastAPI. "
                "Install with `pip install starlette` or use crp.headers.emit.emit_headers "
                "+ crp.headers.middleware.merge_headers directly."
            )

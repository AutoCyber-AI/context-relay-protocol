# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP protocol header surface (CRP-SPEC-002).

The HTTP-header layer that turns the CRP engine's internal analysis into the
wire protocol: canonical header-name constants, response emission, inbound
request parsing, Axiom-4 stripping, and response middleware.
"""

from __future__ import annotations

from . import names
from .emit import emit_headers
from .conditional import (
    CacheDirectives,
    ConditionalResult,
    compute_etag,
    evaluate_conditional,
    parse_cache_directives,
)
from .halt import HaltReason, HaltResponse, build_halt_response
from .middleware import (
    CRPHeaderMiddleware,
    inject_into_raw,
    merge_headers,
)
from .parse import (
    RequestDirectives,
    assert_no_crp_headers,
    parse_request_headers,
    strip_crp_headers,
    strip_inbound_forbidden_headers,
)

__all__ = [
    "names",
    "emit_headers",
    "RequestDirectives",
    "parse_request_headers",
    "strip_crp_headers",
    "strip_inbound_forbidden_headers",
    "assert_no_crp_headers",
    "CRPHeaderMiddleware",
    "merge_headers",
    "inject_into_raw",
    "compute_etag",
    "evaluate_conditional",
    "parse_cache_directives",
    "CacheDirectives",
    "ConditionalResult",
    "build_halt_response",
    "HaltReason",
    "HaltResponse",
]

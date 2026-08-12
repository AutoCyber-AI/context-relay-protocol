# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Progressive SDK — Level 0–3 developer experience (SPEC-032).

Exports:
    CRPClient          — the main steering wheel
    CRPCompletionResponse, CRPAskResponse — response types
    CRPResponseMeta    — governance summary
"""

from __future__ import annotations

from crp.sdk.client import CRPClient
from crp.sdk.dynamic import _ModulesProxy, _OrchestratorProxy
from crp.sdk.proxies import (
    _ActivationProxy,
    _AgentProxy,
    _AuditProxy,
    _CKFProxy,
    _ComplianceProxy,
    _CSOProxy,
    _EventsProxy,
    _ExtractionProxy,
    _KnowledgeProxy,
    _ProvenanceProxy,
    _ProvidersProxy,
    _ReasoningProxy,
    _SafetyProxy,
    _StorageProxy,
)
from crp.sdk.proxies_extra import (
    _ComplyProxy,
    _GatewayProxy,
    _HeadersProxy,
    _ObservabilityProxy,
    _PolicyProxy,
    _ScanProxy,
)
from crp.sdk.proxies_more import (
    _AdvancedProxy,
    _CLIProxy,
    _ContinuationProxy,
    _CoreProxy,
    _EnvelopeProxy,
    _ErrorsProxy,
    _ResourcesProxy,
    _SecurityProxy,
    _StateProxy,
)
from crp.sdk.response import (
    CRPAskResponse,
    CRPCompletionResponse,
    CRPResponseMeta,
    SourceAttribution,
)

__all__ = [
    "CRPClient",
    "CRPCompletionResponse",
    "CRPAskResponse",
    "CRPResponseMeta",
    "SourceAttribution",
    # Namespace proxies for advanced users
    "_SafetyProxy",
    "_CKFProxy",
    "_CSOProxy",
    "_ProvenanceProxy",
    "_ReasoningProxy",
    "_ActivationProxy",
    "_AgentProxy",
    "_EventsProxy",
    "_ProvidersProxy",
    "_ExtractionProxy",
    "_StorageProxy",
    "_KnowledgeProxy",
    "_AuditProxy",
    "_ComplianceProxy",
    # Additional product-facing namespace proxies
    "_GatewayProxy",
    "_HeadersProxy",
    "_ObservabilityProxy",
    "_PolicyProxy",
    "_ScanProxy",
    "_ComplyProxy",
    # Dynamic accessors for full API coverage
    "_OrchestratorProxy",
    "_ModulesProxy",
    # Additional curated namespace proxies
    "_CoreProxy",
    "_ContinuationProxy",
    "_EnvelopeProxy",
    "_StateProxy",
    "_SecurityProxy",
    "_ResourcesProxy",
    "_AdvancedProxy",
    "_CLIProxy",
    "_ErrorsProxy",
]

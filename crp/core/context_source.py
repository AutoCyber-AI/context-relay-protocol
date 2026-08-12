# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Context-source provenance primitives (§7.14.3, introduced in CRP 2.1).

Background
----------
The Decision Provenance Engine (``crp/provenance/``) already classifies every
LLM *output* claim as ``CONTEXT_GROUNDED | PARAMETRIC | MIXED | UNCERTAIN``.
That is *output-side* provenance — where did the answer come from, relative to
the envelope?

This module adds the symmetric *input-side* primitive: where did the envelope
content itself come from?  Was a fact retrieved from a vector DB, pulled from
a relational database, returned by an MCP tool, typed by the end user, or is
it model-parametric knowledge?

Without this, an organisation running CRP cannot answer ISO/IEC 42001 §4.1
(Context of the organisation), GDPR Art. 30 (Records of Processing), or EU
AI Act Art. 10 (Data governance) truthfully.

Design
------
Three types:

* :class:`SourceKind` — a closed enumeration of upstream source categories.
  Closed intentionally: if new kinds appear in the wild, they land here via
  an RFC so auditors have a stable vocabulary.
* :class:`ContextSource` — an immutable record attached to facts and
  messages. Records *what kind* of source supplied the content, *who*
  declared it (a signed manifest, an observed channel, or a heuristic
  parser), and *what* we know about its sensitivity, region, and retrieval
  policy.
* :class:`ContextManifest` — a customer-authored declarative catalogue of
  the sources their application *intends* to use. Observed sources that do
  not appear in the manifest are flagged ``UNATTESTED`` and emitted to the
  audit log as :data:`CONTEXT_ATTESTATION_MISMATCH` events.

This module is pure-data; no I/O, no network, no LLM calls. Consumers (the
envelope builder, dispatch router, Decision Provenance Engine, and the
`crp-comply` compliance-reporting layer) integrate it at their own
pace — every new field is optional and defaults preserve v2.0 behaviour.

References
----------
- ISO/IEC 42001:2023 §4.1–4.2 (Context of the organisation)
- EU AI Act Regulation (EU) 2024/1689, Art. 10 (Data and data governance)
- GDPR Art. 30 (Records of processing activities)
- NIST AI RMF 1.0, MAP 4 (Context mapping)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Literal, Sequence

__all__ = [
    "SourceKind",
    "SourceOrigin",
    "TrustLevel",
    "ContextSource",
    "ContextManifest",
    "ManifestValidationError",
    "AttestationMismatch",
    "detect_source_kind",
    "check_attestation",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class SourceKind(str, Enum):
    """Closed enumeration of upstream context-source categories.

    Stable vocabulary — additions require an RFC so downstream auditors do
    not receive novel strings without warning.
    """

    USER_TURN = "user_turn"
    """End-user's direct chat input."""

    SYSTEM_PROMPT = "system_prompt"
    """Developer-authored system/instruction prompt."""

    DEVELOPER_PROMPT = "developer_prompt"
    """Messages from a developer role (OpenAI-style ``role=developer``)."""

    RAG_RETRIEVAL = "rag_retrieval"
    """Retrieval-augmented generation chunk (generic; use VECTOR_DB or
    DATABASE when the backend is known)."""

    VECTOR_DB = "vector_db"
    """Vector-database retrieval (Pinecone, Weaviate, pgvector, etc.)."""

    DATABASE = "database"
    """Relational/NoSQL database read."""

    KNOWLEDGE_GRAPH = "knowledge_graph"
    """Structured knowledge graph (Neo4j, RDF, etc.)."""

    MCP_TOOL = "mcp_tool"
    """Model Context Protocol server tool invocation."""

    FUNCTION_CALL = "function_call"
    """OpenAI/Anthropic function-calling result returned to the model."""

    WEB_SEARCH = "web_search"
    """Live web-search result."""

    FILE_UPLOAD = "file_upload"
    """User-uploaded document."""

    AGENT_MEMORY = "agent_memory"
    """Agent-framework conversational memory store."""

    CKF_RETRIEVAL = "ckf_retrieval"
    """CRP Contextual Knowledge Fabric retrieval (internal)."""

    WARM_STORE = "warm_store"
    """CRP warm-store fact (internal, recycled from an earlier window)."""

    PARAMETRIC = "parametric"
    """Model-internal knowledge — not a retrievable upstream source."""

    UNATTESTED = "unattested"
    """Content whose kind could not be determined; flagged for audit."""


class SourceOrigin(str, Enum):
    """How this :class:`ContextSource` record came into existence."""

    DECLARED = "declared"
    """Explicitly registered via :class:`ContextManifest`."""

    OBSERVED = "observed"
    """Explicitly attached by the caller (e.g. tool-call plumbing that
    knows it is returning an MCP tool result)."""

    HEURISTIC = "heuristic"
    """Inferred by :func:`detect_source_kind` from marker patterns in the
    message content. Lowest trust — surfaced in audit reports for review."""


class TrustLevel(str, Enum):
    """Caller's trust posture for the source.

    Not a security boundary — this is an *audit* signal. Enforcement (ACLs,
    redaction, refusal) is the integrator's responsibility.
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# ContextSource
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContextSource:
    """Immutable record describing where a piece of envelope content came from.

    Attached optionally to :class:`crp.Fact` via its ``source`` field and to
    ``role=tool`` / ``role=user`` messages by the dispatch router.

    Every field except ``kind`` and ``source_id`` is optional. Defaults
    preserve v2.0 behaviour — callers that do not opt in see no change.

    Parameters
    ----------
    kind
        A :class:`SourceKind` value. Closed enumeration.
    source_id
        Stable handle for the source (e.g. ``"acme-hr-policies-vdb"``,
        ``"mcp://atlassian/jira-search"``). Must be non-empty and ≤ 256 chars.
    origin
        :class:`SourceOrigin` — ``DECLARED`` (from a signed manifest),
        ``OBSERVED`` (plumbed in by the caller), or ``HEURISTIC`` (detected
        by pattern-match).
    trust_level
        Caller's trust posture. Default ``UNKNOWN``.
    contains_pii
        Tri-state: ``True``, ``False``, or ``None`` (unknown). Used by GDPR
        deliverables and by the EU AI Act Art. 10 data-governance report.
    sensitivity
        Free-form sensitivity label (e.g. ``"confidential"``, ``"public"``,
        ``"restricted"``). Not normalised — customer vocabulary passes through.
    region
        Geographic region of the source (``"eu-west-1"``, ``"us-east-2"``,
        ``"on-prem-dc1"``). Enables cross-border-transfer audits.
    retrieval_query
        For RAG/DB/search sources: the query string used. Stored verbatim
        for the Source Grounding Engine. Truncated to 512 chars.
    retrieved_at
        UTC timestamp of retrieval.
    upstream_uri
        Stable URI pointer back to the source record if available.
    declared_by_manifest_id
        Links the record back to a :class:`ContextManifest` when
        ``origin == DECLARED``.
    metadata
        Integrator-defined extras. Size-limited below.
    """

    #: Size-limits on ``metadata`` mirror :class:`crp.extraction.types.Fact`.
    MAX_METADATA_KEYS: int = 32
    MAX_KEY_LENGTH: int = 128
    MAX_VALUE_SIZE: int = 2048
    MAX_SOURCE_ID_LENGTH: int = 256
    MAX_RETRIEVAL_QUERY_LENGTH: int = 512

    kind: SourceKind = SourceKind.UNATTESTED
    source_id: str = ""
    origin: SourceOrigin = SourceOrigin.HEURISTIC
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    contains_pii: bool | None = None
    sensitivity: str | None = None
    region: str | None = None
    retrieval_query: str | None = None
    retrieved_at: float | None = None
    upstream_uri: str | None = None
    declared_by_manifest_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Coerce string values to enums for ergonomic construction
        if isinstance(self.kind, str) and not isinstance(self.kind, SourceKind):
            object.__setattr__(self, "kind", SourceKind(self.kind))
        if isinstance(self.origin, str) and not isinstance(self.origin, SourceOrigin):
            object.__setattr__(self, "origin", SourceOrigin(self.origin))
        if isinstance(self.trust_level, str) and not isinstance(self.trust_level, TrustLevel):
            object.__setattr__(self, "trust_level", TrustLevel(self.trust_level))

        if not isinstance(self.source_id, str):
            raise TypeError("ContextSource.source_id must be a string")
        if len(self.source_id) > self.MAX_SOURCE_ID_LENGTH:
            raise ValueError(
                f"ContextSource.source_id exceeds {self.MAX_SOURCE_ID_LENGTH} chars"
            )

        if self.retrieval_query is not None and len(self.retrieval_query) > self.MAX_RETRIEVAL_QUERY_LENGTH:
            object.__setattr__(
                self,
                "retrieval_query",
                self.retrieval_query[: self.MAX_RETRIEVAL_QUERY_LENGTH],
            )

        if len(self.metadata) > self.MAX_METADATA_KEYS:
            raise ValueError(
                f"ContextSource.metadata exceeds {self.MAX_METADATA_KEYS} keys"
            )
        for key, value in self.metadata.items():
            if len(str(key)) > self.MAX_KEY_LENGTH:
                raise ValueError(
                    f"Metadata key exceeds {self.MAX_KEY_LENGTH} chars"
                )
            if len(str(value)) > self.MAX_VALUE_SIZE:
                raise ValueError(
                    f"Metadata value for '{key}' exceeds {self.MAX_VALUE_SIZE} chars"
                )

    # ------------------------------------------------------------------ I/O

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready dict for audit logs and envelope serialisation."""
        out = asdict(self)
        # Drop class constants that dataclasses.asdict would include if they
        # were promoted to instance vars (they're not — belt-and-braces).
        for const in (
            "MAX_METADATA_KEYS",
            "MAX_KEY_LENGTH",
            "MAX_VALUE_SIZE",
            "MAX_SOURCE_ID_LENGTH",
            "MAX_RETRIEVAL_QUERY_LENGTH",
        ):
            out.pop(const, None)
        # Flatten enums to their string values.
        out["kind"] = self.kind.value
        out["origin"] = self.origin.value
        out["trust_level"] = self.trust_level.value
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSource:
        """Construct from a dict produced by :meth:`to_dict`."""
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# ContextManifest — declarative attestation
# ---------------------------------------------------------------------------


class ManifestValidationError(ValueError):
    """Raised when a :class:`ContextManifest` cannot be loaded or verified."""


@dataclass
class ContextManifest:
    """Customer-authored declaration of upstream context sources.

    Signed with HMAC-SHA256 over a canonical JSON representation.  The
    signature is *advisory* — it proves the declaration has not been tampered
    with since signing, but CRP does not manage the signing key.

    Minimal usage::

        manifest = ContextManifest(system_id="resume-rank-v1", customer_id="acme")
        manifest.add(ContextSource(
            kind=SourceKind.VECTOR_DB,
            source_id="acme-hr-policies-vdb",
            origin=SourceOrigin.DECLARED,
            trust_level=TrustLevel.TRUSTED,
            contains_pii=True,
            region="eu-west-1",
        ))
        manifest.sign(secret=os.environ["CRP_MANIFEST_SECRET"].encode())
        blob = manifest.to_json()   # persist / ship to proxy
    """

    manifest_version: str = "1"
    manifest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    system_id: str = ""
    customer_id: str = ""
    issued_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    sources: list[ContextSource] = field(default_factory=list)
    context_window_tokens: int | None = None
    signature: str | None = None

    # ----------------------------------------------------------------- data

    def add(self, source: ContextSource) -> None:
        """Append a :class:`ContextSource` to the manifest.

        The source's ``origin`` is forced to ``DECLARED`` and the manifest
        id is stamped into ``declared_by_manifest_id``. Invalidates any
        existing signature.
        """
        declared = ContextSource(
            kind=source.kind,
            source_id=source.source_id,
            origin=SourceOrigin.DECLARED,
            trust_level=source.trust_level,
            contains_pii=source.contains_pii,
            sensitivity=source.sensitivity,
            region=source.region,
            retrieval_query=source.retrieval_query,
            retrieved_at=source.retrieved_at,
            upstream_uri=source.upstream_uri,
            declared_by_manifest_id=self.manifest_id,
            metadata=dict(source.metadata),
        )
        self.sources.append(declared)
        self.signature = None

    # ----------------------------------------------------------- signing

    def _canonical_payload(self) -> bytes:
        """Canonical JSON payload used for signing / verification."""
        payload: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "system_id": self.system_id,
            "customer_id": self.customer_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "context_window_tokens": self.context_window_tokens,
            "sources": [s.to_dict() for s in self.sources],
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()

    def sign(self, secret: bytes) -> str:
        """Sign the manifest with HMAC-SHA256 and return the hex digest."""
        if not isinstance(secret, (bytes, bytearray)) or len(secret) == 0:
            raise ManifestValidationError("HMAC secret must be non-empty bytes")
        mac = hmac.new(bytes(secret), self._canonical_payload(), hashlib.sha256).hexdigest()
        self.signature = mac
        return mac

    def verify(self, secret: bytes) -> bool:
        """Verify the HMAC signature in constant time.

        Returns ``True`` iff ``signature`` is present and matches.
        """
        if self.signature is None:
            return False
        expected = hmac.new(
            bytes(secret), self._canonical_payload(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)

    # ---------------------------------------------------------- lifecycle

    def is_expired(self, now: float | None = None) -> bool:
        """Return True if the manifest has passed its expiry timestamp."""
        if self.expires_at is None:
            return False
        t = now if now is not None else time.time()
        return t > self.expires_at

    # -------------------------------------------------------------- lookups

    def declared_kinds(self) -> set[SourceKind]:
        """Set of :class:`SourceKind` values that appear in the manifest."""
        return {s.kind for s in self.sources}

    def declared_source_ids(self) -> set[str]:
        """Return the set of non-empty source IDs declared in the manifest."""
        return {s.source_id for s in self.sources if s.source_id}

    def find(self, source_id: str) -> ContextSource | None:
        """Return the declared source with *source_id*, or None if absent."""
        for s in self.sources:
            if s.source_id == source_id:
                return s
        return None

    # ---------------------------------------------------------------- JSON

    def to_json(self) -> str:
        """Serialise to JSON (includes ``signature`` if present)."""
        payload: dict[str, Any] = {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "system_id": self.system_id,
            "customer_id": self.customer_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "context_window_tokens": self.context_window_tokens,
            "sources": [s.to_dict() for s in self.sources],
            "signature": self.signature,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, blob: str | bytes) -> ContextManifest:
        """Create a new instance from a JSON string or object.
        
            Args:
                blob (str | bytes): The blob value.
        
            Returns:
                ``ContextManifest``.
        """
        try:
            data = json.loads(blob)
        except (TypeError, ValueError) as exc:
            raise ManifestValidationError(f"Invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ManifestValidationError("Manifest JSON must decode to an object")

        sources = [ContextSource.from_dict(s) for s in data.get("sources", [])]
        return cls(
            manifest_version=str(data.get("manifest_version", "1")),
            manifest_id=str(data.get("manifest_id") or uuid.uuid4()),
            system_id=str(data.get("system_id", "")),
            customer_id=str(data.get("customer_id", "")),
            issued_at=float(data.get("issued_at", time.time())),
            expires_at=data.get("expires_at"),
            sources=sources,
            context_window_tokens=data.get("context_window_tokens"),
            signature=data.get("signature"),
        )


# ---------------------------------------------------------------------------
# Detective-mode heuristic detector
# ---------------------------------------------------------------------------


# Conservative patterns — false positives land in audit review, not in
# automated enforcement. Order matters: earlier matches win.
_HEURISTIC_PATTERNS: tuple[tuple[re.Pattern[str], SourceKind], ...] = (
    # Explicit XML/Markdown markers commonly used by agent frameworks.
    (re.compile(r"<rag[\s>]", re.IGNORECASE), SourceKind.RAG_RETRIEVAL),
    (re.compile(r"\[retrieved( documents?)?\]", re.IGNORECASE), SourceKind.RAG_RETRIEVAL),
    (re.compile(r"<vector_?db[\s>]", re.IGNORECASE), SourceKind.VECTOR_DB),
    (re.compile(r"<web_?search[\s>]", re.IGNORECASE), SourceKind.WEB_SEARCH),
    (re.compile(r"search results? from the web", re.IGNORECASE), SourceKind.WEB_SEARCH),
    (re.compile(r"<mcp[:\s>]", re.IGNORECASE), SourceKind.MCP_TOOL),
    (re.compile(r"<file_?upload[\s>]", re.IGNORECASE), SourceKind.FILE_UPLOAD),
    (re.compile(r"<tool[_\s]result[\s>]", re.IGNORECASE), SourceKind.FUNCTION_CALL),
    (re.compile(r"\bSELECT\s+.+\s+FROM\s+", re.IGNORECASE), SourceKind.DATABASE),
    (re.compile(r"\bCypher query", re.IGNORECASE), SourceKind.KNOWLEDGE_GRAPH),
    (re.compile(r"from (?:the )?(?:agent|conversation) memory", re.IGNORECASE), SourceKind.AGENT_MEMORY),
    # CRP 2.2 — extended coverage for structural markers
    (re.compile(r"```(?:json|xml|html|yaml)\s*\n.*?```", re.IGNORECASE | re.DOTALL), SourceKind.FUNCTION_CALL),
    (re.compile(r"\b(?:INSERT|UPDATE|DELETE)\s+(?:INTO\s+)?\w+", re.IGNORECASE), SourceKind.DATABASE),
    (re.compile(r"\bMATCH\s*\([^)]*\)\s*(?:WHERE|RETURN)\b", re.IGNORECASE), SourceKind.KNOWLEDGE_GRAPH),
    (re.compile(r"\bserpapi|google search|bing\.com|duckduckgo", re.IGNORECASE), SourceKind.WEB_SEARCH),
    (re.compile(r"\bpinecone|weaviate|qdrant|chromadb|pgvector|milvus\b", re.IGNORECASE), SourceKind.VECTOR_DB),
    (re.compile(r"\bopenai\.func|function_name['\":]|tool_name['\":]|arguments['\":]", re.IGNORECASE), SourceKind.FUNCTION_CALL),
)


# Structural / MIME signals. If content parses as one of these, we have a
# much stronger signal than a regex hit.
def _structural_hint(content: str) -> SourceKind | None:
    stripped = content.lstrip()
    if not stripped:
        return None
    # JSON object or array that looks like a tool-call payload
    if stripped[:1] in "{[":
        try:
            obj = json.loads(stripped)
        except (ValueError, TypeError):
            obj = None
        if isinstance(obj, dict):
            keys = {k.lower() for k in obj.keys() if isinstance(k, str)}
            if {"function_name", "arguments"} <= keys or {"tool_name", "arguments"} <= keys:
                return SourceKind.FUNCTION_CALL
            if "mcp" in keys or "mcp_server" in keys or "mcp_method" in keys:
                return SourceKind.MCP_TOOL
            if {"url", "snippet"} <= keys or {"title", "link", "snippet"} <= keys:
                return SourceKind.WEB_SEARCH
            if "embedding" in keys or "vector" in keys or "score" in keys and "chunk" in keys:
                return SourceKind.VECTOR_DB
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            first = {k.lower() for k in obj[0].keys() if isinstance(k, str)}
            if {"title", "link"} <= first or {"url", "snippet"} <= first:
                return SourceKind.WEB_SEARCH
            if {"chunk", "score"} <= first or {"text", "score"} <= first:
                return SourceKind.VECTOR_DB
    return None


def detect_source_kind(
    content: str,
    *,
    role: str | None = None,
    default: SourceKind = SourceKind.UNATTESTED,
) -> ContextSource:
    """Heuristically classify *content* into a :class:`ContextSource`.

    The resulting :class:`ContextSource` always has ``origin=HEURISTIC``
    and ``trust_level=UNKNOWN``. Callers that know the true origin should
    construct the record directly rather than relying on this function.

    Parameters
    ----------
    content
        Raw message text.
    role
        Optional OpenAI-style chat role hint (``"user"``, ``"system"``,
        ``"developer"``, ``"tool"``, ``"function"``). If provided, strong
        role-based signals win over content-based ones.
    default
        :class:`SourceKind` to fall back to if nothing matches.

    Returns
    -------
    ContextSource
        With ``source_id`` set to a stable fingerprint of the detected kind
        plus a short content hash.
    """
    if role is not None:
        role_lower = role.lower()
        if role_lower == "system":
            return _heuristic(SourceKind.SYSTEM_PROMPT, content)
        if role_lower == "developer":
            return _heuristic(SourceKind.DEVELOPER_PROMPT, content)
        if role_lower == "tool":
            return _heuristic(SourceKind.FUNCTION_CALL, content)
        if role_lower == "function":
            return _heuristic(SourceKind.FUNCTION_CALL, content)
        if role_lower == "user":
            # User role may still carry RAG/tool-result blobs; fall through
            # to content scan before defaulting to USER_TURN.
            kind = _scan_content(content)
            return _heuristic(kind or SourceKind.USER_TURN, content)

    kind = _scan_content(content)
    return _heuristic(kind or default, content)


def _scan_content(content: str) -> SourceKind | None:
    # Structural signals beat regex — JSON/MIME parsing is higher confidence.
    structural = _structural_hint(content)
    if structural is not None:
        return structural
    for pattern, kind in _HEURISTIC_PATTERNS:
        if pattern.search(content):
            return kind
    return None


def _heuristic(kind: SourceKind, content: str) -> ContextSource:
    digest = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:12]
    return ContextSource(
        kind=kind,
        source_id=f"heuristic://{kind.value}#{digest}",
        origin=SourceOrigin.HEURISTIC,
        trust_level=TrustLevel.UNKNOWN,
    )


# ---------------------------------------------------------------------------
# Attestation check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AttestationMismatch:
    """One audit-log row describing a discrepancy between observed and declared sources.

    Emitted whenever :func:`check_attestation` detects that an observed
    :class:`ContextSource` has no counterpart in the current
    :class:`ContextManifest`. Consumed by the dispatch router's audit
    pipeline (§7.14.2) and by the compliance layer's attestation report.
    """

    manifest_id: str
    observed_source: ContextSource
    reason: Literal[
        "no_manifest",
        "unattested_kind",
        "unattested_source_id",
        "manifest_expired",
    ]
    detected_at: float = field(default_factory=time.time)

    def to_audit_event(self) -> dict[str, Any]:
        """Serialise into the §7.14.2 audit-event envelope shape."""
        return {
            "event_type": "CONTEXT_ATTESTATION_MISMATCH",
            "manifest_id": self.manifest_id,
            "reason": self.reason,
            "observed_source": self.observed_source.to_dict(),
            "detected_at": self.detected_at,
        }


def check_attestation(
    observed: Sequence[ContextSource],
    manifest: ContextManifest | None,
    *,
    now: float | None = None,
) -> list[AttestationMismatch]:
    """Return the set of mismatches between *observed* sources and *manifest*.

    The matching rule is deliberately strict:

    * No manifest → every observed source that is not obviously benign
      (``USER_TURN``, ``SYSTEM_PROMPT``, ``DEVELOPER_PROMPT``, ``PARAMETRIC``)
      yields a ``no_manifest`` mismatch.
    * Expired manifest → every observed source yields a ``manifest_expired``
      mismatch.
    * Otherwise, observed ``source_id`` must match a declared ``source_id``
      *or* observed ``kind`` must be present in ``declared_kinds()``.  A
      missing ``source_id`` match falls back to a kind-only match and yields
      an ``unattested_source_id`` row if the ``source_id`` is non-empty;
      a missing kind match yields ``unattested_kind``.

    Heuristic and declared sources are both checked — customers who want to
    suppress heuristic noise should declare their sources.
    """
    _benign = {
        SourceKind.USER_TURN,
        SourceKind.SYSTEM_PROMPT,
        SourceKind.DEVELOPER_PROMPT,
        SourceKind.PARAMETRIC,
    }

    if manifest is None:
        return [
            AttestationMismatch(
                manifest_id="",
                observed_source=src,
                reason="no_manifest",
            )
            for src in observed
            if src.kind not in _benign
        ]

    if manifest.is_expired(now):
        return [
            AttestationMismatch(
                manifest_id=manifest.manifest_id,
                observed_source=src,
                reason="manifest_expired",
            )
            for src in observed
        ]

    declared_kinds = manifest.declared_kinds()
    declared_ids = manifest.declared_source_ids()

    mismatches: list[AttestationMismatch] = []
    for src in observed:
        if src.kind in _benign:
            continue
        if src.source_id and src.source_id in declared_ids:
            continue
        if src.kind in declared_kinds:
            if src.source_id:
                mismatches.append(
                    AttestationMismatch(
                        manifest_id=manifest.manifest_id,
                        observed_source=src,
                        reason="unattested_source_id",
                    )
                )
            continue
        mismatches.append(
            AttestationMismatch(
                manifest_id=manifest.manifest_id,
                observed_source=src,
                reason="unattested_kind",
            )
        )
    return mismatches


# ---------------------------------------------------------------------------
# Utility — ISO-8601 helper for audit logs
# ---------------------------------------------------------------------------


def iso8601(ts: float) -> str:
    """UTC ISO-8601 string for an epoch timestamp (audit log convenience)."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

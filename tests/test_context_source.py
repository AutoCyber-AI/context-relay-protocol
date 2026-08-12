# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tests for CRP 2.1 context-source provenance primitives (§7.14.3)."""

from __future__ import annotations

import json
import time

import pytest

from crp import (
    AttestationMismatch,
    ContextManifest,
    ContextSource,
    ErrorCode,
    Fact,
    ManifestValidationError,
    SourceKind,
    SourceOrigin,
    TrustLevel,
    check_attestation,
    detect_source_kind,
)


# ---------------------------------------------------------------------------
# SourceKind / ContextSource basics
# ---------------------------------------------------------------------------


class TestContextSource:
    def test_defaults_preserve_v20_behaviour(self) -> None:
        src = ContextSource(source_id="x")
        assert src.kind is SourceKind.UNATTESTED
        assert src.origin is SourceOrigin.HEURISTIC
        assert src.trust_level is TrustLevel.UNKNOWN
        assert src.contains_pii is None

    def test_string_enum_coercion(self) -> None:
        src = ContextSource(kind="vector_db", source_id="vdb", origin="declared", trust_level="trusted")
        assert src.kind is SourceKind.VECTOR_DB
        assert src.origin is SourceOrigin.DECLARED
        assert src.trust_level is TrustLevel.TRUSTED

    def test_is_frozen(self) -> None:
        src = ContextSource(source_id="x")
        with pytest.raises(Exception):  # FrozenInstanceError
            src.source_id = "y"  # type: ignore[misc]

    def test_source_id_length_limit(self) -> None:
        with pytest.raises(ValueError):
            ContextSource(source_id="x" * 300)

    def test_retrieval_query_truncated(self) -> None:
        long = "a" * 1000
        src = ContextSource(source_id="x", retrieval_query=long)
        assert len(src.retrieval_query or "") == ContextSource.MAX_RETRIEVAL_QUERY_LENGTH

    def test_metadata_size_limits(self) -> None:
        with pytest.raises(ValueError):
            ContextSource(source_id="x", metadata={"k" * 200: "v"})
        with pytest.raises(ValueError):
            ContextSource(source_id="x", metadata={"k": "v" * 3000})
        with pytest.raises(ValueError):
            ContextSource(source_id="x", metadata={f"k{i}": "v" for i in range(40)})

    def test_to_dict_round_trip(self) -> None:
        src = ContextSource(
            kind=SourceKind.VECTOR_DB,
            source_id="acme-vdb",
            origin=SourceOrigin.DECLARED,
            trust_level=TrustLevel.TRUSTED,
            contains_pii=True,
            region="eu-west-1",
            retrieval_query="top-k=5",
            metadata={"provider": "pinecone"},
        )
        d = src.to_dict()
        assert d["kind"] == "vector_db"
        assert d["origin"] == "declared"
        assert d["trust_level"] == "trusted"
        restored = ContextSource.from_dict(d)
        assert restored == src

    def test_to_dict_excludes_class_constants(self) -> None:
        d = ContextSource(source_id="x").to_dict()
        for const in ("MAX_METADATA_KEYS", "MAX_KEY_LENGTH", "MAX_SOURCE_ID_LENGTH"):
            assert const not in d


# ---------------------------------------------------------------------------
# Fact.source integration
# ---------------------------------------------------------------------------


class TestFactSource:
    def test_default_is_none(self) -> None:
        f = Fact(text="hello")
        assert f.source is None

    def test_attach_source(self) -> None:
        src = ContextSource(kind=SourceKind.RAG_RETRIEVAL, source_id="rag-1", origin=SourceOrigin.OBSERVED)
        f = Fact(text="retrieved chunk", source=src)
        assert f.source is src
        assert f.source.kind is SourceKind.RAG_RETRIEVAL


# ---------------------------------------------------------------------------
# ContextManifest
# ---------------------------------------------------------------------------


class TestContextManifest:
    def test_add_forces_declared_origin(self) -> None:
        m = ContextManifest(system_id="s", customer_id="c")
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb"))
        assert m.sources[0].origin is SourceOrigin.DECLARED
        assert m.sources[0].declared_by_manifest_id == m.manifest_id

    def test_add_invalidates_signature(self) -> None:
        m = ContextManifest(system_id="s", customer_id="c")
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="a"))
        m.sign(b"secret")
        assert m.signature is not None
        m.add(ContextSource(kind=SourceKind.DATABASE, source_id="b"))
        assert m.signature is None

    def test_sign_and_verify(self) -> None:
        m = ContextManifest(system_id="s", customer_id="c")
        m.add(ContextSource(kind=SourceKind.RAG_RETRIEVAL, source_id="r"))
        m.sign(b"my-secret")
        assert m.verify(b"my-secret") is True
        assert m.verify(b"wrong-secret") is False

    def test_verify_without_signature_returns_false(self) -> None:
        m = ContextManifest(system_id="s", customer_id="c")
        assert m.verify(b"secret") is False

    def test_sign_rejects_empty_secret(self) -> None:
        m = ContextManifest()
        with pytest.raises(ManifestValidationError):
            m.sign(b"")

    def test_expiry(self) -> None:
        m = ContextManifest(expires_at=time.time() - 60)
        assert m.is_expired() is True
        m2 = ContextManifest(expires_at=time.time() + 60)
        assert m2.is_expired() is False
        m3 = ContextManifest()
        assert m3.is_expired() is False

    def test_json_round_trip(self) -> None:
        m = ContextManifest(system_id="s1", customer_id="c1", context_window_tokens=200000)
        m.add(ContextSource(
            kind=SourceKind.VECTOR_DB, source_id="vdb",
            trust_level=TrustLevel.TRUSTED, contains_pii=True, region="eu-west-1",
        ))
        m.sign(b"secret")
        blob = m.to_json()
        restored = ContextManifest.from_json(blob)
        assert restored.system_id == "s1"
        assert restored.sources[0].source_id == "vdb"
        assert restored.verify(b"secret") is True

    def test_from_json_invalid(self) -> None:
        with pytest.raises(ManifestValidationError):
            ContextManifest.from_json("not json")
        with pytest.raises(ManifestValidationError):
            ContextManifest.from_json("[]")

    def test_declared_lookups(self) -> None:
        m = ContextManifest()
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="a"))
        m.add(ContextSource(kind=SourceKind.MCP_TOOL, source_id="b"))
        assert m.declared_kinds() == {SourceKind.VECTOR_DB, SourceKind.MCP_TOOL}
        assert m.declared_source_ids() == {"a", "b"}
        assert m.find("a") is not None
        assert m.find("missing") is None


# ---------------------------------------------------------------------------
# Detective-mode detector
# ---------------------------------------------------------------------------


class TestDetectSourceKind:
    def test_system_role(self) -> None:
        src = detect_source_kind("You are a helpful assistant.", role="system")
        assert src.kind is SourceKind.SYSTEM_PROMPT
        assert src.origin is SourceOrigin.HEURISTIC

    def test_developer_role(self) -> None:
        assert detect_source_kind("hi", role="developer").kind is SourceKind.DEVELOPER_PROMPT

    def test_tool_role(self) -> None:
        assert detect_source_kind("{}", role="tool").kind is SourceKind.FUNCTION_CALL
        assert detect_source_kind("{}", role="function").kind is SourceKind.FUNCTION_CALL

    def test_user_role_with_rag_block(self) -> None:
        src = detect_source_kind("<RAG>chunk 1</RAG>", role="user")
        assert src.kind is SourceKind.RAG_RETRIEVAL

    def test_user_role_without_markers(self) -> None:
        src = detect_source_kind("what is the capital of France?", role="user")
        assert src.kind is SourceKind.USER_TURN

    def test_retrieved_documents_marker(self) -> None:
        assert detect_source_kind("[retrieved documents]\n...").kind is SourceKind.RAG_RETRIEVAL

    def test_web_search(self) -> None:
        assert detect_source_kind("search results from the web say...").kind is SourceKind.WEB_SEARCH

    def test_sql_query(self) -> None:
        assert detect_source_kind("SELECT name FROM users WHERE id=1").kind is SourceKind.DATABASE

    def test_mcp_marker(self) -> None:
        assert detect_source_kind("<mcp:atlassian-jira>").kind is SourceKind.MCP_TOOL

    def test_no_markers_uses_default(self) -> None:
        src = detect_source_kind("just some text", default=SourceKind.PARAMETRIC)
        assert src.kind is SourceKind.PARAMETRIC

    def test_stable_source_id_fingerprint(self) -> None:
        a = detect_source_kind("hello world")
        b = detect_source_kind("hello world")
        assert a.source_id == b.source_id

    def test_unattested_fallback(self) -> None:
        src = detect_source_kind("")
        assert src.kind is SourceKind.UNATTESTED
        assert src.origin is SourceOrigin.HEURISTIC


# ---------------------------------------------------------------------------
# check_attestation
# ---------------------------------------------------------------------------


class TestCheckAttestation:
    def test_no_manifest_benign_sources_pass(self) -> None:
        observed = [
            ContextSource(kind=SourceKind.USER_TURN, source_id="u"),
            ContextSource(kind=SourceKind.SYSTEM_PROMPT, source_id="s"),
        ]
        assert check_attestation(observed, manifest=None) == []

    def test_no_manifest_non_benign_flagged(self) -> None:
        observed = [ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb")]
        mismatches = check_attestation(observed, manifest=None)
        assert len(mismatches) == 1
        assert mismatches[0].reason == "no_manifest"

    def test_expired_manifest_flags_all(self) -> None:
        m = ContextManifest(expires_at=time.time() - 60)
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb"))
        observed = [ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb")]
        mismatches = check_attestation(observed, manifest=m)
        assert len(mismatches) == 1
        assert mismatches[0].reason == "manifest_expired"

    def test_matching_source_id_passes(self) -> None:
        m = ContextManifest()
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb"))
        observed = [ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb", origin=SourceOrigin.OBSERVED)]
        assert check_attestation(observed, manifest=m) == []

    def test_matching_kind_only_passes_when_no_source_id(self) -> None:
        m = ContextManifest()
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb"))
        observed = [ContextSource(kind=SourceKind.VECTOR_DB, source_id="", origin=SourceOrigin.HEURISTIC)]
        assert check_attestation(observed, manifest=m) == []

    def test_unattested_source_id_flagged_even_if_kind_matches(self) -> None:
        m = ContextManifest()
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="approved-vdb"))
        observed = [ContextSource(kind=SourceKind.VECTOR_DB, source_id="rogue-vdb", origin=SourceOrigin.OBSERVED)]
        mismatches = check_attestation(observed, manifest=m)
        assert len(mismatches) == 1
        assert mismatches[0].reason == "unattested_source_id"

    def test_unattested_kind_flagged(self) -> None:
        m = ContextManifest()
        m.add(ContextSource(kind=SourceKind.VECTOR_DB, source_id="vdb"))
        observed = [ContextSource(kind=SourceKind.WEB_SEARCH, source_id="bing", origin=SourceOrigin.HEURISTIC)]
        mismatches = check_attestation(observed, manifest=m)
        assert len(mismatches) == 1
        assert mismatches[0].reason == "unattested_kind"

    def test_audit_event_shape(self) -> None:
        m = ContextManifest(system_id="s", customer_id="c")
        observed = [ContextSource(kind=SourceKind.WEB_SEARCH, source_id="bing")]
        mismatches = check_attestation(observed, manifest=m)
        event = mismatches[0].to_audit_event()
        assert event["event_type"] == "CONTEXT_ATTESTATION_MISMATCH"
        assert event["reason"] == "unattested_kind"
        assert event["observed_source"]["kind"] == "web_search"
        assert "detected_at" in event


# ---------------------------------------------------------------------------
# Error code registration
# ---------------------------------------------------------------------------


class TestErrorCodes:
    def test_new_error_codes_present(self) -> None:
        assert ErrorCode.CONTEXT_ATTESTATION_MISMATCH == 1040
        assert ErrorCode.CONTEXT_MANIFEST_INVALID == 1041


# ---------------------------------------------------------------------------
# Public API surface
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_exports(self) -> None:
        import crp
        for name in (
            "SourceKind", "SourceOrigin", "TrustLevel",
            "ContextSource", "ContextManifest",
            "ManifestValidationError", "AttestationMismatch",
            "detect_source_kind", "check_attestation",
        ):
            assert hasattr(crp, name), f"crp.{name} missing"
            assert name in crp.__all__, f"{name} not in crp.__all__"

# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP conformance test-vector runner (CRP-SPEC-014 §2).

Loads the JSON test vectors under ``tests/conformance/vectors/`` and executes
each against the CRP reference library, returning a pass/fail result with the
failed assertion details. Vectors are dispatched by ``category`` to a
category handler. Because ``crp`` is a library (not a running gateway), each
handler exercises the building blocks the gateway assembles — header sets,
the HMAC window chain, session-token validation, policy parsing/inheritance,
DPE detections, the halt/conditional responses and the safety budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from crp.agent.budget import AgentSafetyBudget
from crp.headers.conditional import compute_etag, evaluate_conditional
from crp.headers.halt import HaltReason, build_halt_response
from crp.headers.parse import strip_inbound_forbidden_headers
from crp.policy import check_inheritance
from crp.policy.grammar import parse_policy
from crp.provenance import (
    DecisionProvenanceEngine,
    WindowChainRecord,
    build_window_hmac,
    build_fan_in_window_hmac,
    WindowHmacInput,
    detect_cross_window_contradictions,
    detect_repetition,
    verify_window_chain,
)
from crp.provenance._types import ProvenanceConfig
from crp.envelope.packer import PackedFact
from crp.security.session_token import (
    TokenStatus,
    issue_token,
    parse_token,
    validate_token,
)

from .levels import ConformanceLevel, mandatory_headers

VECTORS_DIR = Path(__file__).parent / "vectors"
_MASTER_KEY = b"conformance-master-key-32bytes!!"


@dataclass
class AssertionResult:
    ok: bool
    detail: str = ""


@dataclass
class VectorResult:
    test_id: str
    category: str
    conformance_level: str
    passed: bool
    failures: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Vector loading
# ---------------------------------------------------------------------------

def load_vectors(directory: Path | None = None) -> list[dict[str, Any]]:
    """Load and flatten all JSON vector files, sorted by test_id."""
    directory = directory or VECTORS_DIR
    vectors: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        vectors.extend(data.get("vectors", []))
    vectors.sort(key=lambda v: v.get("test_id", ""))
    return vectors


# ---------------------------------------------------------------------------
# Category handlers — each returns a list of AssertionResult
# ---------------------------------------------------------------------------

def _run_headers(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for a in assertions:
        t = a["type"]
        if t == "mandatory_headers_present":
            level = ConformanceLevel(a["level"])
            required = mandatory_headers(level)
            missing = [h for h in required if not h]
            out.append(AssertionResult(not missing, f"missing={missing}"))
        elif t == "crp_headers_stripped":
            cleaned, stripped = strip_inbound_forbidden_headers(inp["inbound_headers"])
            kept = a["kept"]
            kept_ok = all(k in cleaned for k in kept)
            expect_stripped = a.get("stripped", [])
            stripped_ok = all(k in stripped for k in expect_stripped)
            out.append(
                AssertionResult(
                    kept_ok and stripped_ok,
                    f"cleaned={list(cleaned)} stripped={stripped}",
                )
            )
        elif t == "halt_status":
            resp = build_halt_response(
                reason=HaltReason.CRITICAL_HALLUCINATION_RISK,
                session_id="s1",
                audit_trail_uri="https://comply.crprotocol.io/audit/s1",
                hallucination_risk="CRITICAL",
            )
            out.append(AssertionResult(resp.http_status == a["expected"], f"status={resp.http_status}"))
        elif t == "halt_body_field":
            resp = build_halt_response(
                reason=HaltReason.CRITICAL_HALLUCINATION_RISK,
                session_id="s1",
                audit_trail_uri="https://comply.crprotocol.io/audit/s1",
            )
            out.append(AssertionResult(a["field"] in resp.body, f"body keys={list(resp.body)}"))
        elif t == "halt_header_present":
            resp = build_halt_response(
                reason=HaltReason.CRITICAL_HALLUCINATION_RISK,
                session_id="s1",
                audit_trail_uri="https://comply.crprotocol.io/audit/s1",
            )
            out.append(AssertionResult(a["header"] in resp.headers, f"headers={list(resp.headers)}"))
        elif t in ("conditional_status", "conditional_cache_status"):
            etag = compute_etag([("f1", "h1")])
            if_match = etag if inp.get("if_match_equals_current") else "sha256:other"
            directives = ["only-if-ckf"] if inp.get("only_if_ckf") else []
            result = evaluate_conditional(
                if_match=if_match,
                current_etag=etag,
                cache=directives,
                ckf_has_relevant_facts=inp.get("ckf_has_relevant_facts", True),
            )
            if t == "conditional_status":
                out.append(AssertionResult(result.http_status == a["expected"], f"status={result.http_status}"))
            else:
                out.append(AssertionResult(result.cache_status == a["expected"], f"cache={result.cache_status}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


def _run_dpe(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    engine = DecisionProvenanceEngine(config=ProvenanceConfig(rqa_enabled=False))
    report = None
    if "envelope_facts" in inp:
        facts = [
            PackedFact(fact_id=f["fact_id"], text=f["content"], score=0.9, tokens=16)
            for f in inp["envelope_facts"]
        ]
        report = engine.analyse(inp["llm_response"], facts, session_id="s1", window_id="w1")
    for a in assertions:
        t = a["type"]
        if t == "dpe_field_gte":
            val = getattr(report.fidelity, a["field"], 0) if report and report.fidelity else 0
            out.append(AssertionResult(val >= a["value"], f"{a['field']}={val}"))
        elif t == "coherence_contradictions_gte":
            res = detect_cross_window_contradictions(
                inp["current_response"], [inp["prior_window_response"]]
            )
            out.append(
                AssertionResult(len(res.contradictions) >= a["value"], f"contradictions={len(res.contradictions)}")
            )
        elif t == "repetition_level_at_least":
            res = detect_repetition(inp["current_response"], [inp["prior_window_response"]])
            order = ["NONE", "MINOR", "SIGNIFICANT", "SEVERE"]
            got = res.level.value
            ok = order.index(got) >= order.index(a["value"])
            out.append(AssertionResult(ok, f"level={got} ratio={res.repetition_ratio:.2f}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


def _run_safety_policy(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for a in assertions:
        t = a["type"]
        if t == "policy_parses":
            try:
                parse_policy(inp["policy"])
                parsed = True
            except Exception:
                parsed = False
            out.append(AssertionResult(parsed == a["expected"], f"parsed={parsed}"))
        elif t == "policy_directive":
            policy = parse_policy(inp["policy"])
            val = getattr(policy, a["field"], None)
            expected = a["value"]
            got = val.value if hasattr(val, "value") else val
            out.append(AssertionResult(got == expected, f"{a['field']}={got!r}"))
        elif t == "inheritance_valid":
            parent = parse_policy(inp["parent_policy"])
            child = parse_policy(inp["child_policy"])
            result = check_inheritance(parent, child)
            out.append(AssertionResult(result.valid == a["expected"], f"valid={result.valid} relaxations={result.relaxations}"))
        elif t == "inheritance_http_status":
            parent = parse_policy(inp["parent_policy"])
            child = parse_policy(inp["child_policy"])
            result = check_inheritance(parent, child)
            out.append(AssertionResult(result.http_status == a["expected"], f"http={result.http_status}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


def _build_chain_records(inp: dict[str, Any]) -> list[WindowChainRecord]:
    key = _MASTER_KEY
    records: list[WindowChainRecord] = []
    prev = ""
    windows = inp["windows"]
    tamper_idx = inp.get("tamper_window_index")
    for i, w in enumerate(windows):
        wh = build_window_hmac(
            WindowHmacInput(
                session_id=inp["session_id"],
                window_number=w["window_number"],
                timestamp=w["timestamp"],
                response_hash=w["response_hash"],
                dpe_report_hash=w["dpe_report_hash"],
                prev_window_hmac=prev,
            ),
            key,
        )
        response_hash = w["response_hash"]
        if tamper_idx is not None and i == tamper_idx:
            response_hash = inp["tamper_response_hash"]  # alter stored input, not hmac
        records.append(
            WindowChainRecord(
                session_id=inp["session_id"],
                window_number=w["window_number"],
                timestamp=w["timestamp"],
                response_hash=response_hash,
                dpe_report_hash=w["dpe_report_hash"],
                hmac=wh,
            )
        )
        prev = wh
    return records


def _run_hmac(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    for a in assertions:
        t = a["type"]
        if t in ("chain_integrity", "chain_broken_at"):
            records = _build_chain_records(inp)
            verification = verify_window_chain(records, _MASTER_KEY)
            if t == "chain_integrity":
                out.append(AssertionResult(verification.status.value == a["expected"], f"status={verification.status.value}"))
            else:
                out.append(AssertionResult(verification.broken_at_window == a["expected"], f"broken_at={verification.broken_at_window}"))
        elif t == "fan_in_deterministic":
            kwargs = dict(
                session_id=inp["session_id"],
                window_number=inp["window_number"],
                timestamp=inp["timestamp"],
                response_hash=inp["response_hash"],
                dpe_report_hash=inp["dpe_report_hash"],
                key=_MASTER_KEY,
            )
            h1 = build_fan_in_window_hmac(parent_hmacs=inp["parent_hmacs"], **kwargs)
            h2 = build_fan_in_window_hmac(parent_hmacs=list(reversed(inp["parent_hmacs"])), **kwargs)
            out.append(AssertionResult(h1 == h2 and h1.startswith("sha256:"), f"h1==h2={h1 == h2}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


def _issue_and_validate(inp: dict[str, Any]):
    now = 1_000_000_000
    lifetime = 3600
    token, _ = issue_token(
        session_id=inp["session_id"],
        master_key=_MASTER_KEY,
        window=inp.get("window_number", 1),
        safety_budget=inp.get("safety_budget", 1.0),
        lifetime=lifetime,
        now=now,
    )
    if inp.get("tamper_signature"):
        head, _, _ = token.partition(".")
        token = head + ".AAAA"
    validate_now = now + (lifetime + 60 if inp.get("expired") else 10)
    return validate_token(token, master_keys=_MASTER_KEY, now=validate_now)


def _run_session(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    out: list[AssertionResult] = []
    validation = _issue_and_validate(inp)
    for a in assertions:
        t = a["type"]
        if t == "token_status":
            out.append(AssertionResult(validation.status.value == a["expected"], f"status={validation.status.value}"))
        elif t == "token_http_status":
            out.append(AssertionResult(validation.http_status == a["expected"], f"http={validation.http_status}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


def _run_agent(inp: dict[str, Any], assertions: list[dict[str, Any]]) -> list[AssertionResult]:
    from crp.policy.model import RiskLevel

    out: list[AssertionResult] = []
    budget = AgentSafetyBudget(budget=inp["initial_budget"])
    last = budget.peek()
    for risk in inp["calls"]:
        last = budget.account(RiskLevel(risk))
    for a in assertions:
        t = a["type"]
        if t == "budget_after_lte":
            out.append(AssertionResult(budget.budget <= a["value"], f"budget={budget.budget}"))
        elif t == "budget_not_halted":
            out.append(AssertionResult(last.http_status != 451, f"http={last.http_status}"))
        elif t == "budget_http_status":
            out.append(AssertionResult(last.http_status == a["expected"], f"http={last.http_status}"))
        else:
            out.append(AssertionResult(False, f"unknown assertion {t}"))
    return out


_HANDLERS = {
    "headers": _run_headers,
    "dpe": _run_dpe,
    "safety_policy": _run_safety_policy,
    "hmac": _run_hmac,
    "session": _run_session,
    "agent": _run_agent,
}


def run_vector(vector: dict[str, Any]) -> VectorResult:
    """Execute a single test vector and return its result."""
    category = vector["category"]
    handler = _HANDLERS.get(category)
    result = VectorResult(
        test_id=vector["test_id"],
        category=category,
        conformance_level=vector.get("conformance_level", ""),
        passed=False,
    )
    if handler is None:
        result.failures.append(f"no handler for category {category}")
        return result
    try:
        assertion_results = handler(vector.get("input", {}), vector.get("assertions", []))
    except Exception as exc:  # noqa: BLE001 — surface any handler crash as failure
        result.failures.append(f"handler raised: {exc!r}")
        return result
    for a, ar in zip(vector.get("assertions", []), assertion_results):
        if not ar.ok:
            result.failures.append(f"{a.get('type')}: {ar.detail}")
    result.passed = not result.failures
    return result


def run_all(directory: Path | None = None) -> list[VectorResult]:
    """Run every loaded vector and return the results."""
    return [run_vector(v) for v in load_vectors(directory)]


__all__ = [
    "AssertionResult",
    "VectorResult",
    "load_vectors",
    "run_vector",
    "run_all",
    "VECTORS_DIR",
]

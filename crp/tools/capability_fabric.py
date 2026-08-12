# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tool Capability Fabric (TCF) — protocol-level tool selection (CRP-SPEC-050 §3–4).

The TCF is the registry + retrieval system that returns the MINIMAL relevant set of
capabilities for the current STL operation. Tool selection is a *protocol* function,
not an LLM function: the model never sees the full catalogue, only the 1–3 (or up to
5–7 on frontier) capabilities the protocol determined are relevant to THIS operation.

Selection algorithm (CRP-SPEC-050 §4.1):
    1. Retrieve capabilities whose operation_types include the current operation.
    2. Apply the policy pre-filter (§3.4).
    3. Score by semantic similarity, intent overlap, schema compatibility, inverse cost.
    4. Resolve dependencies (deps first) and mutual exclusions.
    5. Take the top-K, where K is bounded by the model's capability profile.

Embeddings are optional and supplied by the caller (the TCF is zero-dependency); when
absent, a deterministic lexical fallback is used.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from enum import Enum

from crp.stl.classifier import STLOperation
from crp.tools.descriptor import CapabilityDescriptor, SafetyClass
from crp.tools.profiles import CapabilityProfile, max_capabilities

logger = logging.getLogger("crp.tools.capability_fabric")


class GateDecision(str, Enum):
    """Outcome of mediating a single capability invocation (CRP-SPEC-050 §3.4).

    ``REQUIRE_APPROVAL`` never auto-executes: the caller must route the action
    through a human checkpoint (SPEC-033) before it may run.
    """

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class CapabilityInvocation:
    """A single proposed capability call, mediated before execution (CRP-SPEC-050 §3.4).

    ``data_labels`` declares the sensitivity labels of the data the invocation
    carries (egress taint); ``irreversible`` marks actions whose effects cannot
    be undone and therefore require human approval.
    """

    capability_id: str
    target: str = ""
    data_labels: set[str] = field(default_factory=set)
    irreversible: bool = False


@dataclass
class PolicyContext:
    """The active policy pre-filter for capability selection (CRP-SPEC-050 §3.4).

    Empty fields mean "no constraint". A capability with no ``data_residency`` or
    ``allowed_policy_domains`` is not restricted by those checks.

    ``authorised_scope`` and ``approved_sinks`` drive invocation-level mediation
    (:meth:`evaluate_invocation`): an invocation whose target falls outside the
    authorised scope is denied, and an invocation carrying ``data_labels`` may
    only target an approved sink (information-flow / egress taint).
    """

    blocked_safety_classes: set[SafetyClass] = field(default_factory=set)
    data_residency: str = ""                       # session jurisdiction, e.g. "EU"
    policy_domains: set[str] = field(default_factory=set)
    allowlist: set[str] | None = None              # if set, ONLY these ids are permitted
    blocklist: set[str] = field(default_factory=set)
    authorised_scope: set[str] = field(default_factory=set)   # targets the agent may act on
    approved_sinks: set[str] = field(default_factory=set)     # sinks labelled data may flow to

    def evaluate(self, cap: CapabilityDescriptor) -> tuple[bool, str]:
        """Return ``(allowed, reason)``; ``reason`` is the rejection cause when blocked."""
        if cap.capability_id in self.blocklist:
            return False, "blocklist"
        if self.allowlist is not None and cap.capability_id not in self.allowlist:
            return False, "not-in-allowlist"
        if cap.cost_profile.safety_class in self.blocked_safety_classes:
            return False, f"safety-class-blocked:{cap.cost_profile.safety_class.value}"
        if self.data_residency and cap.data_residency and cap.data_residency != self.data_residency:
            return False, f"data-residency-conflict:{cap.data_residency}!={self.data_residency}"
        if (
            self.policy_domains
            and cap.allowed_policy_domains
            and not (self.policy_domains & set(cap.allowed_policy_domains))
        ):
            return False, "policy-domain-mismatch"
        return True, ""

    def evaluate_invocation(
        self, invocation: CapabilityInvocation
    ) -> tuple[GateDecision, str]:
        """Mediate one proposed invocation before execution (fail-safe default deny).

        Rules, evaluated in order:
            1. Scope enforcement — if ``authorised_scope`` is declared and the
               invocation's target is outside it, DENY.
            2. Egress taint (information flow) — if the invocation carries
               ``data_labels``, its target must be an approved sink, else DENY.
            3. Irreversible actions REQUIRE_APPROVAL — they never auto-execute.

        Returns ``(decision, reason)``; ``reason`` is the machine-readable cause
        when the decision is not ``ALLOW``.
        """
        if self.authorised_scope and invocation.target not in self.authorised_scope:
            return GateDecision.DENY, f"out-of-scope:{invocation.target}"
        if invocation.data_labels and invocation.target not in self.approved_sinks:
            return GateDecision.DENY, f"egress-taint:{invocation.target}"
        if invocation.irreversible:
            return GateDecision.REQUIRE_APPROVAL, "irreversible-action"
        return GateDecision.ALLOW, ""


@dataclass
class ScoredCapability:
    """A capability with its selection score and the reason it was chosen."""

    descriptor: CapabilityDescriptor
    score: float
    reason: str = ""


@dataclass
class CapabilitySelection:
    """The result of a TCF selection for one operation (feeds the Tool Positioning Frame)."""

    operation: STLOperation
    profile: CapabilityProfile
    selected: list[ScoredCapability] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)  # (capability_id, reason)
    max_k: int = 0

    @property
    def capability_ids(self) -> list[str]:
        """Ids of the selected capabilities, in offered order."""
        return [s.descriptor.capability_id for s in self.selected]

    @property
    def selection_reason(self) -> str:
        """A compact human/audit-readable reason for this selection."""
        return (
            f"operation={self.operation.name}; profile={self.profile.value}; "
            f"offered={len(self.selected)}/{self.max_k}; rejected={len(self.rejected)}"
        )


# ── lexical / vector similarity helpers (zero-dependency) ───────────────────

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _lexical_overlap(query: str, cap: CapabilityDescriptor) -> float:
    """Jaccard-style overlap between the query and the capability's text surface."""
    q = _tokens(query)
    if not q:
        return 0.0
    surface = " ".join([cap.capability_id, cap.description, *cap.serves_intents])
    c = _tokens(surface)
    if not c:
        return 0.0
    inter = len(q & c)
    union = len(q | c)
    return inter / union if union else 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── The Fabric ──────────────────────────────────────────────────────────────


class ToolCapabilityFabric:
    """Registry + retrieval for capability descriptors (CRP-SPEC-050 §3)."""

    def __init__(self) -> None:
        self._by_id: dict[str, CapabilityDescriptor] = {}
        self._by_operation: dict[STLOperation, list[str]] = {}

    # -- registration --------------------------------------------------------

    def register(self, descriptor: CapabilityDescriptor) -> None:
        """Register (or replace) a capability. Raises ValueError if invalid."""
        errors = descriptor.validate()
        if errors:
            raise ValueError(
                f"Invalid capability {descriptor.capability_id!r}: {'; '.join(errors)}"
            )
        cid = descriptor.capability_id
        if cid in self._by_id:
            self._deindex(self._by_id[cid])
        self._by_id[cid] = descriptor
        for op in descriptor.operation_types:
            self._by_operation.setdefault(op, [])
            if cid not in self._by_operation[op]:
                self._by_operation[op].append(cid)
        logger.debug("Registered capability %r for ops %s", cid,
                     [o.name for o in descriptor.operation_types])

    def register_dict(self, data: dict) -> CapabilityDescriptor:
        """Register a capability from its JSON form; returns the parsed descriptor."""
        desc = CapabilityDescriptor.from_dict(data)
        self.register(desc)
        return desc

    def _deindex(self, descriptor: CapabilityDescriptor) -> None:
        for op in descriptor.operation_types:
            ids = self._by_operation.get(op)
            if ids and descriptor.capability_id in ids:
                ids.remove(descriptor.capability_id)

    def unregister(self, capability_id: str) -> None:
        """Remove a capability from the fabric."""
        desc = self._by_id.pop(capability_id, None)
        if desc:
            self._deindex(desc)

    # -- lookup --------------------------------------------------------------

    def get(self, capability_id: str) -> CapabilityDescriptor | None:
        """Return a registered capability by id, or None."""
        return self._by_id.get(capability_id)

    def all(self) -> list[CapabilityDescriptor]:
        """Return all registered capabilities."""
        return list(self._by_id.values())

    def retrieve(self, operation: STLOperation) -> list[CapabilityDescriptor]:
        """Return capabilities whose ``operation_types`` include the operation (§4.1.2)."""
        return [self._by_id[cid] for cid in self._by_operation.get(operation, [])]

    # -- scoring -------------------------------------------------------------

    def _score(
        self,
        cap: CapabilityDescriptor,
        query_text: str,
        query_embedding: list[float] | None,
        available_facts: set[str] | None,
    ) -> float:
        # semantic similarity (embeddings if available, else lexical)
        if query_embedding is not None and cap.embedding_vector is not None:
            semantic = _cosine(query_embedding, cap.embedding_vector)
        else:
            semantic = _lexical_overlap(query_text, cap)

        # intent overlap
        intent = 0.0
        if cap.serves_intents:
            q = query_text.lower()
            hits = sum(1 for it in cap.serves_intents if it.lower() in q)
            intent = hits / len(cap.serves_intents)

        # schema compatibility — can the CSO already satisfy the required inputs?
        schema = 1.0
        required = cap.required_inputs()
        if available_facts is not None and required:
            satisfied = sum(1 for r in required if r in available_facts)
            schema = satisfied / len(required)

        # inverse cost — small preference for cheaper capabilities
        cost = cap.cost_profile.tokens + cap.cost_profile.latency_ms
        inverse_cost = 1.0 / (1.0 + cost / 1000.0)

        return 0.5 * semantic + 0.2 * intent + 0.2 * schema + 0.1 * inverse_cost

    # -- selection -----------------------------------------------------------

    def select(
        self,
        operation: STLOperation,
        query_text: str = "",
        *,
        query_embedding: list[float] | None = None,
        profile: CapabilityProfile = CapabilityProfile.FRONTIER,
        policy: PolicyContext | None = None,
        available_facts: set[str] | None = None,
        k: int | None = None,
    ) -> CapabilitySelection:
        """Select the minimal positioned capability set for an operation (CRP-SPEC-050 §4.1)."""
        max_k = k if k is not None else max_capabilities(profile)
        result = CapabilitySelection(operation=operation, profile=profile, max_k=max_k)

        # 1–2. retrieve + policy pre-filter
        allowed: list[CapabilityDescriptor] = []
        for cap in self.retrieve(operation):
            if policy is not None:
                ok, reason = policy.evaluate(cap)
                if not ok:
                    result.rejected.append((cap.capability_id, reason))
                    continue
            allowed.append(cap)

        # 3. score + rank
        scored = [
            ScoredCapability(
                descriptor=cap,
                score=self._score(cap, query_text, query_embedding, available_facts),
            )
            for cap in allowed
        ]
        scored.sort(key=lambda s: s.score, reverse=True)

        # 4. dependency resolution + mutual exclusion, then top-K
        chosen: list[ScoredCapability] = []
        chosen_ids: set[str] = set()
        excluded: set[str] = set()

        def _try_add(sc: ScoredCapability, reason: str) -> bool:
            cid = sc.descriptor.capability_id
            if cid in chosen_ids or cid in excluded:
                return False
            if len(chosen) >= max_k:
                return False
            # pull in any allowed, registered dependencies first
            for dep_id in sc.descriptor.dependencies:
                if dep_id in chosen_ids or dep_id in excluded or len(chosen) >= max_k:
                    continue
                dep = self._by_id.get(dep_id)
                if dep is None:
                    continue
                if policy is not None and not policy.evaluate(dep)[0]:
                    continue
                dep_score = self._score(dep, query_text, query_embedding, available_facts)
                chosen.append(ScoredCapability(dep, dep_score, reason="dependency"))
                chosen_ids.add(dep_id)
                excluded.update(dep.mutually_exclusive_with)
            if len(chosen) >= max_k:
                return False
            sc.reason = reason
            chosen.append(sc)
            chosen_ids.add(cid)
            excluded.update(sc.descriptor.mutually_exclusive_with)
            return True

        for sc in scored:
            if len(chosen) >= max_k:
                break
            _try_add(sc, reason="scored")

        # record any candidates dropped purely by mutual exclusion / capacity
        for sc in scored:
            cid = sc.descriptor.capability_id
            if cid not in chosen_ids:
                why = "mutually-excluded" if cid in excluded else "frame-capacity"
                result.rejected.append((cid, why))

        result.selected = chosen
        logger.debug("TCF select %s", result.selection_reason)
        return result

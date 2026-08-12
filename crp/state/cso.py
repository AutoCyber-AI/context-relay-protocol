# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Cognitive State Object (CSO) — SPEC-030.

The CSO is the structured, verifiable, revisable state that is relayed between
continuation windows in place of the v3 text summary.

Unlike a text summary (lossy, reasoning-blind, irreversible, contractless), the
CSO carries:
  - **established_facts** with provenance — WHAT was learned and WHERE from
  - **decisions** with rationale — WHAT was decided and WHY
  - **open_questions** — what the next window must still address
  - **goal_state** — the universal window contract (§4)
  - **dependency_graph** — which decisions/facts depend on which (§3)
  - **HMAC chain** — tamper-evident link to predecessor (SPEC-011)

Preservation guarantee (§5.2): every still-valid prior fact MUST survive relay
or be repaired before forwarding. ``relay_cso()`` enforces this.

SPEC-030 §2.3 defines which prior mechanisms the CSO supersedes:
  - SPEC-004 text continuation summary → ``established_facts`` + ``decisions``
  - SPEC-024 ResidualTaskAnchor → ``goal_state.remaining``
  - SPEC-029 tool-result→decision link → ``decisions[].provenance_ref``
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ProvenanceKind(str, Enum):
    """Source of an established fact (SPEC-030 §2.1)."""

    CKF = "CKF"                 # retrieved from CKF graph
    TOOL = "TOOL"               # from tool / scratch buffer result
    CONVERSATION = "CONVERSATION"  # stated by the user in this session
    DERIVED = "DERIVED"         # inferred/derived during a window
    USER = "USER"               # explicit user assertion


class GoalMode(str, Enum):
    """Window execution mode (SPEC-030 §4.2)."""

    DOCUMENT = "DOCUMENT"
    CONVERSATION = "CONVERSATION"
    TOOL = "TOOL"
    AGENTIC = "AGENTIC"


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------


@dataclass
class EstablishedFact:
    """A single fact established and verified during a window (SPEC-030 §2.1).

    ``provenance_ref`` points to the specific CKF fact_id, scratch entry id,
    or turn id that is the source — enabling full traceability (SPEC-029 §8.2).
    """

    fact_id: str
    statement: str
    provenance: ProvenanceKind
    provenance_ref: str = ""        # fact_id / scratch_id / turn_id
    confidence: float = 1.0        # DPE attribution confidence 0.0–1.0
    window_origin: int = 0
    invalidated: bool = False      # True once dependency propagation marks this


@dataclass
class Decision:
    """A decision made in a window, with its full rationale (SPEC-030 §2.2).

    The ``rationale`` field is the single most important addition over text
    relay — it records WHY, not just what, so later windows can evaluate
    whether the reason still holds.
    """

    decision_id: str
    choice: str
    rationale: str                  # WHY — this is what text relay loses
    alternatives: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)  # fact_ids / decision_ids
    revisable: bool = True
    window_origin: int = 0
    revised_by: str = ""           # decision_id that supersedes this, if any
    provenance: ProvenanceKind = ProvenanceKind.DERIVED
    provenance_ref: str = ""       # scratch_id / tool result that informed this


@dataclass
class DependencyEdge:
    """Directed dependency edge in the reasoning graph (SPEC-030 §3)."""

    dependent: str    # decision_id or fact_id that depends on the other
    depends_on: str   # decision_id or fact_id being depended upon


@dataclass
class GoalState:
    """Universal window contract (SPEC-030 §4).

    Replaces mode-specific anchors (ResidualTaskAnchor for documents,
    Active Thread Summary for conversations) with one structure.
    """

    mode: GoalMode = GoalMode.DOCUMENT
    objective: str = ""
    remaining: list[str] = field(default_factory=list)  # sections / questions / sub-tasks
    success_test: str = ""
    completion: float = 0.0        # 0.0–1.0 progress toward overall goal


# ---------------------------------------------------------------------------
# The Cognitive State Object
# ---------------------------------------------------------------------------


@dataclass
class CognitiveStateObject:
    """The relay primitive that replaces the v3 text summary (SPEC-030 §2).

    Produced at the end of every window; consumed at the start of the next.
    Verified by ``relay_cso()`` before forwarding — preservation guaranteed.
    """

    cso_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    window_number: int = 0
    prior_cso_hash: str = ""       # HMAC link to predecessor (SPEC-011)
    created_at: float = field(default_factory=time.time)

    # Core payload
    established_facts: list[EstablishedFact] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    completed_operations: list[str] = field(default_factory=list)
    pending_operations: list[str] = field(default_factory=list)

    # Tool orchestration (SPEC-050 §8) — observations + preventive halts
    tool_observations: list[dict[str, Any]] = field(default_factory=list)
    preventive_halt_history: list[dict[str, Any]] = field(default_factory=list)

    # Structured relay (replaces prior mechanism fields)
    goal_state: GoalState = field(default_factory=GoalState)
    dependency_graph: list[DependencyEdge] = field(default_factory=list)

    # Integrity
    cso_hmac: str = ""
    verified: bool = False         # True once DPE has verified preservation

    # ---------------------------------------------------------------------------
    # Tool observations (SPEC-050 §6.3 / §8)
    # ---------------------------------------------------------------------------

    def add_tool_observation(self, observation: Any) -> EstablishedFact:
        """Store a tool observation and mirror it as a typed established fact.

        Accepts a ``ToolObservation`` (duck-typed via ``to_dict``) or a dict. The raw
        payload stays compact; the established fact carries ``provenance=TOOL`` so the
        observation enters the reasoning graph and survives state relay — this is what
        keeps a 300-tool report from losing its evidence (fixes the WASA M1 failure).
        """
        obs = observation.to_dict() if hasattr(observation, "to_dict") else dict(observation)
        self.tool_observations.append(obs)
        cap = str(obs.get("capability_id", "tool"))
        payload = obs.get("payload")
        rendered = json.dumps(payload, default=str) if isinstance(payload, (dict, list)) else str(payload)
        if len(rendered) > 200:
            rendered = rendered[:197] + "..."
        prov = obs.get("provenance", {})
        ref = prov.get("invocation_id", "") if isinstance(prov, dict) else ""
        fact = EstablishedFact(
            fact_id=str(obs.get("fact_id", f"f_obs_{uuid.uuid4().hex[:16]}")),
            statement=f"{cap} → {rendered}",
            provenance=ProvenanceKind.TOOL,
            provenance_ref=ref,
            window_origin=self.window_number,
        )
        self.established_facts.append(fact)
        return fact

    def record_preventive_halt(self, frame: dict[str, Any]) -> None:
        """Record a preventive-safety halt frame (CRP-SPEC-050 §10)."""
        self.preventive_halt_history.append(frame)

    # ---------------------------------------------------------------------------
    # Rendering
    # ---------------------------------------------------------------------------

    def to_prompt_context(self, max_facts: int = 10, max_decisions: int = 5) -> str:
        """Render the CSO as structured context for the next window.

        Args:
            max_facts: Maximum established facts to include.
            max_decisions: Maximum decisions to include.

        Returns:
            Compact, token-efficient representation — NOT a prose summary.
            The ``goal_state.remaining`` field is the forward-looking anchor
            (replacing ResidualTaskAnchor — SPEC-030 §2.3).
        """
        lines: list[str] = ["[CRP Cognitive State]"]

        # Goal state — what this next window must do
        if self.goal_state.objective:
            lines.append(f"Objective: {self.goal_state.objective}")
        if self.goal_state.remaining:
            rem = self.goal_state.remaining[:5]
            more = f" (+{len(self.goal_state.remaining) - 5} more)" if len(self.goal_state.remaining) > 5 else ""
            lines.append(f"Still to cover: {', '.join(rem)}{more}")

        # Key established facts (most recent first, skip invalidated)
        valid_facts = [f for f in self.established_facts if not f.invalidated]
        if valid_facts:
            lines.append("Established facts:")
            for f in valid_facts[-max_facts:]:
                conf = f" ({f.confidence:.0%})" if f.confidence < 0.95 else ""
                lines.append(f"  • {f.statement}{conf}")

        # Decisions with rationale (most recent first)
        if self.decisions:
            lines.append("Decisions made:")
            for d in self.decisions[-max_decisions:]:
                if not d.revised_by:
                    lines.append(f"  • {d.choice}")
                    if d.rationale:
                        lines.append(f"    Why: {d.rationale}")

        # Open questions for this window
        if self.open_questions:
            lines.append(f"Open questions: {'; '.join(self.open_questions[:3])}")

        # Active constraints
        if self.active_constraints:
            lines.append(f"Constraints: {'; '.join(self.active_constraints[:3])}")

        return "\n".join(lines)

    # ---------------------------------------------------------------------------
    # Preservation (SPEC-030 §5.2)
    # ---------------------------------------------------------------------------

    def preservation_score(self, prior: CognitiveStateObject) -> float:
        """Fraction of still-valid prior facts present in this CSO.

        Args:
            prior: Previous window's CSO.

        Returns:
            1.0 when all prior valid facts survive relay. A score < 1.0 means
            facts were silently dropped and the relay MUST repair.
        """
        prior_valid = [f for f in prior.established_facts if not f.invalidated]
        if not prior_valid:
            return 1.0
        prior_ids = {f.fact_id for f in prior_valid}
        our_ids = {f.fact_id for f in self.established_facts}
        preserved = len(prior_ids & our_ids)
        return preserved / len(prior_ids)

    def repair_from(self, prior: CognitiveStateObject) -> CognitiveStateObject:
        """Re-inject any dropped facts/decisions from prior CSO.

        Args:
            prior: Previous window's CSO.

        Returns:
            ``self`` (mutated in place for efficiency).

        Note:
            Called when ``preservation_score < 1.0`` — ensures no silent state loss.
        """
        our_fact_ids = {f.fact_id for f in self.established_facts}
        for f in prior.established_facts:
            if not f.invalidated and f.fact_id not in our_fact_ids:
                self.established_facts.append(f)
                our_fact_ids.add(f.fact_id)

        our_decision_ids = {d.decision_id for d in self.decisions}
        for d in prior.decisions:
            if not d.revised_by and d.decision_id not in our_decision_ids:
                self.decisions.append(d)
                our_decision_ids.add(d.decision_id)

        # Carry forward open questions not yet answered
        our_questions = set(self.open_questions)
        for q in prior.open_questions:
            if q not in our_questions:
                self.open_questions.append(q)
                our_questions.add(q)

        # Carry forward constraints
        our_constraints = set(self.active_constraints)
        for c in prior.active_constraints:
            if c not in our_constraints:
                self.active_constraints.append(c)

        return self

    # ---------------------------------------------------------------------------
    # Dependency invalidation (SPEC-030 §3.2)
    # ---------------------------------------------------------------------------

    def invalidate_fact(self, fact_id: str) -> set[str]:
        """Invalidate a fact and propagate to dependent decisions/facts.

        Args:
            fact_id: ID of the fact to invalidate.

        Returns:
            Set of all affected item IDs (the fact plus transitive dependents).
        """
        affected: set[str] = set()
        queue = [fact_id]
        while queue:
            node = queue.pop()
            for edge in self.dependency_graph:
                if edge.depends_on == node and edge.dependent not in affected:
                    affected.add(edge.dependent)
                    queue.append(edge.dependent)
        # Mark invalidated
        for f in self.established_facts:
            if f.fact_id == fact_id:
                f.invalidated = True
            elif f.fact_id in affected:
                f.invalidated = True
        for d in self.decisions:
            if d.decision_id in affected and d.revisable:
                d.revised_by = "__needs_revision__"
        return affected

    # ---------------------------------------------------------------------------
    # HMAC chain (SPEC-011)
    # ---------------------------------------------------------------------------

    def compute_hmac(self, key: bytes) -> str:
        """Compute tamper-evident HMAC over CSO content.

        Args:
            key: HMAC signing key.

        Returns:
            Hex-encoded HMAC-SHA256 digest over a canonical CSO payload.
        """
        payload = json.dumps({
            "cso_id": self.cso_id,
            "window_number": self.window_number,
            "prior_cso_hash": self.prior_cso_hash,
            "facts": [f.fact_id for f in self.established_facts],
            "decisions": [d.decision_id for d in self.decisions],
        }, sort_keys=True).encode()
        return hmac.new(key, payload, hashlib.sha256).hexdigest()

    def extend_hmac_chain(self, prior_hash: str, key: bytes) -> str:
        """Extend the HMAC chain: prior_hash → this window's hash.

        Args:
            prior_hash: HMAC of the previous CSO (empty string for window 1).
            key: HMAC signing key.

        Returns:
            The new HMAC to be stored as the next window's ``prior_hash``.

        Side effects:
            Sets ``self.prior_cso_hash`` and ``self.cso_hmac``.
        """
        self.prior_cso_hash = prior_hash
        self.cso_hmac = self.compute_hmac(key)
        return self.cso_hmac

    # ---------------------------------------------------------------------------
    # Serialisation helpers
    # ---------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a JSON-safe dict for session storage.

        Returns:
            Dict representation of the full CSO, including facts, decisions,
            goal state, dependency graph, and integrity fields.
        """
        return {
            "cso_id": self.cso_id,
            "window_number": self.window_number,
            "prior_cso_hash": self.prior_cso_hash,
            "created_at": self.created_at,
            "established_facts": [
                {
                    "fact_id": f.fact_id,
                    "statement": f.statement,
                    "provenance": f.provenance.value,
                    "provenance_ref": f.provenance_ref,
                    "confidence": f.confidence,
                    "window_origin": f.window_origin,
                    "invalidated": f.invalidated,
                }
                for f in self.established_facts
            ],
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "choice": d.choice,
                    "rationale": d.rationale,
                    "alternatives": d.alternatives,
                    "depends_on": d.depends_on,
                    "revisable": d.revisable,
                    "window_origin": d.window_origin,
                    "revised_by": d.revised_by,
                    "provenance": d.provenance.value,
                    "provenance_ref": d.provenance_ref,
                }
                for d in self.decisions
            ],
            "open_questions": self.open_questions,
            "active_constraints": self.active_constraints,
            "completed_operations": self.completed_operations,
            "pending_operations": self.pending_operations,
            "tool_observations": self.tool_observations,
            "preventive_halt_history": self.preventive_halt_history,
            "goal_state": {
                "mode": self.goal_state.mode.value,
                "objective": self.goal_state.objective,
                "remaining": self.goal_state.remaining,
                "success_test": self.goal_state.success_test,
                "completion": self.goal_state.completion,
            },
            "dependency_graph": [
                {"dependent": e.dependent, "depends_on": e.depends_on}
                for e in self.dependency_graph
            ],
            "cso_hmac": self.cso_hmac,
            "verified": self.verified,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitiveStateObject:
        """Restore a CSO from a serialised dict.

        Args:
            data: Dict produced by ``to_dict``.

        Returns:
            Reconstructed ``CognitiveStateObject``.
        """
        cso = cls(
            cso_id=data.get("cso_id", str(uuid.uuid4())),
            window_number=data.get("window_number", 0),
            prior_cso_hash=data.get("prior_cso_hash", ""),
            created_at=data.get("created_at", time.time()),
            open_questions=list(data.get("open_questions", [])),
            active_constraints=list(data.get("active_constraints", [])),
            completed_operations=list(data.get("completed_operations", [])),
            pending_operations=list(data.get("pending_operations", [])),
            tool_observations=list(data.get("tool_observations", [])),
            preventive_halt_history=list(data.get("preventive_halt_history", [])),
            cso_hmac=data.get("cso_hmac", ""),
            verified=data.get("verified", False),
        )
        for f in data.get("established_facts", []):
            cso.established_facts.append(EstablishedFact(
                fact_id=f["fact_id"],
                statement=f["statement"],
                provenance=ProvenanceKind(f.get("provenance", "DERIVED")),
                provenance_ref=f.get("provenance_ref", ""),
                confidence=f.get("confidence", 1.0),
                window_origin=f.get("window_origin", 0),
                invalidated=f.get("invalidated", False),
            ))
        for d in data.get("decisions", []):
            cso.decisions.append(Decision(
                decision_id=d["decision_id"],
                choice=d["choice"],
                rationale=d.get("rationale", ""),
                alternatives=list(d.get("alternatives", [])),
                depends_on=list(d.get("depends_on", [])),
                revisable=d.get("revisable", True),
                window_origin=d.get("window_origin", 0),
                revised_by=d.get("revised_by", ""),
                provenance=ProvenanceKind(d.get("provenance", "DERIVED")),
                provenance_ref=d.get("provenance_ref", ""),
            ))
        gs = data.get("goal_state", {})
        cso.goal_state = GoalState(
            mode=GoalMode(gs.get("mode", "DOCUMENT")),
            objective=gs.get("objective", ""),
            remaining=list(gs.get("remaining", [])),
            success_test=gs.get("success_test", ""),
            completion=gs.get("completion", 0.0),
        )
        for e in data.get("dependency_graph", []):
            cso.dependency_graph.append(DependencyEdge(
                dependent=e["dependent"],
                depends_on=e["depends_on"],
            ))
        return cso


# ---------------------------------------------------------------------------
# Extraction (lightweight — no heavy NLP dependencies)
# ---------------------------------------------------------------------------


def _simple_sentence_split(text: str) -> list[str]:
    """Split text into sentences without requiring NLP libraries.

    Args:
        text: Input text.

    Returns:
        List of sentences with at least four words each.
    """
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s for s in sentences if len(s.split()) >= 4]


def extract_cso(
    window_output: str,
    window_number: int,
    prior_cso: CognitiveStateObject | None = None,
    dpe_report: dict[str, Any] | None = None,
    goal_sections: list[str] | None = None,
) -> CognitiveStateObject:
    """Extract a CSO from window output (lightweight, no external NLP).

    For production use, the DPE's 13-stage analysis pipeline provides richer
    extraction. This function is the baseline extraction for CRP core (zero
    heavy dependencies).

    Args:
        window_output: Raw LLM output for the current window.
        window_number: Current window number.
        prior_cso: Optional previous window CSO to carry forward.
        dpe_report: Optional DPE report for richer extraction (currently advisory).
        goal_sections: Optional list of remaining goal sections.

    Returns:
        New ``CognitiveStateObject`` populated with extracted facts and goal state.

    Strategy:
        - Parse sentences as candidate facts.
        - Carry forward prior CSO's ``goal_state``, advancing completion.
        - Inherit ``open_questions`` and constraints unless resolved in output.
        - Mark ``window_number`` on all new facts/decisions.
    """
    cso = CognitiveStateObject(window_number=window_number)

    # ---- Extract facts from output ----
    sentences = _simple_sentence_split(window_output)
    # Keep only informational sentences (not questions, not imperatives)
    for i, sent in enumerate(sentences[:15]):  # cap at 15 per window
        if sent.endswith("?"):
            continue
        fact = EstablishedFact(
            fact_id=f"w{window_number}_f{i}",
            statement=sent[:200],  # cap length
            provenance=ProvenanceKind.DERIVED,
            confidence=0.85,
            window_origin=window_number,
        )
        cso.established_facts.append(fact)

    # ---- Goal state ----
    if prior_cso is not None and prior_cso.goal_state.remaining:
        remaining = list(prior_cso.goal_state.remaining)
        # Heuristically mark sections whose keywords appear in output
        output_lower = window_output.lower()
        still_remaining = []
        for section in remaining:
            if section.lower().replace("-", " ") not in output_lower:
                still_remaining.append(section)
        completed_count = len(prior_cso.goal_state.remaining) - len(still_remaining)
        total = len(prior_cso.goal_state.remaining) + len(prior_cso.goal_state.completed_operations or [])
        completion = completed_count / max(1, total)
        cso.goal_state = GoalState(
            mode=prior_cso.goal_state.mode,
            objective=prior_cso.goal_state.objective,
            remaining=still_remaining,
            success_test=prior_cso.goal_state.success_test,
            completion=min(1.0, (prior_cso.goal_state.completion or 0.0) + completion * 0.5),
        )
        cso.completed_operations = list(prior_cso.completed_operations)
    elif goal_sections:
        cso.goal_state = GoalState(
            objective="Complete all required sections",
            remaining=list(goal_sections),
        )

    # ---- Carry constraints forward ----
    if prior_cso is not None:
        cso.active_constraints = list(prior_cso.active_constraints)
        # Carry open questions not clearly answered
        for q in prior_cso.open_questions:
            q_lower = q.lower().replace("?", "").strip()
            if q_lower not in window_output.lower():
                cso.open_questions.append(q)

    return cso


# ---------------------------------------------------------------------------
# Relay (the core Round 2 function — replaces text summaries)
# ---------------------------------------------------------------------------


def relay_cso(
    prior_cso: CognitiveStateObject | None,
    window_output: str,
    window_number: int,
    dpe_report: dict[str, Any] | None = None,
    hmac_key: bytes | None = None,
    goal_sections: list[str] | None = None,
) -> CognitiveStateObject:
    """Relay the CSO from window N to window N+1 (SPEC-030 §5).

    Args:
        prior_cso: Previous window's CSO, if any.
        window_output: Raw LLM output for the current window.
        window_number: Current window number.
        dpe_report: Optional DPE report for richer extraction.
        hmac_key: Optional HMAC key for chain integrity.
        goal_sections: Optional list of remaining goal sections.

    Returns:
        Verified, complete CSO for the next window.

    Steps:
        1. Extract new CSO from ``window_output``.
        2. Check preservation score against prior CSO.
        3. If score < 1.0 → repair (re-inject dropped facts/decisions).
        4. Extend HMAC chain.
        5. Mark ``verified=True``.
        6. Return verified CSO for next window.

    Note:
        This replaces the v3 text summary continuation approach:
        ``continuation_context = relay_cso(...).to_prompt_context()``.
    """
    new_cso = extract_cso(
        window_output=window_output,
        window_number=window_number,
        prior_cso=prior_cso,
        dpe_report=dpe_report,
        goal_sections=goal_sections,
    )

    # Preservation check
    if prior_cso is not None:
        score = new_cso.preservation_score(prior_cso)
        if score < 1.0:
            new_cso.repair_from(prior_cso)

    # HMAC chain
    if hmac_key:
        prior_hash = prior_cso.cso_hmac if prior_cso else ""
        new_cso.extend_hmac_chain(prior_hash, hmac_key)

    new_cso.verified = True
    return new_cso


# ---------------------------------------------------------------------------
# Public preservation report (for CRP-Relay-Preservation header)
# ---------------------------------------------------------------------------


def preservation_report(prior: CognitiveStateObject, current: CognitiveStateObject) -> dict[str, Any]:
    """Generate data for CRP-Relay-Preservation header (SPEC-030 §5.3).

    Args:
        prior: Previous window's CSO.
        current: Current window's CSO.

    Returns:
        Dict with preservation score, repaired count, and fact counts.
    """
    score = current.preservation_score(prior)
    prior_valid = [f for f in prior.established_facts if not f.invalidated]
    our_ids = {f.fact_id for f in current.established_facts}
    repaired = [f.fact_id for f in prior_valid if f.fact_id not in our_ids]
    return {
        "score": round(score, 4),
        "repaired": len(repaired),
        "prior_facts": len(prior_valid),
        "current_facts": len([f for f in current.established_facts if not f.invalidated]),
    }

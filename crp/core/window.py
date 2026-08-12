# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""TaskWindow, WindowDAG, and window lifecycle types (§2.4, §5, SPEC-004).

Defines the provenance DAG, window state machine, context-transfer types,
and budget helpers used by the orchestrator and continuation manager.

Window lifecycle:
    CREATED → ASSEMBLED → DISPATCHED → GENERATING → COMPLETED → EXTRACTED
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Window lifecycle
# ---------------------------------------------------------------------------

class WindowState(enum.Enum):
    """Lifecycle states — transitions are strictly forward-only."""

    CREATED = "CREATED"
    ASSEMBLED = "ASSEMBLED"
    DISPATCHED = "DISPATCHED"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    EXTRACTED = "EXTRACTED"


_ALLOWED_TRANSITIONS: dict[WindowState, WindowState] = {
    WindowState.CREATED: WindowState.ASSEMBLED,
    WindowState.ASSEMBLED: WindowState.DISPATCHED,
    WindowState.DISPATCHED: WindowState.GENERATING,
    WindowState.GENERATING: WindowState.COMPLETED,
    WindowState.COMPLETED: WindowState.EXTRACTED,
}


# ---------------------------------------------------------------------------
# DAG patterns & context-transfer types (CRP-SPEC-004 §3, §8)
# ---------------------------------------------------------------------------

class WindowPattern(str, enum.Enum):
    """How a window relates to its parent(s) in the DAG (§3.1)."""

    LINEAR = "LINEAR"
    """Single parent, single child chain."""
    FAN_OUT = "FAN_OUT"
    """One parent spawns multiple parallel children."""
    FAN_IN = "FAN_IN"
    """Multiple parents merge into one child."""
    BRANCH = "BRANCH"
    """Exploratory branch that may later merge or terminate."""


class TransferType(str, enum.Enum):
    """What information flows from a parent window to a child (§8.1)."""

    FULL_CONTEXT = "FULL_CONTEXT"
    """Complete parent response plus envelope."""
    SUMMARY = "SUMMARY"
    """Compressed summary (default)."""
    FACTS_ONLY = "FACTS_ONLY"
    """Deferred facts only, no response content."""
    RESULT_ONLY = "RESULT_ONLY"
    """Final answer only (fan-in synthesis)."""


@dataclass
class WindowEdge:
    """A directed context-flow edge from a parent to a child window (§3.2).

    Attributes:
        source_id: Parent window ID.
        target_id: Child window ID.
        transfer_type: Mode of information transfer.
        transferred_tokens: Tokens carried across this edge.
        summary_hash: Hash of the transferred summary for integrity checks.
    """

    source_id: str
    target_id: str
    transfer_type: TransferType = TransferType.SUMMARY
    transferred_tokens: int = 0
    summary_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialise the edge to a JSON-compatible dict."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "transfer_type": self.transfer_type.value,
            "transferred_tokens": self.transferred_tokens,
            "summary_hash": self.summary_hash,
        }


def select_transfer_type(
    *,
    available_budget: int,
    parent_response_tokens: int,
    summary_tokens: int,
    deferred_facts_tokens: int,
    reserve_fraction: float = 0.60,
) -> TransferType:
    """Select a transfer type from token-budget pressure (§8.2).

    The ``reserve_fraction`` (default 0.60) leaves 40% of the budget for new
    facts specific to the child's query.

    Args:
        available_budget: Tokens available in the child window.
        parent_response_tokens: Tokens of the full parent response.
        summary_tokens: Tokens of a compressed parent summary.
        deferred_facts_tokens: Tokens of deferred facts.
        reserve_fraction: Fraction of budget that may be spent on context relay.

    Returns:
        The most complete transfer type that fits within the reserved budget.
    """
    ceiling = max(0.0, available_budget * reserve_fraction)
    if parent_response_tokens + deferred_facts_tokens <= ceiling:
        return TransferType.FULL_CONTEXT
    if summary_tokens + deferred_facts_tokens <= ceiling:
        return TransferType.SUMMARY
    if deferred_facts_tokens <= ceiling:
        return TransferType.FACTS_ONLY
    return TransferType.RESULT_ONLY


def partition_fan_in_budget(parent_budgets: list[float]) -> float:
    """Fan-in safety budget is the MINIMUM of all parents (§7.3.4, §6.4).

    Args:
        parent_budgets: Envelope budgets of each parent window.

    Returns:
        The conservative minimum budget, or 0.0 if no parents exist.
    """
    return min(parent_budgets) if parent_budgets else 0.0


# ---------------------------------------------------------------------------
# WindowNode — one node in the provenance DAG
# ---------------------------------------------------------------------------

@dataclass
class WindowNode:
    """Represents a single task window in the DAG (§2.4)."""

    window_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    state: WindowState = WindowState.CREATED

    # DAG edges
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)

    # Fact tracking
    facts_produced: list[str] = field(default_factory=list)
    facts_consumed: list[str] = field(default_factory=list)

    # Timestamps
    created_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    extraction_complete_at: float | None = None

    # Content hashes (BLAKE3 when available, else sha256)
    system_prompt_hash: str = ""
    task_input_hash: str = ""
    raw_output_id: str = ""
    finish_reason: str = ""
    continuation_index: int = 0

    # DAG / provenance metadata (CRP-SPEC-004 §3.1)
    window_number: int = 0
    pattern: WindowPattern = WindowPattern.LINEAR
    continuation_id: str = ""
    envelope_etag: str = ""
    quality_tier: str = ""
    risk_level: str = ""
    safety_budget: float = 0.0
    response_hash: str = ""
    dpe_report_hash: str = ""
    hmac: str = ""
    hmac_chain_tip: str = ""

    def advance(self, to_state: WindowState) -> None:
        """Transition to a new state, enforcing the forward-only invariant.

        Args:
            to_state: Target state.

        Raises:
            ValueError: If the transition is not allowed.
        """
        allowed = _ALLOWED_TRANSITIONS.get(self.state)
        if allowed is None or allowed != to_state:
            msg = f"Invalid transition {self.state.value} → {to_state.value}"
            raise ValueError(msg)
        self.state = to_state
        if to_state == WindowState.COMPLETED:
            self.completed_at = time.time()
        elif to_state == WindowState.EXTRACTED:
            self.extraction_complete_at = time.time()


# ---------------------------------------------------------------------------
# WindowMetrics — per-window telemetry (§5, §3.7)
# ---------------------------------------------------------------------------

@dataclass
class WindowMetrics:
    """Recorded per window for telemetry.jsonl output."""

    # Identification
    window_id: str = ""
    chain_position: int = 0
    parent_window: str | None = None

    # Context utilisation
    system_tokens: int = 0
    task_tokens: int = 0
    envelope_tokens: int = 0
    envelope_budget: int = 0
    saturation: float = 0.0
    generation_reserve: int = 0

    # Generation
    generation_tokens: int = 0
    generation_speed: float = 0.0
    wall_time_ms: int = 0

    # Extraction
    extraction_stage_used: str = ""
    facts_extracted: int = 0

    # Information flow
    marginal_gain: float = 0.0
    gap_coverage: float = 0.0

    # Continuation
    continuation_triggered: bool = False
    continuation_index: int = 0
    finish_reason: str = ""

    # Resource
    ram_available_mb: int = 0
    ram_used_by_crp_mb: int = 0
    envelope_latency_ms: float = 0.0
    extraction_latency_ms: float = 0.0
    pressure_level: str = "none"

    # Reasoning / thinking model telemetry
    reasoning_tokens: int = 0  # tokens used for chain-of-thought reasoning

    # CRP overhead breakdown (ms)
    total_dispatch_ms: float = 0.0           # wall clock for entire dispatch()
    total_llm_ms: float = 0.0               # sum of all LLM calls (primary + continuation)
    total_extraction_ms: float = 0.0         # sum of all extraction pipeline runs
    total_envelope_ms: float = 0.0           # sum of all envelope builds
    crp_overhead_ms: float = 0.0             # total_dispatch - total_llm
    crp_overhead_pct: float = 0.0            # (overhead / total_dispatch) * 100

    # Per-continuation-window telemetry
    continuation_windows_detail: list[dict[str, Any]] = field(default_factory=list)

    # Gap / flow metrics (from continuation manager)
    final_gap_score: float = 0.0             # last gap_score from continuation
    sections_covered: int = 0                # unique sections detected
    total_output_tokens: int = 0             # sum of all window output tokens

    # Tool-mediated context relay telemetry (§20)
    tool_rounds: int = 0                      # number of tool call round-trips
    tool_tokens_served: int = 0               # total tokens served via tool calls
    tool_calls_detail: list[dict[str, Any]] = field(default_factory=list)

    # Novel relay strategy telemetry (§21)
    relay_strategy: str = ""                  # "reflexive", "progressive", "stream_augmented", or ""
    reflexive_passes: int = 0                 # number of LLM passes in reflexive mode
    reflexive_corrections: int = 0            # corrections applied in reflexive mode
    reflexive_coverage: float = 0.0           # KB coverage score (0-1)
    progressive_index_entries: int = 0        # entries in context index
    progressive_index_tokens: int = 0         # tokens used by index
    progressive_detail_entries: int = 0       # entries expanded to full detail
    progressive_detail_tokens: int = 0        # tokens used by expanded details
    stream_augment_injections: int = 0        # real-time context injections
    stream_augment_injection_tokens: int = 0  # tokens injected mid-stream

    # Agentic / LLM-in-the-loop telemetry (§22)
    agentic_cognitive_calls: int = 0          # total facilitator LLM calls
    agentic_cognitive_tokens: int = 0         # total tokens spent on cognitive calls
    agentic_cognitive_ms: float = 0.0         # total ms for cognitive calls
    agentic_task_complexity: str = ""         # detected task complexity
    agentic_strategy_chosen: str = ""         # strategy LLM selected
    agentic_strategy_confidence: float = 0.0  # routing confidence
    agentic_synthesis_insights: int = 0       # insights produced by fact synthesis
    agentic_evaluation_grade: str = ""        # output evaluation grade
    agentic_revision_rounds: int = 0          # times output was revised
    agentic_curation_actions: int = 0         # memory curation actions taken
    agentic_plan_steps: int = 0              # execution plan steps planned

    # Adaptive resource allocation telemetry (§resource-alloc)
    adaptive_ewma_overhead_pct: float = 0.0   # EWMA-smoothed overhead %
    adaptive_features_shed: int = 0            # features currently shed
    adaptive_stages_disabled: str = ""         # comma-separated disabled stages
    adaptive_consecutive_over: int = 0         # consecutive windows over cap

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a flat dict for JSONL telemetry output."""
        return {
            "window_id": self.window_id,
            "chain_position": self.chain_position,
            "parent_window": self.parent_window,
            "system_tokens": self.system_tokens,
            "task_tokens": self.task_tokens,
            "envelope_tokens": self.envelope_tokens,
            "envelope_budget": self.envelope_budget,
            "saturation": self.saturation,
            "generation_reserve": self.generation_reserve,
            "generation_tokens": self.generation_tokens,
            "generation_speed": self.generation_speed,
            "wall_time_ms": self.wall_time_ms,
            "extraction_stage_used": self.extraction_stage_used,
            "facts_extracted": self.facts_extracted,
            "marginal_gain": self.marginal_gain,
            "gap_coverage": self.gap_coverage,
            "continuation_triggered": self.continuation_triggered,
            "continuation_index": self.continuation_index,
            "finish_reason": self.finish_reason,
            "ram_available_mb": self.ram_available_mb,
            "ram_used_by_crp_mb": self.ram_used_by_crp_mb,
            "envelope_latency_ms": self.envelope_latency_ms,
            "extraction_latency_ms": self.extraction_latency_ms,
            "pressure_level": self.pressure_level,
            # Reasoning / thinking
            "reasoning_tokens": self.reasoning_tokens,
            # CRP overhead
            "total_dispatch_ms": self.total_dispatch_ms,
            "total_llm_ms": self.total_llm_ms,
            "total_extraction_ms": self.total_extraction_ms,
            "total_envelope_ms": self.total_envelope_ms,
            "crp_overhead_ms": self.crp_overhead_ms,
            "crp_overhead_pct": round(self.crp_overhead_pct, 1),
            # Per-window continuation detail
            "continuation_windows_detail": self.continuation_windows_detail,
            # Gap / flow
            "final_gap_score": self.final_gap_score,
            "sections_covered": self.sections_covered,
            "total_output_tokens": self.total_output_tokens,
            # Tool-mediated context relay (§20)
            "tool_rounds": self.tool_rounds,
            "tool_tokens_served": self.tool_tokens_served,
            "tool_calls_detail": self.tool_calls_detail,
            # Novel relay strategies (§21)
            "relay_strategy": self.relay_strategy,
            "reflexive_passes": self.reflexive_passes,
            "reflexive_corrections": self.reflexive_corrections,
            "reflexive_coverage": self.reflexive_coverage,
            "progressive_index_entries": self.progressive_index_entries,
            "progressive_index_tokens": self.progressive_index_tokens,
            "progressive_detail_entries": self.progressive_detail_entries,
            "progressive_detail_tokens": self.progressive_detail_tokens,
            "stream_augment_injections": self.stream_augment_injections,
            "stream_augment_injection_tokens": self.stream_augment_injection_tokens,
            # Agentic / LLM-in-the-loop (§22)
            "agentic_cognitive_calls": self.agentic_cognitive_calls,
            "agentic_cognitive_tokens": self.agentic_cognitive_tokens,
            "agentic_cognitive_ms": round(self.agentic_cognitive_ms, 1),
            "agentic_task_complexity": self.agentic_task_complexity,
            "agentic_strategy_chosen": self.agentic_strategy_chosen,
            "agentic_strategy_confidence": round(self.agentic_strategy_confidence, 3),
            "agentic_synthesis_insights": self.agentic_synthesis_insights,
            "agentic_evaluation_grade": self.agentic_evaluation_grade,
            "agentic_revision_rounds": self.agentic_revision_rounds,
            "agentic_curation_actions": self.agentic_curation_actions,
            "agentic_plan_steps": self.agentic_plan_steps,
            # Adaptive resource allocation
            "adaptive_ewma_overhead_pct": round(self.adaptive_ewma_overhead_pct, 1),
            "adaptive_features_shed": self.adaptive_features_shed,
            "adaptive_stages_disabled": self.adaptive_stages_disabled,
            "adaptive_consecutive_over": self.adaptive_consecutive_over,
        }


# ---------------------------------------------------------------------------
# WindowDAG — provenance graph
# ---------------------------------------------------------------------------

class WindowDAG:
    """Tracks the provenance graph of all windows in a session (§2.4, Axiom 7)."""

    def __init__(self) -> None:
        """Create an empty DAG."""
        self._nodes: dict[str, WindowNode] = {}
        self._edges: list[WindowEdge] = []

    @property
    def nodes(self) -> dict[str, WindowNode]:
        """Mapping from window ID to ``WindowNode``."""
        return self._nodes

    @property
    def edges(self) -> list[WindowEdge]:
        """List of all context-flow edges."""
        return self._edges

    def add_node(self, node: WindowNode) -> None:
        """Register a created window.

        Args:
            node: Window node to add.

        Raises:
            ValueError: If the window ID already exists.
        """
        if node.window_id in self._nodes:
            msg = f"Duplicate window_id: {node.window_id}"
            raise ValueError(msg)
        self._nodes[node.window_id] = node

    def set_parent(self, child_id: str, parent_id: str) -> None:
        """Declare a provenance edge: parent contributed facts to child.

        Args:
            child_id: Child window ID.
            parent_id: Parent window ID.
        """
        child = self._nodes[child_id]
        parent = self._nodes[parent_id]
        if parent_id not in child.parent_ids:
            child.parent_ids.append(parent_id)
        if child_id not in parent.child_ids:
            parent.child_ids.append(child_id)

    def add_edge(self, edge: WindowEdge) -> None:
        """Record a context-flow edge with transfer metadata (§3.2).

        Establishes the parent/child relationship and rejects edges that would
        introduce a cycle, preserving the acyclic invariant (§3.3).
        """
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            msg = "Both source and target windows must exist before adding an edge"
            raise ValueError(msg)
        if edge.source_id == edge.target_id or edge.source_id in self.descendants(
            edge.target_id
        ):
            msg = (
                f"Edge {edge.source_id} -> {edge.target_id} would create a cycle"
            )
            raise ValueError(msg)
        self.set_parent(edge.target_id, edge.source_id)
        self._edges.append(edge)

    def descendants(self, window_id: str) -> set[str]:
        """Return all transitive descendant window IDs.

        Args:
            window_id: Window to descend from.

        Returns:
            Set of all descendant window IDs (transitive children).
        """
        visited: set[str] = set()
        node = self._nodes.get(window_id)
        if node is None:
            return visited
        stack = list(node.child_ids)
        while stack:
            cid = stack.pop()
            if cid not in visited:
                visited.add(cid)
                stack.extend(self._nodes[cid].child_ids)
        return visited

    def get(self, window_id: str) -> WindowNode:
        """Return the ``WindowNode`` for ``window_id``."""
        return self._nodes[window_id]

    def roots(self) -> list[WindowNode]:
        """Return windows with no parents (initial windows)."""
        return [n for n in self._nodes.values() if not n.parent_ids]

    def leaves(self) -> list[WindowNode]:
        """Return windows with no children (terminal windows)."""
        return [n for n in self._nodes.values() if not n.child_ids]

    def ancestors(self, window_id: str) -> set[str]:
        """Return all transitive ancestor window IDs.

        Args:
            window_id: Window to ascend from.

        Returns:
            Set of all ancestor window IDs (transitive parents).
        """
        visited: set[str] = set()
        stack = list(self._nodes[window_id].parent_ids)
        while stack:
            pid = stack.pop()
            if pid not in visited:
                visited.add(pid)
                stack.extend(self._nodes[pid].parent_ids)
        return visited

    def window_count(self) -> int:
        """Return the number of windows in the DAG."""
        return len(self._nodes)

    def lineage(self, window_id: str) -> list[str]:
        """Return the DAG path from a root to *window_id* (CRP-SPEC-004 §14.2).

        Follows the first parent at each step; suitable for emitting
        ``CRP-Provenance-Window-Lineage`` (``root -> ... -> current``).
        """
        path: list[str] = []
        current: str | None = window_id
        seen: set[str] = set()
        while current is not None and current not in seen:
            seen.add(current)
            path.append(current)
            node = self._nodes.get(current)
            current = node.parent_ids[0] if node and node.parent_ids else None
        path.reverse()
        return path

    def detect_cycle(self) -> bool:
        """Return True if the graph contains a cycle (violates §3.3).

        Uses a three-colour DFS over all nodes.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {wid: WHITE for wid in self._nodes}

        def visit(wid: str) -> bool:
            """Execute visit and return the result.
            
                Args:
                    wid (str): The wid value.
            
                Returns:
                    ``bool``.
            """
            colour[wid] = GREY
            for cid in self._nodes[wid].child_ids:
                if colour.get(cid) == GREY:
                    return True
                if colour.get(cid) == WHITE and visit(cid):
                    return True
            colour[wid] = BLACK
            return False

        return any(colour[wid] == WHITE and visit(wid) for wid in self._nodes)

    def clear(self) -> None:
        """Remove all nodes and edges (session reset)."""
        self._nodes.clear()
        self._edges.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def resolve_generation_reserve(
    max_output_tokens: int | None,
    provider_max_output: int | None,
    context_window: int,
    is_thinking_model: bool = False,
) -> int:
    """Determine generation reserve ``G`` by 3-layer precedence (§2.1).

    Args:
        max_output_tokens: User-specified output limit (highest precedence).
        provider_max_output: Provider-reported output limit.
        context_window: Model context window size.
        is_thinking_model: Whether the model uses internal reasoning tokens.

    Returns:
        The resolved generation reserve in tokens.

    Layer 1: User explicit (TaskIntent.max_output_tokens)
    Layer 2: Provider reported (LLMProvider.max_output_tokens)
    Layer 3: Conservative default scaled to the context window.

    Small-context models (4K / 8K) cannot afford a full C//4 generation
    reserve because it leaves almost no room for the envelope. The
    continuation manager stitches multi-window answers together, so each
    individual window only needs a modest generation budget:

      * C <= 4096  → 384 tokens
      * C <= 8192  → 768 tokens
      * otherwise  → min(C // 4, 16384)

    For thinking models (qwen3, deepseek-r1, o1, etc.) the reserve is
    doubled because the model spends a significant portion of tokens on
    internal reasoning_content before producing final output.
    """
    if max_output_tokens is not None and max_output_tokens > 0:
        g = max_output_tokens
    elif provider_max_output is not None and provider_max_output > 0:
        g = provider_max_output
    else:
        g = min(context_window // 4, 16384)

    # Small-context ceiling: never reserve so much that the envelope
    # disappears. Continuation will recover the full answer across windows.
    if context_window <= 4096:
        g = min(g, 384)
    elif context_window <= 8192:
        g = min(g, 768)

    if is_thinking_model:
        g = min(g * 2, context_window // 2)

    return max(g, 1)


def compute_envelope_budget(
    context_window: int,
    system_tokens: int,
    task_tokens: int,
    generation_reserve: int,
) -> int:
    """Compute ``E = C - S - T - G`` (§2.1, Axiom 2).

    Args:
        context_window: Model context window size ``C``.
        system_tokens: Tokens consumed by the system prompt ``S``.
        task_tokens: Tokens consumed by the task input ``T``.
        generation_reserve: Tokens reserved for generation ``G``.

    Returns:
        Non-negative envelope budget ``E``.
    """
    budget = context_window - system_tokens - task_tokens - generation_reserve
    return max(budget, 0)

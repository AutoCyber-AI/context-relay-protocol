# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Tool-mediated context relay — pull-based architecture (§20).

Instead of pre-loading ALL context into the prompt (push model), CRP
exposes its knowledge stores as callable tools.  The LLM requests
context on demand during generation, consuming only what it needs.

This is fundamentally different from RAG/prompt injection:
- **Push (old)**: Pre-compute all context → stuff into prompt → generate
- **Pull (new)**: Give LLM task + tools → LLM decides what it needs → CRP serves on demand

The module provides:
1. Tool definitions in OpenAI-compatible format
2. A ContextToolExecutor that routes tool calls to CKF/WarmStore
3. Integration with the iterative dispatch loop in the orchestrator
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from crp.ckf.fabric import ContextualKnowledgeFabric
    from crp.state.warm_store import WarmStateStore

logger = logging.getLogger("crp.context_tools")


# ── Tool call data structures ──────────────────────────────────────────

@dataclass
class ToolCall:
    """A single tool call extracted from an LLM response."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call."""
    tool_call_id: str
    name: str
    content: str
    tokens_used: int = 0


# ── Tool definitions (OpenAI function-calling format) ──────────────────

CRP_CONTEXT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "crp_retrieve_context",
            "description": (
                "Search for verified context and facts relevant to a query. "
                "Returns ranked facts from the CRP knowledge base. Use this "
                "when you need specific information, data, or evidence to "
                "support your response."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "What context you need. Be specific about the "
                            "topic, concept, or claim you want facts about."
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of facts to return.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crp_get_document_structure",
            "description": (
                "Get the current document structure and progress: what sections "
                "have been written, what remains, the document outline and map. "
                "Use this to understand the overall state of the document and "
                "plan your continuation."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crp_check_facts",
            "description": (
                "Verify a factual claim against the verified knowledge base. "
                "Returns matching or contradicting facts. Use this to ensure "
                "accuracy before making factual statements."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "claim": {
                        "type": "string",
                        "description": "The factual claim to verify.",
                    },
                },
                "required": ["claim"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crp_get_related_facts",
            "description": (
                "Given a fact ID or topic, retrieve related facts via graph "
                "traversal. Use this to explore connections between concepts "
                "and find supporting evidence."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic or concept to find related facts for.",
                    },
                    "max_hops": {
                        "type": "integer",
                        "description": "How many relationship hops to traverse (1-3).",
                        "default": 2,
                    },
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crp_get_continuation_state",
            "description": (
                "Get the continuation state: what has been completed, what "
                "gaps remain, requirement coverage, and directives for what "
                "to write next. Use this to understand your mission and what "
                "the document still needs."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


# ── Tool name set for validation ───────────────────────────────────────

CRP_TOOL_NAMES: frozenset[str] = frozenset(
    t["function"]["name"] for t in CRP_CONTEXT_TOOLS
)


# ── Context Tool Executor ──────────────────────────────────────────────

class ContextToolExecutor:
    """Routes tool calls to CRP subsystems and returns results.

    Wired to:
    - WarmStateStore: ranked facts, structural state, fact lookup
    - CKF: semantic/graph retrieval, community queries
    - Embedding function: for semantic search
    - Continuation state: gap analysis, directives
    """

    # Safety: cap tokens returned per tool call to prevent context overflow
    MAX_RESULT_TOKENS: int = 2000

    def __init__(
        self,
        warm_store: WarmStateStore,
        ckf: ContextualKnowledgeFabric,
        count_tokens: Callable[[str], int],
        embed_fn: Callable[[str], list[float]] | None = None,
        continuation_state: dict[str, Any] | None = None,
    ) -> None:
        self._warm_store = warm_store
        self._ckf = ckf
        self._count_tokens = count_tokens
        self._embed_fn = embed_fn
        self._continuation_state = continuation_state or {}
        self._calls_executed: int = 0
        self._total_tokens_served: int = 0

    @property
    def calls_executed(self) -> int:
        """Return the calls executed."""
        return self._calls_executed

    @property
    def total_tokens_served(self) -> int:
        """Return the total tokens served."""
        return self._total_tokens_served

    def update_continuation_state(self, state: dict[str, Any]) -> None:
        """Update continuation state (called between windows)."""
        self._continuation_state = state

    def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a single tool call and return the result."""
        self._calls_executed += 1

        handler = {
            "crp_retrieve_context": self._handle_retrieve_context,
            "crp_get_document_structure": self._handle_get_document_structure,
            "crp_check_facts": self._handle_check_facts,
            "crp_get_related_facts": self._handle_get_related_facts,
            "crp_get_continuation_state": self._handle_get_continuation_state,
        }.get(tool_call.name)

        if handler is None:
            logger.warning("Unknown tool call: %s", tool_call.name)
            content = json.dumps({"error": f"Unknown tool: {tool_call.name}"})
            return ToolResult(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=content,
            )

        try:
            content = handler(tool_call.arguments)
        except Exception as exc:
            logger.error("Tool %s failed: %s", tool_call.name, exc)
            content = json.dumps({"error": f"Tool execution failed: {exc}"})

        tokens = self._count_tokens(content)
        self._total_tokens_served += tokens

        logger.info(
            "Tool %s executed: %d tokens served (total: %d across %d calls)",
            tool_call.name, tokens, self._total_tokens_served, self._calls_executed,
        )

        return ToolResult(
            tool_call_id=tool_call.id,
            name=tool_call.name,
            content=content,
            tokens_used=tokens,
        )

    def execute_batch(self, tool_calls: list[ToolCall]) -> list[ToolResult]:
        """Execute multiple tool calls and return results."""
        return [self.execute(tc) for tc in tool_calls]

    # ── Individual tool handlers ───────────────────────────────────────

    def _handle_retrieve_context(self, args: dict[str, Any]) -> str:
        """Search WarmStore + CKF for relevant facts."""
        query = args.get("query", "")
        max_results = min(args.get("max_results", 5), 20)  # Cap at 20

        if not query:
            return json.dumps({"facts": [], "note": "Empty query"})

        facts_out: list[dict[str, str]] = []
        token_budget = self.MAX_RESULT_TOKENS

        # Layer 1: WarmStore ranked facts filtered by text relevance
        ranked = self._warm_store.get_ranked_facts(limit=max_results * 3)
        query_lower = query.lower()
        query_terms = set(query_lower.split())

        # Score facts by term overlap with query
        scored: list[tuple[float, Any]] = []
        for f in ranked:
            text_lower = f.text.lower()
            term_hits = sum(1 for t in query_terms if t in text_lower)
            if term_hits > 0 or query_lower in text_lower:
                score = term_hits / max(len(query_terms), 1)
                if query_lower in text_lower:
                    score += 0.5
                scored.append((score, f))

        scored.sort(key=lambda x: -x[0])

        for _, f in scored[:max_results]:
            fact_text = f.text
            fact_tokens = self._count_tokens(fact_text)
            if fact_tokens > token_budget:
                break
            token_budget -= fact_tokens
            facts_out.append({
                "id": f.id,
                "text": fact_text,
                "confidence": str(round(f.confidence, 2)),
                "source": f.source_window_id or "unknown",
            })

        # Layer 2: CKF semantic retrieval if embedding function available
        if len(facts_out) < max_results and self._embed_fn and token_budget > 100:
            try:
                query_emb = self._embed_fn(query)
                seed_ids = {f["id"] for f in facts_out}
                ckf_result = self._ckf.retrieve(
                    query_embedding=query_emb,
                    seed_ids=seed_ids,
                    topic=query[:100],
                    budget=max_results - len(facts_out),
                )
                seen_ids = {f["id"] for f in facts_out}
                for cf in ckf_result.facts:
                    if cf.id in seen_ids:
                        continue
                    fact_tokens = self._count_tokens(cf.text)
                    if fact_tokens > token_budget:
                        break
                    token_budget -= fact_tokens
                    facts_out.append({
                        "id": cf.id,
                        "text": cf.text,
                        "confidence": str(round(cf.confidence, 2)),
                        "source": getattr(cf, "source_window_id", "ckf"),
                    })
                    if len(facts_out) >= max_results:
                        break
            except Exception as exc:
                logger.debug("CKF semantic retrieval skipped: %s", exc)

        return json.dumps({
            "facts": facts_out,
            "total_available": self._warm_store.fact_count,
        })

    def _handle_get_document_structure(self, args: dict[str, Any]) -> str:
        """Return structural state: document map, outline, progress."""
        ss = self._warm_store.structural_state
        structure: dict[str, Any] = {}

        if hasattr(ss, "to_dict"):
            ss_dict = ss.to_dict()
            structure["document_map"] = ss_dict.get("document_map", "")
            structure["outline"] = ss_dict.get("outline", "")
            structure["sections_completed"] = ss_dict.get("sections_completed", [])
            structure["current_section"] = ss_dict.get("current_section", "")
            structure["word_count"] = ss_dict.get("word_count", 0)
        else:
            # Minimal fallback
            structure["note"] = "Structural state not yet populated"

        # Add critical state info
        cs = self._warm_store.critical_state
        if hasattr(cs, "to_dict"):
            cs_dict = cs.to_dict()
            structure["goal"] = cs_dict.get("goal", "")
            structure["phase"] = cs_dict.get("phase", "")
            structure["constraints"] = cs_dict.get("constraints", [])

        # Truncate to token budget
        result = json.dumps(structure)
        tokens = self._count_tokens(result)
        if tokens > self.MAX_RESULT_TOKENS:
            # Truncate the document_map if it's too large
            if "document_map" in structure and structure["document_map"]:
                structure["document_map"] = structure["document_map"][:500] + "..."
                result = json.dumps(structure)

        return result

    def _handle_check_facts(self, args: dict[str, Any]) -> str:
        """Verify a claim against the knowledge base."""
        claim = args.get("claim", "")
        if not claim:
            return json.dumps({"matching": [], "note": "Empty claim"})

        claim_lower = claim.lower()
        claim_terms = set(claim_lower.split())
        ranked = self._warm_store.get_ranked_facts(limit=50)

        matching: list[dict[str, str]] = []
        token_budget = self.MAX_RESULT_TOKENS

        for f in ranked:
            text_lower = f.text.lower()
            # Check for term overlap
            overlap = sum(1 for t in claim_terms if t in text_lower)
            if overlap >= max(1, len(claim_terms) // 3):
                fact_tokens = self._count_tokens(f.text)
                if fact_tokens > token_budget:
                    break
                token_budget -= fact_tokens
                matching.append({
                    "id": f.id,
                    "text": f.text,
                    "confidence": str(round(f.confidence, 2)),
                    "relevance": "high" if overlap > len(claim_terms) // 2 else "partial",
                })
                if len(matching) >= 5:
                    break

        return json.dumps({
            "matching_facts": matching,
            "facts_searched": min(len(ranked), 50),
        })

    def _handle_get_related_facts(self, args: dict[str, Any]) -> str:
        """Graph traversal to find related facts."""
        topic = args.get("topic", "")
        max_hops = min(args.get("max_hops", 2), 3)

        if not topic:
            return json.dumps({"related": [], "note": "Empty topic"})

        # Find seed facts matching the topic
        ranked = self._warm_store.get_ranked_facts(limit=30)
        topic_lower = topic.lower()
        seed_ids: set[str] = set()

        for f in ranked:
            if topic_lower in f.text.lower():
                seed_ids.add(f.id)
                if len(seed_ids) >= 3:
                    break

        if not seed_ids:
            return json.dumps({
                "related": [],
                "note": f"No seed facts found for topic: {topic}",
            })

        # Graph walk from seeds
        try:
            walk_result = self._ckf.graph_walk(
                seed_ids=seed_ids,
                max_hops=max_hops,
                max_results=10,
            )
            related: list[dict[str, str]] = []
            token_budget = self.MAX_RESULT_TOKENS

            for fact in walk_result.facts:
                fact_tokens = self._count_tokens(fact.text)
                if fact_tokens > token_budget:
                    break
                token_budget -= fact_tokens
                related.append({
                    "id": fact.id,
                    "text": fact.text,
                    "confidence": str(round(fact.confidence, 2)),
                })

            return json.dumps({
                "related": related,
                "seed_count": len(seed_ids),
                "hops": max_hops,
            })
        except Exception as exc:
            logger.debug("Graph walk failed: %s", exc)
            return json.dumps({
                "related": [],
                "note": f"Graph traversal unavailable: {exc}",
            })

    def _handle_get_continuation_state(self, args: dict[str, Any]) -> str:
        """Return continuation state: gaps, directives, progress."""
        if not self._continuation_state:
            return json.dumps({
                "status": "initial",
                "note": "No continuation state yet — this is the first window.",
            })

        result = json.dumps(self._continuation_state)
        tokens = self._count_tokens(result)
        if tokens > self.MAX_RESULT_TOKENS:
            # Truncate large fields
            state = dict(self._continuation_state)
            for key in ("last_output_summary", "document_map", "full_directive"):
                if key in state and isinstance(state[key], str):
                    state[key] = state[key][:300] + "..."
            result = json.dumps(state)

        return result


# ── Helper: build tool-aware system prompt ─────────────────────────────

def build_tool_system_prompt(original_system: str, fact_count: int) -> str:
    """Augment the system prompt with context-tool usage guidance.

    Tells the LLM that it has access to CRP context tools and should
    use them to retrieve verified information instead of relying on
    parametric knowledge alone.
    """
    tool_guidance = (
        "\n\n--- Context Access Protocol ---\n"
        "You have access to a verified knowledge base managed by the "
        "Context Relay Protocol (CRP). Instead of guessing or relying "
        "solely on your training data, use the provided tools to:\n"
        "- Retrieve verified facts relevant to your response\n"
        "- Check claims against the knowledge base before stating them\n"
        "- Get the document structure and continuation state\n"
        "- Explore related concepts via knowledge graph traversal\n"
        f"\nThe knowledge base currently contains {fact_count} verified facts.\n"
        "Call tools as needed during your response. Each tool call "
        "returns targeted context — more efficient than searching "
        "everything at once.\n"
        "--- End Context Access Protocol ---"
    )
    return original_system + tool_guidance


# ── Helper: convert tool results to messages ───────────────────────────

def tool_results_to_messages(
    assistant_message: dict[str, Any],
    results: list[ToolResult],
) -> list[dict[str, Any]]:
    """Build the message sequence for a tool call round-trip.

    Returns [assistant_msg_with_tool_calls, tool_result_1, tool_result_2, ...].
    This is the OpenAI-compatible format for continuing generation
    after tool calls.
    """
    messages: list[dict[str, Any]] = [assistant_message]
    for r in results:
        messages.append({
            "role": "tool",
            "tool_call_id": r.tool_call_id,
            "content": r.content,
        })
    return messages

# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Positioned execution loop — the live positioned-tool-loop (CRP-SPEC-049/050).

``run_positioned`` is the real STL spine that replaces the v4 simulation: it classifies
a request into operations, and for each operation it positions the model on a focused
frame with the 1–3 tools the TCF selected, runs the structured tool call, stores the
observation in the CSO, advances the Operation State Machine, and integrates — then
assembles a coherent final response. The window never accumulates tool history, so the
working set is bounded across hundreds of tool calls (positioning, not injection).

The only external dependency is ``model_call``: a callable ``(prompt, schema) -> text``.
Real providers wrap their ``generate_chat``; tests pass a deterministic stub.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from crp.security.clarify import (
    ClarificationAction,
    ClarificationHandler,
    ClarificationRequest,
    resolve_clarification,
)
from crp.state.cso import CognitiveStateObject, EstablishedFact, GoalMode, ProvenanceKind
from crp.stl.classifier import STLOperation, classify_operations
from crp.stl.depth_model import negotiate_depth
from crp.stl.frame_builder import build_operation_frame
from crp.stl.goal_compass import build_goal_compass
from crp.stl.operation_state import OperationStateMachine
from crp.stl.tool_positioner import (
    ParsedToolCall,
    build_tool_positioning_frame,
    parse_tool_call,
)
from crp.tools.capability_fabric import CapabilityProfile, PolicyContext, ToolCapabilityFabric
from crp.tools.executor import CapabilityExecutor

if TYPE_CHECKING:
    from crp.resources.governor import ResourceGovernor

logger = logging.getLogger("crp.stl.positioned")

# (prompt, optional output schema for constrained decoding) -> model text.
ModelCall = Callable[[str, "dict[str, Any] | None"], str]


class ModelCallError(RuntimeError):
    """Raised when a ``model_call`` genuinely failed (no output was produced).

    Distinguishes a real provider failure from a legitimately short/empty model
    answer, so ``run_positioned`` can halt honestly (SPEC-056 D3 — faithful
    narration: never present a failed step as if it succeeded) instead of
    silently assembling headline-only output around an empty body.
    """


def _estimate_tokens(text: str, count_tokens_fn: Callable[[str], int] | None = None) -> int:
    """Best-effort token count: the provider's exact tokenizer if given, else a
    conservative ~4 chars/token heuristic."""
    if count_tokens_fn is not None:
        try:
            return int(count_tokens_fn(text))
        except Exception:  # noqa: BLE001
            logger.debug("count_tokens_fn failed; falling back to heuristic", exc_info=True)
    return max(1, len(text) // 4)


def guard_prompt_budget(
    prompt: str,
    *,
    context_window: int,
    requested_max_tokens: int,
    count_tokens_fn: Callable[[str], int] | None = None,
    safety_margin: int = 256,
    min_output_tokens: int = 128,
) -> tuple[str, int]:
    """Ensure ``prompt`` + the response never overflow the model's real context window.

    This is the protocol-level context-overflow guard (input, tool-call frames,
    accumulated multi-turn/CSO state, and output are all covered because every call
    site — direct generation, tool positioning, continuation windows — funnels
    through the ``model_call`` this wraps). Returns ``(safe_prompt, safe_max_tokens)``:

    - ``safe_max_tokens`` is capped so ``prompt_tokens + safe_max_tokens + margin``
      fits inside ``context_window`` (never less than ``min_output_tokens``).
    - If the prompt itself is still too large to leave room for the minimum output,
      the **earliest** lines are trimmed (oldest carried-forward state/context) while
      the **tail** — the actual task/operation frame — is preserved intact.
    """
    context_window = max(int(context_window or 0), min_output_tokens + safety_margin + 1)
    prompt_tokens = _estimate_tokens(prompt, count_tokens_fn)

    available_for_output = context_window - prompt_tokens - safety_margin
    max_tokens = min(requested_max_tokens, max(min_output_tokens, available_for_output))
    max_tokens = max(max_tokens, min_output_tokens) if available_for_output >= min_output_tokens else min_output_tokens

    available_for_prompt = context_window - max_tokens - safety_margin
    if prompt_tokens <= available_for_prompt:
        return prompt, max_tokens

    # Overflow: trim from the front (oldest context), preserving the tail (the
    # operation frame / instructions the model needs to act correctly).
    lines = prompt.split("\n")
    while len(lines) > 1 and _estimate_tokens("\n".join(lines), count_tokens_fn) > available_for_prompt:
        lines.pop(0)
    trimmed = "\n".join(lines)
    if _estimate_tokens(trimmed, count_tokens_fn) > available_for_prompt:
        # Single oversized line/frame — hard character-level tail truncation.
        char_budget = max(200, available_for_prompt * 4)
        trimmed = trimmed[-char_budget:]
    logger.warning(
        "Prompt budget guard: trimmed prompt %d -> %d est. tokens (context_window=%d, max_tokens=%d)",
        prompt_tokens, _estimate_tokens(trimmed, count_tokens_fn), context_window, max_tokens,
    )
    return trimmed, max_tokens


def provider_model_call(
    provider: Any,
    *,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> ModelCall:
    """Adapt a CRP ``LLMProvider`` into a positioned-loop ``model_call``.

    The structured-output schema is advisory here — the prompt instructs the model
    to emit JSON and ``parse_tool_call`` robustly extracts it; provider-native
    constrained decoding can be layered on later (CRP-SPEC-049 §4.4).

    Every call is passed through :func:`guard_prompt_budget` using the provider's own
    ``context_window_size()``/``count_tokens()`` (mandatory on the ``LLMProvider`` ABC),
    so input, tool-call frames, continuation windows, and multi-turn state can never
    overflow the model's real context window — the guard adapts to whatever window
    the connected LLM (local or frontier) actually reports.
    """

    def model_call(prompt: str, schema: dict[str, Any] | None) -> str:
        try:
            context_window = int(provider.context_window_size())
        except Exception:  # noqa: BLE001
            context_window = 8192
        count_tokens_fn = getattr(provider, "count_tokens", None)
        safe_prompt, safe_max_tokens = guard_prompt_budget(
            prompt,
            context_window=context_window,
            requested_max_tokens=max_tokens,
            count_tokens_fn=count_tokens_fn,
        )
        messages = [{"role": "user", "content": safe_prompt}]
        try:
            text, finish = provider.generate_chat(
                messages, temperature=temperature, max_tokens=safe_max_tokens
            )
        except TypeError:
            text, finish = provider.generate_chat(messages)
        if finish == "error":
            raise ModelCallError(
                f"provider {getattr(provider, 'model_name', provider)!r} returned "
                "finish_reason='error' (no output produced)"
            )
        return text or ""

    return model_call


@dataclass
class PositionedResult:
    """The result of a positioned-tool-loop run."""

    text: str = ""
    cso: CognitiveStateObject = field(default_factory=CognitiveStateObject)
    state_machine: OperationStateMachine | None = None
    operations: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)
    frame_tokens_total: int = 0
    observation_count: int = 0
    halted: bool = False
    continuation_windows: int = 0

    @property
    def event_stream(self) -> list[dict[str, Any]]:
        """The Operation State Machine event log (visibility / audit)."""
        return self.state_machine.event_stream() if self.state_machine else []


def _summarise_payload(payload: Any) -> str:
    rendered = json.dumps(payload, default=str) if isinstance(payload, (dict, list)) else str(payload)
    return rendered[:300] + ("..." if len(rendered) > 300 else "")


def _preventive_check(
    descriptor: Any,
    call: ParsedToolCall,
    policy: PolicyContext | None,
    operation: STLOperation,
    oversight_required: set[Any] | None = None,
) -> dict[str, Any] | None:
    """Inspect a tool selection before execution (CRP-SPEC-050 §10). Returns a halt frame or None."""
    if descriptor is None:
        return {
            "crp_halt_reason": "PREVENTIVE_SAFETY_VIOLATION",
            "halt_point": "TOOL_SELECTED",
            "problematic_frame": {
                "operation_type": operation.name,
                "capability_id": call.capability_id,
                "violation": "unknown_capability",
            },
        }
    if policy is not None:
        ok, reason = policy.evaluate(descriptor)
        if not ok:
            return {
                "crp_halt_reason": "PREVENTIVE_SAFETY_VIOLATION",
                "halt_point": "TOOL_SELECTED",
                "problematic_frame": {
                    "operation_type": operation.name,
                    "capability_id": call.capability_id,
                    "violation": reason,
                },
            }
    if oversight_required and descriptor.cost_profile.safety_class in oversight_required:
        return {
            "crp_halt_reason": "PREVENTIVE_SAFETY_VIOLATION",
            "halt_point": "TOOL_SELECTED",
            "problematic_frame": {
                "operation_type": operation.name,
                "capability_id": call.capability_id,
                "violation": f"requires_oversight:{descriptor.cost_profile.safety_class.value}",
            },
        }
    return None


def _seek_oversight_approval(
    halt: dict[str, Any],
    call: ParsedToolCall,
    operation: STLOperation,
    clarify_handler: ClarificationHandler | None,
) -> bool:
    """Ask the user to approve an oversight-gated capability. Returns True if approved."""
    if clarify_handler is None:
        return False
    violation = halt["problematic_frame"].get("violation", "")
    if "requires_oversight" not in violation:
        return False
    req = ClarificationRequest(
        question=f"Approve '{call.capability_id}' for {operation.name}? ({violation})",
        operation_type=operation.name,
        reason="oversight_required",
        options=["approve", "deny"],
        context=halt["problematic_frame"],
    )
    return resolve_clarification(req, clarify_handler).approved


def _assemble(request: str, operations: list[STLOperation], outputs: list[str]) -> str:
    if not outputs:
        return ""
    if len(outputs) == 1:
        return outputs[0]
    return "\n\n".join(
        f"## {op.value.upper()}\n{out}" for op, out in zip(operations, outputs)
    )


def _looks_like_structured_data(text: str) -> bool:
    """Heuristic: is the assembled text mostly raw JSON/tool payloads?"""
    t = text.strip()
    if not t:
        return False
    # Detect a single JSON object or list, including when wrapped in markdown fences.
    stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return True
    if stripped.startswith("[") and stripped.endswith("]"):
        return True
    # Detect JSON lines inside operation sections (e.g. "## RETRIEVE\n{...}").
    json_like_lines = sum(
        1 for line in t.splitlines()
        if line.strip().startswith("{") or line.strip().startswith("[")
    )
    return json_like_lines >= 1


def _synthesise_answer(
    request: str,
    model_call: ModelCall,
    cso: CognitiveStateObject,
    depth: Any,
    prior_ops: list[str],
) -> str:
    """Produce a final natural-language answer from collected tool observations.

    This is the integration step that turns raw tool payloads into coherent prose
    for the user. It runs only when the assembled operation outputs look like
    structured data and tool observations exist.

    Small local models sometimes ignore "no JSON" instructions and echo the same
    tool-call-shaped JSON as their "answer" (a model-capability limit, not a
    parsing bug). One retry with a more forceful instruction is attempted; if the
    model still cannot produce prose, a deterministic bullet rendering of the
    facts is returned instead of surfacing raw JSON to the user — faithful
    narration must never degrade to showing internal tool-call syntax.
    """
    facts: list[str] = []
    for obs in cso.tool_observations:
        # ``cso.tool_observations`` entries are plain dicts (CognitiveStateObject
        # stores ``observation.to_dict()``, never the object itself) — dict.get,
        # not getattr, or "payload" silently falls back to the whole raw
        # observation record (fact_id/provenance/etc.) instead of the tool's
        # actual return value.
        payload = obs.get("payload", obs) if isinstance(obs, dict) else getattr(obs, "payload", obs)
        if isinstance(payload, dict):
            # Keep concise but informative: full text fields can be long, so summarize.
            summary_items: list[str] = []
            for key, value in payload.items():
                if isinstance(value, str):
                    summary_items.append(f"{key}: {value[:400]}")
                else:
                    summary_items.append(f"{key}: {value}")
            facts.append("; ".join(summary_items))
        else:
            facts.append(str(payload))

    if not facts:
        return ""

    facts_text = "\n".join(f"- {f}" for f in facts[-6:])
    prompt = (
        "You have just gathered the following facts from real tools. "
        "Answer the user's original question in clear, natural-language prose. "
        "Do not output JSON. Do not list the tools. Cite the data sources if they are mentioned in the facts.\n\n"
        f"User question: {request}\n\n"
        f"Facts gathered:\n{facts_text}\n\n"
        "Answer:"
    )
    answer = model_call(prompt, None).strip()

    if _looks_like_structured_data(answer):
        retry_prompt = (
            prompt
            + "\n\nYour previous attempt returned JSON or tool-call syntax, which is "
            "not acceptable here. Write 2-4 plain English sentences summarising the "
            "facts above. No braces, no quotes-around-keys, no code fences.\n\nAnswer:"
        )
        answer = model_call(retry_prompt, None).strip()

    if _looks_like_structured_data(answer):
        # Deterministic fallback — guaranteed coherent, never raw JSON/tool syntax.
        answer = "Based on the investigation:\n" + "\n".join(f"- {f}" for f in facts[-6:])

    return answer


# Operations whose output is long-form generation and may span the token wall.
_GENERATIVE_OPS = {
    STLOperation.GENERATE,
    STLOperation.SYNTHESISE,
    STLOperation.ANALYSE,
    STLOperation.COMPARE,
    STLOperation.TRANSFORM,
}


def _looks_truncated(text: str) -> bool:
    """Heuristic: does this window end mid-thought (i.e. hit the token wall)?"""
    t = text.rstrip()
    return bool(t) and t[-1] not in ".!?)]}\"'`" and not t.endswith("```")


def _ngram_set(text: str, n: int = 4) -> set[tuple[str, ...]]:
    toks = text.lower().split()
    return {tuple(toks[i:i + n]) for i in range(max(0, len(toks) - n + 1))}


def _repetition_ratio(chunk: str, prior: str, n: int = 4) -> float:
    """Fraction of the chunk's n-grams already present in prior output (0..1)."""
    c = _ngram_set(chunk, n)
    if not c:
        return 0.0
    p = _ngram_set(prior, n)
    if not p:
        return 0.0
    return len(c & p) / len(c)


def _generate_with_continuation(
    op: STLOperation,
    base_prompt: str,
    state_ctx: str,
    model_call: ModelCall,
    sm: OperationStateMachine,
    max_windows: int,
) -> tuple[str, int]:
    """Run a generative operation across continuation windows until complete.

    Wires the v4 continuation engine (CRP-SPEC-004) into the positioned loop. Each
    window is re-positioned with (a) the residual task, (b) a bounded tail of prior
    output, and (c) a **coverage map** of the sections already written (from
    :class:`DocumentMap`) so the model writes the NEXT, different section rather than
    restating. An n-gram repetition guard drops near-duplicate windows (with one
    stronger retry), and :class:`CompletionDetector` decides structural completion.
    The working prompt stays bounded (tail + TOC only), so a 10-window document never
    accumulates the whole draft in-window.
    """
    from crp.continuation.completion import CompletionDetector
    from crp.continuation.document_map import DocumentMap

    detector = CompletionDetector(content_type="")
    doc_map = DocumentMap()
    accumulated = model_call(base_prompt, None).strip()
    windows = 1
    doc_map.update(accumulated, f"w{windows}")
    result = detector.evaluate(accumulated, facts_produced=max(1, accumulated.count(". ")),
                               tokens_consumed=max(1, len(accumulated.split())))

    # Continue until the output is structurally complete or the window cap is hit.
    while windows < max_windows and not result.is_complete:
        tail = accumulated[-600:]
        toc = doc_map.get_toc()
        covered = f"Sections already written (do NOT repeat any of these):\n{toc}\n\n" if toc else ""
        cont_prompt = (
            f"{state_ctx}\n\nContinue the {op.value}. {covered}"
            f"Write the NEXT, DIFFERENT section(s) with new information — never restate "
            f"content above. Finish with a clear conclusion once the task is fully covered. "
            f"Already written {len(accumulated.split())} words. Continue from:\n...{tail}"
        )
        chunk = model_call(cont_prompt, None).strip()
        if not chunk:
            break
        # Anti-repetition guard: if the chunk mostly restates prior output, retry once
        # with a stronger instruction; if still repetitive, stop (avoids padding).
        if _repetition_ratio(chunk, accumulated) >= 0.6:
            retry = model_call(
                cont_prompt + "\n\nIMPORTANT: your previous attempt repeated earlier text. "
                "Write ENTIRELY NEW material on an as-yet-uncovered aspect, or end with a conclusion.",
                None,
            ).strip()
            if not retry or _repetition_ratio(retry, accumulated) >= 0.6:
                sm.note(f"continuation_stopped=repetition window={windows + 1}", operation=op)
                break
            chunk = retry
        accumulated += ("" if accumulated.endswith(("\n", " ")) else "\n\n") + chunk
        windows += 1
        doc_map.update(chunk, f"w{windows}")
        sm.note(
            f"continuation_window={windows} words={len(accumulated.split())} "
            f"sections={len(doc_map.headings)}",
            operation=op,
        )
        result = detector.evaluate(chunk, facts_produced=max(1, chunk.count(". ")),
                                   tokens_consumed=max(1, len(chunk.split())))
    return accumulated, windows


def run_positioned(
    user_request: str,
    model_call: ModelCall,
    *,
    fabric: ToolCapabilityFabric | None = None,
    executor: CapabilityExecutor | None = None,
    profile: CapabilityProfile = CapabilityProfile.FRONTIER,
    policy: PolicyContext | None = None,
    context_facts: list[str] | None = None,
    max_operations: int = 12,
    oversight_required: set[Any] | None = None,
    governor: ResourceGovernor | None = None,
    clarify_handler: ClarificationHandler | None = None,
    hmac_key: bytes | None = None,
    prior_cso: CognitiveStateObject | None = None,
    max_continuation_windows: int = 1,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    final_synthesis: bool = True,
) -> PositionedResult:
    """Run the positioned-tool-loop for a request (CRP-SPEC-049/050).

    Args:
        user_request: The natural-language request.
        model_call: ``(prompt, schema|None) -> text``. The only LLM dependency.
        fabric: Optional Tool Capability Fabric; if absent, operations are direct-generation.
        executor: Optional capability executor; if absent, tool ops run in selection-only mode.
        profile: Capability profile bounding frame size (small-local 1–2 tools, etc.).
        policy: Optional policy pre-filter / preventive-safety context.
        context_facts: Optional pre-retrieved facts for the first operations.
        max_operations: Hard cap on operations (loop guard).
        hmac_key: If provided, seals the CSO with an HMAC chain link.
        prior_cso: Optional prior-turn CSO to relay forward (multi-turn workflows).
        final_synthesis: If True and tool observations were made, run a final SYNTHESISE
            step so raw payloads become natural-language prose.
    """
    operations = classify_operations(user_request)
    depth, _ = negotiate_depth(user_request, operations)

    governor_reason = ""
    if governor is not None:
        plan = governor.plan(profile)
        profile = plan.profile
        max_operations = min(max_operations, plan.max_operations)
        governor_reason = plan.reason

    cso = CognitiveStateObject()
    if prior_cso is not None:
        # Multi-turn state relay (SPEC-030): carry forward everything the prior
        # turn established so this turn is positioned with full accumulated context.
        cso.window_number = prior_cso.window_number + 1
        cso.prior_cso_hash = prior_cso.cso_hmac or prior_cso.prior_cso_hash
        cso.established_facts = list(prior_cso.established_facts)
        cso.tool_observations = list(prior_cso.tool_observations)
        cso.decisions = list(prior_cso.decisions)
        cso.active_constraints = list(prior_cso.active_constraints)
        cso.completed_operations = list(prior_cso.completed_operations)
        cso.open_questions = list(prior_cso.open_questions)
    cso.goal_state.mode = GoalMode.AGENTIC
    cso.goal_state.objective = user_request
    cso.goal_state.remaining = [op.name for op in operations]

    sm = OperationStateMachine(plan=operations, event_callback=event_callback)
    outputs: list[str] = []
    prior_ops: list[str] = []
    frame_tokens = 0
    continuation_windows_total = 0

    for op in operations[:max_operations]:
        sm.position()
        compass = build_goal_compass(op.value, user_request, prior_ops)
        frame = build_operation_frame(op, user_request, context_facts, depth, compass)
        frame_tokens += frame.estimated_tokens
        state_ctx = cso.to_prompt_context(max_facts=8, max_decisions=3)

        tpf = None
        if fabric is not None:
            selection = fabric.select(op, query_text=user_request, profile=profile, policy=policy)
            if selection.selected:
                tpf = build_tool_positioning_frame(frame, selection, profile=profile, depth=depth)

        try:
            if op is STLOperation.CLARIFY and clarify_handler is not None:
                request = ClarificationRequest(
                    question=frame.assignment or "Clarification needed to proceed.",
                    operation_type=op.name,
                    reason="missing_information",
                )
                resolution = resolve_clarification(request, clarify_handler)
                if resolution.action is ClarificationAction.ABORT:
                    sm.halt("user_aborted")
                    outputs.append("[aborted by user]")
                    break
                if resolution.action is ClarificationAction.ANSWER and resolution.answer:
                    cso.established_facts.append(EstablishedFact(
                        fact_id=f"f_clar_{cso.window_number}_{len(cso.established_facts)}",
                        statement=f"User clarification: {resolution.answer}",
                        provenance=ProvenanceKind.USER,
                        window_origin=cso.window_number,
                    ))
                    output = resolution.answer
                    sm.verify(detail="clarified-by-user")
                else:
                    output = model_call(f"{state_ctx}\n\n{frame.to_prompt()}", None).strip()
                    sm.verify(detail="clarify-skipped")
            elif tpf is not None and tpf.capabilities:
                prompt = f"{state_ctx}\n\n{tpf.to_prompt()}"
                raw = model_call(prompt, tpf.output_schema())
                call = parse_tool_call(raw, tpf)

                if call is not None and call.is_tool_call:
                    descriptor = fabric.get(call.capability_id or "") if fabric else None
                    halt = _preventive_check(descriptor, call, policy, op, oversight_required)
                    if halt is not None and _seek_oversight_approval(halt, call, op, clarify_handler):
                        halt = None  # user approved the gated capability
                    if halt is not None:
                        cso.record_preventive_halt(halt)
                        sm.halt(halt["problematic_frame"]["violation"])
                        outputs.append(f"[halted: {halt['problematic_frame']['violation']}]")
                        break

                    sm.select_tool(call.capability_id or "")
                    if executor is not None and descriptor is not None and executor.has_impl(call.capability_id or ""):
                        res = executor.execute(descriptor, call.arguments, op, window_id=cso.cso_id)
                        sm.execute_tool(call.capability_id or "")
                        if res.ok and res.observation is not None:
                            cso.add_tool_observation(res.observation)
                            output = _summarise_payload(res.observation.payload)
                            sm.verify(detail="tool-grounded")
                            if event_callback is not None:
                                event_callback({
                                    "event_type": "observation_received",
                                    # Uppercase token — matches the operation
                                    # tag every other state-machine event uses
                                    # (operation_to_token), so a UI can
                                    # correlate TOOL_CALL_START/RESULT by the
                                    # same call id instead of a casing mismatch.
                                    "operation": op.name,
                                    "operation_index": sm.current_index,
                                    "capability_id": call.capability_id,
                                    "payload": res.observation.payload,
                                })
                        else:
                            output = f"[tool {call.capability_id} failed: {'; '.join(res.errors)}]"
                            sm.verify(detail="tool-failed")
                    else:
                        # Selection-only mode: no implementation registered; record the call.
                        sm.execute_tool(call.capability_id or "")
                        output = json.dumps(
                            {"capability_id": call.capability_id, "arguments": call.arguments}
                        )
                        sm.verify(detail="selection-only")
                else:
                    output = (call.answer if call else raw).strip()
                    sm.verify(detail="direct-answer")
            else:
                prompt = f"{state_ctx}\n\n{frame.to_prompt()}"
                if max_continuation_windows > 1 and op in _GENERATIVE_OPS:
                    output, win = _generate_with_continuation(
                        op, prompt, state_ctx, model_call, sm, max_continuation_windows
                    )
                    continuation_windows_total += win
                    sm.verify(detail=f"direct-generation ({win} window{'s' if win != 1 else ''})")
                else:
                    raw = model_call(prompt, None)
                    output = raw.strip()
                    sm.verify(detail="direct-generation")
        except ModelCallError as exc:
            # A genuine provider failure (SPEC-056 D3 faithful narration): halt
            # honestly rather than assembling a plausible-looking response
            # around an empty body. ``sm.halt`` flips ``is_halted`` so the
            # caller reports risk=CRITICAL / grounded=False, not a silent LOW.
            logger.warning("Positioned loop: model call failed for operation %s: %s", op.name, exc)
            sm.halt("provider_call_failed")
            outputs.append(
                "[unable to complete this step: the language model provider did not "
                f"return a response — {exc}]"
            )
            break

        outputs.append(output)
        prior_ops.append(op.value)
        cso.completed_operations.append(op.name)
        done = len(outputs)
        cso.goal_state.completion = min(done / max(len(operations), 1), 1.0)
        cso.goal_state.remaining = [o.name for o in operations[done:]]
        sm.integrate(detail=f"output_len={len(output)}")

    if not sm.is_halted:
        sm.complete()

    text = _assemble(user_request, operations[: len(outputs)], outputs)

    # Trigger synthesis when the assembled text looks like raw tool-call JSON
    # OR when it's blank — a model that mis-selected/misparsed a tool call still
    # left real, usable tool observations behind; an empty answer in that case
    # is a coherence bug, not a legitimate "nothing to say" response.
    if (
        final_synthesis
        and cso.tool_observations
        and (_looks_like_structured_data(text) or not text.strip())
        and not sm.is_halted
    ):
        try:
            text = _synthesise_answer(user_request, model_call, cso, depth, prior_ops)
        except ModelCallError as exc:
            # The operations themselves already succeeded (real tool
            # observations exist) — degrade to the raw assembled output
            # rather than losing a working result over a failed polish step.
            logger.warning("Positioned loop: final synthesis call failed: %s", exc)

    if hmac_key:
        cso.extend_hmac_chain("", hmac_key)

    headers = sm.to_headers()
    headers["CRP-Tool-Observation-Count"] = str(len(cso.tool_observations))
    headers["CRP-STL-Frame-Tokens"] = str(frame_tokens)
    headers["CRP-Agent-Capability-Profile"] = profile.value
    if continuation_windows_total:
        headers["CRP-Continuation-Windows"] = str(continuation_windows_total)
    if governor_reason:
        headers["CRP-Resource-Plan"] = governor_reason

    return PositionedResult(
        text=text,
        cso=cso,
        state_machine=sm,
        operations=[op.value for op in operations],
        headers=headers,
        frame_tokens_total=frame_tokens,
        observation_count=len(cso.tool_observations),
        halted=sm.is_halted,
        continuation_windows=continuation_windows_total,
    )

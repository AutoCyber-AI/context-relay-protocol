# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Demo F backend — CRP Agent vs raw LLM, side-by-side, same model.

Both arms answer the SAME question against the SAME detected local model, at
the same time:

* raw arm  - tool descriptions crammed into the system prompt as plain text;
  nothing executes whatever the model prints. Streamed live token by token.
* CRP arm  - crp.Agent with the same tools declared natively; every lifecycle
  event (intent, operation, tool call, observation, governance) is forwarded
  to the browser as it happens via ``event_callback``.

API (used by ``server.py``):

  POST /api/agent/start    → {"run_id"}   body: question, real_search
  GET  /api/agent/stream   → SSE (run_id query param)
  GET  /api/agent/status   → run state
  POST /api/agent/cancel   → {"cancelled": bool}
"""

from __future__ import annotations

import json
import logging
import queue
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .pipeline import discover_local_llms, stream_generate

logger = logging.getLogger("crp.demos.agent")

_RUNS: dict[str, _AgentRun] = {}
_RUNS_LOCK = threading.Lock()

_DEFAULT_QUESTION = ("Use the get_weather tool to check the weather in London, then "
                     "use convert_temp to convert the Celsius temperature to Fahrenheit. "
                     "Report both tool results.")

# Reasoning-first models burn their output budget on <think> before answering.
# On a capped local server (LM Studio max_out=1024) that means no answer at all
# and 5-10x slower calls. Demo F (agent vs raw) therefore prefers a direct
# (non-thinking) instruct model and JIT-loads one when the loaded primary is a
# reasoning model. The demos that showcase thinking (App 1/2) keep it enabled.
_THINKING_MODEL_MARKERS = ("qwen3", "deepseek-r1", "r1-distill", "qwq")
# Preference order when a direct model must be loaded (first match wins).
_DIRECT_MODEL_PREFS = ("qwen2.5-7b-instruct", "meta-llama-3.1-8b-instruct",
                       "qwen2.5", "llama-3.1", "llama-3.2", "gemma-3")


def _is_thinking_model(model_id: str) -> bool:
    return any(marker in (model_id or "").lower() for marker in _THINKING_MODEL_MARKERS)


def _no_think_body(model_id: str) -> dict[str, Any] | None:
    """Request-body extras that switch a reasoning-first model to direct answers."""
    if _is_thinking_model(model_id):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return None


def _ensure_direct_model(primary: Any, report: Any) -> Any:
    """Return a non-thinking model for the demo, JIT-loading one if needed.

    Reasoning models make the side-by-side comparison degenerate (the raw arm
    can think for minutes before emitting anything). If the loaded primary is a
    reasoning model and a direct instruct model is installed in the runtime,
    ask LM Studio to load it (JIT) and wait briefly. Falls back to the primary
    when no candidate exists or the load fails - the demo still works, slower.
    """
    if not _is_thinking_model(primary.id):
        return primary
    candidates = [
        m for m in report.models
        if m.model_type == "llm" and m.endpoint == primary.endpoint
        and not _is_thinking_model(m.id) and not m.is_reasoning_model
    ]
    if not candidates:
        logger.warning("primary %s is a thinking model and no direct model is installed; "
                       "the comparison will be slow", primary.id)
        return primary

    def _rank(m: Any) -> int:
        mid = m.id.lower()
        for i, pref in enumerate(_DIRECT_MODEL_PREFS):
            if pref in mid:
                return i
        return len(_DIRECT_MODEL_PREFS)

    target = sorted(candidates, key=_rank)[0]
    if target.is_loaded:
        logger.info("using already-loaded direct model %s instead of thinking primary %s",
                    target.id, primary.id)
        return target

    logger.info("primary %s is a thinking model; JIT-loading %s for the comparison",
                primary.id, target.id)
    try:
        import urllib.request
        body = json.dumps({"model": target.id}).encode("utf-8")
        req = urllib.request.Request(
            primary.endpoint.rstrip("/") + "/api/v1/models/load",
            data=body, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=30).read()
        deadline = time.time() + 150
        while time.time() < deadline:
            time.sleep(5)
            fresh = discover_local_llms(timeout=2.5)
            for m in fresh.models:
                if m.id == target.id and m.is_loaded:
                    logger.info("direct model %s loaded", m.id)
                    return m
        logger.warning("timed out waiting for %s to load; using thinking primary", target.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("JIT load of %s failed (%s); using thinking primary", target.id, exc)
    return primary


def _load_tools(real_search: bool) -> tuple[list[Any], str, str]:
    """Return (tools, tool_docs, tool_set_label) for both arms."""
    if real_search:
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "templates"))
            from research_assistant_agent import (  # type: ignore[import-not-found]
                read_page,
                web_search,
            )

            return [web_search, read_page], (
                "web_search(query: str) -> list[dict]: search Wikipedia's public Search API.\n"
                "read_page(url: str) -> str: fetch a URL and return its main visible text."
            ), "wikipedia_search_api"
        except Exception as exc:  # noqa: BLE001
            logger.warning("real search unavailable (%s); using synthetic tools", exc)
    def get_weather(city: str) -> str:
        """Get the current weather (temperature and conditions) for a city."""
        return f"The weather in {city} is 22°C and sunny."

    def convert_temp(celsius: float) -> str:
        """Convert a Celsius temperature to Fahrenheit."""
        return f"{celsius}°C is {celsius * 9 / 5 + 32:.1f}°F."

    return [get_weather, convert_temp], (
        "get_weather(city: str) -> returns weather in the city.\n"
        "convert_temp(celsius: float) -> converts Celsius to Fahrenheit."
    ), "synthetic"


class _AgentRun:
    def __init__(self, run_id: str, question: str, real_search: bool) -> None:
        self.run_id = run_id
        self.question = question
        self.real_search = real_search
        self.status = "pending"
        self.error: str | None = None
        self.events: queue.Queue = queue.Queue(maxsize=4000)
        self._cancel = threading.Event()
        self.raw_response = ""
        self.crp_response: dict[str, Any] = {}
        self._arms_done = 0
        self.started_at = 0.0

    def emit(self, event_type: str, data: Any) -> None:
        try:
            self.events.put_nowait({"type": event_type, "data": data, "ts": time.time()})
        except queue.Full:
            pass

    def cancel(self) -> None:
        self._cancel.set()
        self.status = "cancelled"


def _raw_arm(run: _AgentRun, primary: Any, tool_docs: str) -> None:
    """The no-protocol arm: tools described in prose, output streamed live."""
    system = (
        "You are a helpful assistant. You have these tools:\n\n"
        f"{tool_docs}\n\n"
        "If you need a tool, output JSON like:\n"
        '{"tool": "<name>", "arguments": {...}}\n'
        "Then stop. The user will give you the result.\n\n"
        "Answer the user's question."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": run.question},
    ]
    text, finish = "", "stop"
    try:
        for kind, delta in stream_generate(
            primary, messages, extra_body=_no_think_body(primary.id)
        ):
            if run._cancel.is_set():
                break
            if kind == "done":
                text, finish = delta["text"], delta["finish_reason"]
            else:
                run.emit("raw_token", {"delta": delta})
    except Exception as exc:  # noqa: BLE001
        text, finish = f"[raw arm failed: {exc}]", "error"
    run.raw_response = text
    run.emit("raw_done", {"response": text, "finish_reason": finish})


def _crp_arm(run: _AgentRun, primary: Any, tools: list[Any]) -> None:
    """The CRP arm: native tool fabric + full lifecycle event stream."""
    import crp
    from crp.providers.openai import OpenAIAdapter

    base_url = primary.endpoint.rstrip("/") + "/v1"
    no_think = _no_think_body(primary.id)
    if no_think:
        # Best-effort thinking-disable for SDK versions / runtimes that accept
        # it (goes in the JSON body via extra_body; a bare kwarg makes the
        # OpenAI SDK raise TypeError). Usually unused: _ensure_direct_model
        # already swapped to a direct model. Kept as the fallback-path guard.
        extra = {"chat_template_kwargs": no_think["chat_template_kwargs"]}

        class _NoThinkAdapter(OpenAIAdapter):
            def generate_chat(self, messages: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("extra_body", extra)
                return super().generate_chat(messages, **kwargs)

            def generate_chat_with_tools(self, messages: Any, tools: Any, **kwargs: Any) -> Any:
                kwargs.setdefault("extra_body", extra)
                return super().generate_chat_with_tools(messages, tools, **kwargs)

        provider: Any = _NoThinkAdapter(
            model=primary.id, base_url=base_url, api_key="lm-studio",
        )
    else:
        provider = OpenAIAdapter(
            model=primary.id, base_url=base_url, api_key="lm-studio",
        )
    agent = crp.Agent(
        provider=provider,
        tools=tools,
        system="You are a helpful assistant. Use the real tools you have - "
               "never claim a result you didn't actually get from one.",
        profile="small-local",
    )

    def on_event(event: Any) -> None:
        if not run._cancel.is_set():
            run.emit("crp_event", {"event": event.to_dict()})

    try:
        result = agent.run(run.question, event_callback=on_event)
        gov = {
            "risk": result.crp.risk,
            "grounded": result.crp.grounded,
            "chain_valid": result.crp.chain_valid,
            "audit_url": result.crp.audit_url,
            "operations": result.operations,
            "sources": result.sources,
        }
        run.crp_response = {"response": result.answer, "governance": gov}
        run.emit("crp_done", run.crp_response)
    except Exception as exc:  # noqa: BLE001
        logger.exception("CRP arm failed")
        run.crp_response = {"response": f"[CRP arm failed: {exc}]", "governance": None}
        run.emit("crp_done", run.crp_response)


def _run_agent_demo(run: _AgentRun) -> None:
    run.status = "running"
    run.started_at = time.time()
    report = discover_local_llms(timeout=2.5)
    primary = report.primary_model()
    if primary is None:
        run.status = "error"
        run.error = "no local model detected - load one in LM Studio first"
        run.emit("run_error", {"error": run.error})
        return
    primary = _ensure_direct_model(primary, report)

    tools, tool_docs, tool_set = _load_tools(run.real_search)
    run.emit("run_started", {
        "run_id": run.run_id,
        "question": run.question,
        "model": primary.id,
        "runtime": primary.runtime.value,
        "tool_set": tool_set,
    })

    def arm_guard(fn: Any, *args: Any) -> None:
        try:
            fn(run, *args)
        except Exception as exc:  # noqa: BLE001 — one arm must not kill the other
            logger.exception("arm failed")
            run.emit("arm_error", {"error": str(exc)})
        finally:
            run._arms_done += 1

    t_raw = threading.Thread(target=arm_guard, args=(_raw_arm, primary, tool_docs), daemon=True)
    t_crp = threading.Thread(target=arm_guard, args=(_crp_arm, primary, tools), daemon=True)
    t_raw.start()
    t_crp.start()
    while run._arms_done < 2 and not run._cancel.is_set():
        time.sleep(0.2)

    if run._cancel.is_set():
        run.status = "cancelled"
        return
    run.status = "done"
    run.emit("run_done", {
        "run_id": run.run_id,
        "raw": {"response": run.raw_response},
        "crp": run.crp_response,
        "summary": {
            "raw_word_count": len((run.raw_response or "").split()),
            "crp_word_count": len((run.crp_response.get("response") or "").split()),
            "crp_operation_count": len(run.crp_response.get("governance", {}).get("operations") or []),
            "raw_has_governance": False,
            "crp_has_governance": run.crp_response.get("governance") is not None,
        },
        "elapsed_s": round(time.time() - run.started_at, 1),
    })


def start_run(question: str, real_search: bool = True) -> str:
    run_id = str(uuid.uuid4())
    run = _AgentRun(run_id, question or _DEFAULT_QUESTION, real_search)
    with _RUNS_LOCK:
        _RUNS[run_id] = run
    t = threading.Thread(target=_run_agent_demo, args=(run,), daemon=True)
    t.start()
    return run_id


def get_run(run_id: str) -> _AgentRun | None:
    with _RUNS_LOCK:
        return _RUNS.get(run_id)


def cancel_run(run_id: str) -> bool:
    run = get_run(run_id)
    if run:
        run.cancel()
        return True
    return False


def get_status(run_id: str) -> dict[str, Any]:
    run = get_run(run_id)
    if not run:
        return {"error": "run not found"}
    return {
        "run_id": run_id,
        "status": run.status,
        "elapsed_s": round(time.time() - run.started_at, 1) if run.started_at else 0,
        "error": run.error,
    }


def stream_events(run_id: str, timeout: float = 60.0) -> list[dict[str, Any]]:
    run = get_run(run_id)
    if not run:
        return []
    events = []
    deadline = time.time() + timeout
    while time.time() < deadline and len(events) < 200:
        try:
            evt = run.events.get(timeout=0.1)
            events.append(evt)
            if evt.get("type") in ("run_done", "run_error"):
                break
        except queue.Empty:
            if run.status in ("done", "cancelled", "error"):
                break
    return events

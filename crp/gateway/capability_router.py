# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Gateway Capability Router — execute OpenAI ``tools`` via the positioned loop (CRP-SPEC-054).

When a ``/v1/chat/completions`` request includes ``tools``, the Gateway does not
proxy them blindly to the provider. Instead it runs the CRP positioned loop:
the protocol selects the relevant capability for each operation, the model emits
a structured tool selection, and the capability is executed. The final response
is a normal OpenAI-compatible chat completion containing the integrated result.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from crp.gateway.api import ChatMessage, ChatRequest, GatewaySession, ProviderResponse
from crp.gateway.tool_adapter import openai_tool_to_descriptor
from crp.stl.positioned import PositionedResult, run_positioned
from crp.tools.capability_fabric import CapabilityProfile, PolicyContext, ToolCapabilityFabric
from crp.tools.executor import CapabilityExecutor

logger = logging.getLogger("crp.gateway.capability_router")

ToolImpl = Callable[[dict[str, Any]], Any]


class CapabilityRouter:
    """Route tool-bearing chat-completion requests through the positioned loop."""

    def __init__(
        self,
        tools: list[dict[str, Any]],
        *,
        profile: CapabilityProfile = CapabilityProfile.FRONTIER,
        policy: PolicyContext | None = None,
        implementations: dict[str, ToolImpl] | None = None,
        max_operations: int = 12,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        max_continuation_windows: int = 1,
        allow_repair: bool = True,
    ) -> None:
        """Create a router for the given OpenAI-style tool definitions."""
        self._tools = tools
        self.profile = profile
        self.policy = policy or PolicyContext()
        self.max_operations = max_operations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_continuation_windows = max_continuation_windows
        self.allow_repair = allow_repair
        self._impls: dict[str, ToolImpl] = dict(implementations or {})
        self._fabric: ToolCapabilityFabric | None = None
        self._executor: CapabilityExecutor | None = None

    def register_impl(self, capability_id: str, fn: ToolImpl) -> CapabilityRouter:
        """Register a local implementation for a capability."""
        self._impls[capability_id] = fn
        self._executor = None  # force rebuild
        return self

    def _build_fabric_and_executor(self) -> tuple[ToolCapabilityFabric, CapabilityExecutor]:
        """Build the TCF and executor from the OpenAI tool definitions."""
        if self._fabric is not None and self._executor is not None:
            return self._fabric, self._executor

        fabric = ToolCapabilityFabric()
        executor = CapabilityExecutor()
        for tool in self._tools:
            try:
                descriptor = openai_tool_to_descriptor(tool)
            except ValueError as exc:
                logger.warning("Skipping invalid tool: %s", exc)
                continue
            fabric.register(descriptor)
            impl = self._impls.get(descriptor.capability_id)
            if impl is not None:
                executor.register_impl(
                    descriptor.capability_id,
                    lambda args, _fn=impl: _fn(args),
                )
        self._fabric = fabric
        self._executor = executor
        return fabric, executor

    def _build_model_call(
        self,
        request: ChatRequest,
        session: GatewaySession,
        router: Any,
    ) -> Callable[[str, dict[str, Any] | None], str]:
        """Return a ``model_call`` that dispatches through the provider router."""

        def model_call(prompt: str, _schema: dict[str, Any] | None) -> str:
            messages = [ChatMessage(role="user", content=prompt)]
            temp_request = ChatRequest(
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            if _schema:
                # SPEC-054: when the provider supports constrained decoding,
                # pass the schema down so arguments are valid by construction.
                # Otherwise the positioned loop's validate+repair path applies
                # unchanged.
                try:
                    from crp.gateway.constrained import attach_constraints

                    config = router.resolve_provider(request.model, session.tenant_id)
                    attach_constraints(temp_request, _schema, config)
                except Exception as exc:
                    logger.debug("Constrained decoding unavailable, using validate+repair: %s", exc)
            response = router.dispatch(temp_request, messages, session)
            return response.content or ""

        return model_call

    def execute(
        self,
        request: ChatRequest,
        session: GatewaySession,
        router: Any,
    ) -> ProviderResponse:
        """Run the positioned loop and return an OpenAI-compatible response."""
        fabric, executor = self._build_fabric_and_executor()
        if not fabric.all():
            # No valid tools parsed — fall back to direct provider dispatch.
            logger.warning("No valid capabilities parsed; falling back to provider dispatch")
            return router.dispatch(request, request.messages, session)

        user_request = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_request = msg.content
                break
        if not user_request:
            user_request = request.messages[-1].content if request.messages else ""

        model_call = self._build_model_call(request, session, router)
        result: PositionedResult = run_positioned(
            user_request,
            model_call,
            fabric=fabric,
            executor=executor,
            profile=self.profile,
            policy=self.policy,
            max_operations=self.max_operations,
            max_continuation_windows=self.max_continuation_windows,
        )

        finish_reason = "stop" if not result.halted else "content_filter"
        completion_text = result.text or ""
        return ProviderResponse(
            content=completion_text,
            model=request.model,
            finish_reason=finish_reason,
            prompt_tokens=result.frame_tokens_total,
            completion_tokens=max(1, len(completion_text.split())),
        )

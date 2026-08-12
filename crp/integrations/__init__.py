# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Provider/framework hooks for uninstrumented call sites (CRP 2.3).

CRP 2.2 only enforced when the caller routed through
:func:`crp.core.dispatch_router.assemble_messages`.  Applications that
call ``openai.chat.completions.create`` or ``anthropic.messages.create``
directly — or drive the model from LangChain / LlamaIndex — bypassed the
enforcer completely.

This sub-package closes that gap with thin wrappers:

* :func:`wrap_openai` — drop-in wrapper around an
  ``openai.OpenAI`` / ``openai.AsyncOpenAI`` client.
* :func:`wrap_anthropic` — drop-in wrapper around an
  ``anthropic.Anthropic`` / ``anthropic.AsyncAnthropic`` client.
* :class:`CRPContextCallback` — LangChain callback handler that runs the
  default enforcer on every LLM/ChatModel invocation.

Each wrapper:

1. Intercepts the outgoing ``messages`` payload before the HTTP call.
2. Runs the installed default enforcer (or the one injected explicitly).
3. Raises :class:`crp.core.errors.CRPError` under REJECT policy; logs
   under WARN; records audit events under OBSERVE. Zero behavioural
   change for callers that don't install an enforcer.

Imports of the target SDKs are lazy inside the wrapper — CRP itself has
zero runtime dependency on ``openai``, ``anthropic``, or ``langchain``.
"""

from __future__ import annotations

from .openai_hook import wrap_openai
from .anthropic_hook import wrap_anthropic
from .langchain_hook import CRPContextCallback

__all__ = [
    "wrap_openai",
    "wrap_anthropic",
    "CRPContextCallback",
]

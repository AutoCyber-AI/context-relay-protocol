# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""User-defined cognition layer for CRP agents (CRP-SPEC-046 §2).

``crp.cognition`` lets users declare thinking presets, reasoning scaffolds,
operating modes, safeguards, emotions, and tool/knowledge bundles in simple
YAML or Python and apply them to ``crp.Agent``.  A preset turns the user's
intent into a compiled agent configuration: system prompt enrichment, policy
context, operation-sequence hints, registered tools, output-format constraints,
and optional emotion/safeguard hooks.

Example::

    import crp
    from crp.cognition import CognitivePreset

    agent = crp.Agent(model="local/llama3.1", preset="socratic_tutor")
    result = agent.run("Explain quantum computing")
"""

from __future__ import annotations

from crp.cognition.compiler import PresetCompiler
from crp.cognition.preset import (
    CognitivePreset,
    EmotionConfig,
    OutputProfile,
    ReasoningPhase,
    ReasoningScaffold,
    Safeguard,
    ToolBundle,
)

__all__ = [
    "CognitivePreset",
    "EmotionConfig",
    "OutputProfile",
    "PresetCompiler",
    "ReasoningPhase",
    "ReasoningScaffold",
    "Safeguard",
    "ToolBundle",
]

# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Compile a CognitivePreset into agent-ready configuration (CRP-SPEC-046 §2.3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crp.cognition.emotion import detect_emotion
from crp.cognition.phase_machine import PhasePlan
from crp.cognition.preset import CognitivePreset
from crp.cognition.safeguard import SafeguardEngine
from crp.tools.descriptor import SafetyClass


@dataclass
class CompiledPreset:
    """The runtime-ready output of compiling a preset."""

    system: str = ""
    policy_overrides: dict[str, Any] = field(default_factory=dict)
    depth: str = "auto"
    operations: list[str] = field(default_factory=list)
    tool_ids: list[str] = field(default_factory=list)
    safety_classes: set[SafetyClass] = field(default_factory=set)
    phase_plan: PhasePlan | None = None
    safeguard_engine: SafeguardEngine | None = None
    emotion_detector: Any | None = None
    output_hints: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "system": self.system,
            "policy_overrides": self.policy_overrides,
            "depth": self.depth,
            "operations": self.operations,
            "tool_ids": self.tool_ids,
            "safety_classes": [s.value for s in self.safety_classes],
            "phase_plan": self.phase_plan.to_dict() if self.phase_plan else None,
            "output_hints": self.output_hints,
            "metadata": self.metadata,
        }


class PresetCompiler:
    """Compile a :class:`CognitivePreset` into a :class:`CompiledPreset`."""

    # Mapping from declarative safeguard action names to Policy/policy effects.
    _SAFEGUARD_ACTION_MAP: dict[str, str] = {
        "warn": "warn",
        "ask": "ask",
        "halt": "halt",
    }

    def __init__(self, preset: CognitivePreset) -> None:
        self.preset = preset

    def compile(self) -> CompiledPreset:
        """Return a runtime-ready configuration."""
        system = self._build_system_prompt()
        operations = self._collect_operations()
        tool_ids = self._collect_tool_ids()
        depth = self._resolve_depth()
        policy_overrides = self._build_policy_overrides()
        safety_classes = self._resolve_safety_classes()
        safeguard_engine = self._build_safeguard_engine()
        emotion_detector = self._build_emotion_hook()
        output_hints = self._build_output_hints()
        phase_plan = self._build_phase_plan()

        return CompiledPreset(
            system=system,
            policy_overrides=policy_overrides,
            depth=depth,
            operations=operations,
            tool_ids=tool_ids,
            safety_classes=safety_classes,
            phase_plan=phase_plan,
            safeguard_engine=safeguard_engine,
            emotion_detector=emotion_detector,
            output_hints=output_hints,
            metadata={
                "preset_id": self.preset.id,
                "preset_name": self.preset.name,
                "preset_version": self.preset.version,
            },
        )

    def _build_system_prompt(self) -> str:
        """Merge persona, reasoning scaffold, operating modes, and output profile."""
        parts: list[str] = []
        if self.preset.persona:
            parts.append(f"Persona: {self.preset.persona}")
        if self.preset.voice:
            parts.append(f"Voice: {self.preset.voice}")

        if self.preset.reasoning.phases:
            parts.append("\nFollow this reasoning process:")
            for i, phase in enumerate(self.preset.reasoning.phases, 1):
                line = f"{i}. {phase.name}"
                if phase.prompt:
                    line += f": {phase.prompt}"
                if phase.operations:
                    line += f" [ops: {', '.join(phase.operations)}]"
                if phase.tools:
                    line += f" [tools: {', '.join(phase.tools)}]"
                parts.append(line)
            if self.preset.reasoning.loop_until:
                parts.append(f"\nLoop until: {self.preset.reasoning.loop_until}")

        if self.preset.operating_modes:
            parts.append("\nOperating modes:")
            for mode in self.preset.operating_modes:
                when = mode.get("when", "")
                then = mode.get("then", "")
                if when and then:
                    parts.append(f"- When {when}: {then}")

        if self.preset.safeguards:
            parts.append("\nSafeguards:")
            for rule in self.preset.safeguards:
                parts.append(
                    f"- {rule.name} ({rule.scope}): {rule.condition} → {rule.action}"
                )

        if self.preset.emotions.enabled:
            parts.append("\nEmotional tone:")
            parts.append(f"- Default affect: {self.preset.emotions.default_affect}")
            if self.preset.emotions.triggers:
                parts.append("- Triggers:")
                for affect, instruction in self.preset.emotions.triggers.items():
                    parts.append(f"  * When the user seems {affect}: {instruction}")

        output = self.preset.output
        if output.length or output.format or output.tone:
            parts.append("\nOutput profile:")
            if output.length:
                parts.append(f"- Length: {output.length}")
            if output.format:
                parts.append(f"- Format: {output.format}")
            if output.tone:
                parts.append(f"- Tone: {output.tone}")
            if output.citation_style:
                parts.append(f"- Citations: {output.citation_style}")

        return "\n".join(parts)

    def _collect_operations(self) -> list[str]:
        """Collect preferred operations from the reasoning scaffold."""
        ops: list[str] = []
        for phase in self.preset.reasoning.phases:
            for op in phase.operations:
                if op not in ops:
                    ops.append(op)
        return ops

    def _collect_tool_ids(self) -> list[str]:
        """Collect tool ids referenced by the preset."""
        ids: list[str] = []
        for phase in self.preset.reasoning.phases:
            if phase.tools is None:
                continue
            for tid in phase.tools:
                if tid not in ids:
                    ids.append(tid)
        for bundle in self.preset.bundles:
            for tid in bundle.tools:
                if tid not in ids:
                    ids.append(tid)
        return ids

    def _resolve_depth(self) -> str:
        """Pick the deepest depth requested by any phase."""
        order = ["quick", "standard", "thorough", "exhaustive"]
        best = "auto"
        for phase in self.preset.reasoning.phases:
            if phase.depth and phase.depth in order:
                if best == "auto" or order.index(phase.depth) > order.index(best):
                    best = phase.depth
        return best

    def _build_phase_plan(self) -> PhasePlan | None:
        """Compile the reasoning scaffold into a hard-enforced phase plan."""
        if not self.preset.reasoning.phases:
            return None
        return PhasePlan.from_reasoning_scaffold(
            [p.to_dict() for p in self.preset.reasoning.phases],
            loop_until=self.preset.reasoning.loop_until,
        )

    def _build_policy_overrides(self) -> dict[str, Any]:
        """Convert declarative policy hints into Policy-compatible overrides."""
        overrides: dict[str, Any] = {}
        # Output format can be signalled through extra policy metadata.
        if self.preset.output.length:
            overrides["cognition.output.length"] = self.preset.output.length
        if self.preset.output.format:
            overrides["cognition.output.format"] = self.preset.output.format
        if self.preset.output.tone:
            overrides["cognition.output.tone"] = self.preset.output.tone
        return overrides

    def _resolve_safety_classes(self) -> set[SafetyClass]:
        """Infer safety classes from safeguard scopes/actions."""
        classes: set[SafetyClass] = set()
        for rule in self.preset.safeguards:
            if rule.action in ("halt", "ask"):
                classes.add(SafetyClass.DESTRUCTIVE)
            if "pii" in rule.name.lower() or "privacy" in rule.name.lower():
                classes.add(SafetyClass.HUMAN_OVERSIGHT)
        return classes

    def _build_safeguard_engine(self) -> SafeguardEngine | None:
        """Build a runtime safeguard engine if the preset declares safeguards."""
        if not self.preset.safeguards:
            return None
        return SafeguardEngine(self.preset.safeguards)

    def _build_emotion_hook(self) -> Any:
        """Return an emotion detector if enabled."""
        if not self.preset.emotions.enabled:
            return None
        return detect_emotion

    def _build_output_hints(self) -> dict[str, Any]:
        return self.preset.output.to_dict()

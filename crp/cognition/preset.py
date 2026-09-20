# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Data model for user-defined cognitive presets (CRP-SPEC-046 §2.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReasoningPhase:
    """One phase in a reasoning scaffold."""

    name: str
    prompt: str = ""
    operations: list[str] = field(default_factory=list)
    tools: list[str] | None = None  # None = unrestricted; [] = no tools allowed
    depth: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "operations": self.operations,
            "tools": self.tools,
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningPhase:
        return cls(
            name=data.get("name", ""),
            prompt=data.get("prompt", ""),
            operations=list(data.get("operations", [])),
            tools=list(data["tools"]) if data.get("tools") is not None else None,
            depth=data.get("depth", ""),
        )


@dataclass
class ReasoningScaffold:
    """An ordered list of phases that guide the agent's thinking process."""

    phases: list[ReasoningPhase] = field(default_factory=list)
    loop_until: str = "complete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "phases": [p.to_dict() for p in self.phases],
            "loop_until": self.loop_until,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningScaffold:
        phases = [ReasoningPhase.from_dict(p) for p in data.get("phases", [])]
        return cls(phases=phases, loop_until=data.get("loop_until", "complete"))


@dataclass
class Safeguard:
    """A declarative safety rule attached to a preset."""

    name: str
    scope: str = "global"  # global, tool, topic, output
    condition: str = ""
    action: str = "warn"  # warn, halt, ask
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "scope": self.scope,
            "condition": self.condition,
            "action": self.action,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Safeguard:
        return cls(
            name=data.get("name", ""),
            scope=data.get("scope", "global"),
            condition=data.get("condition", ""),
            action=data.get("action", "warn"),
            rationale=data.get("rationale", ""),
        )


@dataclass
class EmotionConfig:
    """Optional affect preset and emotion-recognition hook."""

    enabled: bool = False
    default_affect: str = "neutral"
    recognizer: str = "rule"  # rule, ml, or dotted path to callable
    triggers: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "default_affect": self.default_affect,
            "recognizer": self.recognizer,
            "triggers": self.triggers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmotionConfig:
        return cls(
            enabled=bool(data.get("enabled", False)),
            default_affect=data.get("default_affect", "neutral"),
            recognizer=data.get("recognizer", "rule"),
            triggers=dict(data.get("triggers", {})),
        )


@dataclass
class OutputProfile:
    """Constraints on the agent's output."""

    length: str = "medium"  # short, medium, long, concise, exhaustive
    format: str = "paragraph"  # paragraph, bullets, json, table, markdown
    tone: str = "neutral"  # neutral, formal, friendly, socratic, compassionate
    citation_style: str = "inline"  # inline, footnote, none

    def to_dict(self) -> dict[str, Any]:
        return {
            "length": self.length,
            "format": self.format,
            "tone": self.tone,
            "citation_style": self.citation_style,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutputProfile:
        return cls(
            length=data.get("length", "medium"),
            format=data.get("format", "paragraph"),
            tone=data.get("tone", "neutral"),
            citation_style=data.get("citation_style", "inline"),
        )


@dataclass
class ToolBundle:
    """A named bundle of tools and knowledge sources a preset can reference."""

    name: str
    tools: list[str] = field(default_factory=list)
    knowledge: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "tools": self.tools, "knowledge": self.knowledge}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolBundle:
        return cls(
            name=data.get("name", ""),
            tools=list(data.get("tools", [])),
            knowledge=list(data.get("knowledge", [])),
        )


@dataclass
class CognitivePreset:
    """A complete user-defined thinking/reasoning/operating preset.

    A preset is a declarative bundle of:
      - persona (who the agent is)
      - reasoning scaffold (how it thinks)
      - operating modes (when to change behavior)
      - safeguards (hard rules)
      - emotions / affect (optional)
      - output profile (length, format, tone)
      - tool/knowledge bundles
    """

    id: str = ""
    name: str = ""
    description: str = ""
    version: str = "1.0"
    persona: str = ""
    voice: str = ""
    reasoning: ReasoningScaffold = field(default_factory=ReasoningScaffold)
    operating_modes: list[dict[str, Any]] = field(default_factory=list)
    safeguards: list[Safeguard] = field(default_factory=list)
    emotions: EmotionConfig = field(default_factory=EmotionConfig)
    output: OutputProfile = field(default_factory=OutputProfile)
    bundles: list[ToolBundle] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "persona": self.persona,
            "voice": self.voice,
            "reasoning": self.reasoning.to_dict(),
            "operating_modes": self.operating_modes,
            "safeguards": [s.to_dict() for s in self.safeguards],
            "emotions": self.emotions.to_dict(),
            "output": self.output.to_dict(),
            "bundles": [b.to_dict() for b in self.bundles],
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CognitivePreset:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            persona=data.get("persona", ""),
            voice=data.get("voice", ""),
            reasoning=ReasoningScaffold.from_dict(data.get("reasoning", {})),
            operating_modes=list(data.get("operating_modes", [])),
            safeguards=[Safeguard.from_dict(s) for s in data.get("safeguards", [])],
            emotions=EmotionConfig.from_dict(data.get("emotions", {})),
            output=OutputProfile.from_dict(data.get("output", {})),
            bundles=[ToolBundle.from_dict(b) for b in data.get("bundles", [])],
            extra=dict(data.get("extra", {})),
        )

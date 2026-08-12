# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""LLM context curation — progressive understanding synthesis (§18).

Periodically dispatches curation windows to build an evolving synthesis
of findings, relationships, and gaps. Injected into envelopes as
Section 1.5 between CRITICAL STATE and DISCOVERIES.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Curation interval by tier: {tier: (interval, max_tokens)}
TIER_CONFIG: dict[str, tuple[int, int]] = {
    "A": (5, 500),
    "B": (5, 800),
    "C": (10, 1000),
    "D": (20, 1500),
}


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class LLMSynthesis:
    """Curated synthesis from LLM review of accumulated facts."""

    synthesis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    window_index: int = 0
    supersedes: str | None = None
    evolution_count: int = 1
    critical_findings: list[str] | None = None
    key_relationships: list[str] | None = None
    gaps: list[str] | None = None
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize this synthesis to a JSON-ready dict."""
        return {
            "synthesis_id": self.synthesis_id,
            "text": self.text,
            "window_index": self.window_index,
            "supersedes": self.supersedes,
            "evolution_count": self.evolution_count,
            "critical_findings": self.critical_findings,
            "key_relationships": self.key_relationships,
            "gaps": self.gaps,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMSynthesis:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``LLMSynthesis``.
        """
        return cls(
            synthesis_id=data.get("synthesis_id", str(uuid.uuid4())),
            text=data.get("text", ""),
            window_index=data.get("window_index", 0),
            supersedes=data.get("supersedes"),
            evolution_count=data.get("evolution_count", 1),
            critical_findings=data.get("critical_findings"),
            key_relationships=data.get("key_relationships"),
            gaps=data.get("gaps"),
            confidence=data.get("confidence", 1.0),
            created_at=data.get("created_at", 0.0),
        )


@dataclass
class CurationConfig:
    """Configuration for LLM curation."""

    enabled: bool = True
    curation_interval: int = 5
    max_synthesis_tokens: int = 1500
    progressive: bool = True
    quality_tier: str = "B"


# ---------------------------------------------------------------------------
# LLMContextCurator
# ---------------------------------------------------------------------------


class LLMContextCurator:
    """LLM-driven context curation with progressive understanding."""

    def __init__(
        self,
        dispatch_fn: Callable[[str, str], tuple[str, Any]] | None = None,
        config: CurationConfig | None = None,
    ) -> None:
        self._dispatch_fn = dispatch_fn
        self.config = config or CurationConfig()
        self._current_synthesis: LLMSynthesis | None = None
        self._synthesis_history: list[LLMSynthesis] = []

    @property
    def current_synthesis(self) -> LLMSynthesis | None:
        """Return the current synthesis."""
        return self._current_synthesis

    @property
    def evolution_count(self) -> int:
        """Return the current evolution count."""
        if self._current_synthesis:
            return self._current_synthesis.evolution_count
        return 0

    def should_curate(self, window_index: int) -> bool:
        """Check if curation should run at this window."""
        if not self.config.enabled:
            return False
        interval, _ = TIER_CONFIG.get(
            self.config.quality_tier,
            (self.config.curation_interval, self.config.max_synthesis_tokens),
        )
        return window_index > 0 and window_index % interval == 0

    def curate(
        self,
        window_index: int,
        top_facts: list[str],
        recent_output_summary: str = "",
    ) -> LLMSynthesis | None:
        """Run curation (initial or progressive).

        Returns new synthesis or None if dispatch unavailable.
        """
        if not self._dispatch_fn:
            return None

        if self.config.progressive and self._current_synthesis:
            return self._progressive_curation(
                window_index, top_facts, recent_output_summary,
            )
        return self._initial_curation(window_index, top_facts, recent_output_summary)

    def _initial_curation(
        self,
        window_index: int,
        top_facts: list[str],
        recent_output_summary: str,
    ) -> LLMSynthesis:
        """First curation — no prior synthesis to build on."""
        facts_text = "\n".join(f"- {f}" for f in top_facts[:40])
        prompt = (
            "Analyze the extracted facts and provide:\n"
            "1. 5 most critical findings\n"
            "2. 3 key relationships between findings\n"
            "3. Current assessment\n"
            "4. What's missing / gaps\n\n"
            f"Recent output:\n{recent_output_summary[:1000]}\n\n"
            "Be concise."
        )

        output, _ = self._dispatch_fn(prompt, facts_text)  # type: ignore[misc]
        synthesis = self._parse_synthesis(output, window_index)
        self._current_synthesis = synthesis
        self._synthesis_history.append(synthesis)
        return synthesis

    def _progressive_curation(
        self,
        window_index: int,
        top_facts: list[str],
        recent_output_summary: str,
    ) -> LLMSynthesis:
        """Progressive curation — revise previous synthesis."""
        prev = self._current_synthesis
        facts_text = "\n".join(f"- {f}" for f in top_facts[:40])
        prompt = (
            "Revise your previous synthesis based on new facts.\n"
            f"Previous synthesis:\n{prev.text[:1500] if prev else ''}\n\n"
            "Update:\n"
            "1. Revised critical findings\n"
            "2. Updated relationships\n"
            "3. Updated assessment\n"
            "4. New gaps identified\n\n"
            f"New facts since last synthesis:\n{facts_text}\n\n"
            f"Recent output:\n{recent_output_summary[:500]}\n\n"
            "Be concise."
        )

        output, _ = self._dispatch_fn(prompt, "")  # type: ignore[misc]
        synthesis = self._parse_synthesis(output, window_index)
        synthesis.supersedes = prev.synthesis_id if prev else None
        synthesis.evolution_count = (prev.evolution_count + 1) if prev else 1
        self._current_synthesis = synthesis
        self._synthesis_history.append(synthesis)
        return synthesis

    def _parse_synthesis(self, output: str, window_index: int) -> LLMSynthesis:
        """Parse curation output into structured synthesis."""
        findings: list[str] = []
        relationships: list[str] = []
        gaps: list[str] = []

        section = ""
        for line in output.split("\n"):
            line_lower = line.lower().strip()
            if "finding" in line_lower or "critical" in line_lower:
                section = "findings"
            elif "relationship" in line_lower:
                section = "relationships"
            elif "gap" in line_lower or "missing" in line_lower:
                section = "gaps"
            elif "assessment" in line_lower:
                section = "assessment"

            if line.strip().startswith("-") or line.strip().startswith("•"):
                item = line.strip().lstrip("-•").strip()
                if section == "findings":
                    findings.append(item)
                elif section == "relationships":
                    relationships.append(item)
                elif section == "gaps":
                    gaps.append(item)

        return LLMSynthesis(
            text=output,
            window_index=window_index,
            critical_findings=findings or None,
            key_relationships=relationships or None,
            gaps=gaps or None,
        )

    def format_for_envelope(self) -> str:
        """Format current synthesis for envelope injection (Section 1.5)."""
        if not self._current_synthesis:
            return ""
        s = self._current_synthesis
        parts = [
            f"[LLM_SYNTHESIS (Window {s.window_index}, evolution {s.evolution_count})]",
        ]
        if s.critical_findings:
            parts.append("CRITICAL FINDINGS: " + "; ".join(s.critical_findings))
        if s.key_relationships:
            parts.append("KEY RELATIONSHIPS: " + "; ".join(s.key_relationships))
        if s.gaps:
            parts.append("GAPS: " + "; ".join(s.gaps))
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the curator state, history and configuration to a dict."""
        return {
            "current": self._current_synthesis.to_dict() if self._current_synthesis else None,
            "history": [s.to_dict() for s in self._synthesis_history],
            "config": {
                "enabled": self.config.enabled,
                "curation_interval": self.config.curation_interval,
                "max_synthesis_tokens": self.config.max_synthesis_tokens,
                "progressive": self.config.progressive,
                "quality_tier": self.config.quality_tier,
            },
        }

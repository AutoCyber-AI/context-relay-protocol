# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Critical & structural state — always-included envelope sections (§3.1).

CriticalState: goal, phase, blockers, constraints (Tier 0 — never evicted).
StructuralState: continuation tracking for document position (§04 §3.5.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CriticalState:
    """Tier-0 critical state — ALWAYS included in every envelope (§3.1).

    Tracks the task's fundamental parameters that must survive every window.
    """

    goal: str = ""
    phase: str = ""
    blockers: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    window_id: str = ""  # last window that updated this

    def to_sections(self) -> dict[str, str]:
        """Convert to envelope section dict for the formatter."""
        sections: dict[str, str] = {}
        if self.goal:
            sections["GOAL"] = self.goal
        if self.phase:
            sections["PHASE"] = self.phase
        if self.blockers:
            sections["BLOCKER"] = "\n".join(f"- {b}" for b in self.blockers)
        if self.constraints:
            sections["CONSTRAINT"] = "\n".join(f"- {c}" for c in self.constraints)
        return sections

    def update(self, **kwargs: Any) -> None:
        """Partial update of critical state fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def to_dict(self) -> dict[str, Any]:
        """Serialize critical state to a dict."""
        return {
            "goal": self.goal,
            "phase": self.phase,
            "blockers": self.blockers,
            "constraints": self.constraints,
            "window_id": self.window_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriticalState:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``CriticalState``.
        """
        return cls(
            goal=data.get("goal", ""),
            phase=data.get("phase", ""),
            blockers=data.get("blockers", []),
            constraints=data.get("constraints", []),
            window_id=data.get("window_id", ""),
        )


@dataclass
class StructuralState:
    """Document structure tracking for continuation stitching (§04 §3.5.2).

    Tracks where the LLM is in its output so continuation windows can resume
    from the correct position.
    """

    current_section: str = ""
    list_position: int = 0
    open_blocks: list[str] = field(default_factory=list)  # e.g. ["```python", "- item"]
    markdown_depth: int = 0  # heading level (1-6)
    last_heading: str = ""
    code_block_open: bool = False
    code_language: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize structural state to a dict."""
        return {
            "current_section": self.current_section,
            "list_position": self.list_position,
            "open_blocks": self.open_blocks,
            "markdown_depth": self.markdown_depth,
            "last_heading": self.last_heading,
            "code_block_open": self.code_block_open,
            "code_language": self.code_language,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StructuralState:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, Any]): The data value.
        
            Returns:
                ``StructuralState``.
        """
        return cls(
            current_section=data.get("current_section", ""),
            list_position=data.get("list_position", 0),
            open_blocks=data.get("open_blocks", []),
            markdown_depth=data.get("markdown_depth", 0),
            last_heading=data.get("last_heading", ""),
            code_block_open=data.get("code_block_open", False),
            code_language=data.get("code_language", ""),
        )

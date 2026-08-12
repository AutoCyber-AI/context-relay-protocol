# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Document map — incremental TOC tracking across windows (§04 §3.5.2)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class HeadingEntry:
    """A single heading in the document map."""

    text: str
    level: int  # 1–6 for markdown headings
    window_id: str
    position: int  # character offset within window output
    completed: bool = False  # True if content follows before next heading


@dataclass
class DocumentMap:
    """Incremental table-of-contents tracker (§04 §3.5.2).

    Maintains a running TOC as the LLM generates content across windows.
    Tracks heading hierarchy, list positions, and structural completeness.
    """

    headings: list[HeadingEntry] = field(default_factory=list)
    list_positions: dict[str, int] = field(default_factory=dict)  # heading_text → last item #
    current_section: str = ""
    total_sections_expected: int = 0  # 0 = unknown
    windows_processed: int = 0

    def update(self, text: str, window_id: str) -> list[HeadingEntry]:
        """Process a window output and update the document map.

        Returns new headings found in this window.
        Deduplicates headings by section number to prevent the same
        section from being tracked multiple times across windows (GAP C fix).
        """
        new_headings: list[HeadingEntry] = []

        # Build set of existing section numbers for dedup
        existing_section_nums: set[int] = set()
        for h in self.headings:
            m = re.match(r"(\d{1,3})\.", h.text)
            if m:
                existing_section_nums.add(int(m.group(1)))

        # Extract markdown headings
        for match in re.finditer(r"^(#{1,6})\s+(.+)$", text, re.MULTILINE):
            level = len(match.group(1))
            heading_text = match.group(2).strip()

            # Dedup: skip if this section number already exists
            sec_match = re.match(r"(\d{1,3})\.", heading_text)
            if sec_match:
                sec_num = int(sec_match.group(1))
                if sec_num in existing_section_nums:
                    continue  # duplicate section number — skip
                existing_section_nums.add(sec_num)

            entry = HeadingEntry(
                text=heading_text,
                level=level,
                window_id=window_id,
                position=match.start(),
            )
            new_headings.append(entry)
            self.headings.append(entry)

        # Mark previous headings as completed if we have new ones
        if new_headings and len(self.headings) > len(new_headings):
            for h in self.headings[:-len(new_headings)]:
                h.completed = True

        # Track list positions (numbered lists under current section)
        self._update_list_positions(text)

        # Update current section
        if new_headings:
            self.current_section = new_headings[-1].text

        self.windows_processed += 1
        return new_headings

    def get_toc(self) -> str:
        """Render the current TOC as markdown."""
        if not self.headings:
            return ""

        lines: list[str] = []
        for h in self.headings:
            indent = "  " * (h.level - 1)
            marker = "✓" if h.completed else "→" if h.text == self.current_section else "○"
            lines.append(f"{indent}{marker} {h.text}")

        return "\n".join(lines)

    def progress(self) -> float:
        """Estimate document completion progress (0.0–1.0)."""
        if not self.headings:
            return 0.0

        if self.total_sections_expected > 0:
            return min(1.0, len(self.headings) / self.total_sections_expected)

        completed = sum(1 for h in self.headings if h.completed)
        return completed / len(self.headings) if self.headings else 0.0

    def missing_sections(self, expected: list[str]) -> list[str]:
        """Compare against expected sections and return missing ones."""
        found = {h.text.lower() for h in self.headings}
        return [s for s in expected if s.lower() not in found]

    def to_dict(self) -> dict[str, object]:
        """Serialize the document map state to a JSON-ready dict."""
        return {
            "headings": [
                {
                    "text": h.text,
                    "level": h.level,
                    "window_id": h.window_id,
                    "position": h.position,
                    "completed": h.completed,
                }
                for h in self.headings
            ],
            "list_positions": self.list_positions,
            "current_section": self.current_section,
            "total_sections_expected": self.total_sections_expected,
            "windows_processed": self.windows_processed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DocumentMap:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, object]): The data value.
        
            Returns:
                ``DocumentMap``.
        """
        headings = [
            HeadingEntry(**h)  # type: ignore[arg-type]
            for h in data.get("headings", [])  # type: ignore[union-attr, attr-defined]
        ]
        return cls(
            headings=headings,
            list_positions=dict(data.get("list_positions", {})),  # type: ignore[arg-type, call-overload]
            current_section=str(data.get("current_section", "")),
            total_sections_expected=int(data.get("total_sections_expected", 0)),  # type: ignore[call-overload]
            windows_processed=int(data.get("windows_processed", 0)),  # type: ignore[call-overload]
        )

    # ── Internal ──────────────────────────────────────────────

    def _update_list_positions(self, text: str) -> None:
        """Track numbered list positions."""
        section = self.current_section or "__root__"
        max_num = 0
        for match in re.finditer(r"^(\d+)[.)]\s+", text, re.MULTILINE):
            num = int(match.group(1))
            max_num = max(max_num, num)
        if max_num > 0:
            self.list_positions[section] = max_num

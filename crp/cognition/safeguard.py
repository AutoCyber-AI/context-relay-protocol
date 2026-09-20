# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Runtime safeguard engine for cognitive presets (CRP-SPEC-046 §2.4).

Safeguards declared in a preset are evaluated at runtime against user input,
tool selections, tool arguments, and generated output.  They are advisory or
enforcing depending on their ``action`` (warn, ask, halt).  The engine returns
a structured result that the agent loop can act on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from crp.cognition.preset import Safeguard


@dataclass
class SafeguardResult:
    """Outcome of evaluating one safeguard rule."""

    rule: str
    triggered: bool
    action: str
    rationale: str
    scope: str
    matched: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "triggered": self.triggered,
            "action": self.action,
            "rationale": self.rationale,
            "scope": self.scope,
            "matched": self.matched,
        }


class SafeguardEngine:
    """Evaluate a list of declarative safeguards against runtime signals."""

    def __init__(self, rules: list[Safeguard]) -> None:
        self.rules = rules

    def evaluate(
        self,
        *,
        user_input: str = "",
        tool_id: str = "",
        tool_args: dict[str, Any] | None = None,
        output: str = "",
    ) -> list[SafeguardResult]:
        """Evaluate all rules and return triggered results."""
        results: list[SafeguardResult] = []
        for rule in self.rules:
            result = self._evaluate_rule(
                rule,
                user_input=user_input,
                tool_id=tool_id,
                tool_args=tool_args or {},
                output=output,
            )
            if result.triggered:
                results.append(result)
        return results

    def _evaluate_rule(
        self,
        rule: Safeguard,
        *,
        user_input: str,
        tool_id: str,
        tool_args: dict[str, Any],
        output: str,
    ) -> SafeguardResult:
        """Evaluate a single safeguard rule.

        Conditions may contain multiple terms separated by ``;`` or ``|``.
        A match on any term triggers the rule.
        """
        raw_condition = rule.condition or ""
        patterns = [
            p.strip().lower()
            for p in raw_condition.replace("|", ";").split(";")
            if p.strip()
        ]
        matched = ""
        triggered = False

        def _matches(text: str) -> str | None:
            for pattern in patterns:
                if pattern and re.search(re.escape(pattern), text):
                    return pattern
            return None

        if rule.scope == "global":
            text = f"{user_input} {output}".lower()
            hit = _matches(text)
            if hit:
                matched = hit
                triggered = True

        elif rule.scope == "tool":
            if tool_id:
                hit = _matches(tool_id.lower())
                if hit:
                    matched = tool_id
                    triggered = True

        elif rule.scope == "topic":
            text = f"{user_input} {output}".lower()
            hit = _matches(text)
            if hit:
                matched = hit
                triggered = True

        elif rule.scope == "output":
            hit = _matches(output.lower())
            if hit:
                matched = hit
                triggered = True

        elif rule.scope == "args":
            args_text = " ".join(str(v) for v in tool_args.values()).lower()
            hit = _matches(args_text)
            if hit:
                matched = hit
                triggered = True

        return SafeguardResult(
            rule=rule.name,
            triggered=triggered,
            action=rule.action,
            rationale=rule.rationale,
            scope=rule.scope,
            matched=matched,
        )

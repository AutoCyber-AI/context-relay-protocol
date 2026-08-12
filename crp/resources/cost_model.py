# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Provider pricing, real-time cost tracking, and budget enforcement (§6.8).

Budget invariants:
  - Warn at 80% of any cap.
  - Hard stop at 100% → BudgetExhaustedError.
  - OverheadBudget caps total overhead at 15%.
  - Feature shedding cascade: review_tier3 → orc_steps → curation →
    re_grounding → review_tier2 (lowest priority shed first).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.core.errors import BudgetExhaustedError

logger = logging.getLogger("crp.cost_model")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WARN_THRESHOLD_PCT = 80
DEFAULT_OVERHEAD_CAP = 15.0  # %
GRACE_PCT = 5.0              # high-priority features may exceed by 5%
HIGH_PRIORITY_WEIGHT = 2     # features with weight >= 2 get grace


# ---------------------------------------------------------------------------
# Provider pricing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProviderPricing:
    """Token pricing for an LLM provider (USD per 1M tokens)."""

    input_price_per_million: float = 0.0
    output_price_per_million: float = 0.0
    provider_name: str = "unknown"

    def input_cost(self, tokens: int) -> float:
        """Return estimated input cost in USD for *tokens* tokens."""
        return tokens * self.input_price_per_million / 1_000_000

    def output_cost(self, tokens: int) -> float:
        """Return estimated output cost in USD for *tokens* tokens."""
        return tokens * self.output_price_per_million / 1_000_000

    def total_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return total estimated cost in USD for input and output tokens."""
        return self.input_cost(input_tokens) + self.output_cost(output_tokens)


# Built-in pricing tables (approximate, users can override)
KNOWN_PRICING: dict[str, ProviderPricing] = {
    "gpt-4o": ProviderPricing(2.50, 10.00, "openai"),
    "gpt-4o-mini": ProviderPricing(0.15, 0.60, "openai"),
    "gpt-4-turbo": ProviderPricing(10.00, 30.00, "openai"),
    "claude-3-opus": ProviderPricing(15.00, 75.00, "anthropic"),
    "claude-3-sonnet": ProviderPricing(3.00, 15.00, "anthropic"),
    "claude-3-haiku": ProviderPricing(0.25, 1.25, "anthropic"),
    "gemini-1.5-pro": ProviderPricing(3.50, 10.50, "google"),
    "gemini-1.5-flash": ProviderPricing(0.075, 0.30, "google"),
}


# ---------------------------------------------------------------------------
# Window cost record
# ---------------------------------------------------------------------------


@dataclass
class WindowCost:
    """Cost record for a single window."""

    window_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    is_overhead: bool = False
    feature_name: str = ""


# ---------------------------------------------------------------------------
# Budget warning
# ---------------------------------------------------------------------------


class BudgetWarningLevel(str, Enum):
    """Budget warning levels."""

    NONE = "none"
    WARN = "warn"          # 80%+
    CRITICAL = "critical"  # 95%+
    EXCEEDED = "exceeded"  # 100%+


@dataclass
class BudgetWarning:
    """A budget warning emitted when approaching limits."""

    cap_type: str = ""          # "windows" | "input_tokens" | "output_tokens"
    level: BudgetWarningLevel = BudgetWarningLevel.NONE
    used: int = 0
    limit: int = 0
    pct_used: float = 0.0


# ---------------------------------------------------------------------------
# CostModel
# ---------------------------------------------------------------------------


class CostModel:
    """Real-time cost tracking with budget enforcement (§6.8).

    Tracks per-window, per-session, and cumulative costs.
    Warns at 80%, hard-stops at 100% of user-set budgets.
    """

    def __init__(
        self,
        pricing: ProviderPricing | None = None,
        max_windows: int | None = None,
        max_input_tokens: int | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        self._pricing = pricing or ProviderPricing()
        self._max_windows = max_windows
        self._max_input_tokens = max_input_tokens
        self._max_output_tokens = max_output_tokens

        # Running totals
        self._windows: list[WindowCost] = []
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0
        self._warnings: list[BudgetWarning] = []

    @property
    def pricing(self) -> ProviderPricing:
        """Return the pricing."""
        return self._pricing

    @property
    def total_windows(self) -> int:
        """Return the total windows."""
        return len(self._windows)

    @property
    def total_input_tokens(self) -> int:
        """Return the total input tokens."""
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        """Return the total output tokens."""
        return self._total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        """Return the total cost usd."""
        return self._total_cost_usd

    @property
    def warnings(self) -> list[BudgetWarning]:
        """Return the warnings."""
        return list(self._warnings)

    def record_window(
        self,
        window_id: str,
        input_tokens: int,
        output_tokens: int,
        is_overhead: bool = False,
        feature_name: str = "",
    ) -> WindowCost:
        """Record a completed window's cost. Returns the WindowCost record."""
        cost_usd = self._pricing.total_cost(input_tokens, output_tokens)
        record = WindowCost(
            window_id=window_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            is_overhead=is_overhead,
            feature_name=feature_name,
        )
        self._windows.append(record)
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        self._total_cost_usd += cost_usd
        return record

    def check_budget(self, input_tokens: int = 0) -> list[BudgetWarning]:
        """Check all budget caps. Raises BudgetExhaustedError if exceeded.

        Returns any warnings generated (80%+ of cap).
        """
        warnings: list[BudgetWarning] = []

        # Windows cap
        if self._max_windows is not None:
            w = self._check_cap(
                "windows",
                self.total_windows + 1,
                self._max_windows,
            )
            if w:
                warnings.append(w)

        # Input tokens cap
        if self._max_input_tokens is not None:
            w = self._check_cap(
                "input_tokens",
                self._total_input_tokens + input_tokens,
                self._max_input_tokens,
            )
            if w:
                warnings.append(w)

        # Output tokens cap (check cumulative)
        if self._max_output_tokens is not None:
            w = self._check_cap(
                "output_tokens",
                self._total_output_tokens,
                self._max_output_tokens,
            )
            if w:
                warnings.append(w)

        self._warnings.extend(warnings)
        return warnings

    def _check_cap(
        self, cap_type: str, used: int, limit: int
    ) -> BudgetWarning | None:
        """Check a single budget cap. Raises on exceeded."""
        if limit <= 0:
            return None

        pct = (used / limit) * 100

        if pct >= 100:
            raise BudgetExhaustedError(
                f"{cap_type} budget exceeded",
                cap_type=cap_type,
                used=used,
                limit=limit,
                windows_completed=self.total_windows,
            )

        if pct >= 95:
            level = BudgetWarningLevel.CRITICAL
        elif pct >= WARN_THRESHOLD_PCT:
            level = BudgetWarningLevel.WARN
        else:
            return None

        warning = BudgetWarning(
            cap_type=cap_type,
            level=level,
            used=used,
            limit=limit,
            pct_used=round(pct, 1),
        )
        logger.warning(
            "Budget %s: %s at %.1f%% (%d / %d)",
            level.value, cap_type, pct, used, limit,
        )
        return warning

    def estimate(
        self,
        planned_dispatches: int = 1,
        avg_input_tokens: int = 0,
        avg_output_tokens: int = 0,
    ) -> dict[str, Any]:
        """Pre-flight cost estimation."""
        total_in = planned_dispatches * avg_input_tokens
        total_out = planned_dispatches * avg_output_tokens
        cost = self._pricing.total_cost(total_in, total_out)
        return {
            "estimated_windows": planned_dispatches,
            "estimated_input_tokens": total_in,
            "estimated_output_tokens": total_out,
            "estimated_cost_usd": cost if cost > 0 else None,
        }

    def reset(self) -> None:
        """Reset all counters (on session start)."""
        self._windows.clear()
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_cost_usd = 0.0
        self._warnings.clear()


# ---------------------------------------------------------------------------
# OverheadBudget (§6.9)
# ---------------------------------------------------------------------------


@dataclass
class FeaturePriority:
    """Priority entry for overhead feature shedding."""

    name: str
    weight: int


FEATURE_PRIORITY: list[FeaturePriority] = [
    FeaturePriority("review_tier3", 3),      # Full review windows (most expensive)
    FeaturePriority("orc_steps", 2),         # Extra ORC reasoning steps
    FeaturePriority("curation", 1),          # Curation windows
    FeaturePriority("re_grounding", 1),      # Re-grounding windows
    FeaturePriority("review_tier2", 0),      # Binary probes (cheapest, shed last)
]


class OverheadDecision(str, Enum):
    """Result of overhead budget check."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass
class OverheadBudget:
    """Caps total protocol overhead across all features (§6.9).

    Default: 15% of productive windows.
    Feature shedding: lowest priority shed first.
    Never shed: extraction (always runs) and Tier 1 validation (zero LLM cost).
    """

    max_overhead_pct: float = DEFAULT_OVERHEAD_CAP
    current_overhead_windows: int = 0
    current_productive_windows: int = 0
    shed_log: list[str] = field(default_factory=list)

    @property
    def current_ratio(self) -> float:
        """Return the current ratio."""
        if self.current_productive_windows == 0:
            return 0.0
        return self.current_overhead_windows / self.current_productive_windows

    def record_productive(self) -> None:
        """Record a productive (non-overhead) window."""
        self.current_productive_windows += 1

    def check(self, feature_name: str) -> OverheadDecision:
        """Check if an overhead window is allowed for the given feature.

        Returns ALLOW or DENY. If denied, logs the shedding event.
        """
        ratio = self.current_ratio

        if ratio < self.max_overhead_pct / 100:
            self.current_overhead_windows += 1
            return OverheadDecision.ALLOW

        # Over budget — check if feature is high-priority (gets grace)
        weight = self._get_weight(feature_name)
        if weight >= HIGH_PRIORITY_WEIGHT:
            grace_limit = (self.max_overhead_pct + GRACE_PCT) / 100
            if ratio < grace_limit:
                self.current_overhead_windows += 1
                return OverheadDecision.ALLOW

        # Deny and log
        msg = (
            f"Overhead budget exceeded ({ratio:.1%} > {self.max_overhead_pct}%). "
            f"Shedding {feature_name}."
        )
        logger.info(msg)
        self.shed_log.append(msg)
        return OverheadDecision.DENY

    def reset(self) -> None:
        """Reset on session start."""
        self.current_overhead_windows = 0
        self.current_productive_windows = 0
        self.shed_log.clear()

    @staticmethod
    def _get_weight(feature_name: str) -> int:
        for fp in FEATURE_PRIORITY:
            if fp.name == feature_name:
                return fp.weight
        return 0

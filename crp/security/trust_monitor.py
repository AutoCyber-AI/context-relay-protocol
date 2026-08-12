# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Runtime trust monitor with trust decay and graduated response (SPEC-033 §3.5).

Observes agent behavior (tool calls, I/O strings, out-of-pattern actions) and
computes a session trust score that decays when indicators of compromise (IoCs)
are detected.  The monitor recommends one of four actions:

  ``allow``   — trust is healthy, continue normally.
  ``constrain`` — minor anomaly; tighten policy (e.g., require grounding).
  ``gate``    — significant anomaly; halt for checkpoint / human review.
  ``kill``    — trust collapsed; fire the kill-switch.

The monitor is intentionally lightweight and rule-first: it runs synchronously
in the governance loop and never blocks on external ML inference.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from crp.security.kill_switch import KillSwitch, KillSwitchReason

logger = logging.getLogger("crp.security.trust_monitor")


class TrustAction(str):
    """Graduated trust action recommendation."""


class TrustActions:
    """Canonical trust actions."""

    ALLOW = "allow"
    CONSTRAIN = "constrain"
    GATE = "gate"
    KILL = "kill"


@dataclass
class IndicatorOfCompromise:
    """One observed behavioral anomaly."""

    kind: str
    evidence: str
    confidence: float
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize IoC to a dict."""
        return {
            "kind": self.kind,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class TrustDecision:
    """Outcome of a trust observation."""

    action: str
    trust_score: float
    iocs: list[IndicatorOfCompromise]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize decision to a dict."""
        return {
            "action": self.action,
            "trust_score": self.trust_score,
            "iocs": [i.to_dict() for i in self.iocs],
            "reason": self.reason,
        }


@dataclass
class TrustMonitorConfig:
    """Configuration for the trust monitor."""

    initial_trust: float = 1.0
    min_trust: float = 0.0
    decay_rate: float = 0.15  # per-Ioc decay multiplier
    recovery_rate: float = 0.02  # per-allow observation recovery
    constrain_threshold: float = 0.75
    gate_threshold: float = 0.50
    kill_threshold: float = 0.25
    ioc_retention_seconds: float = 300.0

    def __post_init__(self) -> None:
        self.initial_trust = max(0.0, min(1.0, self.initial_trust))
        self.min_trust = max(0.0, min(1.0, self.min_trust))
        self.constrain_threshold = max(0.0, min(1.0, self.constrain_threshold))
        self.gate_threshold = max(0.0, min(1.0, self.gate_threshold))
        self.kill_threshold = max(0.0, min(1.0, self.kill_threshold))


class TrustMonitor:
    """Runtime behavioral trust monitor with graduated response.

    Usage::

        monitor = TrustMonitor(session_id="s-1", kill_switch=ks)
        decision = monitor.observe({"tool": "http", "output": "..."})
    """

    def __init__(
        self,
        session_id: str,
        *,
        kill_switch: KillSwitch | None = None,
        config: TrustMonitorConfig | None = None,
        custom_patterns: dict[str, re.Pattern[str]] | None = None,
    ) -> None:
        self._session_id = session_id
        self._kill_switch = kill_switch
        self._config = config or TrustMonitorConfig()
        self._trust = self._config.initial_trust
        self._iocs: list[IndicatorOfCompromise] = []
        self._patterns = custom_patterns or self._default_patterns()

    @staticmethod
    def _default_patterns() -> dict[str, re.Pattern[str]]:
        """Return default IoC regex patterns."""
        return {
            "leak_string": re.compile(
                r"(?i)(api[_\s-]?key|password|token|secret)\b[^:=\n]{0,20}[:=]\s*['\"]?[\w\-]{8,}",
                re.IGNORECASE,
            ),
            "jailbreak_marker": re.compile(
                r"(?i)(ignore\s+(all\s+)?previous\s+instructions|DAN|do\s+anything\s+now|"
                r"system\s+prompt|override\s+constraints|jailbreak)",
            ),
            "shell_injection": re.compile(
                r"(?i)(?:;\s*|^|\s)\b(?:rm\s+-rf|bash|sh|python|curl|wget)\b|`[^`]+`|\$\([^)]+\)",
            ),
            "out_of_pattern_tool": re.compile(
                r"(?i)(unauthorized|forbidden|not\s+allowed|bypass|escape\s+sandbox)",
            ),
        }

    @property
    def trust_score(self) -> float:
        """Current trust score in [0, 1]."""
        return round(self._trust, 4)

    def observe(self, observation: dict[str, Any]) -> TrustDecision:
        """Evaluate an observation and update trust.

        Args:
            observation: Dict describing the event.  Recognised keys:
                ``tool`` (str), ``output`` (str), ``input`` (str),
                ``action`` (str), ``risk_level`` (str).  Any unknown key is
                stringified and scanned for patterns.

        Returns:
            A ``TrustDecision`` with the recommended action and detected IoCs.
        """
        iocs = self._detect_iocs(observation)
        if iocs:
            decay = self._config.decay_rate * len(iocs)
            self._trust = max(self._config.min_trust, self._trust - decay)
            self._iocs.extend(iocs)
            reason = f"{len(iocs)} IoC(s) detected: {', '.join(i.kind for i in iocs)}"
        else:
            self._trust = min(1.0, self._trust + self._config.recovery_rate)
            reason = "no anomalies observed"

        self._expire_iocs()
        action = self._graduated_action()

        decision = TrustDecision(
            action=action,
            trust_score=self.trust_score,
            iocs=iocs,
            reason=reason,
        )

        if action == TrustActions.KILL and self._kill_switch is not None:
            self._kill_switch.fire(
                session_id=self._session_id,
                reason=KillSwitchReason.TRUST_THRESHOLD_CROSSED.value,
                triggered_by="crp.security.trust_monitor",
                snapshot=decision.to_dict(),
            )
        elif action == TrustActions.GATE and self._kill_switch is not None:
            # Gate does not fire the kill-switch but is a hard stop in policy.
            logger.warning(
                "Trust gate triggered for session %s: score=%.2f",
                self._session_id,
                self._trust,
            )

        return decision

    def _detect_iocs(self, observation: dict[str, Any]) -> list[IndicatorOfCompromise]:
        """Scan observation for default and custom IoC patterns."""
        found: list[IndicatorOfCompromise] = []
        now = time.time()
        for _key, value in observation.items():
            text = str(value)
            for kind, pattern in self._patterns.items():
                for match in pattern.finditer(text):
                    evidence = match.group(0)[:120]
                    found.append(
                        IndicatorOfCompromise(
                            kind=kind,
                            evidence=evidence,
                            confidence=0.7,
                            timestamp=now,
                        )
                    )
        # Deduplicate by (kind, evidence) to avoid runaway decay.
        seen: set[tuple[str, str]] = set()
        unique: list[IndicatorOfCompromise] = []
        for ioc in found:
            key = (ioc.kind, ioc.evidence)
            if key not in seen:
                seen.add(key)
                unique.append(ioc)
        return unique

    def _expire_iocs(self) -> None:
        """Drop old IoCs so trust can recover over time."""
        cutoff = time.time() - self._config.ioc_retention_seconds
        self._iocs = [ioc for ioc in self._iocs if ioc.timestamp > cutoff]

    def _graduated_action(self) -> str:
        """Map trust score to a graduated action."""
        if self._trust <= self._config.kill_threshold:
            return TrustActions.KILL
        if self._trust <= self._config.gate_threshold:
            return TrustActions.GATE
        if self._trust <= self._config.constrain_threshold:
            return TrustActions.CONSTRAIN
        return TrustActions.ALLOW

    def summary(self) -> dict[str, Any]:
        """Return a JSON-safe summary of the monitor state."""
        return {
            "session_id": self._session_id,
            "trust_score": self.trust_score,
            "action": self._graduated_action(),
            "active_iocs": [i.to_dict() for i in self._iocs],
        }

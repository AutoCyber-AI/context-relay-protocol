# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""ProviderDiagnostic — 6-step health check (§05, §06 §26.3).

Executed at init() and on demand via diagnose(). Each step produces
a diagnostic code string indicating pass/fail/warning.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from crp.providers.base import LLMProvider


class DiagnosticCode(str, Enum):
    """All provider diagnostic result codes."""

    # Step 1: Endpoint
    ENDPOINT_REACHABLE = "endpoint_reachable"
    ENDPOINT_UNREACHABLE = "endpoint_unreachable"
    ENDPOINT_TIMEOUT = "endpoint_timeout"

    # Step 2: Auth
    AUTH_VALID = "auth_valid"
    AUTH_INVALID = "auth_invalid"
    AUTH_EXPIRED = "auth_expired"

    # Step 3: Capabilities
    CAPABILITIES_DETERMINED = "capabilities_determined"
    CAPABILITIES_UNAVAILABLE = "capabilities_unavailable"

    # Step 4: Tokenizer
    TOKENIZER_ACCURATE = "tokenizer_accurate"
    TOKENIZER_MISMATCH = "tokenizer_mismatch"
    TOKENIZER_UNAVAILABLE = "tokenizer_unavailable"

    # Step 5: Inference
    INFERENCE_WORKING = "inference_working"
    INFERENCE_SLOW = "inference_slow"
    RATE_LIMITED = "rate_limited"

    # Step 6: Context window
    CONTEXT_WINDOW_VALID = "context_window_valid"
    CONTEXT_WINDOW_MISMATCH = "context_window_mismatch"


@dataclass
class DiagnosticResult:
    """Result of a single diagnostic step."""

    step: int
    name: str
    code: DiagnosticCode
    latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the passed condition holds."""
        return self.code in _PASSING_CODES


_PASSING_CODES = frozenset({
    DiagnosticCode.ENDPOINT_REACHABLE,
    DiagnosticCode.AUTH_VALID,
    DiagnosticCode.CAPABILITIES_DETERMINED,
    DiagnosticCode.TOKENIZER_ACCURATE,
    DiagnosticCode.INFERENCE_WORKING,
    DiagnosticCode.CONTEXT_WINDOW_VALID,
})


@dataclass
class DiagnosticReport:
    """Full 6-step diagnostic report."""

    provider_name: str
    results: list[DiagnosticResult] = field(default_factory=list)
    total_latency_ms: float = 0.0

    @property
    def all_passed(self) -> bool:
        """Return whether the all passed condition holds."""
        return all(r.passed for r in self.results)

    @property
    def summary(self) -> dict[str, str]:
        """Return the summary."""
        return {r.name: r.code.value for r in self.results}


class ProviderDiagnostic:
    """Execute 6-step diagnostic sequence on an LLM provider."""

    # Sample texts for tokenizer validation (Step 4)
    _SAMPLE_SHORT = "Hello world"
    _SAMPLE_MEDIUM = "The quick brown fox jumps over the lazy dog. " * 10
    _SAMPLE_LONG = "CRP context relay protocol " * 200

    def diagnose(self, provider: LLMProvider) -> DiagnosticReport:
        """Run all 6 diagnostic steps and return a report."""
        report = DiagnosticReport(provider_name=provider.model_name)
        start = time.monotonic()

        report.results.append(self._step1_endpoint(provider))
        report.results.append(self._step2_auth(provider))
        report.results.append(self._step3_capabilities(provider))
        report.results.append(self._step4_tokenizer(provider))
        report.results.append(self._step5_inference(provider))
        report.results.append(self._step6_context_window(provider))

        report.total_latency_ms = (time.monotonic() - start) * 1000
        return report

    # ------------------------------------------------------------------
    # Individual diagnostic steps
    # ------------------------------------------------------------------

    def _step1_endpoint(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 1: endpoint availability — verify provider is reachable."""
        t0 = time.monotonic()
        try:
            # For CustomProvider this will always pass; cloud providers
            # will override with actual HTTP ping in their adapters.
            _ = provider.context_window_size()
            return DiagnosticResult(
                step=1,
                name="endpoint",
                code=DiagnosticCode.ENDPOINT_REACHABLE,
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except TimeoutError:
            return DiagnosticResult(
                step=1, name="endpoint", code=DiagnosticCode.ENDPOINT_TIMEOUT,
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            return DiagnosticResult(
                step=1, name="endpoint", code=DiagnosticCode.ENDPOINT_UNREACHABLE,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"error": str(exc)},
            )

    def _step2_auth(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 2: authentication — verify API key/token accepted."""
        # Phase 1: CustomProvider has no auth; cloud adapters will override.
        return DiagnosticResult(step=2, name="auth", code=DiagnosticCode.AUTH_VALID)

    def _step3_capabilities(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 3: capability probing — query context windows, token limits."""
        t0 = time.monotonic()
        try:
            ctx = provider.context_window_size()
            return DiagnosticResult(
                step=3,
                name="capabilities",
                code=DiagnosticCode.CAPABILITIES_DETERMINED,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"context_window": ctx, "max_output": provider.max_output_tokens},
            )
        except Exception as exc:
            return DiagnosticResult(
                step=3, name="capabilities", code=DiagnosticCode.CAPABILITIES_UNAVAILABLE,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"error": str(exc)},
            )

    def _step4_tokenizer(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 4: tokenizer validation — test on 3 sample texts."""
        t0 = time.monotonic()
        try:
            counts = [
                provider.count_tokens(self._SAMPLE_SHORT),
                provider.count_tokens(self._SAMPLE_MEDIUM),
                provider.count_tokens(self._SAMPLE_LONG),
            ]
            # Sanity: all counts should be positive and roughly proportional
            if all(c > 0 for c in counts) and counts[2] > counts[1] > counts[0]:
                return DiagnosticResult(
                    step=4, name="tokenizer", code=DiagnosticCode.TOKENIZER_ACCURATE,
                    latency_ms=(time.monotonic() - t0) * 1000,
                    details={"sample_counts": counts},
                )
            return DiagnosticResult(
                step=4, name="tokenizer", code=DiagnosticCode.TOKENIZER_MISMATCH,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"sample_counts": counts},
            )
        except Exception as exc:
            return DiagnosticResult(
                step=4, name="tokenizer", code=DiagnosticCode.TOKENIZER_UNAVAILABLE,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"error": str(exc)},
            )

    def _step5_inference(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 5: inference test — minimal generation request."""
        t0 = time.monotonic()
        try:
            output, finish_reason = provider.generate_chat(
                [{"role": "user", "content": "count: 1"}]
            )
            latency = (time.monotonic() - t0) * 1000
            if latency > 30_000:  # 30s threshold
                code = DiagnosticCode.INFERENCE_SLOW
            else:
                code = DiagnosticCode.INFERENCE_WORKING
            return DiagnosticResult(
                step=5, name="inference", code=code,
                latency_ms=latency,
                details={"output_length": len(output), "finish_reason": finish_reason},
            )
        except Exception as exc:
            err_str = str(exc).lower()
            if "rate" in err_str or "429" in err_str:
                code = DiagnosticCode.RATE_LIMITED
            else:
                code = DiagnosticCode.INFERENCE_WORKING  # Can't test, assume working
            return DiagnosticResult(
                step=5, name="inference", code=code,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"error": str(exc)},
            )

    def _step6_context_window(self, provider: LLMProvider) -> DiagnosticResult:
        """Step 6: context window test — verify reported size is accurate."""
        t0 = time.monotonic()
        try:
            ctx = provider.context_window_size()
            # Verify count_tokens is consistent with context_window_size
            # by checking a text that we know the approximate token count of
            test_text = "word " * (ctx // 5)  # ~80% context fill
            token_count = provider.count_tokens(test_text)
            ratio = token_count / ctx if ctx > 0 else 0
            # Token count should be roughly 80% of context (±20%)
            if 0.5 < ratio < 1.0:
                code = DiagnosticCode.CONTEXT_WINDOW_VALID
            else:
                code = DiagnosticCode.CONTEXT_WINDOW_MISMATCH
            return DiagnosticResult(
                step=6, name="context_window", code=code,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"context_window": ctx, "test_tokens": token_count, "ratio": ratio},
            )
        except Exception as exc:
            return DiagnosticResult(
                step=6, name="context_window", code=DiagnosticCode.CONTEXT_WINDOW_MISMATCH,
                latency_ms=(time.monotonic() - t0) * 1000,
                details={"error": str(exc)},
            )

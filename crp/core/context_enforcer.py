# Copyright © 2025-2026 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Context enforcement pipeline (§7.14.4, introduced in CRP 2.2).

CRP 2.1 defined the *vocabulary* (``ContextSource``, ``ContextManifest``).
CRP 2.2 defines the *enforcement point* — the single choke-point that every
envelope assembly flows through when a manifest is attached.

Pipeline::

    observed sources + manifest
        ├─ manifest-signature verify       (fails → CONTEXT_MANIFEST_INVALID)
        ├─ manifest expiry check           (fails → CONTEXT_MANIFEST_INVALID)
        ├─ attestation mismatch scan       (mismatches → audit events)
        ├─ injection-signal scan (trusted) (hits     → audit events)
        └─ return EnforcementResult (never raises by default; policy decides)

The enforcer is deliberately *non-raising* for mismatches — in production the
right behaviour varies (block, downgrade trust, alert, ignore). Raising is
the integrator's decision via ``policy=``.

Guarantee: every observed source is either
 (a) declared in a signed, unexpired manifest, or
 (b) captured in an audit event emitted to the configured sink.

The "global application context" the pessimist asked for lives here: once
this enforcer is wired into ``assemble_messages``, no CRP request to an LLM
can occur without the orchestrator having seen and classified every
non-benign source.
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .context_source import (
    AttestationMismatch,
    ContextManifest,
    ContextSource,
    ManifestValidationError,
    SourceKind,
    SourceOrigin,
    TrustLevel,
    check_attestation,
)
from .errors import CRPError, ErrorCode

__all__ = [
    "EnforcementPolicy",
    "InjectionSignal",
    "EnforcementResult",
    "ContextEnforcer",
    "AuditSink",
    "LoggingAuditSink",
    "InMemoryAuditSink",
    "detect_injection_signals",
    "default_enforcer",
    "set_default_enforcer",
]


logger = logging.getLogger("crp.context_enforcer")


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class EnforcementPolicy(str, Enum):
    """What the enforcer does when a violation is detected.

    * ``OBSERVE`` — record audit events, never raise. Default for dev.
    * ``WARN``    — log a WARNING for every violation, still pass through.
    * ``REJECT``  — raise :class:`crp.core.errors.CRPError` with
                    :attr:`CONTEXT_ATTESTATION_MISMATCH` or
                    :attr:`CONTEXT_MANIFEST_INVALID`. Default for prod.
    """

    OBSERVE = "observe"
    WARN = "warn"
    REJECT = "reject"


# ---------------------------------------------------------------------------
# Injection-signal detector — content-side verification of declared trust
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InjectionSignal:
    """A suspicious pattern found inside a source that was labelled TRUSTED.

    Trust labels are declarative — a developer marking a ``SYSTEM_PROMPT`` as
    ``TRUSTED`` doesn't make its contents safe (they may have templated
    untrusted input into it).  This record is emitted to the audit sink so
    the gap between *declared* and *actual* trust is observable.
    """

    source: ContextSource
    pattern_id: str
    excerpt: str
    severity: str = "medium"

    def to_audit_event(self) -> dict[str, Any]:
        """Convert this signal into a CONTEXT_TRUST_VIOLATION audit event."""
        return {
            "event_type": "CONTEXT_TRUST_VIOLATION",
            "pattern_id": self.pattern_id,
            "severity": self.severity,
            "excerpt": self.excerpt[:256],
            "source": self.source.to_dict(),
            "detected_at": time.time(),
        }


# Conservative, high-precision patterns. Every hit is surfaced for human
# review — this is an *observability* pipeline, not a classifier.
_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(?:ignore|disregard|forget|override)\s+"
            r"(?:(?:all|any|previous|above|prior|the|your)\s+){1,4}"
            r"(?:instructions?|prompts?|rules?|system\s+message|directives?|guidelines?)\b",
            re.IGNORECASE,
        ),
        "high",
    ),
    (
        "role_jailbreak",
        re.compile(
            r"\b(?:you\s+are\s+now|pretend\s+to\s+be|act\s+as|roleplay\s+as|from\s+now\s+on\s+you'?re)\s+"
            r"(?:a\s+)?(?:DAN|developer\s+mode|jailb(?:reak|roken)|unrestricted|uncensored|evil|admin|root)\b",
            re.IGNORECASE,
        ),
        "high",
    ),
    (
        "exfil_secret",
        re.compile(
            r"\b(?:reveal|print|output|display|share|send)\s+"
            r"(?:your|the)\s+(?:system\s+prompt|initial\s+instructions?|api[_\s]?keys?|secret|credentials?)",
            re.IGNORECASE,
        ),
        "high",
    ),
    (
        "delimiter_forgery",
        re.compile(
            r"\[(?:END\s+)?(?:VERIFIED\s+CONTEXT|SYSTEM|USER|INST|/INST)\]|<\|im_(?:start|end)\|>|\bBEGIN\s+SYSTEM\b",
            re.IGNORECASE,
        ),
        "medium",
    ),
    (
        "payload_url",
        re.compile(
            r"(?:data|javascript|vbscript|file):[^\s]{0,256}",
            re.IGNORECASE,
        ),
        "medium",
    ),
    (
        "embedded_tool_call",
        re.compile(
            r"<(?:tool_call|function_call|execute)[\s>]|\bexec\s*\(\s*['\"]rm\s+-rf",
            re.IGNORECASE,
        ),
        "medium",
    ),
)


def detect_injection_signals(
    content: str,
    source: ContextSource,
    *,
    only_trusted: bool = True,
) -> list[InjectionSignal]:
    """Scan *content* for patterns that contradict the source's declared trust.

    By default only sources with ``trust_level == TRUSTED`` are scanned —
    untrusted content is expected to contain arbitrary text and scanning it
    would produce noise.  Pass ``only_trusted=False`` to scan everything
    (useful for a red-team sweep).

    Returns an empty list if the source is skipped or no signals match.
    """
    if only_trusted and source.trust_level != TrustLevel.TRUSTED:
        return []
    if not isinstance(content, str) or not content:
        return []

    hits: list[InjectionSignal] = []
    for pattern_id, pattern, severity in _INJECTION_PATTERNS:
        m = pattern.search(content)
        if m:
            start = max(0, m.start() - 32)
            end = min(len(content), m.end() + 32)
            hits.append(
                InjectionSignal(
                    source=source,
                    pattern_id=pattern_id,
                    excerpt=content[start:end],
                    severity=severity,
                )
            )
    return hits


# ---------------------------------------------------------------------------
# Audit sinks
# ---------------------------------------------------------------------------


class AuditSink:
    """Protocol for audit-event consumers.

    Implementations MUST be thread-safe.  The enforcer calls ``emit()`` once
    per event with a JSON-ready dict.  Events are never re-emitted.
    """

    def emit(self, event: dict[str, Any]) -> None:  # pragma: no cover - interface
        """Emit an audit event to the sink.

        Args:
            event: JSON-ready audit event dict.

        Raises:
            NotImplementedError: Subclasses must implement this method.
        """
        raise NotImplementedError


class LoggingAuditSink(AuditSink):
    """Emits to the ``crp.audit`` logger at WARNING level."""

    def __init__(self, logger_name: str = "crp.audit") -> None:
        self._log = logging.getLogger(logger_name)

    def emit(self, event: dict[str, Any]) -> None:
        """Log the audit event to the ``crp.audit`` logger at WARNING level."""
        try:
            self._log.warning("CRP_AUDIT %s", json.dumps(event, default=str))
        except (TypeError, ValueError):
            self._log.warning("CRP_AUDIT (unserialisable) %r", event)


class InMemoryAuditSink(AuditSink):
    """Thread-safe ring buffer for tests and cross-turn replay.

    The most recent *max_events* events are retained; older events are
    dropped silently.  Iterating the sink is snapshot-consistent.
    """

    def __init__(self, max_events: int = 1024) -> None:
        self._max = int(max_events)
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def emit(self, event: dict[str, Any]) -> None:
        """Store a copy of the audit event in the ring buffer."""
        with self._lock:
            self._events.append(dict(event))
            if len(self._events) > self._max:
                # Drop oldest.
                del self._events[: len(self._events) - self._max]

    @property
    def events(self) -> list[dict[str, Any]]:
        """Return the events."""
        with self._lock:
            return list(self._events)

    def clear(self) -> None:
        """Remove all stored audit events."""
        with self._lock:
            self._events.clear()


# ---------------------------------------------------------------------------
# Enforcement result
# ---------------------------------------------------------------------------


@dataclass
class EnforcementResult:
    """Outcome of a single enforcement pass.

    Always non-None even if everything passed — consumers can inspect
    ``ok``, ``mismatches``, ``injection_signals`` to decide next steps.
    """

    ok: bool
    mismatches: list[AttestationMismatch] = field(default_factory=list)
    injection_signals: list[InjectionSignal] = field(default_factory=list)
    manifest_invalid: bool = False
    manifest_invalid_reason: str = ""

    @property
    def has_violations(self) -> bool:
        """Return whether this object has violations."""
        return (
            self.manifest_invalid
            or bool(self.mismatches)
            or bool(self.injection_signals)
        )


# ---------------------------------------------------------------------------
# ContextEnforcer
# ---------------------------------------------------------------------------


@dataclass
class _ObservedContent:
    """Bundle of (source, content) presented for scanning."""

    source: ContextSource
    content: str = ""


class ContextEnforcer:
    """Single enforcement choke-point for CRP 2.2.

    Construct once per application / orchestrator and reuse across turns::

        enforcer = ContextEnforcer(
            policy=EnforcementPolicy.REJECT,
            sink=LoggingAuditSink(),
            manifest_secret=os.environ["CRP_MANIFEST_SECRET"].encode(),
        )
        result = enforcer.check(manifest, observed)
        if not result.ok:
            ...

    The same instance can be installed as the process-wide default via
    :func:`set_default_enforcer` so libraries (dispatch router, CKF, warm
    store) can find it without explicit plumbing.
    """

    def __init__(
        self,
        *,
        policy: EnforcementPolicy = EnforcementPolicy.OBSERVE,
        sink: AuditSink | None = None,
        manifest_secret: bytes | None = None,
        key_provider: Any = None,
        ledger: Any = None,
        session_id: str | None = None,
        require_signed_manifest: bool = False,
        scan_injection: bool = True,
    ) -> None:
        self.policy = policy
        self.sink: AuditSink = sink if sink is not None else LoggingAuditSink()
        self._secret = bytes(manifest_secret) if manifest_secret else None
        # KeyProvider takes precedence over raw secret when both are set.
        self._key_provider = key_provider
        self._ledger = ledger
        self._session_id = session_id
        self.require_signed_manifest = bool(require_signed_manifest)
        self.scan_injection = bool(scan_injection)
        # Track manifest_ids already recorded this session to avoid dupes.
        self._recorded_manifest_ids: set[str] = set()
        self._record_lock = threading.Lock()

    # ---------------------------------------------------------------- config

    def with_sink(self, sink: AuditSink) -> "ContextEnforcer":
        """Return a shallow copy with a different sink (ergonomic swap)."""
        return ContextEnforcer(
            policy=self.policy,
            sink=sink,
            manifest_secret=self._secret,
            key_provider=self._key_provider,
            ledger=self._ledger,
            session_id=self._session_id,
            require_signed_manifest=self.require_signed_manifest,
            scan_injection=self.scan_injection,
        )

    def _verify_signature(self, manifest: ContextManifest) -> tuple[bool, str]:
        """Try KeyProvider candidates first, then the static secret.

        Returns ``(ok, reason)``. ``ok=True`` when verification succeeded;
        ``ok=False`` when no candidate matched or no key source is
        available. ``reason`` distinguishes "unverifiable" (we had a
        signature but no way to check it) from "invalid" (we checked and
        it failed).
        """
        if manifest.signature is None:
            return False, "manifest_unsigned"
        if self._key_provider is not None:
            try:
                if self._key_provider.verify(manifest):
                    return True, ""
                return False, "manifest_signature_invalid"
            except ManifestValidationError as exc:
                return False, f"manifest_verify_raised:{exc}"
        if self._secret is not None:
            try:
                if manifest.verify(self._secret):
                    return True, ""
                return False, "manifest_signature_invalid"
            except ManifestValidationError as exc:
                return False, f"manifest_verify_raised:{exc}"
        return False, "manifest_unverifiable"

    # --------------------------------------------------------------- manifest

    def _validate_manifest(self, manifest: ContextManifest | None) -> tuple[bool, str]:
        """Return ``(ok, reason)`` — signature + expiry check."""
        if manifest is None:
            if self.require_signed_manifest:
                return False, "manifest_missing"
            return True, ""
        if manifest.is_expired():
            return False, "manifest_expired"
        has_key_source = self._key_provider is not None or self._secret is not None
        if self.require_signed_manifest:
            if manifest.signature is None:
                return False, "manifest_unsigned"
            if not has_key_source:
                return False, "no_enforcer_secret_configured"
            return self._verify_signature(manifest)
        # Best-effort verify whenever we have both a signature and a key source.
        if manifest.signature is not None and has_key_source:
            return self._verify_signature(manifest)
        # Signed but no way to verify — surface explicitly rather than
        # silently pretending the signature is valid.
        if manifest.signature is not None and not has_key_source:
            return False, "manifest_unverifiable"
        return True, ""

    # ------------------------------------------------------------------ core

    def check(
        self,
        manifest: ContextManifest | None,
        observed: Sequence[ContextSource | _ObservedContent],
        *,
        emit: bool = True,
    ) -> EnforcementResult:
        """Run the full enforcement pipeline.

        Accepts either bare :class:`ContextSource` objects (no content
        scanning) or :class:`_ObservedContent` bundles (source + text, which
        enables injection-signal detection for TRUSTED sources).

        If ``emit`` is True (default), audit events are pushed to the sink.
        Pass ``emit=False`` for dry-run analysis.
        """
        sources: list[ContextSource] = []
        payloads: list[tuple[ContextSource, str]] = []
        for item in observed:
            if isinstance(item, _ObservedContent):
                sources.append(item.source)
                payloads.append((item.source, item.content))
            elif isinstance(item, ContextSource):
                sources.append(item)
                # For bare sources, scan any metadata/retrieval_query the
                # source itself carries. This ensures injection detection
                # is reachable even when callers don't construct bundles.
                scan_text_parts: list[str] = []
                if item.retrieval_query:
                    scan_text_parts.append(item.retrieval_query)
                if item.upstream_uri:
                    scan_text_parts.append(item.upstream_uri)
                if scan_text_parts:
                    payloads.append((item, "\n".join(scan_text_parts)))
            else:
                raise TypeError(
                    f"Observed items must be ContextSource or _ObservedContent, got {type(item).__name__}"
                )

        mf_ok, mf_reason = self._validate_manifest(manifest)
        result = EnforcementResult(
            ok=True,
            manifest_invalid=not mf_ok,
            manifest_invalid_reason=mf_reason,
        )

        if not mf_ok:
            result.ok = False
            if emit:
                self.sink.emit(
                    {
                        "event_type": "CONTEXT_MANIFEST_INVALID",
                        "manifest_id": manifest.manifest_id if manifest else "",
                        "reason": mf_reason,
                        "detected_at": time.time(),
                    }
                )
            if self.policy == EnforcementPolicy.REJECT:
                raise CRPError(
                    ErrorCode.CONTEXT_MANIFEST_INVALID,
                    f"Context manifest invalid: {mf_reason}",
                )
            if self.policy == EnforcementPolicy.WARN:
                logger.warning("CRP manifest invalid: %s", mf_reason)
            # OBSERVE / WARN still continue to scan sources for completeness
            # when the manifest is merely missing (not tampered).
            if mf_reason not in ("manifest_missing",):
                return result

        # Attestation scan
        mismatches = check_attestation(sources, manifest if mf_ok else None)
        if mismatches:
            result.mismatches = mismatches
            result.ok = False
            if emit:
                for m in mismatches:
                    self.sink.emit(m.to_audit_event())

        # Injection scan
        if self.scan_injection:
            signals: list[InjectionSignal] = []
            for src, content in payloads:
                signals.extend(detect_injection_signals(content, src))
            if signals:
                result.injection_signals = signals
                result.ok = False
                if emit:
                    for s in signals:
                        self.sink.emit(s.to_audit_event())

        # Policy
        if result.has_violations:
            if self.policy == EnforcementPolicy.REJECT:
                code = ErrorCode.CONTEXT_ATTESTATION_MISMATCH
                bad_ids = [m.observed_source.source_id for m in result.mismatches if m.observed_source.source_id]
                bad_patterns = [s.pattern_id for s in result.injection_signals]
                detail_parts: list[str] = []
                if bad_ids:
                    detail_parts.append(f"mismatched_sources={bad_ids[:5]}")
                if bad_patterns:
                    detail_parts.append(f"injection_patterns={bad_patterns[:5]}")
                detail = "; ".join(detail_parts) if detail_parts else "violation detected"
                raise CRPError(
                    code,
                    f"{len(result.mismatches)} attestation mismatch(es), "
                    f"{len(result.injection_signals)} injection signal(s): {detail}",
                )
            if self.policy == EnforcementPolicy.WARN:
                logger.warning(
                    "CRP enforcement: %d mismatches, %d injection signals",
                    len(result.mismatches),
                    len(result.injection_signals),
                )

        # Auto-record to ledger on successful verification (fresh manifests only).
        self._maybe_record(manifest, result)

        return result

    # --------------------------------------------------------------- ledger

    def _maybe_record(
        self,
        manifest: ContextManifest | None,
        result: EnforcementResult,
    ) -> None:
        """Append *manifest* to the configured ledger if conditions met."""
        if (
            self._ledger is None
            or self._session_id is None
            or manifest is None
            or result.manifest_invalid
        ):
            return
        mid = manifest.manifest_id
        with self._record_lock:
            if mid in self._recorded_manifest_ids:
                return
            try:
                self._ledger.record(self._session_id, manifest)
                self._recorded_manifest_ids.add(mid)
            except (ValueError, ManifestValidationError) as exc:
                logger.warning("CRP ledger record failed: %s", exc)

    # ------------------------------------------------------------ per-turn

    def check_messages(
        self,
        messages: Sequence[dict[str, Any]],
        manifest: ContextManifest | None = None,
        *,
        session_id: str | None = None,
        derive_manifest: bool = False,
        emit: bool = True,
    ) -> EnforcementResult:
        """Re-run the enforcement pipeline against a full chat history (CRP 2.3).

        For every message the enforcer derives a :class:`ContextSource`
        (system/user/assistant/tool → kind+trust) and an observed-content
        bundle, so both *attestation* and *injection* scans run over the
        actual bytes that will be sent to the model. Tool-call loops
        benefit most: ``tool_result`` payloads are re-validated every
        turn instead of only at first assembly.

        When ``derive_manifest=True`` and *manifest* is ``None``, a fresh
        manifest is derived from the messages themselves (unsigned, one
        source per message). This is the "belt-and-braces" path for
        integrators who want a per-turn audit record even if they never
        authored a manifest.
        """
        from .manifest_derive import derive_sources_from_messages, derive_manifest_from_messages

        sid = session_id or self._session_id
        effective_manifest = manifest
        if effective_manifest is None and derive_manifest:
            effective_manifest = derive_manifest_from_messages(
                messages, session_id=sid
            )
        bundles: list[_ObservedContent] = []
        for source, text in derive_sources_from_messages(
            messages, session_id=sid
        ):
            bundles.append(_ObservedContent(source=source, content=text))
        return self.check(effective_manifest, bundles, emit=emit)

    def check_tool_result(
        self,
        content: str | dict[str, Any] | list[Any],
        *,
        source: ContextSource | None = None,
        manifest: ContextManifest | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        emit: bool = True,
    ) -> EnforcementResult:
        """Validate a single tool-call / function-call result (CRP 2.3).

        Runs the same pipeline as :meth:`check` but bounded to one
        payload, so agent loops can re-validate each tool response
        individually.  If *source* is not supplied, a derived
        ``FUNCTION_CALL`` source is constructed with an ``UNKNOWN`` trust
        level (tool outputs are never implicitly trusted).
        """
        from .manifest_derive import _flatten_content, content_hash

        text = _flatten_content(content)
        if source is None:
            metadata: dict[str, Any] = {
                "content_sha256": content_hash(text) if text else "sha256:",
                "content_len": len(text),
            }
            if tool_call_id:
                metadata["tool_call_id"] = str(tool_call_id)[:128]
            if tool_name:
                metadata["tool_name"] = str(tool_name)[:128]
            source = ContextSource(
                kind=SourceKind.FUNCTION_CALL,
                source_id=f"tool_result:{tool_call_id or tool_name or 'anon'}",
                origin=SourceOrigin.OBSERVED,
                trust_level=TrustLevel.UNKNOWN,
                retrieved_at=time.time(),
                metadata=metadata,
            )
        return self.check(manifest, [_ObservedContent(source=source, content=text)], emit=emit)


# ---------------------------------------------------------------------------
# Convenience: observed-content bundle factory
# ---------------------------------------------------------------------------


def observed_content(source: ContextSource, content: str = "") -> Any:
    """Build an ``_ObservedContent`` bundle for :meth:`ContextEnforcer.check`.

    Kept as a function (rather than exporting the class) so the public
    surface area stays minimal — the bundle is an implementation detail.
    """
    return _ObservedContent(source=source, content=content or "")


__all__.append("observed_content")


# ---------------------------------------------------------------------------
# Process-wide default (opt-in + env-var safety net, CRP 2.3)
# ---------------------------------------------------------------------------


_DEFAULT: ContextEnforcer | None = None
_DEFAULT_LOCK = threading.Lock()
_ENV_AUTO_INSTALL_DONE = False
_ENV_VAR = "CRP_DEFAULT_ENFORCEMENT"


def _maybe_install_from_env() -> None:
    """Auto-install a default enforcer if ``CRP_DEFAULT_ENFORCEMENT`` is set.

    Runs at most once per process. Accepted values (case-insensitive):
    ``observe``, ``warn``, ``reject``, ``off``. Any other value is logged
    and ignored. When ``CRP_MANIFEST_SECRET`` is present, an
    :class:`~crp.core.manifest_ledger.EnvVarKeyProvider` is attached
    automatically so signature verification works without further wiring.

    This closes the footgun where an integrator forgets to call
    :func:`set_default_enforcer` — operations teams can flip the env var
    to ``observe`` in production and get an audit trail immediately.
    """
    global _ENV_AUTO_INSTALL_DONE, _DEFAULT
    with _DEFAULT_LOCK:
        if _ENV_AUTO_INSTALL_DONE:
            return
        _ENV_AUTO_INSTALL_DONE = True
        if _DEFAULT is not None:
            return  # Explicit opt-in wins — don't clobber.
        import os as _os
        raw = _os.environ.get(_ENV_VAR, "").strip().lower()
        if raw in ("", "off", "none", "disabled", "0", "false"):
            return
        try:
            policy = EnforcementPolicy(raw)
        except ValueError:
            logger.warning(
                "CRP: %s=%r is invalid; expected observe/warn/reject/off",
                _ENV_VAR,
                raw,
            )
            return
        key_provider: Any = None
        if _os.environ.get("CRP_MANIFEST_SECRET"):
            try:
                from crp.core.manifest_ledger import EnvVarKeyProvider
                key_provider = EnvVarKeyProvider()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "CRP: failed to build EnvVarKeyProvider from env: %s", exc
                )
        _DEFAULT = ContextEnforcer(policy=policy, key_provider=key_provider)
        logger.info(
            "CRP: installed default enforcer policy=%s from %s",
            policy.value,
            _ENV_VAR,
        )


def default_enforcer() -> ContextEnforcer | None:
    """Return the installed process-wide enforcer, or ``None``.

    On first call, honours the ``CRP_DEFAULT_ENFORCEMENT`` environment
    variable (``observe|warn|reject|off``) as a safety net when
    :func:`set_default_enforcer` was never called. Explicit calls to
    :func:`set_default_enforcer` always take precedence — env auto-install
    only fires when no enforcer has been installed yet.
    """
    _maybe_install_from_env()
    with _DEFAULT_LOCK:
        return _DEFAULT


def set_default_enforcer(enforcer: ContextEnforcer | None) -> ContextEnforcer | None:
    """Install *enforcer* as the process-wide default. Returns the previous one.

    Marks env auto-install as "done" so a later ``default_enforcer()`` call
    does not clobber an explicit ``None``.
    """
    global _DEFAULT, _ENV_AUTO_INSTALL_DONE
    with _DEFAULT_LOCK:
        old = _DEFAULT
        _DEFAULT = enforcer
        _ENV_AUTO_INSTALL_DONE = True
        return old


def _reset_default_enforcer_for_tests() -> None:
    """Testing hook: clear the default + re-arm env auto-install."""
    global _DEFAULT, _ENV_AUTO_INSTALL_DONE
    with _DEFAULT_LOCK:
        _DEFAULT = None
        _ENV_AUTO_INSTALL_DONE = False

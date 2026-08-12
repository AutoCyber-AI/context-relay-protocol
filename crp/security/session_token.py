# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""CRP Session Token v3 — signed, stateless session relay (CRP-SPEC-007).

The session token carries signed session state in the ``CRP-Set-Session``
response header.  The client echoes it back via ``CRP-Session-Token``.  Any
gateway instance sharing the master key can validate the signature and resume
the session — no shared session store required.

Pipeline:

* :func:`build_token` — serialise + HMAC-sign a :class:`SessionTokenPayload`.
* :func:`format_set_session_header` — render the ``CRP-Set-Session`` wire value.
* :func:`parse_token` — split + decode a token without verifying.
* :func:`validate_token` — full validation (signature, expiry, chain tip,
  scope, policy-hash tightening, nonce) per SPEC-007 §5.

Signing (SPEC-007 §3)::

    session_signing_key = HKDF-SHA256(IKM=master_key, salt=sid_bytes,
                                      info="crp-session-sign-v3", L=32)
    header    = base64url({"alg":"HS256","typ":"CRP"})
    payload   = base64url(json(payload_object))
    signature = HMAC-SHA256(header + "." + payload, session_signing_key)
    token     = payload + "." + base64url(signature)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from enum import Enum

# Fixed JOSE-style header (typ=CRP distinguishes from JWT) — SPEC-007 §3.2.
_HEADER_OBJ = {"alg": "HS256", "typ": "CRP"}
_HKDF_INFO = b"crp-session-sign-v3"
_MAX_PAYLOAD_B64_BYTES = 4096  # SPEC-007 §2.4
DEFAULT_TOKEN_LIFETIME = 3600  # seconds (SPEC-007 §4.4)


# ── base64url helpers (no padding) ─────────────────────────────────────────


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# ── HKDF-SHA256 (RFC 5869) ─────────────────────────────────────────────────


def _hkdf_sha256(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    """Derive *length* bytes from *ikm* using HKDF-SHA256."""
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()  # extract
    out = b""
    t = b""
    counter = 1
    while len(out) < length:
        t = hmac.new(prk, t + info + bytes([counter]), hashlib.sha256).digest()
        out += t
        counter += 1
    return out[:length]


def derive_signing_key(master_key: bytes, session_id: str) -> bytes:
    """Derive the per-session 256-bit signing key (SPEC-007 §3.1)."""
    return _hkdf_sha256(
        ikm=master_key,
        salt=session_id.encode("utf-8"),
        info=_HKDF_INFO,
        length=32,
    )


# ── Payload ─────────────────────────────────────────────────────────────────


@dataclass
class SessionTokenPayload:
    """Decoded CRP session-token payload (SPEC-007 §2.2)."""

    sid: str
    win: int = 1
    qh: list[str] = field(default_factory=list)
    sb: float = 1.0
    ct: str = ""  # HMAC chain tip
    cid: str = ""  # continuation id
    dag: str = "LINEAR"
    strategy: str = ""  # serialised as "str"
    pol: str = ""  # policy hash
    ckf: str = ""  # CKF state hash
    scope: str = ""  # API key prefix
    iat: int = 0
    exp: int = 0
    nonce: str = ""
    kv: int | None = None  # master-key version (SPEC-007 §6.2)
    v: str = "3.0.0"
    # v4 additions (SPEC-007 amendment / SPEC-030 §4.2, SPEC-027 §2.5)
    cso_ref: str = ""            # HMAC of latest CSO (SPEC-030)
    coverage_set_hash: str = ""  # SHA-256 of Coverage Set state (SPEC-024)
    embedding_model_id: str = "" # must match across all windows (SPEC-027 §2.5)

    def to_json_obj(self) -> dict[str, object]:
        """Serialize the payload to a JSON-serializable dict."""
        obj: dict[str, object] = {
            "v": self.v,
            "sid": self.sid,
            "win": self.win,
            "qh": list(self.qh),
            "sb": self.sb,
            "ct": self.ct,
            "cid": self.cid,
            "dag": self.dag,
            "str": self.strategy,
            "pol": self.pol,
            "ckf": self.ckf,
            "scope": self.scope,
            "iat": self.iat,
            "exp": self.exp,
            "nonce": self.nonce,
        }
        if self.kv is not None:
            obj["kv"] = self.kv
        # v4 CSO fields (optional, only included when set)
        if self.cso_ref:
            obj["cso_ref"] = self.cso_ref
        if self.coverage_set_hash:
            obj["cov_hash"] = self.coverage_set_hash
        if self.embedding_model_id:
            obj["emb_mid"] = self.embedding_model_id
        return obj

    @classmethod
    def from_json_obj(cls, obj: dict[str, object]) -> SessionTokenPayload:
        """Create a new instance from a JSON-compatible object.
        
            Args:
                obj (dict[str, object]): The obj value.
        
            Returns:
                ``SessionTokenPayload``.
        """
        return cls(
            v=str(obj.get("v", "3.0.0")),
            sid=str(obj.get("sid", "")),
            win=int(obj.get("win", 1) or 1),
            qh=[str(x) for x in (obj.get("qh") or [])],
            sb=float(obj.get("sb", 1.0)),
            ct=str(obj.get("ct", "")),
            cid=str(obj.get("cid", "")),
            dag=str(obj.get("dag", "LINEAR")),
            strategy=str(obj.get("str", "")),
            pol=str(obj.get("pol", "")),
            ckf=str(obj.get("ckf", "")),
            scope=str(obj.get("scope", "")),
            iat=int(obj.get("iat", 0) or 0),
            exp=int(obj.get("exp", 0) or 0),
            nonce=str(obj.get("nonce", "")),
            kv=(int(obj["kv"]) if obj.get("kv") is not None else None),
            cso_ref=str(obj.get("cso_ref", "")),
            coverage_set_hash=str(obj.get("cov_hash", "")),
            embedding_model_id=str(obj.get("emb_mid", "")),
        )


# ── Signing / building ──────────────────────────────────────────────────────


def _header_b64() -> str:
    return _b64url_encode(
        json.dumps(_HEADER_OBJ, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )


def _sign(payload_b64: str, key: bytes) -> str:
    msg = (_header_b64() + "." + payload_b64).encode("ascii")
    return _b64url_encode(hmac.new(key, msg, hashlib.sha256).digest())


def build_token(payload: SessionTokenPayload, master_key: bytes) -> str:
    """Serialise + sign *payload*, returning ``payload_b64.signature_b64``.

    Raises:
        ValueError: if the encoded payload exceeds 4096 bytes (SPEC-007 §2.4).
    """
    body = json.dumps(payload.to_json_obj(), separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(body)
    if len(payload_b64) > _MAX_PAYLOAD_B64_BYTES:
        raise ValueError(
            f"session token payload {len(payload_b64)}B exceeds 4096B limit"
        )
    key = derive_signing_key(master_key, payload.sid)
    sig_b64 = _sign(payload_b64, key)
    return f"{payload_b64}.{sig_b64}"


def issue_token(
    *,
    session_id: str,
    master_key: bytes,
    window: int = 1,
    quality_history: list[str] | None = None,
    safety_budget: float = 1.0,
    chain_tip: str = "",
    continuation_id: str = "",
    dag_pattern: str = "LINEAR",
    strategy: str = "",
    policy_hash: str = "",
    ckf_hash: str = "",
    scope: str = "",
    nonce: str = "",
    key_version: int | None = None,
    lifetime: int = DEFAULT_TOKEN_LIFETIME,
    now: int | None = None,
) -> tuple[str, SessionTokenPayload]:
    """Convenience: build a fresh payload with iat/exp and sign it."""
    issued = int(now if now is not None else time.time())
    payload = SessionTokenPayload(
        sid=session_id,
        win=window,
        qh=list(quality_history or []),
        sb=safety_budget,
        ct=chain_tip,
        cid=continuation_id,
        dag=dag_pattern,
        strategy=strategy,
        pol=policy_hash,
        ckf=ckf_hash,
        scope=scope,
        iat=issued,
        exp=issued + lifetime,
        nonce=nonce,
        kv=key_version,
    )
    return build_token(payload, master_key), payload


def format_set_session_header(
    token: str, payload: SessionTokenPayload, *, max_age: int | None = None
) -> str:
    """Render the ``CRP-Set-Session`` header value (SPEC-007 §2.1)."""
    if max_age is None:
        max_age = max(0, payload.exp - payload.iat) or DEFAULT_TOKEN_LIFETIME
    parts = [
        f"token={token}",
        "Path=/",
        f"Max-Age={max_age}",
        "Signed",
        "SameSite=Strict",
        f"Window={payload.win}",
    ]
    if payload.qh:
        parts.append("QualityHistory=" + ",".join(payload.qh))
    return "; ".join(parts)


# ── Parsing / validation ──────────────────────────────────────────────────


def parse_token(token: str) -> SessionTokenPayload:
    """Split + decode a token's payload **without** verifying its signature."""
    payload_b64, _, _ = token.partition(".")
    obj = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    return SessionTokenPayload.from_json_obj(obj)


class TokenStatus(str, Enum):
    """Validation outcomes (SPEC-007 §5)."""

    VALID = "VALID"
    BAD_SIGNATURE = "BAD_SIGNATURE"  # → HTTP 401
    EXPIRED = "EXPIRED"  # → HTTP 401, Retry-After: 0
    CHAIN_TIP_MISMATCH = "CHAIN_TIP_MISMATCH"  # → HTTP 409
    SCOPE_MISMATCH = "SCOPE_MISMATCH"  # → HTTP 403
    POLICY_NOT_TIGHTER = "POLICY_NOT_TIGHTER"  # → HTTP 403
    NONCE_MISMATCH = "NONCE_MISMATCH"  # → HTTP 400
    MALFORMED = "MALFORMED"  # → HTTP 400


_STATUS_HTTP: dict[TokenStatus, int] = {
    TokenStatus.VALID: 200,
    TokenStatus.BAD_SIGNATURE: 401,
    TokenStatus.EXPIRED: 401,
    TokenStatus.CHAIN_TIP_MISMATCH: 409,
    TokenStatus.SCOPE_MISMATCH: 403,
    TokenStatus.POLICY_NOT_TIGHTER: 403,
    TokenStatus.NONCE_MISMATCH: 400,
    TokenStatus.MALFORMED: 400,
}


@dataclass
class TokenValidation:
    """Result of :func:`validate_token`."""

    status: TokenStatus
    payload: SessionTokenPayload | None = None

    @property
    def ok(self) -> bool:
        """Return whether the ok condition holds."""
        return self.status is TokenStatus.VALID

    @property
    def http_status(self) -> int:
        """Return the HTTP status."""
        return _STATUS_HTTP[self.status]


def _verify_signature(token: str, master_keys: list[bytes]) -> tuple[bool, str | None]:
    """Verify the token signature against any of *master_keys* (rotation)."""
    payload_b64, _, sig_b64 = token.partition(".")
    if not payload_b64 or not sig_b64:
        return False, payload_b64 or None
    obj = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    sid = str(obj.get("sid", ""))
    for mk in master_keys:
        expected = _sign(payload_b64, derive_signing_key(mk, sid))
        if hmac.compare_digest(expected, sig_b64):
            return True, payload_b64
    return False, payload_b64


def validate_token(
    token: str,
    *,
    master_keys: bytes | list[bytes],
    expected_chain_tip: str | None = None,
    expected_scope: str | None = None,
    presented_policy_hash: str | None = None,
    policy_is_more_restrictive: bool | None = None,
    presented_nonce: str | None = None,
    now: int | None = None,
) -> TokenValidation:
    """Full session-token validation (SPEC-007 §5).

    Args:
        token: the raw ``CRP-Session-Token`` value.
        master_keys: the gateway master key(s).  A list allows trying both the
            current and previous key during master-key rotation (SPEC-007 §6).
        expected_chain_tip: gateway's recorded HMAC chain tip for the session.
            Mismatch → 409 (stale/replayed token).
        expected_scope: API-key prefix from the request ``Authorization``.
            Mismatch → 403.
        presented_policy_hash: hash of a ``CRP-Safety-Policy`` presented with
            the request.  If it differs from the token's ``pol`` it MUST be more
            restrictive (set *policy_is_more_restrictive*) else → 403.
        policy_is_more_restrictive: caller-computed tightening check.
        presented_nonce: ``CRP-Safety-Nonce`` from the request.  Mismatch → 400.
        now: override current epoch seconds (for testing).

    Returns:
        :class:`TokenValidation`.
    """
    keys = [master_keys] if isinstance(master_keys, (bytes, bytearray)) else list(master_keys)

    # 5.1 Signature.
    try:
        ok, _ = _verify_signature(token, keys)
    except Exception:  # noqa: BLE001 — any decode failure is malformed
        return TokenValidation(TokenStatus.MALFORMED)
    if not ok:
        return TokenValidation(TokenStatus.BAD_SIGNATURE)

    payload = parse_token(token)
    current = int(now if now is not None else time.time())

    # 5.2 Expiry.
    if payload.exp and current > payload.exp:
        return TokenValidation(TokenStatus.EXPIRED, payload)

    # 5.3 Chain tip.
    if expected_chain_tip is not None and payload.ct != expected_chain_tip:
        return TokenValidation(TokenStatus.CHAIN_TIP_MISMATCH, payload)

    # 5.4 Scope.
    if expected_scope is not None and payload.scope != expected_scope:
        return TokenValidation(TokenStatus.SCOPE_MISMATCH, payload)

    # 5.5 Policy-hash tightening.
    if presented_policy_hash is not None and presented_policy_hash != payload.pol:
        if not policy_is_more_restrictive:
            return TokenValidation(TokenStatus.POLICY_NOT_TIGHTER, payload)

    # 5.6 Nonce.
    if presented_nonce is not None and payload.nonce and presented_nonce != payload.nonce:
        return TokenValidation(TokenStatus.NONCE_MISMATCH, payload)

    return TokenValidation(TokenStatus.VALID, payload)

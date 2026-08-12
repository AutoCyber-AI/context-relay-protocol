# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""RQA Stages 6-9 + re-dispatch protocol (CRP-SPEC-005 §8-11, §19).

These are the *Response Quality Assurance* stages that operate across windows
in a session (as opposed to the single-window fidelity/attribution stages):

* **Stage 6 — Cross-window coherence** (§8): contradictions vs prior windows.
* **Stage 7 — Repetition** (§9): 4-gram + semantic overlap with prior windows.
* **Stage 8 — Completeness** (§10): sub-query coverage of the cumulative answer.
* **Stage 9 — Flow & continuity** (§11): opening/topic/register/transition.
* **Re-dispatch** (§19): trigger conditions + augmented-prompt construction.

The module is *callback-pluggable* and degrades gracefully.  A caller MAY pass
an ``embedder`` (text → vector) and/or an ``nli`` (premise, hypothesis →
P(contradiction)); when absent, lexical fallbacks (bag-of-words cosine, Jaccard,
4-gram overlap, rule-based contradiction) are used so the engine never
hard-depends on a model.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum

Embedder = Callable[[str], Sequence[float]]
NLI = Callable[[str, str], float]  # → P(contradiction) ∈ [0,1]

_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[.%]\d+)?")
_SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_NUM_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")

_STOPWORDS = frozenset(
    """a an the of to in on for and or but with without as at by from into is are was were be been
    being this that these those it its their his her our your my we you they he she i them us
    which who whom whose what when where why how than then so such not no nor can could will would
    shall should may might must do does did done have has had having about over under between""".split()
)

_TRANSITION_MARKERS = (
    "furthermore", "moreover", "in addition", "additionally", "building on",
    "as noted", "as mentioned", "as previously", "consequently", "therefore",
    "thus", "however", "nevertheless", "in conclusion", "to summarise",
    "to summarize", "next", "the next", "following on", "continuing",
    "these obligations", "this classification", "as a result",
)

_POSITIVE = frozenset({"approved", "positive", "increase", "increased", "grew", "growth", "up", "rising", "gain"})
_NEGATIVE = frozenset({"rejected", "negative", "decrease", "decreased", "declined", "decline", "down", "falling", "loss"})


# ── lexical helpers ─────────────────────────────────────────────────────────


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text)]


def _content_tokens(text: str) -> list[str]:
    return [t for t in _tokens(text) if t not in _STOPWORDS]


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT_RE.split(text.strip()) if s.strip()]


def _bow_cosine(a: str, b: str) -> float:
    ta, tb = _content_tokens(a), _content_tokens(b)
    if not ta or not tb:
        return 0.0
    va: dict[str, int] = {}
    vb: dict[str, int] = {}
    for t in ta:
        va[t] = va.get(t, 0) + 1
    for t in tb:
        vb[t] = vb.get(t, 0) + 1
    common = set(va) & set(vb)
    dot = sum(va[t] * vb[t] for t in common)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    return dot / (na * nb) if na and nb else 0.0


def _vec_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _similarity(a: str, b: str, embedder: Embedder | None) -> float:
    if embedder is not None:
        try:
            return max(0.0, min(1.0, _vec_cosine(embedder(a), embedder(b))))
        except Exception:  # noqa: BLE001 — fall back to lexical
            pass
    return _bow_cosine(a, b)


def _ngrams(tokens: list[str], n: int = 4) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)} if len(tokens) >= n else set()


# ═══════════════════════════════════════════════════════════════════════════
# Stage 6 — Cross-window coherence (§8)
# ═══════════════════════════════════════════════════════════════════════════


class ContradictionSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class CrossWindowContradiction:
    current_claim: str
    prior_claim: str
    severity: ContradictionSeverity
    contradiction_type: str  # numeric / logical / temporal / stance / minor
    probability: float = 1.0


@dataclass
class CoherenceResult:
    """Stage 6 output."""

    contradictions: list[CrossWindowContradiction] = field(default_factory=list)

    @property
    def contradiction_ratio(self) -> float:
        """Fraction signal for the RQA score; 0.0 when none found."""
        return 0.0 if not self.contradictions else min(1.0, len(self.contradictions) / 5.0)

    @property
    def has_critical(self) -> bool:
        """Return whether this object has critical."""
        return any(c.severity is ContradictionSeverity.CRITICAL for c in self.contradictions)

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        return {"CRP-Safety-Contradictions": f"{len(self.contradictions)}; scope=cross-window"}


def _nums(text: str) -> list[str]:
    return [n.replace(",", "") for n in _NUM_RE.findall(text)]


def _classify_contradiction(current: str, prior: str) -> tuple[bool, str, ContradictionSeverity]:
    """Rule-based contradiction classifier (lexical NLI fallback, §8.4)."""
    cl, pl = current.lower(), prior.lower()
    cn, pn = _nums(current), _nums(prior)

    # Numeric contradiction: shared topic, differing numbers.
    if cn and pn and set(cn) != set(pn) and _bow_cosine(current, prior) >= 0.35:
        # Minor inconsistency if both hedged ("about"/"approximately") and close.
        hedged = any(w in cl for w in ("about", "approximately", "around")) and any(
            w in pl for w in ("about", "approximately", "around")
        )
        if hedged:
            return True, "minor", ContradictionSeverity.LOW
        return True, "numeric", ContradictionSeverity.CRITICAL

    # Temporal contradiction: differing year mentions on a shared topic.
    cy = {n for n in cn if len(n) == 4 and n.isdigit() and n.startswith(("19", "20"))}
    py = {n for n in pn if len(n) == 4 and n.isdigit() and n.startswith(("19", "20"))}
    if cy and py and cy != py and _bow_cosine(current, prior) >= 0.35:
        return True, "temporal", ContradictionSeverity.HIGH

    # Logical / stance contradiction via antonym polarity on a shared topic.
    ctoks, ptoks = set(_content_tokens(current)), set(_content_tokens(prior))
    if _bow_cosine(current, prior) >= 0.30:
        cpos, cneg = ctoks & _POSITIVE, ctoks & _NEGATIVE
        ppos, pneg = ptoks & _POSITIVE, ptoks & _NEGATIVE
        if (cpos and pneg) or (cneg and ppos):
            # "approved"/"rejected" = logical; sentiment words = stance.
            strong = {"approved", "rejected"}
            if (ctoks | ptoks) & strong:
                return True, "logical", ContradictionSeverity.HIGH
            return True, "stance", ContradictionSeverity.MEDIUM
    return False, "", ContradictionSeverity.LOW


def detect_cross_window_contradictions(
    current_response: str,
    prior_window_texts: Sequence[str],
    *,
    nli: NLI | None = None,
    threshold: float = 0.75,
) -> CoherenceResult:
    """Stage 6 (§8): detect contradictions between *current* and prior windows."""
    result = CoherenceResult()
    cur_sents = _sentences(current_response)
    prior_sents: list[str] = []
    for t in prior_window_texts:
        prior_sents.extend(_sentences(t))

    for cs in cur_sents:
        if not _nums(cs) and not (set(_content_tokens(cs)) & (_POSITIVE | _NEGATIVE)):
            continue  # only assertions referencing numbers/dates/states
        for ps in prior_sents:
            if nli is not None:
                try:
                    if nli(ps, cs) <= threshold:
                        continue
                    is_c, ctype, sev = _classify_contradiction(cs, ps)
                    if not is_c:
                        ctype, sev = "logical", ContradictionSeverity.HIGH
                    result.contradictions.append(
                        CrossWindowContradiction(cs, ps, sev, ctype, 1.0)
                    )
                    break
                except Exception:  # noqa: BLE001 — fall back to rule-based
                    pass
            is_c, ctype, sev = _classify_contradiction(cs, ps)
            if is_c:
                result.contradictions.append(
                    CrossWindowContradiction(cs, ps, sev, ctype, 1.0)
                )
                break
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Stage 7 — Repetition detection (§9)
# ═══════════════════════════════════════════════════════════════════════════


class RepetitionLevel(str, Enum):
    NONE = "NONE"
    MINOR = "MINOR"
    SIGNIFICANT = "SIGNIFICANT"
    SEVERE = "SEVERE"


@dataclass
class RepetitionResult:
    """Stage 7 output."""

    level: RepetitionLevel = RepetitionLevel.NONE
    ngram_overlap: float = 0.0
    semantic_overlap: float = 0.0

    @property
    def repetition_ratio(self) -> float:
        """RQA signal — the worse of the two overlap measures."""
        return max(self.ngram_overlap, self.semantic_overlap)

    @property
    def triggers_redispatch(self) -> bool:
        """Return whether the triggers redispatch condition holds."""
        return self.level is RepetitionLevel.SEVERE

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        if self.level is RepetitionLevel.NONE:
            return {"CRP-Quality-Repetition": "NONE"}
        return {
            "CRP-Quality-Repetition": f"{self.level.value}; overlap={self.repetition_ratio:.2f}"
        }


def _classify_repetition(ngram: float, semantic: float) -> RepetitionLevel:
    if ngram > 0.30 or semantic > 0.50:
        return RepetitionLevel.SEVERE
    if ngram >= 0.15 or semantic >= 0.25:
        return RepetitionLevel.SIGNIFICANT
    if ngram >= 0.05 or semantic >= 0.10:
        return RepetitionLevel.MINOR
    return RepetitionLevel.NONE


def detect_repetition(
    current_response: str,
    prior_responses: Sequence[str],
    *,
    embedder: Embedder | None = None,
    semantic_threshold: float = 0.92,
) -> RepetitionResult:
    """Stage 7 (§9): n-gram + semantic overlap with prior responses."""
    if not prior_responses:
        return RepetitionResult()

    # 7.1 — 4-gram overlap.
    cur_grams = _ngrams(_tokens(current_response), 4)
    prior_grams: set[tuple[str, ...]] = set()
    for r in prior_responses:
        prior_grams |= _ngrams(_tokens(r), 4)
    ngram_overlap = (
        len(cur_grams & prior_grams) / len(cur_grams) if cur_grams else 0.0
    )

    # 7.2 — semantic per-sentence overlap.
    cur_sents = _sentences(current_response)
    prior_sents: list[str] = []
    for r in prior_responses:
        prior_sents.extend(_sentences(r))
    repeated = 0
    for cs in cur_sents:
        max_sim = max((_similarity(cs, ps, embedder) for ps in prior_sents), default=0.0)
        if max_sim > semantic_threshold:
            repeated += 1
    semantic_overlap = repeated / len(cur_sents) if cur_sents else 0.0

    return RepetitionResult(
        level=_classify_repetition(ngram_overlap, semantic_overlap),
        ngram_overlap=round(ngram_overlap, 4),
        semantic_overlap=round(semantic_overlap, 4),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Stage 8 — Completeness verification (§10)
# ═══════════════════════════════════════════════════════════════════════════


class CompletenessLevel(str, Enum):
    COMPLETE = "COMPLETE"
    MOSTLY_COMPLETE = "MOSTLY_COMPLETE"
    PARTIAL = "PARTIAL"
    INCOMPLETE = "INCOMPLETE"


@dataclass
class CompletenessResult:
    """Stage 8 output."""

    level: CompletenessLevel = CompletenessLevel.COMPLETE
    score: float = 1.0
    covered: list[str] = field(default_factory=list)
    uncovered: list[str] = field(default_factory=list)
    total_sub_queries: int = 0

    @property
    def should_auto_continue(self) -> bool:
        """Return whether this object should auto continue."""
        return self.level in (CompletenessLevel.PARTIAL, CompletenessLevel.INCOMPLETE)

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        covered = len(self.covered)
        val = f"{self.level.value}; sub-queries={covered}/{self.total_sub_queries}"
        if self.uncovered:
            slugs = ",".join(_slug(u) for u in self.uncovered)
            val += f"; uncovered={slugs}"
        return {"CRP-Quality-Completeness": val}


def _slug(text: str) -> str:
    toks = _content_tokens(text)[:3]
    return "-".join(toks) if toks else "topic"


def _classify_completeness(score: float) -> CompletenessLevel:
    if score >= 0.90:
        return CompletenessLevel.COMPLETE
    if score >= 0.70:
        return CompletenessLevel.MOSTLY_COMPLETE
    if score >= 0.40:
        return CompletenessLevel.PARTIAL
    return CompletenessLevel.INCOMPLETE


def _default_decompose(query: str) -> list[str]:
    """Lexical sub-query decomposition fallback (§10.2 / SPEC-003 §5.2)."""
    parts = re.split(r"\b(?:and|;|,|\bor\b)\b|\?", query)
    subs = [p.strip() for p in parts if len(_content_tokens(p)) >= 2]
    return subs or ([query.strip()] if query.strip() else [])


def verify_completeness(
    query: str,
    session_responses: Sequence[str],
    *,
    decompose: Callable[[str], list[str]] | None = None,
    embedder: Embedder | None = None,
    coverage_threshold: float = 0.70,
) -> CompletenessResult:
    """Stage 8 (§10): does the cumulative answer cover every sub-query?"""
    sub_queries = (decompose or _default_decompose)(query)
    if not sub_queries:
        return CompletenessResult(total_sub_queries=0)

    sentences: list[str] = []
    for r in session_responses:
        sentences.extend(_sentences(r))

    covered: list[str] = []
    uncovered: list[str] = []
    for sq in sub_queries:
        max_rel = max((_similarity(sq, s, embedder) for s in sentences), default=0.0)
        (covered if max_rel > coverage_threshold else uncovered).append(sq)

    score = len(covered) / len(sub_queries)
    return CompletenessResult(
        level=_classify_completeness(score),
        score=round(score, 4),
        covered=covered,
        uncovered=uncovered,
        total_sub_queries=len(sub_queries),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Stage 9 — Flow & continuity analysis (§11)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class FlowResult:
    """Stage 9 output."""

    flow_score: float = 1.0
    opening_coherence: float = 1.0
    topic_continuity: float = 1.0
    register_consistency: float = 1.0
    transition_presence: float = 1.0
    remediation: str | None = None  # "prompt-augmented" / "stitch" / None

    @property
    def triggers_redispatch(self) -> bool:
        """Return whether the triggers redispatch condition holds."""
        return self.flow_score < 0.30

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        val = f"{self.flow_score:.2f}"
        if self.remediation:
            val += f"; remediation={self.remediation}"
        return {"CRP-Quality-Flow": val}


def _topics(text: str, top: int = 5) -> set[str]:
    freq: dict[str, int] = {}
    for t in _content_tokens(text):
        freq[t] = freq.get(t, 0) + 1
    return {t for t, _ in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:top]}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _passive_ratio(sents: list[str]) -> float:
    if not sents:
        return 0.0
    hits = sum(1 for s in sents if re.search(r"\b(?:was|were|been|is|are|be)\b\s+\w+ed\b", s.lower()))
    return hits / len(sents)


def _pronoun_ratio(text: str) -> float:
    toks = _tokens(text)
    if not toks:
        return 0.0
    pron = {"i", "we", "you", "he", "she", "they", "our", "your", "my", "their"}
    return sum(1 for t in toks if t in pron) / len(toks)


def _within(cur: float, prior: float, tol: float) -> float:
    """Return 1.0 if *cur* is within *tol* (fractional) of *prior*, else scaled."""
    if prior == 0:
        return 1.0 if cur == 0 else 0.0
    diff = abs(cur - prior) / abs(prior)
    return max(0.0, 1.0 - (diff / tol)) if tol else (1.0 if diff == 0 else 0.0)


def _register_consistency(current: str, prior: str) -> float:
    cs, ps = _sentences(current), _sentences(prior)
    cur_len = sum(len(_tokens(s)) for s in cs) / len(cs) if cs else 0.0
    pri_len = sum(len(_tokens(s)) for s in ps) / len(ps) if ps else 0.0
    ct, pt = _tokens(current), _tokens(prior)
    cur_voc = sum(len(t) for t in ct) / len(ct) if ct else 0.0
    pri_voc = sum(len(t) for t in pt) / len(pt) if pt else 0.0
    s_len = _within(cur_len, pri_len, 0.20)
    s_voc = _within(cur_voc, pri_voc, 0.15)
    s_pass = _within(_passive_ratio(cs), _passive_ratio(ps), 0.10)
    cur_pr, pri_pr = _pronoun_ratio(current), _pronoun_ratio(prior)
    s_pron = 1.0 if (cur_pr > 0) == (pri_pr > 0) else 0.5
    return (s_len + s_voc + s_pass + s_pron) / 4.0


def _has_transition(current: str) -> bool:
    first3 = _sentences(current)[:3]
    for s in first3:
        low = s.lower().lstrip()
        if any(low.startswith(m) or m in low[:40] for m in _TRANSITION_MARKERS):
            return True
    return False


def analyze_flow(
    current_response: str,
    prior_response: str,
    *,
    window_number: int = 2,
    embedder: Embedder | None = None,
) -> FlowResult:
    """Stage 9 (§11): flow & continuity for continuation windows (window>1)."""
    if window_number <= 1 or not prior_response.strip():
        return FlowResult()  # not applicable to the first window

    cur_sents = _sentences(current_response)
    pri_sents = _sentences(prior_response)
    cur_open = " ".join(cur_sents[:2])
    pri_close = " ".join(pri_sents[-2:])

    opening = _similarity(cur_open, pri_close, embedder)
    topic = _jaccard(_topics(prior_response), _topics(current_response))
    register = _register_consistency(current_response, prior_response)
    transition = 1.0 if _has_transition(current_response) else 0.0

    flow = round(0.35 * opening + 0.25 * topic + 0.20 * register + 0.20 * transition, 4)

    remediation: str | None = None
    if flow < 0.50:
        remediation = "prompt-augmented"
    return FlowResult(
        flow_score=flow,
        opening_coherence=round(opening, 4),
        topic_continuity=round(topic, 4),
        register_consistency=round(register, 4),
        transition_presence=transition,
        remediation=remediation,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Re-dispatch protocol (§19)
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RedispatchDecision:
    """Whether a window should be re-dispatched and why (§19)."""

    should_redispatch: bool = False
    reasons: list[str] = field(default_factory=list)
    # Re-dispatch parameters (§19).
    temperature: float = 0.2
    strategy: str = "reflexive"
    augmented_prompt: str = ""

    @property
    def headers(self) -> dict[str, str]:
        """Return the headers."""
        return {} if not self.should_redispatch else {"CRP-Agent-Revision-Round": "1"}


def evaluate_redispatch(
    *,
    repetition: RepetitionResult | None = None,
    coherence: CoherenceResult | None = None,
    flow: FlowResult | None = None,
    risk_upgrade_triggered: bool = False,
    upgrade_on_risk: bool = False,
    revision_round: int = 0,
    max_revisions: int = 2,
) -> RedispatchDecision:
    """Decide whether to re-dispatch a window (§19.1-19.2).

    Triggers: upgrade-on-risk + risk threshold, SEVERE repetition, CRITICAL
    cross-window contradiction, or flow_score < 0.30.  Capped at *max_revisions*
    per window; re-dispatch does NOT decrement the safety budget (§19.3).
    """
    reasons: list[str] = []
    if upgrade_on_risk and risk_upgrade_triggered:
        reasons.append("upgrade-on-risk")
    if repetition is not None and repetition.triggers_redispatch:
        reasons.append("severe-repetition")
    if coherence is not None and coherence.has_critical:
        reasons.append("critical-contradiction")
    if flow is not None and flow.triggers_redispatch:
        reasons.append("flow-degraded")

    if not reasons or revision_round >= max_revisions:
        return RedispatchDecision(should_redispatch=False, reasons=reasons)
    return RedispatchDecision(should_redispatch=True, reasons=reasons)


def build_anti_repetition_prompt(prior_summary: str) -> str:
    """Augmented system prompt for SEVERE repetition re-dispatch (§9.3)."""
    return (
        "IMPORTANT: The following content has already been provided to the user "
        "in prior responses. DO NOT repeat this content. Build upon it, extend "
        "it, or address different aspects.\n\n"
        f"{prior_summary}\n\n"
        "Continue from where the prior response ended. Provide NEW information only."
    )


def build_flow_prompt(prior_last_sentences: str) -> str:
    """Augmented system prompt for flow remediation (§11.5 Option A)."""
    return (
        "This is a continuation of a prior response. The prior response ended "
        f"with:\n\n'{prior_last_sentences}'\n\n"
        "Continue naturally from that point. Do NOT re-introduce the topic. "
        "Do NOT repeat content from the prior response. Use transitional "
        "language to bridge from the prior content. Maintain the same style, "
        "formality, and level of detail."
    )

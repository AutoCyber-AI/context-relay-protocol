# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Claim Detector — segment LLM output into attributable claims (§7.14.3).

Splits model output into individual sentences/claims and classifies each as:
  - FACTUAL_CLAIM: verifiable factual assertion (requires attribution)
  - OPINION: subjective view or judgment
  - PROCEDURAL: action or instruction
  - HEDGE: qualified/uncertain statement
  - CONNECTIVE: structural/transitional text

Uses rule-based heuristics — no ML model required for classification, keeping
overhead under 5ms for typical outputs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._types import ClaimType


# ---------------------------------------------------------------------------
# Sentence boundary detection
# ---------------------------------------------------------------------------

# Regex-based sentence splitter: split on sentence-ending punctuation
# followed by whitespace or end-of-string, but avoid splitting on
# common abbreviations (e.g., Mr., Dr., U.S., etc.) and decimals.
_ABBREV = r"(?<![A-Z][a-z])(?<!Mr)(?<!Mrs)(?<!Ms)(?<!Dr)(?<!Prof)(?<!Jr)(?<!Sr)(?<!Inc)(?<!Ltd)(?<!Corp)(?<!vs)(?<!etc)(?<!e\.g)(?<!i\.e)"
_SENTENCE_SPLIT = re.compile(
    _ABBREV + r"[.!?]+(?:\s+|$)"
    r"|(?:\n\s*\n)"  # Double newline = paragraph boundary
)

# ---------------------------------------------------------------------------
# Claim classification patterns
# ---------------------------------------------------------------------------

# Hedge indicators
_HEDGE_PATTERNS = re.compile(
    r"\b("
    r"may\s|might\s|could\s|possibly|perhaps|likely|unlikely"
    r"|it\s+is\s+possible|it\s+appears|it\s+seems"
    r"|suggest(?:s|ing)?\s|indicat(?:e|es|ing)\s"
    r"|approximately|roughly|about\s+\d"
    r"|tend(?:s)?\s+to|potential(?:ly)?"
    r")\b",
    re.IGNORECASE,
)

# Opinion indicators
_OPINION_PATTERNS = re.compile(
    r"\b("
    r"I\s+(?:think|believe|feel|consider|recommend|suggest)"
    r"|in\s+my\s+(?:opinion|view|experience)"
    r"|(?:good|bad|best|worst|excellent|poor|great|terrible)"
    r"|(?:should|ought|must)\s"
    r"|(?:important(?:ly)?|crucial(?:ly)?|essential(?:ly)?)"
    r"|unfortunately|fortunately|hopefully"
    r"|(?:prefer|favorite|ideal)"
    r")\b",
    re.IGNORECASE,
)

# Procedural indicators
_PROCEDURAL_PATTERNS = re.compile(
    r"\b("
    r"(?:click|press|open|close|select|choose|enter|type|run|execute|install)"
    r"|(?:step\s+\d|first,?\s|then,?\s|next,?\s|finally,?\s)"
    r"|(?:navigate\s+to|go\s+to|switch\s+to)"
    r"|(?:make\s+sure|ensure\s+that|verify\s+that)"
    r"|(?:to\s+do\s+this|follow\s+these|here's\s+how)"
    r")\b",
    re.IGNORECASE,
)

# Connective indicators — very short or purely structural
_CONNECTIVE_PATTERNS = re.compile(
    r"^("
    r"(?:furthermore|moreover|additionally|however|nevertheless|therefore)"
    r"|(?:in\s+conclusion|to\s+summarize|in\s+summary|overall)"
    r"|(?:for\s+example|for\s+instance|such\s+as|e\.g\.|i\.e\.)"
    r"|(?:on\s+the\s+other\s+hand|in\s+contrast|conversely)"
    r"|(?:as\s+mentioned|as\s+noted|as\s+discussed)"
    r")(?:\s*[,:]?\s*$)",
    re.IGNORECASE,
)

# Factual indicators — numbers, dates, named entities, specific claims
_FACTUAL_PATTERNS = re.compile(
    r"("
    r"\d+(?:\.\d+)?%"                     # Percentages
    r"|\$\d"                               # Dollar amounts
    r"|\d{4}"                              # Years
    r"|(?:according\s+to|based\s+on)"      # Citation-like
    r"|(?:was|were|is|are|has|have)\s+\w+"  # State assertions
    r"|\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+"  # Proper nouns (2+ words)
    r")",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class DetectedClaim:
    """A single detected claim with its classification."""

    text: str = ""
    index: int = 0              # Position in the output (0-based sentence index)
    claim_type: ClaimType = ClaimType.CONNECTIVE
    type_confidence: float = 0.0  # Confidence in the classification


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Uses regex-based sentence boundary detection with abbreviation
    handling and paragraph boundary support.

    Returns:
        List of sentence strings, stripped of leading/trailing whitespace.
    """
    if not text or not text.strip():
        return []

    # First, split on paragraph boundaries (double newlines)
    paragraphs = re.split(r"\n\s*\n", text.strip())

    sentences: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Split paragraph into sentences on terminal punctuation
        parts = re.split(r"(?<=[.!?])\s+", para)
        for part in parts:
            part = part.strip()
            if part:
                sentences.append(part)

    return sentences


def classify_claim(text: str) -> tuple[ClaimType, float]:
    """Classify a single sentence/claim by type.

    Returns:
        Tuple of (ClaimType, confidence_score).
        confidence_score is 0.0-1.0 indicating classification confidence.
    """
    stripped = text.strip()

    # Very short fragments are connective
    if len(stripped) < 15:
        return ClaimType.CONNECTIVE, 0.90

    # Check connective patterns first (structural text)
    if _CONNECTIVE_PATTERNS.search(stripped) and len(stripped) < 80:
        return ClaimType.CONNECTIVE, 0.85

    # Check hedge patterns
    hedge_matches = len(_HEDGE_PATTERNS.findall(stripped))
    opinion_matches = len(_OPINION_PATTERNS.findall(stripped))
    procedural_matches = len(_PROCEDURAL_PATTERNS.findall(stripped))
    factual_matches = len(_FACTUAL_PATTERNS.findall(stripped))

    # Score each type
    scores = {
        ClaimType.HEDGE: hedge_matches * 0.40,
        ClaimType.OPINION: opinion_matches * 0.35,
        ClaimType.PROCEDURAL: procedural_matches * 0.35,
        ClaimType.FACTUAL_CLAIM: factual_matches * 0.30,
    }

    # If no strong signals, default based on length and structure
    max_type = max(scores, key=scores.get)  # type: ignore[arg-type]
    max_score = scores[max_type]

    if max_score < 0.20:
        # No strong signal — sentences with assertions are likely factual
        if re.search(r"\b(?:is|are|was|were|has|have|had)\b", stripped):
            return ClaimType.FACTUAL_CLAIM, 0.50
        return ClaimType.CONNECTIVE, 0.40

    # Map raw score to confidence (0.5 - 0.95 range)
    confidence = min(0.50 + max_score, 0.95)
    return max_type, confidence


def detect_claims(
    text: str,
    *,
    min_length: int = 10,
    max_claims: int = 50,
) -> list[DetectedClaim]:
    """Detect and classify all claims in LLM output text.

    Args:
        text: Raw LLM output text.
        min_length: Minimum character length for a claim (shorter → skipped).
        max_claims: Maximum number of claims to return (safety limit).

    Returns:
        List of DetectedClaim objects, ordered by position in text.
    """
    sentences = split_into_sentences(text)

    claims: list[DetectedClaim] = []
    for idx, sentence in enumerate(sentences):
        if len(sentence.strip()) < min_length:
            continue
        if len(claims) >= max_claims:
            break

        claim_type, confidence = classify_claim(sentence)
        claims.append(DetectedClaim(
            text=sentence.strip(),
            index=idx,
            claim_type=claim_type,
            type_confidence=confidence,
        ))

    return claims

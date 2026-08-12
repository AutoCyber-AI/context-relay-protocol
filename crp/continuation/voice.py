# Copyright © 2025 Constantinos Vidiniotis. All rights reserved.
# Licensed under Elastic License 2.0 — see LICENSE.md for details.
"""Voice profile — tone, terminology, style extraction from first window (§04 §3.5.1)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class VoiceProfile:
    """Captured voice characteristics from the first generation window."""

    tone: str  # e.g. "formal", "casual", "technical", "mixed"
    avg_sentence_length: float
    vocabulary_level: str  # "basic", "intermediate", "advanced", "technical"
    person: str  # "first", "second", "third", "mixed"
    active_voice_ratio: float  # 0.0–1.0
    key_terminology: list[str]  # domain terms used
    style_markers: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialize the voice profile to a JSON-ready dict."""
        return {
            "tone": self.tone,
            "avg_sentence_length": self.avg_sentence_length,
            "vocabulary_level": self.vocabulary_level,
            "person": self.person,
            "active_voice_ratio": self.active_voice_ratio,
            "key_terminology": self.key_terminology,
            "style_markers": self.style_markers,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> VoiceProfile:
        """Create a new instance from a dictionary.
        
            Args:
                data (dict[str, object]): The data value.
        
            Returns:
                ``VoiceProfile``.
        """
        return cls(
            tone=str(data.get("tone", "neutral")),
            avg_sentence_length=float(data.get("avg_sentence_length", 0)),  # type: ignore[arg-type]
            vocabulary_level=str(data.get("vocabulary_level", "intermediate")),
            person=str(data.get("person", "third")),
            active_voice_ratio=float(data.get("active_voice_ratio", 0.5)),  # type: ignore[arg-type]
            key_terminology=list(data.get("key_terminology", [])),  # type: ignore[call-overload]
            style_markers=dict(data.get("style_markers", {})),  # type: ignore[call-overload]
        )


# ── Extraction helpers ───────────────────────────────────────────

_FORMAL_MARKERS = {
    "therefore", "consequently", "furthermore", "moreover", "nevertheless",
    "notwithstanding", "henceforth", "whereby", "wherein", "herein",
    "accordingly", "albeit", "hitherto", "therein",
}

_CASUAL_MARKERS = {
    "okay", "ok", "cool", "awesome", "basically", "literally",
    "gonna", "wanna", "kinda", "sorta", "yeah", "nope", "stuff",
    "thing", "actually", "pretty much", "like",
}

_TECHNICAL_TERMS_PATTERN = re.compile(
    r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b"  # CamelCase
    r"|\b[a-z]+_[a-z]+\b"  # snake_case
    r"|\b[A-Z]{2,}\b"  # ACRONYMS
    r"|\b\w+(?:tion|ment|ness|ity|ism|ize|ify)\b"  # nominalizations
)

_PASSIVE_PATTERN = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+\s+)*?\w+(?:ed|en)\b",
    re.IGNORECASE,
)

_FIRST_PERSON = re.compile(r"\b(?:I|me|my|mine|we|us|our|ours)\b", re.IGNORECASE)
_SECOND_PERSON = re.compile(r"\b(?:you|your|yours)\b", re.IGNORECASE)
_THIRD_PERSON = re.compile(r"\b(?:he|she|it|they|him|her|them|his|its|their)\b", re.IGNORECASE)


def extract_voice_profile(text: str) -> VoiceProfile:
    """Extract a voice profile from the first window's output (§04 §3.5.1)."""
    words = text.lower().split()
    word_count = max(1, len(words))
    word_set = set(words)

    sentences = [s.strip() for s in re.split(r"[.!?]+\s*", text) if s.strip()]
    sentence_count = max(1, len(sentences))

    # Tone classification
    formal_count = len(word_set & _FORMAL_MARKERS)
    casual_count = len(word_set & _CASUAL_MARKERS)
    tech_matches = _TECHNICAL_TERMS_PATTERN.findall(text)

    if len(tech_matches) > word_count * 0.05:
        tone = "technical"
    elif formal_count > casual_count:
        tone = "formal"
    elif casual_count > formal_count:
        tone = "casual"
    else:
        tone = "neutral"

    # Average sentence length
    avg_sentence_length = word_count / sentence_count

    # Vocabulary level
    unique_ratio = len(word_set) / word_count
    avg_word_len = sum(len(w) for w in words) / word_count
    if avg_word_len > 7 and unique_ratio > 0.6:
        vocabulary_level = "advanced"
    elif avg_word_len > 5.5 or unique_ratio > 0.5:
        vocabulary_level = "intermediate"
    elif len(tech_matches) > 5:
        vocabulary_level = "technical"
    else:
        vocabulary_level = "basic"

    # Person detection
    first = len(_FIRST_PERSON.findall(text))
    second = len(_SECOND_PERSON.findall(text))
    third = len(_THIRD_PERSON.findall(text))
    total_person = first + second + third
    if total_person == 0:
        person = "third"
    elif first > second and first > third:
        person = "first"
    elif second > first and second > third:
        person = "second"
    elif first > 0 and second > 0:
        person = "mixed"
    else:
        person = "third"

    # Active voice ratio
    passive_count = len(_PASSIVE_PATTERN.findall(text))
    active_ratio = 1.0 - (passive_count / sentence_count) if sentence_count > 0 else 0.5
    active_ratio = max(0.0, min(1.0, active_ratio))

    # Key terminology (most frequent technical-looking terms)
    term_counter: Counter[str] = Counter()
    for match in tech_matches:
        term_counter[match] += 1
    key_terms = [t for t, _ in term_counter.most_common(20)]

    return VoiceProfile(
        tone=tone,
        avg_sentence_length=round(avg_sentence_length, 1),
        vocabulary_level=vocabulary_level,
        person=person,
        active_voice_ratio=round(active_ratio, 2),
        key_terminology=key_terms,
        style_markers={
            "formal_markers": formal_count,
            "casual_markers": casual_count,
            "tech_terms": len(tech_matches),
            "unique_word_ratio": round(unique_ratio, 3),
        },
    )

"""Fuzzy-match a transcribed word against an exercise's option labels.

A Down-syndrome child's speech, plus whatever noise Whisper's ASR adds on
top, means exact string equality would reject almost every correct answer.
This does light per-language normalization (Arabic diacritics/letter-shape
folding, case/whitespace for both) and then a Levenshtein-based ratio via
rapidfuzz, picking the option with the best score. The caller decides what
score counts as a real match (see app.core.config.settings.speech_match_threshold).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

_AR_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٟۖ-ۭـ]")


def _normalize(text: str, lang: str) -> str:
    text = text.strip().lower()
    if lang == "ar":
        text = _AR_DIACRITICS.sub("", text)
        text = (
            text.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ى", "ي")
            .replace("ة", "ه")
        )
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@dataclass
class MatchResult:
    option_id: str | None
    score: float  # 0..1, best fuzzy ratio achieved among the options


def best_option_match(transcript: str, options: list[dict], lang: str) -> MatchResult:
    norm_transcript = _normalize(transcript, lang)
    if not norm_transcript:
        return MatchResult(option_id=None, score=0.0)

    label_key = "label_ar" if lang == "ar" else "label_en"
    best_id: str | None = None
    best_score = 0.0
    for opt in options:
        label = _normalize(opt[label_key], lang)
        score = fuzz.ratio(norm_transcript, label) / 100.0
        if score > best_score:
            best_score = score
            best_id = opt["id"]
    return MatchResult(option_id=best_id, score=best_score)

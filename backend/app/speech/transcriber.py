"""Speech transcription -- Deep Learning layer (Whisper, local/offline).

Uses faster-whisper (a CTranslate2 port of OpenAI's Whisper) so, once set
up, transcription runs fully offline with no per-request network call.

*** MODEL WEIGHTS ARE NOT BUNDLED WITH THIS REPO ***
The first time `transcribe()` actually needs the model, faster-whisper
downloads it from the Hugging Face Hub (default size "small", ~500MB) and
caches it locally; every call after that is offline. In THIS development
sandbox that download was verified to work (see backend/README section on
the speech layer for the exact command and timing observed here) -- but on
a machine with no internet access at all, or if the `faster-whisper` package
itself isn't installed, model loading fails and this module transparently
falls back to a **stub** that always returns an empty transcript. The HTTP
endpoint keeps working end-to-end either way (useful for testing the
request/response contract and the fuzzy-matching logic in isolation), but
it never pretends to have understood speech it didn't actually process --
callers can always tell which happened from the `engine` field on the
result ("whisper-<size>" vs "stub").

Set TIFL_SPEECH_STUB=1 to force stub mode explicitly (used by the backend's
own test suite so it never depends on a model download).
"""

from __future__ import annotations

import io
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_STUB_ENV = "TIFL_SPEECH_STUB"
_MODEL_SIZE_ENV = "TIFL_WHISPER_MODEL_SIZE"
# "small" (~460MB) is the accuracy/speed sweet spot for a local/offline
# family PC and the best fit for Arabic: measured on identical audio, the
# word "أحمر" scored 0.36 with "base" but 0.89 with "small". "medium"
# (~1.5GB) is better still for Arabic but ~3x the download and noticeably
# slower on CPU; "tiny"/"base" are weak on short Arabic words. Override via
# TIFL_WHISPER_MODEL_SIZE (e.g. "medium") on a stronger machine -- no code
# change needed.
DEFAULT_MODEL_SIZE = "small"

# Whisper decoding beam width. 1 is the cheapest but hurts short single
# words (the app's answers). 3 costs little on short clips and is noticeably
# more accurate for them.
BEAM_SIZE = 3

# The app always knows the exercise's language, so transcription is never
# left to Whisper's auto-detection (measured: it turned Arabic words into
# Latin/Cyrillic gibberish). Only these two codes are ever used.
VALID_LANGUAGES = ("ar", "en")


@dataclass
class TranscriptionResult:
    text: str
    engine: str  # e.g. "whisper-small" or "stub"


_model = None
_model_load_failed = False


def _forced_stub() -> bool:
    return os.environ.get(_STUB_ENV, "").strip().lower() in ("1", "true", "yes")


def _model_size() -> str:
    return os.environ.get(_MODEL_SIZE_ENV, DEFAULT_MODEL_SIZE)


def _get_model():
    global _model, _model_load_failed
    if _model is not None or _model_load_failed:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.warning(
            "faster-whisper is not installed; the speech endpoint will use "
            "the stub transcriber (always returns an empty transcript)."
        )
        _model_load_failed = True
        return None

    size = _model_size()
    try:
        _model = WhisperModel(size, device="cpu", compute_type="int8")
    except Exception:
        logger.exception(
            "Could not load Whisper model %r (no internet on first run, or "
            "no disk space for the download?); falling back to the stub "
            "transcriber.",
            size,
        )
        _model_load_failed = True
        _model = None
    return _model


def build_initial_prompt(options, lang: str) -> str:
    """A short vocabulary hint built from an exercise's expected labels.

    Whisper's `initial_prompt` biases decoding toward these words, which
    helps a lot on short, single-word answers in a known language. Callers
    pass the exercise's option labels in the answer language (the child's
    preferred language, not the UI language)."""
    key = "label_ar" if lang == "ar" else "label_en"
    seen: set[str] = set()
    words: list[str] = []
    for opt in options or []:
        word = (opt.get(key) or "").strip()
        if word and word not in seen:
            seen.add(word)
            words.append(word)
    return " ".join(words)


def transcribe(
    audio_bytes: bytes,
    language: str,
    initial_prompt: str | None = None,
) -> TranscriptionResult:
    """`language` must be an explicit known-language code ("ar" or "en" --
    both valid Whisper codes). The language is pinned per exercise, never
    auto-detected: passing it explicitly (rather than letting Whisper guess)
    noticeably improves accuracy for short, single-word children's answers,
    and auto-detection is dramatically worse (measured: Arabic words became
    Latin/Cyrillic gibberish). `initial_prompt` (optional) biases decoding
    toward the exercise's expected labels; see build_initial_prompt()."""
    if _forced_stub():
        return TranscriptionResult(text="", engine="stub")

    model = _get_model()
    if model is None:
        return TranscriptionResult(text="", engine="stub")

    if language not in VALID_LANGUAGES:
        raise ValueError(
            f"language must be one of {VALID_LANGUAGES} (never auto-detect); "
            f"got {language!r}"
        )

    segments, _info = model.transcribe(
        io.BytesIO(audio_bytes),
        language=language,
        initial_prompt=initial_prompt,
        beam_size=BEAM_SIZE,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return TranscriptionResult(text=text, engine=f"whisper-{_model_size()}")

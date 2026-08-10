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
# "base" (~150MB) balances accuracy against a reasonable one-time download
# for a local/offline family PC. Bump to "small" or "medium" via
# TIFL_WHISPER_MODEL_SIZE for better accuracy at a larger download cost.
DEFAULT_MODEL_SIZE = "base"


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


def transcribe(audio_bytes: bytes, language: str) -> TranscriptionResult:
    """`language` should be "ar" or "en" -- both are valid Whisper language
    codes, and passing it explicitly (rather than auto-detecting) noticeably
    improves accuracy for short, single-word children's answers."""
    if _forced_stub():
        return TranscriptionResult(text="", engine="stub")

    model = _get_model()
    if model is None:
        return TranscriptionResult(text="", engine="stub")

    segments, _info = model.transcribe(
        io.BytesIO(audio_bytes),
        language=language,
        beam_size=1,
        vad_filter=True,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return TranscriptionResult(text=text, engine=f"whisper-{_model_size()}")

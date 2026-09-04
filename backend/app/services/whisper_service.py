"""Local speech-to-text via faster-whisper.

Runs entirely on the backend machine — no external transcription API, no
network call. The model is loaded once (lazily, on first use) and cached for
the life of the process.
"""

from __future__ import annotations

import tempfile
from functools import lru_cache

from faster_whisper import WhisperModel

from app.core.config import settings


@lru_cache(maxsize=1)
def _model() -> WhisperModel:
    return WhisperModel(
        settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes to Russian text.

    Accepts whatever container ``MediaRecorder`` produced (webm/opus, ogg,
    mp4, wav, ...) — faster-whisper decodes it itself via PyAV, so no separate
    transcoding step is needed here.
    """
    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        segments, _info = _model().transcribe(tmp.name, language="ru")
        return " ".join(segment.text.strip() for segment in segments).strip()


__all__ = ["transcribe"]

"""Local speech-to-text via GigaAM-v3 (``ai-sage/GigaAM-v3``).

Runs entirely on the backend machine — no external transcription API, no
network call at request time. The model is loaded once (lazily, on first use)
and cached for the life of the process, so a request never pays for loading
weights more than once.

Two things differ from the faster-whisper setup this replaced, and both are
contained inside this module — :func:`transcribe` keeps the exact same
``bytes -> str`` contract, so the rest of the voice pipeline still has no idea
which STT model is running:

* GigaAM is trained on 16 kHz mono audio and its ``transcribe`` takes a file
  path, so whatever container ``MediaRecorder`` produced (webm/opus, ogg, mp4,
  wav, ...) is transcoded here with ffmpeg first. faster-whisper used to do
  that decoding internally via PyAV.
* ``transformers``/``torch`` are imported inside :func:`_model`, not at module
  import time: importing torch costs seconds and hundreds of MB of RSS, and
  nothing but an actual transcription needs it (the unit tests and every
  non-voice endpoint included).

The default revision is ``e2e_rnnt`` — the end-to-end variant that emits
punctuation and normalised numerals ("1200", not "тысяча двести"), which is
what the downstream LLM extraction prompt expects to read amounts out of.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import settings

#: GigaAM's fixed input format — a property of the model, not a setting.
_SAMPLE_RATE = 16000
_CHANNELS = 1

#: GigaAM's own ``transcribe`` raises ``ValueError("Too long wav file...")``
#: above this (``LONGFORM_THRESHOLD`` in its modeling code). Longer audio needs
#: ``transcribe_longform``, which pulls in pyannote.audio and a gated Hugging
#: Face model behind a token — deliberately not a dependency of this app. So the
#: limit is checked here instead, to fail with a sentence the user can act on
#: rather than an English exception from inside the model.
_MAX_AUDIO_SECONDS = 25

#: An upload that ffmpeg cannot decode is a user problem, not a hang; a voice
#: note is seconds long, so a minute is already far beyond generous.
_FFMPEG_TIMEOUT_SECONDS = 60


class GigaAMError(Exception):
    """Audio could not be decoded, or the model failed to transcribe it."""


class AudioTooLongError(GigaAMError):
    """The recording is longer than the model's single-shot limit.

    Unlike every other failure here, this one is the user's to fix, so its
    message is written to be shown to them — see ``voice_service.build_draft``.
    """


@lru_cache(maxsize=1)
def _model() -> Any:
    """The GigaAM model, loaded once and cached for the process lifetime.

    Weights are downloaded from Hugging Face on first use and cached in
    ``HF_HOME`` (a named volume in docker-compose), so only the very first
    transcription after a fresh install pays the download.
    """
    from transformers import AutoModel

    model = AutoModel.from_pretrained(
        settings.gigaam_model,
        revision=settings.gigaam_revision,
        trust_remote_code=True,
    )
    model.to(settings.gigaam_device)
    model.eval()
    return model


def _to_wav(audio_bytes: bytes, source: Path, destination: Path) -> None:
    """Transcode the uploaded audio to 16 kHz mono WAV, in place on disk.

    The upload is written to a real file rather than piped into ffmpeg's
    stdin: webm/mp4 demuxing needs a seekable input, which a pipe is not.
    """
    ffmpeg = shutil.which(settings.gigaam_ffmpeg_binary)
    if ffmpeg is None:
        raise GigaAMError(
            f"ffmpeg не найден ({settings.gigaam_ffmpeg_binary}) — "
            "он нужен для декодирования аудиозаписи"
        )

    source.write_bytes(audio_bytes)
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(source),
                "-ac",
                str(_CHANNELS),
                "-ar",
                str(_SAMPLE_RATE),
                "-f",
                "wav",
                str(destination),
            ],
            capture_output=True,
            timeout=_FFMPEG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GigaAMError("Не удалось декодировать аудиозапись: ffmpeg не ответил") from exc

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise GigaAMError(f"Не удалось декодировать аудиозапись: {detail}")


def _reject_if_too_long(wav: Path) -> None:
    """Check the duration of the decoded WAV before loading the model."""
    with wave.open(str(wav), "rb") as handle:
        seconds = handle.getnframes() / float(handle.getframerate() or _SAMPLE_RATE)
    if seconds > _MAX_AUDIO_SECONDS:
        raise AudioTooLongError(
            f"Запись длиннее {_MAX_AUDIO_SECONDS} секунд — "
            "запишите покороче или добавьте расход вручную"
        )


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe raw audio bytes to Russian text.

    Accepts whatever container ``MediaRecorder`` produced (webm/opus, ogg,
    mp4, wav, ...): it is transcoded to the 16 kHz mono WAV GigaAM expects
    before inference. Both temporary files live in one temporary directory
    that is removed on every path out of this function, success or failure.

    Raises :class:`GigaAMError` when the audio cannot be decoded or the model
    returns something that isn't text; the caller
    (:func:`app.services.voice_service.build_draft`) turns any failure here
    into the same "не удалось обработать аудиозапись" 400 it always has —
    except :class:`AudioTooLongError`, whose message is shown as-is.
    """
    with tempfile.TemporaryDirectory(prefix="skladchina-voice-") as tmpdir:
        workdir = Path(tmpdir)
        source = workdir / "upload.audio"
        wav = workdir / "audio.wav"

        _to_wav(audio_bytes, source, wav)
        _reject_if_too_long(wav)

        result = _model().transcribe(str(wav))

    if isinstance(result, str):
        return result.strip()
    # ``transcribe(..., word_timestamps=True)`` returns an object instead of a
    # plain string; we never ask for that, but accept it rather than crash.
    text = getattr(result, "text", None)
    if isinstance(text, str):
        return text.strip()
    raise GigaAMError(f"Модель распознавания вернула неожиданный результат: {type(result)!r}")


__all__ = ["AudioTooLongError", "GigaAMError", "transcribe"]

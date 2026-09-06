"""Unit tests for ``gigaam_service`` — the local speech-to-text adapter.

The real ``ai-sage/GigaAM-v3`` weights are never downloaded and torch is never
imported here: ``_model`` is monkeypatched, so these tests pin the parts this
repository actually owns — lazy loading and caching of the model, the ffmpeg
transcoding step, temp-file cleanup, and how each failure is reported.

Coverage against the real model (does GigaAM transcribe this audio correctly)
lives in ``test_gigaam_smoke.py``, which is skipped unless it is asked for
explicitly — see that file.
"""

from __future__ import annotations

import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import pytest

from app.core.config import settings
from app.services import gigaam_service


@pytest.fixture(autouse=True)
def _clear_model_cache() -> Any:
    """``_model`` is an ``lru_cache``; never let one test's stub leak into another."""
    gigaam_service._model.cache_clear()
    yield
    gigaam_service._model.cache_clear()


class _FakeModel:
    """Stands in for the loaded GigaAM model: records what it was asked to read."""

    def __init__(self, result: Any = " Заплатил за обед 500 рублей ") -> None:
        self.result = result
        self.calls: list[str] = []

    def transcribe(self, path: str) -> Any:
        self.calls.append(path)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _install_model(monkeypatch: pytest.MonkeyPatch, model: _FakeModel) -> None:
    monkeypatch.setattr(gigaam_service, "_model", lambda: model)


def _wav_bytes(seconds: float = 0.1, sample_rate: int = 44100) -> bytes:
    """A real (silent) WAV file — ffmpeg has to be able to decode this for real."""
    with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
        with wave.open(handle.name, "wb") as writer:
            writer.setnchannels(2)
            writer.setsampwidth(2)
            writer.setframerate(sample_rate)
            writer.writeframes(b"\x00\x00\x00\x00" * int(sample_rate * seconds))
        return Path(handle.name).read_bytes()


# --------------------------------------------------------------- transcription


def test_transcribe_returns_stripped_text(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _FakeModel()
    _install_model(monkeypatch, model)

    assert gigaam_service.transcribe(_wav_bytes()) == "Заплатил за обед 500 рублей"


def test_transcribe_returns_empty_string_for_silence(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty is a valid answer here — ``voice_service`` is what turns "nothing
    was said" into a 400, and it must still get a plain string to check."""
    _install_model(monkeypatch, _FakeModel(result="   "))

    assert gigaam_service.transcribe(_wav_bytes()) == ""


def test_transcribe_accepts_a_result_object_with_text(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Result:
        text = "  Такси 1200  "

    _install_model(monkeypatch, _FakeModel(result=_Result()))

    assert gigaam_service.transcribe(_wav_bytes()) == "Такси 1200"


def test_transcribe_rejects_an_unusable_result(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_model(monkeypatch, _FakeModel(result=object()))

    with pytest.raises(gigaam_service.GigaAMError):
        gigaam_service.transcribe(_wav_bytes())


def test_model_errors_propagate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inference blowing up must reach ``voice_service``, which turns any
    exception here into the endpoint's existing 400 — never a silent empty
    transcript that would look like a successful, wordless recording."""
    _install_model(monkeypatch, _FakeModel(result=RuntimeError("inference failed")))

    with pytest.raises(RuntimeError):
        gigaam_service.transcribe(_wav_bytes())


# ------------------------------------------------------------ audio conversion


def test_audio_is_converted_to_16k_mono_wav(monkeypatch: pytest.MonkeyPatch) -> None:
    """The one hard requirement of the model: 16 kHz, mono, WAV — whatever the
    browser recorded. Asserted on the real file ffmpeg produced, not on argv."""
    captured: dict[str, Any] = {}

    class _InspectingModel(_FakeModel):
        def transcribe(self, path: str) -> Any:
            with wave.open(path, "rb") as handle:
                captured["rate"] = handle.getframerate()
                captured["channels"] = handle.getnchannels()
            return super().transcribe(path)

    _install_model(monkeypatch, _InspectingModel())

    gigaam_service.transcribe(_wav_bytes(sample_rate=44100))

    assert captured == {"rate": 16000, "channels": 1}


def test_invalid_audio_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bytes ffmpeg cannot decode must fail before the model is ever loaded."""
    model = _FakeModel()
    _install_model(monkeypatch, model)

    with pytest.raises(gigaam_service.GigaAMError):
        gigaam_service.transcribe(b"this is not audio at all")

    assert model.calls == []


def test_missing_ffmpeg_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gigaam_ffmpeg_binary", "ffmpeg-that-does-not-exist")

    with pytest.raises(gigaam_service.GigaAMError, match="ffmpeg"):
        gigaam_service.transcribe(_wav_bytes())


def test_ffmpeg_timeout_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(gigaam_service.subprocess, "run", _timeout)

    with pytest.raises(gigaam_service.GigaAMError):
        gigaam_service.transcribe(_wav_bytes())


def test_audio_over_the_model_limit_is_rejected_with_a_useful_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GigaAM's own ``transcribe`` raises "Too long wav file" past 25s. Catching
    it here means the user gets a Russian sentence they can act on, and a 2 GB
    model is not loaded just to reject the recording."""
    model = _FakeModel()
    _install_model(monkeypatch, model)

    with pytest.raises(gigaam_service.AudioTooLongError) as excinfo:
        gigaam_service.transcribe(_wav_bytes(seconds=26, sample_rate=8000))

    assert "25" in str(excinfo.value)
    assert model.calls == []  # rejected before inference


def test_audio_within_the_model_limit_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _FakeModel()
    _install_model(monkeypatch, model)

    gigaam_service.transcribe(_wav_bytes(seconds=24, sample_rate=8000))

    assert len(model.calls) == 1


def test_too_long_is_a_gigaam_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """``voice_service`` handles it specially but still catches ``GigaAMError``
    broadly — the subclass must stay inside that hierarchy."""
    assert issubclass(gigaam_service.AudioTooLongError, gigaam_service.GigaAMError)


# ----------------------------------------------------------------- temp files


def test_temporary_files_are_cleaned_up(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Path] = {}

    class _PathCapturingModel(_FakeModel):
        def transcribe(self, path: str) -> Any:
            seen["wav"] = Path(path)
            return super().transcribe(path)

    _install_model(monkeypatch, _PathCapturingModel())

    gigaam_service.transcribe(_wav_bytes())

    wav = seen["wav"]
    assert not wav.exists()
    # The whole working directory goes, not just the wav — the raw upload was
    # written next to it and must not outlive the request either.
    assert not wav.parent.exists()


def test_temporary_files_are_cleaned_up_after_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Path] = {}

    class _FailingModel(_FakeModel):
        def transcribe(self, path: str) -> Any:
            seen["wav"] = Path(path)
            raise RuntimeError("inference failed")

    _install_model(monkeypatch, _FailingModel())

    with pytest.raises(RuntimeError):
        gigaam_service.transcribe(_wav_bytes())

    assert not seen["wav"].parent.exists()


# -------------------------------------------------------- lazy loading/caching


def test_model_is_loaded_lazily_and_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing imports torch or touches Hugging Face until the first
    transcription, and the weights are loaded once per process, not per request.
    """
    loads: list[dict[str, Any]] = []

    class _FakeAutoModel:
        @staticmethod
        def from_pretrained(model_id: str, **kwargs: Any) -> Any:
            loads.append({"model_id": model_id, **kwargs})
            return _LoadedModel()

    class _LoadedModel(_FakeModel):
        def to(self, device: str) -> None:
            loads[-1]["device"] = device

        def eval(self) -> None:
            loads[-1]["eval"] = True

    fake_transformers = type("_M", (), {"AutoModel": _FakeAutoModel})
    monkeypatch.setitem(__import__("sys").modules, "transformers", fake_transformers)

    assert loads == []  # importing the service loaded nothing

    for _ in range(3):
        gigaam_service.transcribe(_wav_bytes())

    assert len(loads) == 1
    assert loads[0]["model_id"] == settings.gigaam_model
    assert loads[0]["revision"] == settings.gigaam_revision
    assert loads[0]["trust_remote_code"] is True
    assert loads[0]["device"] == settings.gigaam_device
    assert loads[0]["eval"] is True

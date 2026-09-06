"""Smoke tests against the REAL local models — skipped unless asked for.

Everything else in ``tests/`` mocks the AI layer, on purpose: the default suite
must stay fast and must never download a 2 GB acoustic model or need a running
Ollama server. These two tests are the opposite — they are how you check, by
hand, that the migration works end to end on a machine where the models are
actually installed.

Run them with::

    # Qwen only (needs Ollama up: ollama serve, with OLLAMA_MODEL pulled)
    SKLADCHINA_AI_SMOKE=1 python -m pytest tests/test_ai_smoke.py -v

    # ...and GigaAM too, on a real recording of Russian speech
    SKLADCHINA_AI_SMOKE=1 SKLADCHINA_AI_SMOKE_AUDIO=/path/to/voice.webm \\
        python -m pytest tests/test_ai_smoke.py -v

The assertions are deliberately loose: a language model's exact wording is not
a contract, so these check the shape and the plumbing (the server answers, the
JSON parses, the schema validates, the transcript is non-empty), not that a
particular sentence came back.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.schemas.notification import DebtReminderInput
from app.services import gigaam_service, ollama_service

pytestmark = pytest.mark.skipif(
    os.environ.get("SKLADCHINA_AI_SMOKE") != "1",
    reason="real-model smoke test; set SKLADCHINA_AI_SMOKE=1 to run",
)


class _Category:
    def __init__(self, slug: str, name: str) -> None:
        self.slug = slug
        self.name = name


_CATEGORIES = [
    _Category("food", "Кафе и рестораны"),
    _Category("groceries", "Продукты"),
    _Category("transport", "Транспорт"),
    _Category("other", "Другое"),
]


def test_qwen_extracts_a_real_expense() -> None:
    """The live Ollama answers the extraction prompt in the app's schema."""
    result = ollama_service.extract_expense(
        "Заплатил 1200 рублей за такси.", _CATEGORIES
    )

    assert result.amount is not None, "the model did not hear an amount at all"
    assert result.category_slug in {c.slug for c in _CATEGORIES}, (
        f"invented a category slug: {result.category_slug!r}"
    )


def test_qwen_words_a_real_debt_reminder() -> None:
    result = ollama_service.generate_debt_reminder(
        DebtReminderInput(
            expense="Ужин",
            amount_due="1250.00",
            currency="RUB",
            payer="Алиса",
            group="Квартира",
        )
    )

    assert result.message.strip()


def test_gigaam_transcribes_a_real_recording() -> None:
    """Transcribes an actual recording — pass one via SKLADCHINA_AI_SMOKE_AUDIO.

    Any container the browser can produce works (webm/opus, ogg, mp4, wav):
    the point is to exercise the real ffmpeg + GigaAM path on real audio.
    """
    audio_path = os.environ.get("SKLADCHINA_AI_SMOKE_AUDIO")
    if not audio_path:
        pytest.skip("set SKLADCHINA_AI_SMOKE_AUDIO=/path/to/recording to run this")

    transcript = gigaam_service.transcribe(Path(audio_path).read_bytes())

    assert transcript.strip(), "GigaAM returned an empty transcript"
    print(f"\nGigaAM transcript: {transcript!r}")

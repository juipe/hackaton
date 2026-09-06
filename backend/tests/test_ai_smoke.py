"""Smoke tests against the REAL models — skipped unless asked for.

Everything else in ``tests/`` mocks the AI layer, on purpose: the default
suite must stay fast, must never download a 2 GB acoustic model, and must
never spend a billed GigaChat request or need an API key. These tests are the
opposite — they are how you check, by hand, that the pipeline works end to end
on a machine that has real credentials configured.

Run them with::

    # GigaChat only (needs GIGACHAT_CREDENTIALS in the environment)
    SKLADCHINA_AI_SMOKE=1 python -m pytest tests/test_ai_smoke.py -v

    # ...and GigaAM too, on a real recording of Russian speech
    SKLADCHINA_AI_SMOKE=1 SKLADCHINA_AI_SMOKE_AUDIO=/path/to/voice.webm \\
        python -m pytest tests/test_ai_smoke.py -v

``SKLADCHINA_AI_SMOKE=1`` also switches off the hermetic-network guard in
``conftest.py``, so the real ``GIGACHAT_*`` settings (from the environment or
``backend/.env``) are what these tests use. The key itself is never read,
printed or asserted on here.

The assertions are deliberately loose: a language model's exact wording is not
a contract, so these check the shape and the plumbing (the API answers, the
JSON parses, the schema validates, the transcript is non-empty), not that a
particular sentence came back.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.expense import Expense
from app.models.group import Group
from app.models.user import User
from app.schemas.notification import DebtReminderInput
from app.schemas.saving_tips import SavingTipsCategoryInput, SavingTipsInput
from app.services import gigaam_service, gigachat_service, voice_service

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


# ------------------------------------------------------------ authentication


def test_token_is_acquired_and_then_reused() -> None:
    """The Authorization Key really is exchangeable for an access token, and
    the second call reuses it instead of paying for another round trip."""
    gigachat_service._token_cache.invalidate()

    started = time.monotonic()
    token = gigachat_service._token_cache.get()
    first = time.monotonic() - started

    started = time.monotonic()
    again = gigachat_service._token_cache.get()
    second = time.monotonic() - started

    assert token and again == token
    # A cache hit does no I/O at all; the first call did.
    assert second < first
    print(f"\ntoken acquisition: {first:.2f}s (cached lookup: {second * 1000:.2f}ms)")


# -------------------------------------------------------- expense extraction


@pytest.mark.parametrize(
    "transcript",
    [
        "Заплатил 1200 рублей за такси",
        "Мы с Максимом сходили в кино за 2000 рублей, я заплатил",
    ],
)
def test_extracts_a_real_expense(transcript: str) -> None:
    """The live API answers the extraction prompt in the app's own schema."""
    started = time.monotonic()
    result = gigachat_service.extract_expense(transcript, _CATEGORIES)
    elapsed = time.monotonic() - started

    assert result.amount is not None, "the model did not hear an amount at all"
    assert result.category_slug in {c.slug for c in _CATEGORIES}, (
        f"invented a category slug: {result.category_slug!r}"
    )
    # Names only — an id from the model would be resolved against nothing.
    for participant in result.participants:
        assert participant.name
    print(f"\nextraction ({elapsed:.2f}s) {transcript!r} -> {result.model_dump()}")


# ---------------------------------------------------------------saving tips


def test_words_real_saving_tips() -> None:
    """The backend's already-formatted numbers must survive into the prose
    unchanged — the model is told to copy them verbatim, never recompute."""
    payload = SavingTipsInput(
        total_spending_display="5 000,00 ₽",
        expense_count=12,
        currency="RUB",
        categories=[
            SavingTipsCategoryInput(
                name="Продукты",
                amount_display="2 500,00 ₽",
                percentage_display="50%",
                expense_count=8,
            )
        ],
        trend=None,
    )

    started = time.monotonic()
    result = gigachat_service.generate_saving_tips(payload)
    elapsed = time.monotonic() - started

    assert 2 <= len(result.tips) <= 3
    assert all(tip.title.strip() and tip.text.strip() for tip in result.tips)
    print(f"\nsaving tips ({elapsed:.2f}s):")
    for tip in result.tips:
        print(f"  [{tip.type}] {tip.title}: {tip.text}")


# ------------------------------------------------------------ debt reminders


def test_words_a_real_debt_reminder() -> None:
    started = time.monotonic()
    result = gigachat_service.generate_debt_reminder(
        DebtReminderInput(
            expense="Ужин",
            amount_due="1250.00",
            currency="RUB",
            payer="Алиса",
            group="Квартира",
        )
    )
    elapsed = time.monotonic() - started

    assert result.message.strip()
    print(f"\ndebt reminder ({elapsed:.2f}s): {result.message!r}")


# ---------------------------------------------------------------- GigaAM STT


def _smoke_audio() -> bytes:
    audio_path = os.environ.get("SKLADCHINA_AI_SMOKE_AUDIO")
    if not audio_path:
        pytest.skip("set SKLADCHINA_AI_SMOKE_AUDIO=/path/to/recording to run this")
    return Path(audio_path).read_bytes()


def test_gigaam_transcribes_a_real_recording() -> None:
    """Transcribes an actual recording — pass one via SKLADCHINA_AI_SMOKE_AUDIO.

    Any container the browser can produce works (webm/opus, ogg, mp4, wav):
    the point is to exercise the real ffmpeg + GigaAM path on real audio.
    """
    audio = _smoke_audio()

    started = time.monotonic()
    transcript = gigaam_service.transcribe(audio)
    elapsed = time.monotonic() - started

    assert transcript.strip(), "GigaAM returned an empty transcript"
    print(f"\nGigaAM transcript ({elapsed:.2f}s): {transcript!r}")


# ------------------------------------------------------- full voice pipeline


def test_voice_route_with_real_gigachat_and_a_stubbed_transcript(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    monkeypatch: pytest.MonkeyPatch,
    db,
) -> None:
    """The pipeline below transcription, over real HTTP against real GigaChat.

    Only :func:`gigaam_service.transcribe` is replaced, with a sentence it
    really does produce — so this exercises the half the provider migration
    touched (extraction, name/category resolution, split validation, draft
    shaping) without needing a 2 GB acoustic model on the machine.
    ``test_full_voice_pipeline_returns_a_draft_and_creates_nothing`` covers the
    same route with the real recording when one is supplied.
    """
    monkeypatch.setattr(
        voice_service.gigaam_service,
        "transcribe",
        lambda _audio: "Мы с Максимом сходили в кино за 2000 рублей, я заплатил",
    )

    payer = make_user(name="Саша", email="sasha-route@example.com")
    maksim = make_user(name="Максим", email="maksim-route@example.com")
    group = group_factory(payer, name="Квартира", currency="RUB", members=[maksim])
    client = api_client(payer)

    started = time.monotonic()
    response = client.post(
        f"/api/groups/{group.id}/voice-expenses",
        files={"audio": ("voice.webm", b"RIFF....not-really-audio", "audio/webm")},
    )
    elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    draft = response.json()
    # The payer said "я", so resolution must land on the caller, not on a name
    # the model invented; participants must be real members of this group.
    assert draft["payer"]["status"] == "resolved"
    assert draft["payer"]["value"]["user"]["id"] == str(payer.id)
    resolved_names = {p["member"]["user"]["name"] for p in draft["participants"]["resolved"]}
    assert resolved_names <= {"Саша", "Максим"}
    assert db.query(Expense).count() == 0, "the voice endpoint must never create an expense"

    print(f"\nvoice route, real GigaChat ({elapsed:.2f}s):")
    print(f"  title={draft['title']!r} amount_cents={draft['amount_cents']}")
    print(f"  payer={draft['payer']['value']['user']['name']!r} resolved={sorted(resolved_names)}")
    print(f"  category={draft['category']['status']} warnings={draft['warnings']}")


def test_full_voice_pipeline_returns_a_draft_and_creates_nothing(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    db,
) -> None:
    """audio -> GigaAM -> GigaChat -> resolver -> draft, over real HTTP.

    Nothing is stubbed. The assertion that matters most is the last one: the
    endpoint must return a draft and leave the expenses table empty, however
    confident the model was.
    """
    audio = _smoke_audio()

    payer = make_user(name="Саша", email="sasha-smoke@example.com")
    maksim = make_user(name="Максим", email="maksim-smoke@example.com")
    group = group_factory(payer, name="Квартира", currency="RUB", members=[maksim])
    client = api_client(payer)

    started = time.monotonic()
    response = client.post(
        f"/api/groups/{group.id}/voice-expenses",
        files={"audio": ("voice.webm", audio, "audio/webm")},
    )
    elapsed = time.monotonic() - started

    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["transcript"].strip()
    assert draft["payer"]["status"] in {"resolved", "ambiguous", "unresolved"}
    assert draft["category"]["status"] in {"resolved", "ambiguous", "unresolved"}
    assert db.query(Expense).count() == 0, "the voice endpoint must never create an expense"

    print(f"\nfull voice pipeline ({elapsed:.2f}s), model {settings.gigachat_model}:")
    print(f"  transcript: {draft['transcript']!r}")
    print(f"  title={draft['title']!r} amount_cents={draft['amount_cents']}")
    print(f"  payer={draft['payer']['status']} category={draft['category']['status']}")
    print(f"  warnings={draft['warnings']}")

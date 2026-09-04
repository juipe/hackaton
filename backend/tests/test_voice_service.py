"""Voice draft resolution logic.

Whisper and Ollama are monkeypatched — this is not a test of the local model
weights, it is a test of the pure resolution logic: turning whatever the LLM
said into a draft where payer/participants/category are either resolved
against real group data, flagged ambiguous, or left unresolved, with no
guessing anywhere.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.core.errors import BadRequest
from app.models.group import Group
from app.models.user import User
from app.schemas.voice import LLMExpenseExtraction
from app.services import ollama_service, voice_service


@pytest.fixture()
def people(make_user: Callable[..., User]) -> tuple[User, User, User]:
    return (
        make_user(name="Аня", email="anya@example.com"),
        make_user(name="Андрей", email="andrey@example.com"),
        make_user(name="Борис", email="boris@example.com"),
    )


@pytest.fixture()
def group(group_factory: Callable[..., Group], people: tuple[User, User, User]) -> Group:
    anya, andrey, boris = people
    return group_factory(anya, name="Соседи", currency="RUB", members=[andrey, boris])


def _extraction(**overrides: object) -> LLMExpenseExtraction:
    return LLMExpenseExtraction(**overrides)


def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch, *, transcript: str, extraction: LLMExpenseExtraction
) -> None:
    monkeypatch.setattr(voice_service.whisper_service, "transcribe", lambda _audio: transcript)
    monkeypatch.setattr(
        voice_service.ollama_service,
        "extract_expense",
        lambda _transcript, _categories: extraction,
    )


def test_resolves_amount_payer_participants_and_category(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, andrey, boris = people
    _stub_pipeline(
        monkeypatch,
        transcript="Заплатил 1200 рублей за такси, разделить с Андреем и Борисом",
        extraction=_extraction(
            title="Такси",
            amount="1200",
            category_slug="transport",
            payer_name="я",
            participant_names=["Андрей", "Борис"],
        ),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.transcript.startswith("Заплатил 1200")
    assert draft.title == "Такси"
    assert draft.amount_cents == 120000
    assert draft.split_mode == "equal"

    # "я" always resolves to the actor, who is a member of the group.
    assert draft.payer.status == "resolved"
    assert draft.payer.value is not None
    assert draft.payer.value.user.id == anya.id

    resolved_ids = {member.user.id for member in draft.participants.resolved}
    assert resolved_ids == {andrey.id, boris.id}
    assert draft.participants.ambiguous == []
    assert draft.participants.unresolved == []

    assert draft.category.status == "resolved"
    assert draft.category.value is not None
    assert draft.category.value.slug == "transport"

    assert draft.warnings == []


def test_ambiguous_participant_name_is_flagged_not_guessed(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, andrey, boris = people
    _stub_pipeline(
        monkeypatch,
        transcript="Разделить с Аней",
        # "Ан" matches both "Аня" and "Андрей" — must never be silently guessed.
        extraction=_extraction(payer_name="я", participant_names=["Ан"]),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.participants.resolved == []
    assert len(draft.participants.ambiguous) == 1
    ambiguous = draft.participants.ambiguous[0]
    assert ambiguous.raw_text == "Ан"
    assert {c.user.id for c in ambiguous.candidates} == {anya.id, andrey.id}
    assert draft.participants.unresolved == []


def test_unmatched_participant_name_is_unresolved(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, *_ = people
    _stub_pipeline(
        monkeypatch,
        transcript="Разделить с Зиной",
        extraction=_extraction(payer_name="я", participant_names=["Зина"]),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.participants.resolved == []
    assert draft.participants.ambiguous == []
    assert draft.participants.unresolved == ["Зина"]


def test_category_falls_back_to_other_when_qwen_slips_up(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    """Qwen is instructed to always pick "other" when nothing fits, and to
    never invent a slug — but if it slips up and returns one that doesn't
    match any real category, the backend falls back to "other" itself rather
    than leaving the category unresolved (that status is reserved for a
    genuine technical failure, not an unclear transcript)."""
    anya, *_ = people
    _stub_pipeline(
        monkeypatch,
        transcript="Купил что-то странное",
        extraction=_extraction(payer_name="я", category_slug="not-a-real-slug"),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.category.status == "resolved"
    assert draft.category.value is not None
    assert draft.category.value.slug == "other"


def test_category_resolves_semantically_without_exact_wording(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    """The transcript never says "транспорт" — Qwen is expected to map the
    meaning ("такси") to the right slug itself; the backend just validates
    that slug against the real category list."""
    anya, *_ = people
    _stub_pipeline(
        monkeypatch,
        transcript="Заплатил 1200 за такси",
        extraction=_extraction(payer_name="я", amount="1200", category_slug="transport"),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.category.status == "resolved"
    assert draft.category.value is not None
    assert draft.category.value.slug == "transport"


def test_unparseable_amount_and_date_produce_warnings_not_errors(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, *_ = people
    _stub_pipeline(
        monkeypatch,
        transcript="Что-то заплатил",
        extraction=_extraction(payer_name="я", amount="много денег", occurred_at="вчера"),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.amount_cents is None
    assert draft.occurred_at is None
    assert "Не удалось распознать сумму" in draft.warnings
    assert "Не удалось распознать дату" in draft.warnings


def test_empty_transcript_raises_bad_request(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, *_ = people
    _stub_pipeline(monkeypatch, transcript="   ", extraction=_extraction())

    with pytest.raises(BadRequest):
        voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")


def test_ollama_failure_degrades_gracefully_instead_of_erroring(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    """Ollama being unreachable must not lose the transcript or 500 the request."""
    anya, *_ = people
    monkeypatch.setattr(
        voice_service.whisper_service, "transcribe", lambda _audio: "Заплатил за обед"
    )

    def _boom(_transcript: str, _categories: object) -> LLMExpenseExtraction:
        raise ollama_service.OllamaError("Ollama недоступна")

    monkeypatch.setattr(voice_service.ollama_service, "extract_expense", _boom)

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.transcript == "Заплатил за обед"
    assert draft.amount_cents is None
    assert draft.category.status == "unresolved"
    # No LLM data at all still defaults the payer to the person who recorded it.
    assert draft.payer.status == "resolved"
    assert draft.payer.value is not None
    assert draft.payer.value.user.id == anya.id
    assert any("Qwen" in warning for warning in draft.warnings)

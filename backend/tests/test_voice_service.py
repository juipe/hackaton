"""Voice draft resolution logic.

Whisper and Ollama are monkeypatched — this is not a test of the local model
weights, it is a test of the pure resolution logic: turning whatever the LLM
said into a draft where payer/participants/category/split are either
resolved against real group data and validated, or flagged for the user to
fix in the existing confirmation UI, with no guessing anywhere.

Real-model coverage (does Qwen actually produce this shape for these exact
transcripts) is exercised separately against a live local Ollama — see the
verification report, not this file.
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


@pytest.fixture()
def split_people(make_user: Callable[..., User]) -> tuple[User, User, User]:
    return (
        make_user(name="Аня", email="anya-split@example.com"),
        make_user(name="Максим", email="maksim-split@example.com"),
        make_user(name="Саша", email="sasha-split@example.com"),
    )


@pytest.fixture()
def split_group(
    group_factory: Callable[..., Group], split_people: tuple[User, User, User]
) -> Group:
    anya, maksim, sasha = split_people
    return group_factory(anya, name="Складчина", currency="RUB", members=[maksim, sasha])


def _extraction(**overrides: object) -> LLMExpenseExtraction:
    return LLMExpenseExtraction(**overrides)


def _share(name: str, value: str | None = None) -> dict[str, str | None]:
    return {"name": name, "value": value}


def _stub_pipeline(
    monkeypatch: pytest.MonkeyPatch, *, transcript: str, extraction: LLMExpenseExtraction
) -> None:
    monkeypatch.setattr(voice_service.whisper_service, "transcribe", lambda _audio: transcript)
    monkeypatch.setattr(
        voice_service.ollama_service,
        "extract_expense",
        lambda _transcript, _categories: extraction,
    )


def _resolved_by_name(draft: object) -> dict[str, str | None]:
    return {
        participant.member.user.name: participant.value
        for participant in draft.participants.resolved  # type: ignore[attr-defined]
    }


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
            participants=[_share("Андрей"), _share("Борис")],
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

    resolved_ids = {p.member.user.id for p in draft.participants.resolved}
    assert resolved_ids == {andrey.id, boris.id}
    assert all(p.value is None for p in draft.participants.resolved)
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
        extraction=_extraction(payer_name="я", participants=[_share("Ан")]),
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
        extraction=_extraction(payer_name="я", participants=[_share("Зина")]),
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


# -------------------------------------------------------------------- title


def test_missing_title_falls_back_to_resolved_category_name(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    """No explicit title, but the category resolves — title should fall back
    to the category name rather than being left blank (which would fail the
    same "Укажите название" validation manual entry enforces)."""
    anya, andrey, boris = people
    _stub_pipeline(
        monkeypatch,
        transcript="Заплатил 1200 рублей за такси, разделить с Андреем и Борисом",
        extraction=_extraction(
            amount="1200",
            category_slug="transport",
            payer_name="я",
            participants=[_share("Андрей"), _share("Борис")],
        ),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.category.status == "resolved"
    assert draft.category.value is not None
    assert draft.title == draft.category.value.name
    assert draft.amount_cents == 120000


def test_explicit_title_is_kept_over_category_fallback(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    anya, andrey, boris = people
    _stub_pipeline(
        monkeypatch,
        transcript="Заплатил 1200 рублей за такси до аэропорта",
        extraction=_extraction(
            title="Такси до аэропорта",
            amount="1200",
            category_slug="transport",
            payer_name="я",
            participants=[_share("Андрей"), _share("Борис")],
        ),
    )

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.title == "Такси до аэропорта"


def test_missing_title_and_unresolved_category_leaves_title_blank(
    monkeypatch: pytest.MonkeyPatch, db: Session, group: Group, people: tuple[User, User, User]
) -> None:
    """No title and no category to fall back to (Ollama unreachable, so the
    category is genuinely unresolved) — title stays ``None`` rather than
    inventing anything; the confirmation form still asks for it by hand."""
    anya, *_ = people
    monkeypatch.setattr(
        voice_service.whisper_service, "transcribe", lambda _audio: "Заплатил за обед"
    )

    def _boom(_transcript: str, _categories: object) -> LLMExpenseExtraction:
        raise ollama_service.OllamaError("Ollama недоступна")

    monkeypatch.setattr(voice_service.ollama_service, "extract_expense", _boom)

    draft = voice_service.build_draft(db, group=group, actor=anya, audio_bytes=b"fake-audio")

    assert draft.category.status == "unresolved"
    assert draft.title is None


# --------------------------------------------------------------- exact split


def test_exact_split_natural_phrasing_dolzhen(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Я заплатил за пиццу 1500, Максим должен 500, я 1000." — the transcript
    from the task spec, verbatim."""
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Я заплатил за пиццу 1500, Максим должен 500, я 1000.",
        extraction=_extraction(
            title="Пицца",
            amount="1500",
            category_slug="food",
            payer_name="я",
            split_mode="exact",
            participants=[_share("Максим", "500"), _share("я", "1000")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "exact"
    assert draft.amount_cents == 150000
    assert draft.payer.status == "resolved"
    assert draft.payer.value is not None
    assert draft.payer.value.user.id == anya.id

    by_name = _resolved_by_name(draft)
    assert by_name == {"Максим": "500", "Аня": "1000"}
    assert draft.participants.ambiguous == []
    assert draft.participants.unresolved == []
    assert draft.warnings == []


def test_exact_split_natural_phrasing_second_example(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Я заплатил 3000, Максим должен 1000, я 2000." """
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Я заплатил 3000, Максим должен 1000, я 2000.",
        extraction=_extraction(
            amount="3000",
            payer_name="я",
            split_mode="exact",
            participants=[_share("Максим", "1000"), _share("я", "2000")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "exact"
    assert draft.amount_cents == 300000
    assert _resolved_by_name(draft) == {"Максим": "1000", "Аня": "2000"}
    assert draft.warnings == []


def test_exact_split_infers_total_when_only_shares_are_stated(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Саша 500, Максим 1000, я 1500." never states a total — it's the sum
    of the three shares, not a guess."""
    anya, maksim, sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Саша 500, Максим 1000, я 1500.",
        extraction=_extraction(
            split_mode="exact",
            participants=[_share("Саша", "500"), _share("Максим", "1000"), _share("я", "1500")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "exact"
    assert draft.amount_cents == 300000
    assert draft.warnings == []


def test_exact_split_various_self_and_third_person_phrasings(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Я заплатил 5000, за меня 2000, Максим 3000." — self-reference via "за
    меня" is expected to already arrive normalised to "я" per the prompt, so
    this only tests that the resolver treats "я" as the actor either way."""
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Я заплатил 5000, за меня 2000, Максим 3000.",
        extraction=_extraction(
            amount="5000",
            payer_name="я",
            split_mode="exact",
            participants=[_share("я", "2000"), _share("Максим", "3000")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.amount_cents == 500000
    assert _resolved_by_name(draft) == {"Аня": "2000", "Максим": "3000"}
    assert draft.warnings == []


def test_exact_split_inconsistent_sum_produces_warning_not_correction(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Максим 500, я 700" with a stated total of 1500 — 500 + 700 != 1500."""
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Всего 1500, Максим 500, я 700.",
        extraction=_extraction(
            amount="1500",
            payer_name="я",
            split_mode="exact",
            participants=[_share("Максим", "500"), _share("я", "700")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    # Never invented or silently corrected — exactly what was said comes back.
    assert draft.amount_cents == 150000
    assert _resolved_by_name(draft) == {"Максим": "500", "Аня": "700"}
    assert any("не совпадают" in warning for warning in draft.warnings)


# ---------------------------------------------------------- percentage split


def test_percentage_split_basic(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Я заплатил 3000, я 60 процентов, Максим 40 процентов." """
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Я заплатил 3000, я 60 процентов, Максим 40 процентов.",
        extraction=_extraction(
            amount="3000",
            payer_name="я",
            split_mode="percentage",
            participants=[_share("я", "60"), _share("Максим", "40")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "percentage"
    assert draft.amount_cents == 300000
    assert _resolved_by_name(draft) == {"Аня": "60", "Максим": "40"}
    assert draft.warnings == []


def test_percentage_split_short_form_without_word_or_amount(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Я 60%, Максим 40%." — no stated total; the second value also omits
    the unit word but is still a percentage by context."""
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Я 60%, Максим 40%.",
        extraction=_extraction(
            split_mode="percentage",
            participants=[_share("я", "60"), _share("Максим", "40")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "percentage"
    assert draft.amount_cents is None
    assert _resolved_by_name(draft) == {"Аня": "60", "Максим": "40"}
    assert draft.warnings == []


def test_percentage_split_divide_between_phrasing(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Делим 70 на 30 между мной и Максимом." """
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Делим 70 на 30 между мной и Максимом.",
        extraction=_extraction(
            split_mode="percentage",
            participants=[_share("я", "70"), _share("Максим", "30")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert draft.split_mode == "percentage"
    assert _resolved_by_name(draft) == {"Аня": "70", "Максим": "30"}
    assert draft.warnings == []


def test_percentage_split_incomplete_sum_produces_warning(
    monkeypatch: pytest.MonkeyPatch,
    db: Session,
    split_group: Group,
    split_people: tuple[User, User, User],
) -> None:
    """"Максим 30%, я 50%" — sums to 80, not 100."""
    anya, maksim, _sasha = split_people
    _stub_pipeline(
        monkeypatch,
        transcript="Максим 30%, я 50%.",
        extraction=_extraction(
            split_mode="percentage",
            participants=[_share("Максим", "30"), _share("я", "50")],
        ),
    )

    draft = voice_service.build_draft(
        db, group=split_group, actor=anya, audio_bytes=b"fake-audio"
    )

    assert _resolved_by_name(draft) == {"Максим": "30", "Аня": "50"}
    assert any("80" in warning and "100" in warning for warning in draft.warnings)

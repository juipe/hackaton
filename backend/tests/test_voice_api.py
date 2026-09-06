"""Voice expense draft endpoint.

Exercises the route through the real HTTP/auth/CSRF/membership stack, with
GigaAM and GigaChat monkeypatched so the test suite never needs a speech
model or an API key. Asserts the one hard rule of this endpoint: it never
creates an expense, only an ephemeral draft.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.expense import Expense
from app.models.group import Group
from app.models.user import User
from app.schemas.voice import LLMExpenseExtraction
from app.services import voice_service


@pytest.fixture()
def people(make_user: Callable[..., User]) -> tuple[User, User]:
    return (
        make_user(name="Аня", email="anya@example.com"),
        make_user(name="Борис", email="boris@example.com"),
    )


@pytest.fixture()
def group(group_factory: Callable[..., Group], people: tuple[User, User]) -> Group:
    anya, boris = people
    return group_factory(anya, name="Соседи", currency="RUB", members=[boris])


def _stub_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        voice_service.gigaam_service,
        "transcribe",
        lambda _audio: "Заплатил 500 рублей за обед",
    )
    monkeypatch.setattr(
        voice_service.gigachat_service,
        "extract_expense",
        lambda _transcript, _categories: LLMExpenseExtraction(
            title="Обед", amount="500", category_slug="food", payer_name="я"
        ),
    )


def _upload(client: TestClient, group_id: str, *, content: bytes = b"RIFF....fake-wav") -> object:
    return client.post(
        f"/api/groups/{group_id}/voice-expenses",
        files={"audio": ("voice.webm", content, "audio/webm")},
    )


def _with_csrf_only(client: TestClient) -> TestClient:
    """A client that passes the CSRF check but carries no session cookie.

    Without this an anonymous unsafe request is rejected by ``CsrfMiddleware``
    (403) before authentication ever runs, which would hide the 401.
    """
    token = "csrf-anonymous"
    client.cookies.set(settings.csrf_cookie_name, token)
    client.headers[settings.csrf_header_name] = token
    return client


def test_requires_authentication(anon_client: TestClient, group: Group) -> None:
    response = _upload(_with_csrf_only(anon_client), str(group.id))
    assert response.status_code == 401


def test_requires_membership(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group: Group,
) -> None:
    _stub_pipeline(monkeypatch)
    outsider = make_user(name="Чужой", email="outsider@example.com")
    client = api_client(outsider)

    response = _upload(client, str(group.id))
    assert response.status_code == 403


def test_empty_audio_is_rejected(
    api_client: Callable[[User], TestClient], people: tuple[User, User], group: Group
) -> None:
    anya, _boris = people
    client = api_client(anya)

    response = _upload(client, str(group.id), content=b"")
    assert response.status_code == 400


def test_oversized_audio_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User],
    group: Group,
) -> None:
    anya, _boris = people
    client = api_client(anya)
    monkeypatch.setattr(settings, "voice_max_upload_bytes", 10)

    response = _upload(client, str(group.id), content=b"a" * 100)
    assert response.status_code == 400


def test_too_long_recording_returns_a_message_the_user_can_act_on(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User],
    group: Group,
) -> None:
    """The 25s GigaAM limit has to reach the user as readable Russian, not a
    generic failure: the dialog renders ``ApiError.detail`` verbatim (see
    ``errorMessage`` in frontend/src/lib/api.ts), so this response body is
    literally what gets shown."""
    anya, _boris = people

    def _too_long(_audio: bytes) -> str:
        raise voice_service.gigaam_service.AudioTooLongError(
            "Запись длиннее 25 секунд — запишите покороче или добавьте расход вручную"
        )

    monkeypatch.setattr(voice_service.gigaam_service, "transcribe", _too_long)
    client = api_client(anya)

    response = _upload(client, str(group.id))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "25 секунд" in detail
    # Names no model and no exception type — see the "твой AI помощник" rule.
    assert "GigaAM" not in detail and "Error" not in detail


def test_generic_transcription_failure_keeps_the_generic_message(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User],
    group: Group,
) -> None:
    """Only the too-long case gets its own wording; everything else keeps the
    message the endpoint has always returned."""
    anya, _boris = people

    def _boom(_audio: bytes) -> str:
        raise voice_service.gigaam_service.GigaAMError("ffmpeg fell over")

    monkeypatch.setattr(voice_service.gigaam_service, "transcribe", _boom)
    client = api_client(anya)

    response = _upload(client, str(group.id))

    assert response.status_code == 400
    assert response.json()["detail"] == "Не удалось обработать аудиозапись"


def test_returns_draft_and_never_creates_an_expense(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User],
    group: Group,
    db: Session,
) -> None:
    anya, boris = people
    _stub_pipeline(monkeypatch)
    client = api_client(anya)

    response = _upload(client, str(group.id))
    assert response.status_code == 200

    body = response.json()
    assert body["transcript"] == "Заплатил 500 рублей за обед"
    assert body["title"] == "Обед"
    assert body["amount_cents"] == 50000
    assert body["split_mode"] == "equal"
    assert body["payer"]["status"] == "resolved"
    assert body["payer"]["value"]["user"]["id"] == str(anya.id)
    assert body["category"]["status"] == "resolved"
    assert body["category"]["value"]["slug"] == "food"

    assert db.query(Expense).count() == 0

"""Черновик расхода из фото чека: ``POST /api/groups/{id}/receipt-expenses``.

Как и голосовой сосед, прогоняется через настоящий HTTP/auth-стек, но
``gigachat_service.extract_expense_from_receipt`` замокан — набор никогда не
ходит в GigaChat и не требует ключа.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.models.group import Group
from app.models.user import User
from app.schemas.voice import LLMExpenseExtraction
from app.services import gigachat_service

_PNG_STUB = b"\x89PNG\r\n\x1a\nfakepngbytes"


def _url(group: Group) -> str:
    return f"/api/groups/{group.id}/receipt-expenses"


def _upload(client: TestClient, group: Group, *, content_type: str = "image/png"):
    return client.post(
        _url(group),
        files={"receipt": ("receipt.png", _PNG_STUB, content_type)},
    )


@pytest.fixture()
def world(
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> tuple[User, User, Group]:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, name="Квартира", currency="RUB", members=[bob])
    return alice, bob, group


def test_requires_membership(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    world: tuple[User, User, Group],
) -> None:
    _, _, group = world
    outsider = make_user(name="Outsider")
    response = _upload(api_client(outsider), group)
    assert response.status_code == 403


def test_successful_receipt_becomes_a_draft(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
) -> None:
    alice, _, group = world
    monkeypatch.setattr(
        gigachat_service,
        "extract_expense_from_receipt",
        lambda *_args, **_kwargs: LLMExpenseExtraction(
            title="Продукты в Пятёрочке",
            description="Хлеб, молоко, сыр",
            amount="754.20",
            occurred_at="2026-09-05",
            category_slug="groceries",
            payer_name="я",
            split_mode="equal",
            participants=[],
        ),
    )

    response = _upload(api_client(alice), group)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Продукты в Пятёрочке"
    assert body["amount_cents"] == 75420
    assert body["split_mode"] == "equal"
    assert body["category"]["status"] == "resolved"
    assert body["category"]["value"]["slug"] == "groceries"
    # «я» на чеке — тот, кто его загрузил.
    assert body["payer"]["status"] == "resolved"
    assert body["payer"]["value"]["user"]["id"] == str(alice.id)
    assert body["occurred_at"].startswith("2026-09-05")
    assert body["warnings"] == []


def test_rejects_a_non_image_upload_without_calling_the_llm(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
) -> None:
    alice, _, group = world

    def _fail(*_args: object, **_kwargs: object) -> LLMExpenseExtraction:
        raise AssertionError("must not be called for a rejected upload")

    monkeypatch.setattr(gigachat_service, "extract_expense_from_receipt", _fail)

    response = _upload(api_client(alice), group, content_type="application/pdf")
    assert response.status_code == 400
    assert "JPEG" in response.json()["detail"]


def test_llm_failure_degrades_to_an_empty_draft_with_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
) -> None:
    alice, _, group = world

    def _raise(*_args: object, **_kwargs: object) -> LLMExpenseExtraction:
        raise gigachat_service.GigaChatError("boom")

    monkeypatch.setattr(gigachat_service, "extract_expense_from_receipt", _raise)

    response = _upload(api_client(alice), group)
    assert response.status_code == 200
    body = response.json()
    assert body["amount_cents"] is None
    assert body["warnings"]
    # Категория остаётся нерешённой: модель не запускалась, угадывать нечем.
    assert body["category"]["status"] == "unresolved"


def test_unreadable_total_adds_a_warning(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: tuple[User, User, Group],
) -> None:
    alice, _, group = world
    monkeypatch.setattr(
        gigachat_service,
        "extract_expense_from_receipt",
        lambda *_args, **_kwargs: LLMExpenseExtraction(
            title="Чек",
            amount=None,
            category_slug="other",
            payer_name="я",
            split_mode="equal",
            participants=[],
        ),
    )

    response = _upload(api_client(alice), group)
    assert response.status_code == 200
    body = response.json()
    assert body["amount_cents"] is None
    assert any("сумм" in warning for warning in body["warnings"])

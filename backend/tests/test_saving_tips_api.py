"""AI saving-tips dashboard endpoint.

Exercises ``POST /api/dashboard/saving-tips`` through the real HTTP/auth
stack, with ``ollama_service.generate_saving_tips`` monkeypatched so the
suite never needs a running Ollama server. Reuses the same ``world`` fixture
shape as ``test_dashboard_api.py`` (two groups, real expenses) so the period
and group-scoping behaviour is exercised against real data, not a mock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.expense import Expense, SplitMode
from app.models.group import Group
from app.models.user import User
from app.schemas.saving_tips import SavingTip, SavingTipsOut
from app.services import ollama_service
from app.utils.time import utcnow


def _category(categories: list[Category], slug: str) -> Category:
    return next(category for category in categories if category.slug == slug)


@dataclass
class World:
    alice: User
    bob: User
    family: Group


@pytest.fixture()
def world(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> World:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    family = group_factory(alice, name="Family", currency="RUB", members=[bob])

    expense = Expense(
        group_id=family.id,
        created_by=alice.id,
        title="Groceries",
        amount_cents=8000,
        currency=family.currency,
        category_id=_category(categories, "groceries").id,
        paid_by=alice.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.commit()
    return World(alice=alice, bob=bob, family=family)


def _stub_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ollama_service,
        "generate_saving_tips",
        lambda _payload: SavingTipsOut(
            tips=[
                SavingTip(
                    title="Продукты",
                    text="Продукты — крупная категория.",
                    type="data_driven",
                ),
                SavingTip(title="Лимит", text="Установите недельный лимит.", type="generic"),
            ]
        ),
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


def test_requires_authentication(anon_client: TestClient) -> None:
    response = _with_csrf_only(anon_client).post("/api/dashboard/saving-tips")
    assert response.status_code == 401


def test_rejects_a_group_the_caller_does_not_belong_to(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    world: World,
) -> None:
    outsider = make_user(name="Outsider")
    response = api_client(outsider).post(
        "/api/dashboard/saving-tips", params={"group_id": str(world.family.id)}
    )
    assert response.status_code == 403


def test_returns_qwens_tips_on_success(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    _stub_success(monkeypatch)

    response = api_client(world.alice).post("/api/dashboard/saving-tips")

    assert response.status_code == 200
    body = response.json()
    assert 2 <= len(body["tips"]) <= 3
    assert body["tips"][0]["type"] == "data_driven"


def test_falls_back_to_generic_tips_when_ollama_fails(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    def _raise(_payload: object) -> SavingTipsOut:
        raise ollama_service.OllamaError("boom")

    monkeypatch.setattr(ollama_service, "generate_saving_tips", _raise)

    response = api_client(world.alice).post("/api/dashboard/saving-tips")

    assert response.status_code == 200
    body = response.json()
    assert 2 <= len(body["tips"]) <= 3
    assert all(tip["type"] == "generic" for tip in body["tips"])


def test_falls_back_without_calling_ollama_when_there_is_no_spending(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
) -> None:
    called = False

    def _spy(_payload: object) -> SavingTipsOut:
        nonlocal called
        called = True
        raise AssertionError("should not be called for an account with no expenses")

    monkeypatch.setattr(ollama_service, "generate_saving_tips", _spy)

    response = api_client(make_user()).post("/api/dashboard/saving-tips")

    assert response.status_code == 200
    body = response.json()
    assert 2 <= len(body["tips"]) <= 3
    assert all(tip["type"] == "generic" for tip in body["tips"])
    assert called is False


def test_group_id_scopes_the_analysed_data(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    captured: list[object] = []

    def _capture(payload: object) -> SavingTipsOut:
        captured.append(payload)
        return SavingTipsOut(
            tips=[
                SavingTip(title="A", text="A.", type="generic"),
                SavingTip(title="B", text="B.", type="generic"),
            ]
        )

    monkeypatch.setattr(ollama_service, "generate_saving_tips", _capture)

    response = api_client(world.alice).post(
        "/api/dashboard/saving-tips", params={"group_id": str(world.family.id)}
    )

    assert response.status_code == 200
    assert captured[0].total_spending_cents == 8000
    assert captured[0].expense_count == 1
    assert captured[0].currency == "RUB"
    assert len(captured[0].categories) == 1
    assert captured[0].categories[0].name == "Продукты"
    assert captured[0].categories[0].percentage == 100.0


def test_unknown_period_is_rejected(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    response = api_client(world.alice).post(
        "/api/dashboard/saving-tips", params={"period": "since_forever"}
    )
    assert response.status_code == 400


def test_custom_period_requires_both_dates(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    response = api_client(world.alice).post(
        "/api/dashboard/saving-tips", params={"period": "custom", "date_to": "2026-09-30"}
    )
    assert response.status_code == 400


def test_custom_period_excludes_data_outside_the_window(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    called = False

    def _spy(_payload: object) -> SavingTipsOut:
        nonlocal called
        called = True
        raise AssertionError("should not be called — no spending inside this window")

    monkeypatch.setattr(ollama_service, "generate_saving_tips", _spy)

    response = api_client(world.alice).post(
        "/api/dashboard/saving-tips",
        params={"period": "custom", "date_from": "2020-01-01", "date_to": "2020-01-31"},
    )

    assert response.status_code == 200
    assert called is False
    assert all(tip["type"] == "generic" for tip in response.json()["tips"])


def test_sends_no_ids_or_member_data_to_qwen(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    captured: list[object] = []

    def _capture(payload: object) -> SavingTipsOut:
        captured.append(payload)
        return SavingTipsOut(
            tips=[
                SavingTip(title="A", text="A.", type="generic"),
                SavingTip(title="B", text="B.", type="generic"),
            ]
        )

    monkeypatch.setattr(ollama_service, "generate_saving_tips", _capture)

    api_client(world.alice).post("/api/dashboard/saving-tips")

    payload = captured[0]
    dumped = payload.model_dump()
    assert "categories" in dumped and "months" in dumped
    # Only the documented fields exist anywhere on the payload — no member
    # names, emails, group/category ids, or debt/balance figures.
    assert set(dumped.keys()) == {
        "total_spending_cents",
        "expense_count",
        "currency",
        "categories",
        "months",
    }
    for category in dumped["categories"]:
        assert set(category.keys()) == {"name", "amount_cents", "percentage", "expense_count"}
    for month in dumped["months"]:
        assert set(month.keys()) == {"month", "amount_cents", "your_share_cents"}

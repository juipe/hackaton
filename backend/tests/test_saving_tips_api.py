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
from app.utils.time import add_months, start_of_month, utcnow


def _category(categories: list[Category], slug: str) -> Category:
    return next(category for category in categories if category.slug == slug)


@dataclass
class World:
    alice: User
    bob: User
    carol: User
    family: Group
    #: A second group of Alice's, used only to prove group-scoped generation
    #: never leaks another group's spending into the analysed data.
    trip: Group


@pytest.fixture()
def world(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> World:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    family = group_factory(alice, name="Family", currency="RUB", members=[bob])
    trip = group_factory(alice, name="Trip", currency="RUB", members=[carol])

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
    trip_expense = Expense(
        group_id=trip.id,
        created_by=alice.id,
        title="Flights",
        amount_cents=50000,
        currency=trip.currency,
        category_id=_category(categories, "travel").id,
        paid_by=alice.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.add(trip_expense)
    db.commit()
    return World(alice=alice, bob=bob, carol=carol, family=family, trip=trip)


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
    # 8000 cents (80,00 ₽) is Family's own expense total — Trip's 50000
    # (a second group of Alice's) must never leak in just because she also
    # belongs to it.
    assert captured[0].total_spending_display == "80,00 ₽"
    assert captured[0].expense_count == 1
    assert captured[0].currency == "RUB"
    assert len(captured[0].categories) == 1
    assert captured[0].categories[0].name == "Продукты"
    assert captured[0].categories[0].amount_display == "80,00 ₽"
    assert captured[0].categories[0].percentage_display == "100%"


def test_group_scope_never_includes_another_groups_spending(
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    world: World,
) -> None:
    """Generating tips for one group must analyse that group alone — not every
    group the caller belongs to, and not any other specific group."""
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
        "/api/dashboard/saving-tips", params={"group_id": str(world.trip.id)}
    )

    assert response.status_code == 200
    assert captured[0].total_spending_display == "500,00 ₽"
    assert captured[0].expense_count == 1
    assert [category.name for category in captured[0].categories] == ["Путешествия"]


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
    assert "categories" in dumped and "trend" in dumped
    # Only the documented fields exist anywhere on the payload — no member
    # names, emails, group/category ids, or debt/balance figures. Every
    # amount and percentage is already a formatted display string, never a
    # raw cents integer or an unrounded ratio Qwen could recompute.
    assert set(dumped.keys()) == {
        "total_spending_display",
        "expense_count",
        "currency",
        "categories",
        "trend",
    }
    assert isinstance(dumped["total_spending_display"], str)
    for category in dumped["categories"]:
        assert set(category.keys()) == {
            "name",
            "amount_display",
            "percentage_display",
            "expense_count",
        }
        assert isinstance(category["amount_display"], str)
        assert isinstance(category["percentage_display"], str)
    # Both expenses in this fixture occur "now", so they land in the same
    # month bucket — no second month to compare against, so no trend.
    assert dumped["trend"] is None


def test_odd_cents_are_converted_to_rubles_before_reaching_qwen(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    """A non-round cents amount must already be a correct ruble string.

    Regression for the real E2E failure where Qwen was handed a raw cents
    integer and mis-converted it (5 RUB reported as "500 RUB", 70 RUB
    reported as "19,000 RUB"). The backend must do this conversion, not Qwen
    — so it must already be right in the payload Qwen receives.
    """
    alice = make_user(name="Alice")
    group = group_factory(alice, name="Solo")

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

    # An odd, easy-to-corrupt amount — 500 cents is 5,00 ₽, not "500 ₽".
    db.add(
        Expense(
            group_id=group.id,
            created_by=alice.id,
            title="Coffee",
            amount_cents=500,
            currency=group.currency,
            category_id=_category(categories, "food").id,
            paid_by=alice.id,
            split_mode=SplitMode.EQUAL.value,
            occurred_at=utcnow(),
        )
    )
    db.commit()

    response = api_client(alice).post(
        "/api/dashboard/saving-tips", params={"group_id": str(group.id)}
    )

    assert response.status_code == 200
    assert captured[0].total_spending_display == "5,00 ₽"
    assert captured[0].categories[0].amount_display == "5,00 ₽"
    assert captured[0].categories[0].percentage_display == "100%"


def test_trend_percentage_is_calculated_by_the_backend(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    """Month-to-month change must arrive pre-computed, exactly like the
    real E2E failure this fixes: 220,00 ₽ -> 300,00 ₽ is +36,4%, not a
    number Qwen invented or mis-derived.
    """
    alice = make_user(name="Alice")
    group = group_factory(alice, name="Two Months")
    food = _category(categories, "food")

    this_month = start_of_month(utcnow())
    last_month = add_months(this_month, -1)

    db.add(
        Expense(
            group_id=group.id,
            created_by=alice.id,
            title="Last month",
            amount_cents=22000,
            currency=group.currency,
            category_id=food.id,
            paid_by=alice.id,
            split_mode=SplitMode.EQUAL.value,
            occurred_at=last_month,
        )
    )
    db.add(
        Expense(
            group_id=group.id,
            created_by=alice.id,
            title="This month",
            amount_cents=30000,
            currency=group.currency,
            category_id=food.id,
            paid_by=alice.id,
            split_mode=SplitMode.EQUAL.value,
            occurred_at=this_month,
        )
    )
    db.commit()

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

    response = api_client(alice).post(
        "/api/dashboard/saving-tips", params={"group_id": str(group.id)}
    )

    assert response.status_code == 200
    trend = captured[0].trend
    assert trend is not None
    assert trend.from_display == "220,00 ₽"
    assert trend.to_display == "300,00 ₽"
    assert trend.change_display == "+36,4%"


def test_no_trend_when_only_one_month_has_data(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    """A single month of history must never produce a fabricated trend."""
    alice = make_user(name="Alice")
    group = group_factory(alice, name="One Month")

    db.add(
        Expense(
            group_id=group.id,
            created_by=alice.id,
            title="Coffee",
            amount_cents=500,
            currency=group.currency,
            category_id=_category(categories, "food").id,
            paid_by=alice.id,
            split_mode=SplitMode.EQUAL.value,
            occurred_at=utcnow(),
        )
    )
    db.commit()

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

    response = api_client(alice).post(
        "/api/dashboard/saving-tips", params={"group_id": str(group.id)}
    )

    assert response.status_code == 200
    assert captured[0].trend is None


def test_saving_tip_output_carries_no_numeric_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Qwen's return value is free text only — ``title``/``text``/``type``.

    Even if Qwen's generated text contains a wrong number, there is no
    numeric field anywhere on ``SavingTip``/``SavingTipsOut`` for that wrong
    number to land in and be reused elsewhere in the app — it can only ever
    exist inside a display string, never parsed back into a value that
    drives any calculation, balance, or persisted record.
    """
    tip = SavingTip(title="A", text="Что-то про 19 000 ₽, но это просто текст.", type="generic")
    dumped = tip.model_dump()
    assert set(dumped.keys()) == {"title", "text", "type"}
    assert all(isinstance(value, str) for value in dumped.values())

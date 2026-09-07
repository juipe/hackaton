"""«Критическая точка бюджета»: поле профиля + ``GET /api/dashboard/budget-status``.

Проверяет три вещи: частичное обновление бюджета через ``PATCH /auth/me``
(включая явный ``null`` как «снять лимит»), расчёт статуса от личной доли за
текущий месяц, и то, что лимит не утекает в публичные представления
пользователя (плательщик расхода, участник группы).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.models.category import Category
from app.models.group import Group
from app.models.user import User


def _expense_payload(
    *,
    category: Category,
    paid_by: User,
    participants: list[tuple[User, Any]],
    amount_cents: int,
    split_mode: str = "equal",
    title: str = "Ужин",
) -> dict[str, Any]:
    return {
        "title": title,
        "amount_cents": amount_cents,
        "category_id": str(category.id),
        "paid_by": str(paid_by.id),
        "split_mode": split_mode,
        "participants": [
            {"user_id": str(user.id), "value": value} for user, value in participants
        ],
    }


@pytest.fixture()
def food(categories: list[Category]) -> Category:
    return next(category for category in categories if category.slug == "food")


def test_patch_me_sets_keeps_and_clears_budget(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    client = api_client(make_user())

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": 4_000_000})
    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] == 4_000_000

    # Пропущенное поле оставляет лимит как был.
    response = client.patch("/api/auth/me", json={"name": "Новое Имя"})
    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] == 4_000_000

    # Явный null — команда «снять лимит».
    response = client.patch("/api/auth/me", json={"monthly_budget_cents": None})
    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] is None


@pytest.mark.parametrize("bad", [0, -100, "0", "-100", -100.0, "сорок тысяч", True])
def test_patch_me_rejects_a_non_positive_budget(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    bad: Any,
) -> None:
    client = api_client(make_user())
    response = client.patch("/api/auth/me", json={"monthly_budget_cents": bad})
    assert response.status_code == 422


def test_budget_status_is_none_level_until_a_budget_is_set(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    client = api_client(make_user())
    response = client.get("/api/dashboard/budget-status")
    assert response.status_code == 200
    body = response.json()
    assert body["level"] == "none"
    assert body["monthly_budget_cents"] is None
    assert body["remaining_cents"] is None
    assert body["spent_cents"] == 0


def test_budget_status_levels_track_the_personal_share(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    food: Category,
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, name="Ужины", currency="RUB", members=[bob])
    client = api_client(alice)

    assert (
        client.patch("/api/auth/me", json={"monthly_budget_cents": 10_000}).status_code
        == 200
    )

    # Поровну на двоих: доля Алисы — 6 000 из 12 000 (60% лимита) -> ok.
    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_expense_payload(
            category=food,
            paid_by=alice,
            participants=[(alice, None), (bob, None)],
            amount_cents=12_000,
        ),
    )
    assert response.status_code == 201, response.text

    body = client.get("/api/dashboard/budget-status").json()
    assert body["level"] == "ok"
    assert body["spent_cents"] == 6_000
    assert body["remaining_cents"] == 4_000

    # Ещё 5 000 поровну: доля 2 500, всего 8 500 из 10 000 (85%) -> warning.
    assert (
        client.post(
            f"/api/groups/{group.id}/expenses",
            json=_expense_payload(
                category=food,
                paid_by=alice,
                participants=[(alice, None), (bob, None)],
                amount_cents=5_000,
                title="Кофе",
            ),
        ).status_code
        == 201
    )
    body = client.get("/api/dashboard/budget-status").json()
    assert body["level"] == "warning"
    assert body["spent_cents"] == 8_500

    # Ещё 4 000 поровну: доля 2 000, всего 10 500 — превышение -> critical.
    assert (
        client.post(
            f"/api/groups/{group.id}/expenses",
            json=_expense_payload(
                category=food,
                paid_by=alice,
                participants=[(alice, None), (bob, None)],
                amount_cents=4_000,
                title="Десерт",
            ),
        ).status_code
        == 201
    )
    body = client.get("/api/dashboard/budget-status").json()
    assert body["level"] == "critical"
    assert body["spent_cents"] == 10_500
    assert body["remaining_cents"] == -500


def test_budget_never_leaks_into_public_user_shapes(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    food: Category,
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, name="Ужины", currency="RUB", members=[bob])
    client = api_client(alice)
    assert (
        client.patch("/api/auth/me", json={"monthly_budget_cents": 4_000_000}).status_code
        == 200
    )

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_expense_payload(
            category=food,
            paid_by=alice,
            participants=[(alice, None), (bob, None)],
            amount_cents=1_000,
        ),
    )
    assert response.status_code == 201
    body = response.json()
    # Плательщик, автор и участники — UserPublic: личного лимита там нет.
    assert "monthly_budget_cents" not in body["payer"]
    assert "monthly_budget_cents" not in body["creator"]

    members = api_client(bob).get(f"/api/groups/{group.id}/members")
    assert members.status_code == 200
    for member in members.json():
        assert "monthly_budget_cents" not in member["user"]

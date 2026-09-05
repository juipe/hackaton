"""End-to-end tests for the critical budget threshold feature.

Exercises the real HTTP stack the same way ``test_notifications_api.py`` does:
profile configuration through ``/auth/me``, and the threshold check triggered by
real expense/payment creation, read back through the existing ``/notifications``
endpoint (unchanged — the new notification just rides the same mechanism).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.group import Group
from app.models.user import User


def _food(categories: list[Category]) -> Category:
    return next(category for category in categories if category.slug == "food")


def _expense_payload(
    *, category: Category, paid_by: User, participants: list[tuple[User, Any]], amount_cents: int
) -> dict[str, Any]:
    return {
        "title": "Аренда",
        "amount_cents": amount_cents,
        "category_id": str(category.id),
        "paid_by": str(paid_by.id),
        "split_mode": "equal",
        "participants": [
            {"user_id": str(user.id), "value": value} for user, value in participants
        ],
    }


def _notifications(client: TestClient) -> list[dict[str, Any]]:
    response = client.get("/api/notifications")
    assert response.status_code == 200
    return response.json()


def _budget_notifications(client: TestClient) -> list[dict[str, Any]]:
    return [n for n in _notifications(client) if n["type"] == "budget_threshold"]


# --------------------------------------------------------------- profile configuration


def test_user_without_configured_budget_reads_null(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] is None


def test_set_valid_budget(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": 50_000_00})

    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] == 50_000_00


def test_zero_budget_is_rejected(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": 0})

    assert response.status_code == 422


def test_negative_budget_is_rejected(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": -100_00})

    assert response.status_code == 422


def test_absurdly_large_budget_is_rejected(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": 10**15})

    assert response.status_code == 422


def test_update_existing_budget(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user()
    client = api_client(user)
    client.patch("/api/auth/me", json={"monthly_budget_cents": 50_000_00})

    response = client.patch("/api/auth/me", json={"monthly_budget_cents": 80_000_00})

    assert response.status_code == 200
    assert response.json()["monthly_budget_cents"] == 80_000_00


def test_clearing_budget_disables_future_checks(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    client = api_client(debtor)
    client.patch("/api/auth/me", json={"monthly_budget_cents": 100_00})
    client.patch("/api/auth/me", json={"monthly_budget_cents": None})

    payer_client = api_client(payer)
    body = _expense_payload(
        category=_food(categories),
        paid_by=payer,
        participants=[(payer, None), (debtor, None)],
        amount_cents=400_00,
    )
    response = payer_client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    debtor_client = api_client(debtor)
    assert _budget_notifications(debtor_client) == []
    db.refresh(debtor)
    assert debtor.budget_alert_state is None


# --------------------------------------------------------------- trigger behaviour


def test_expense_creation_triggers_check_after_persisting(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    api_client(debtor).patch("/api/auth/me", json={"monthly_budget_cents": 100_00})

    payer_client = api_client(payer)
    body = _expense_payload(
        category=_food(categories),
        paid_by=payer,
        participants=[(payer, None), (debtor, None)],
        amount_cents=200_00,  # debtor's share = 100 -> exactly 100% of their budget
    )
    response = payer_client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    debtor_client = api_client(debtor)
    notifications = _budget_notifications(debtor_client)
    assert len(notifications) == 1
    assert notifications[0]["amount_due_cents"] == 100_00


def test_payer_is_not_notified_for_their_own_expense(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    # Payer configures a tiny budget — irrelevant, since paying never grows debt.
    api_client(payer).patch("/api/auth/me", json={"monthly_budget_cents": 1})

    payer_client = api_client(payer)
    body = _expense_payload(
        category=_food(categories),
        paid_by=payer,
        participants=[(payer, None), (debtor, None)],
        amount_cents=200_00,
    )
    response = payer_client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    assert _budget_notifications(payer_client) == []


def test_payment_creation_can_trigger_check_for_receiver(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    sender = make_user(name="Sender")
    receiver = make_user(name="Receiver")
    group = group_factory(sender, members=[receiver])
    api_client(receiver).patch("/api/auth/me", json={"monthly_budget_cents": 100_00})

    sender_client = api_client(sender)
    response = sender_client.post(
        f"/api/groups/{group.id}/payments",
        json={
            "from_user_id": str(sender.id),
            "to_user_id": str(receiver.id),
            "amount_cents": 150_00,
        },
    )
    assert response.status_code == 201

    receiver_client = api_client(receiver)
    notifications = _budget_notifications(receiver_client)
    assert len(notifications) == 1


# --------------------------------------------------------------- notifications


def test_approaching_and_exceeded_wording_differs(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    api_client(debtor).patch("/api/auth/me", json={"monthly_budget_cents": 100_00})
    payer_client = api_client(payer)
    food = _food(categories)

    payer_client.post(
        f"/api/groups/{group.id}/expenses",
        json=_expense_payload(
            category=food,
            paid_by=payer,
            participants=[(payer, None), (debtor, None)],
            amount_cents=180_00,  # debtor share 90 -> 90%
        ),
    )
    debtor_client = api_client(debtor)
    approaching = _budget_notifications(debtor_client)
    assert len(approaching) == 1
    assert "приближ" in approaching[0]["message"].lower()

    payer_client.post(
        f"/api/groups/{group.id}/expenses",
        json=_expense_payload(
            category=food,
            paid_by=payer,
            participants=[(payer, None), (debtor, None)],
            amount_cents=40_00,  # debtor share +20 -> 110%
        ),
    )
    exceeded = _budget_notifications(debtor_client)
    assert len(exceeded) == 2
    assert "превышен" in exceeded[0]["message"].lower()


def test_duplicate_notifications_are_not_created_while_state_is_unchanged(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    api_client(debtor).patch("/api/auth/me", json={"monthly_budget_cents": 10_000})
    payer_client = api_client(payer)
    food = _food(categories)

    # First expense crosses into "approaching" (85%); the next two only add a
    # little more debt and stay under 100%, so the state never changes again.
    debtor_shares = [8_500, 100, 100]
    for share in debtor_shares:
        payer_client.post(
            f"/api/groups/{group.id}/expenses",
            json=_expense_payload(
                category=food,
                paid_by=payer,
                participants=[(payer, None), (debtor, None)],
                amount_cents=share * 2,
            ),
        )

    debtor_client = api_client(debtor)
    notifications = _budget_notifications(debtor_client)
    assert len(notifications) == 1


def test_unrelated_debt_reminder_notifications_still_work(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
    monkeypatch: Any,
) -> None:
    """Regression: a debt reminder and a budget-threshold notification can
    coexist for the same user without hitting the debt-reminder's unique
    constraint on (expense_id, user_id) — see the Notification model.
    """
    monkeypatch.setattr(settings, "debt_reminder_delay_seconds", 0)
    payer = make_user(name="Payer")
    debtor = make_user(name="Debtor")
    group = group_factory(payer, members=[debtor])
    api_client(debtor).patch("/api/auth/me", json={"monthly_budget_cents": 100_00})

    payer_client = api_client(payer)
    response = payer_client.post(
        f"/api/groups/{group.id}/expenses",
        json=_expense_payload(
            category=_food(categories),
            paid_by=payer,
            participants=[(payer, None), (debtor, None)],
            amount_cents=200_00,  # debtor share 100 -> exceeded
        ),
    )
    assert response.status_code == 201

    debtor_client = api_client(debtor)
    all_notifications = _notifications(debtor_client)
    types = {n["type"] for n in all_notifications}
    assert types == {"debt_reminder", "budget_threshold"}

"""Debt-reminder notifications — created as a side effect of expense creation.

Exercises the feature through the real HTTP stack wherever possible (expense
creation, the notifications endpoints, auth), the same way ``test_expenses_api.py``
and ``test_invariants.py`` do. ``TestClient`` runs ``BackgroundTasks``
synchronously before the response comes back, so the Qwen-enhancement step is
deterministic here without any sleeping or polling.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.group import Group
from app.models.notification import Notification
from app.models.user import User
from app.repositories import notification_repo
from app.schemas.notification import DebtReminderOut
from app.services import debt_reminder_service, ollama_service
from app.utils.time import utcnow


def _category(categories: list[Category], slug: str) -> Category:
    return next(category for category in categories if category.slug == slug)


def _payload(
    *,
    category: Category,
    paid_by: User,
    participants: list[tuple[User, Any]],
    amount_cents: int = 12000,
    split_mode: str = "equal",
    title: str = "Ужин",
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "amount_cents": amount_cents,
        "category_id": str(category.id),
        "paid_by": str(paid_by.id),
        "split_mode": split_mode,
        "participants": [
            {"user_id": str(user.id), "value": value} for user, value in participants
        ],
    }
    body.update(extra)
    return body


@pytest.fixture()
def people(make_user: Callable[..., User]) -> tuple[User, User, User]:
    return (
        make_user(name="Ada", email="ada@example.com"),
        make_user(name="Ben", email="ben@example.com"),
        make_user(name="Cleo", email="cleo@example.com"),
    )


@pytest.fixture()
def group(group_factory: Callable[..., Group], people: tuple[User, User, User]) -> Group:
    ada, ben, cleo = people
    return group_factory(ada, name="Flatmates", currency="RUB", members=[ben, cleo])


@pytest.fixture()
def food(categories: list[Category]) -> Category:
    return _category(categories, "food")


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    """Most tests here care about *who* gets notified, not the 10-second delay.

    The delay itself gets its own tests below, which override this back up.
    """
    monkeypatch.setattr(settings, "debt_reminder_delay_seconds", 0)


def _notifications_for_expense(db: Session, expense_id: str) -> list[Notification]:
    stmt = select(Notification).where(Notification.expense_id == uuid.UUID(expense_id))
    return list(db.scalars(stmt))


# --------------------------------------------------------------- debtor detection


def test_debtors_are_notified_and_payer_is_not(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    body = _payload(
        category=food, paid_by=ada, participants=[(ada, None), (ben, None), (cleo, None)]
    )
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201
    expense_id = response.json()["id"]

    notifications = _notifications_for_expense(db, expense_id)
    notified_user_ids = {str(notification.user_id) for notification in notifications}

    assert notified_user_ids == {str(ben.id), str(cleo.id)}
    assert str(ada.id) not in notified_user_ids


def test_multiple_debtors_get_separate_notifications(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    body = _payload(
        category=food, paid_by=ada, participants=[(ada, None), (ben, None), (cleo, None)]
    )
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    expense_id = response.json()["id"]

    notifications = _notifications_for_expense(db, expense_id)
    assert len(notifications) == 2
    assert len({notification.id for notification in notifications}) == 2


def test_zero_share_participant_is_not_notified(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    # Exact split, in cents: Ben owes nothing, Cleo owes the whole thing.
    body = _payload(
        category=food,
        paid_by=ada,
        split_mode="exact",
        amount_cents=12000,
        participants=[(ada, "0"), (ben, "0"), (cleo, "12000")],
    )
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201
    expense_id = response.json()["id"]

    notifications = _notifications_for_expense(db, expense_id)
    notified_user_ids = {str(notification.user_id) for notification in notifications}
    assert notified_user_ids == {str(cleo.id)}


def test_exact_calculated_share_is_used(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    # Shares mode: Ada 1 share, Ben 3 shares of 10000 cents -> 2500 / 7500.
    body = _payload(
        category=food,
        paid_by=ada,
        split_mode="shares",
        amount_cents=10000,
        participants=[(ada, "1"), (ben, "3")],
    )
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201
    body_out = response.json()
    ben_share = next(
        split["calculated_amount_cents"]
        for split in body_out["splits"]
        if split["user_id"] == str(ben.id)
    )
    assert ben_share == 7500

    notifications = _notifications_for_expense(db, body_out["id"])
    assert len(notifications) == 1
    assert notifications[0].amount_due_cents == ben_share == 7500


def test_no_reminder_when_payer_covers_everyone(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, _ben, _cleo = people
    client = api_client(ada)

    body = _payload(
        category=food, paid_by=ada, split_mode="exact", amount_cents=5000,
        participants=[(ada, "5000")],
    )
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    assert _notifications_for_expense(db, response.json()["id"]) == []


# --------------------------------------------------------------- availability delay


def test_notification_unavailable_before_delay(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "debt_reminder_delay_seconds", 10)
    ada, ben, _cleo = people

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    api_client(ada).post(f"/api/groups/{group.id}/expenses", json=body)

    response = api_client(ben).get("/api/notifications")
    assert response.status_code == 200
    assert response.json() == []


def test_notification_available_after_delay(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "debt_reminder_delay_seconds", 10)
    ada, ben, _cleo = people

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    api_client(ada).post(f"/api/groups/{group.id}/expenses", json=body)

    # Time has passed — simulate it the same way the rest of the suite does
    # (see test_invites_api.py): edit the row directly rather than mocking a clock.
    notification = db.scalar(select(Notification).where(Notification.user_id == ben.id))
    assert notification is not None
    notification.available_at = utcnow() - timedelta(seconds=1)
    db.commit()

    response = api_client(ben).get("/api/notifications")
    assert response.status_code == 200
    assert len(response.json()) == 1


# --------------------------------------------------------------- listing


def test_at_most_ten_notifications_newest_first(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, _cleo = people
    client = api_client(ada)

    for i in range(12):
        body = _payload(
            category=food,
            paid_by=ada,
            title=f"Расход {i}",
            participants=[(ada, None), (ben, None)],
        )
        client.post(f"/api/groups/{group.id}/expenses", json=body)

    # Give each notification a distinct, increasing `created_at` so "newest
    # first" is unambiguous — expenses created in the same test can otherwise
    # land in the same instant.
    notifications = list(
        db.scalars(select(Notification).where(Notification.user_id == ben.id))
    )
    assert len(notifications) == 12
    base = utcnow()
    for index, notification in enumerate(notifications):
        notification.created_at = base + timedelta(seconds=index)
    db.commit()

    response = api_client(ben).get("/api/notifications")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 10
    titles = [item["expense_title"] for item in body]
    assert titles == [f"Расход {i}" for i in range(11, 1, -1)]


def test_user_isolation(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    body = _payload(
        category=food, paid_by=ada, participants=[(ada, None), (ben, None), (cleo, None)]
    )
    client.post(f"/api/groups/{group.id}/expenses", json=body)

    ben_notifications = api_client(ben).get("/api/notifications").json()
    cleo_notifications = api_client(cleo).get("/api/notifications").json()

    assert len(ben_notifications) == 1
    assert len(cleo_notifications) == 1
    assert ben_notifications[0]["id"] != cleo_notifications[0]["id"]


def test_unauthorized_access_is_rejected(anon_client: TestClient) -> None:
    response = anon_client.get("/api/notifications")
    assert response.status_code == 401

    # POST needs a CSRF pair to get past the middleware and reach authentication
    # — see the same pattern in test_payments_api.py::test_anonymous_is_unauthenticated.
    anon_client.cookies.set(settings.csrf_cookie_name, "csrf-token")
    anon_client.headers[settings.csrf_header_name] = "csrf-token"
    response = anon_client.post("/api/notifications/read")
    assert response.status_code == 401


def test_mark_read_only_affects_current_user(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    body = _payload(
        category=food, paid_by=ada, participants=[(ada, None), (ben, None), (cleo, None)]
    )
    client.post(f"/api/groups/{group.id}/expenses", json=body)

    response = api_client(ben).post("/api/notifications/read")
    assert response.status_code == 204

    assert api_client(ben).get("/api/notifications").json()[0]["is_read"] is True
    assert api_client(cleo).get("/api/notifications").json()[0]["is_read"] is False


# --------------------------------------------------------------- duplicate prevention


def test_duplicate_reminder_is_never_created_for_the_same_expense_and_debtor(
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    from app.models.expense import Expense, SplitMode
    from app.services.split_engine import SplitResult

    ada, ben, _cleo = people
    expense = Expense(
        group_id=group.id,
        created_by=ada.id,
        title="Ужин",
        amount_cents=10000,
        currency="RUB",
        category_id=food.id,
        paid_by=ada.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.flush()
    results = [
        SplitResult(user_id=ada.id, input_value=None, calculated_amount_cents=5000),
        SplitResult(user_id=ben.id, input_value=None, calculated_amount_cents=5000),
    ]

    first = debt_reminder_service.create_reminders_for_expense(
        db, expense=expense, group=group, results=results
    )
    second = debt_reminder_service.create_reminders_for_expense(
        db, expense=expense, group=group, results=results
    )
    db.commit()

    assert len(first) == 1
    assert len(second) == 0
    assert len(notification_repo.ids_for_expense(db, expense.id)) == 1


# --------------------------------------------------------------- restart safety


def test_reminder_survives_in_a_fresh_session_without_any_qwen_step(
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reminder must exist and be fully usable from data alone.

    Nothing about it — its facts, its fallback wording, or the 10-second
    delay — depends on any state held in the process that created it. This
    simulates a restart between the expense committing and the background
    Qwen step ever running: a brand-new ``SessionLocal()`` (the same one a
    freshly started process would open) sees a complete notification with no
    scheduled job or in-memory timer required to produce it.
    """
    from app.db.session import SessionLocal

    # No Qwen call happens at all in this test — proving the row it inspects
    # was never dependent on the background step having run.
    monkeypatch.setattr(
        ollama_service,
        "generate_debt_reminder",
        lambda _data: pytest.fail("must not be called before the process 'restarts'"),
    )
    ada, ben, _cleo = people
    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])

    # A plain DB write (skipping the route's background-task wiring) is the
    # honest way to model "the process died right after the commit, before
    # BackgroundTasks got to run" — see module docstring on `create_reminders_for_expense`.
    from app.models.expense import Expense, SplitMode
    from app.services.split_engine import SplitResult

    expense = Expense(
        group_id=group.id,
        created_by=ada.id,
        title=body["title"],
        amount_cents=body["amount_cents"],
        currency="RUB",
        category_id=food.id,
        paid_by=ada.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.flush()
    results = [
        SplitResult(user_id=ada.id, input_value=None, calculated_amount_cents=6000),
        SplitResult(user_id=ben.id, input_value=None, calculated_amount_cents=6000),
    ]
    debt_reminder_service.create_reminders_for_expense(
        db, expense=expense, group=group, results=results
    )
    db.commit()

    with SessionLocal() as fresh_session:
        notification = fresh_session.scalar(
            select(Notification).where(Notification.expense_id == expense.id)
        )
        assert notification is not None
        assert notification.user_id == ben.id
        assert notification.amount_due_cents == 6000
        assert notification.source == "fallback"
        assert notification.message  # a complete, displayable sentence already


# --------------------------------------------------------------- Qwen wording


def test_qwen_success_replaces_fallback_message(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ollama_service,
        "generate_debt_reminder",
        lambda _data: DebtReminderOut(message="Не забудьте вернуть долг за ужин!"),
    )
    ada, ben, _cleo = people
    client = api_client(ada)

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)

    notification = db.scalar(
        select(Notification).where(Notification.expense_id == uuid.UUID(response.json()["id"]))
    )
    assert notification is not None
    assert notification.message == "Не забудьте вернуть долг за ужин!"
    assert notification.source == "qwen"


def test_qwen_failure_keeps_deterministic_fallback(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(_data: object) -> None:
        raise ollama_service.OllamaError("Ollama timed out")

    monkeypatch.setattr(ollama_service, "generate_debt_reminder", _raise)
    ada, ben, _cleo = people
    client = api_client(ada)

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    notification = db.scalar(
        select(Notification).where(Notification.expense_id == uuid.UUID(response.json()["id"]))
    )
    assert notification is not None
    assert notification.source == "fallback"
    assert "Ужин" in notification.message
    # The fallback names the payer (who is owed), not the debtor it's shown to.
    assert ada.name in notification.message


def test_invalid_qwen_response_falls_back(
    db: Session,
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid Qwen response surfaces as ``OllamaError`` (see
    ``test_ollama_service.py``); this proves the notification pipeline treats
    that exactly like any other Ollama failure — deterministic fallback, never
    a broken expense request."""

    def _raise(_data: object) -> None:
        raise ollama_service.OllamaError("Модель вернула данные неожиданной формы")

    monkeypatch.setattr(ollama_service, "generate_debt_reminder", _raise)
    ada, ben, _cleo = people
    client = api_client(ada)

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

    notification = db.scalar(
        select(Notification).where(Notification.expense_id == uuid.UUID(response.json()["id"]))
    )
    assert notification is not None
    assert notification.source == "fallback"


def test_expense_creation_succeeds_even_if_qwen_blows_up(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _explode(_data: object) -> None:
        raise RuntimeError("something Ollama-shaped went very wrong")

    monkeypatch.setattr(ollama_service, "generate_debt_reminder", _explode)
    ada, ben, _cleo = people
    client = api_client(ada)

    body = _payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)])
    # A completely unexpected exception in the background Qwen step (not just
    # an `OllamaError`) must still never take the already-sent response down
    # with it.
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 201

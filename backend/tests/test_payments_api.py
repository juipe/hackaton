"""API tests for settle-up payments."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity import Activity, ActivityType
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.user import User
from app.utils.time import utcnow


def payments_url(group: Group) -> str:
    return f"/api/groups/{group.id}/payments"


def add_equal_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    participants: Sequence[User],
    amount_cents: int,
    category: Category,
) -> Expense:
    """Seed a debt by writing the expense rows directly.

    This suite is about payments, so the ledger is set up through the models
    rather than through the expense API owned by another slice.
    """
    share = amount_cents // len(participants)
    expense = Expense(
        group_id=group.id,
        created_by=payer.id,
        title="Dinner",
        amount_cents=amount_cents,
        currency=group.currency,
        category_id=category.id,
        paid_by=payer.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
        splits=[
            ExpenseSplit(
                user_id=participant.id,
                split_mode=SplitMode.EQUAL.value,
                input_value=None,
                calculated_amount_cents=share,
            )
            for participant in participants
        ],
    )
    db.add(expense)
    db.commit()
    return expense


def nets(db: Session, group: Group) -> dict[uuid.UUID, int]:
    from app.services import balance_service

    balances = balance_service.compute_group_balances(db, group.id)
    return {balance.user_id: balance.net_cents for balance in balances.balances}


def test_record_payment_returns_both_users_and_group_currency(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, name="Flat", currency="RUB", members=[bob])
    client = api_client(bob)

    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(alice.id),
            "amount_cents": 4000,
            "note": "  bank transfer  ",
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["group_id"] == str(group.id)
    assert body["from_user_id"] == str(bob.id)
    assert body["to_user_id"] == str(alice.id)
    assert body["from_user"] == {"id": str(bob.id), "name": bob.name, "email": bob.email}
    assert body["to_user"] == {"id": str(alice.id), "name": alice.name, "email": alice.email}
    assert body["amount_cents"] == 4000
    assert body["currency"] == "RUB"
    assert body["note"] == "bank transfer"
    assert datetime.fromisoformat(body["paid_at"]).tzinfo is not None
    assert "password_hash" not in body["from_user"]


def test_payment_clears_the_debt(
    db: Session,
    categories: list[Category],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, members=[bob])
    add_equal_expense(
        db,
        group=group,
        payer=alice,
        participants=[alice, bob],
        amount_cents=8000,
        category=categories[0],
    )

    before = nets(db, group)
    assert before[alice.id] == 4000
    assert before[bob.id] == -4000

    client = api_client(bob)
    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(alice.id),
            "amount_cents": 4000,
        },
    )
    assert response.status_code == 201, response.text

    after = nets(db, group)
    assert after[alice.id] == 0
    assert after[bob.id] == 0


def test_partial_payment_leaves_the_rest_outstanding(
    db: Session,
    categories: list[Category],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, members=[bob])
    add_equal_expense(
        db,
        group=group,
        payer=alice,
        participants=[alice, bob],
        amount_cents=8000,
        category=categories[0],
    )

    client = api_client(bob)
    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(alice.id),
            "amount_cents": 1500,
        },
    )
    assert response.status_code == 201, response.text

    after = nets(db, group)
    assert after[alice.id] == 2500
    assert after[bob.id] == -2500


def test_list_payments_is_newest_first(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, members=[bob])
    client = api_client(bob)

    now = utcnow()
    for offset_days, amount in ((3, 100), (1, 200), (2, 300)):
        response = client.post(
            payments_url(group),
            json={
                "from_user_id": str(bob.id),
                "to_user_id": str(alice.id),
                "amount_cents": amount,
                "paid_at": (now - timedelta(days=offset_days)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text

    listed = client.get(payments_url(group))
    assert listed.status_code == 200
    assert [item["amount_cents"] for item in listed.json()] == [200, 300, 100]


def test_amount_must_be_greater_than_zero(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    bob = make_user()
    group = group_factory(alice, members=[bob])
    client = api_client(bob)

    for amount in (0, -4000):
        response = client.post(
            payments_url(group),
            json={
                "from_user_id": str(bob.id),
                "to_user_id": str(alice.id),
                "amount_cents": amount,
            },
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "Сумма должна быть больше нуля"


def test_payment_needs_two_different_people(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    bob = make_user()
    group = group_factory(alice, members=[bob])
    client = api_client(bob)

    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(bob.id),
            "amount_cents": 500,
        },
    )
    assert response.status_code in (400, 422)
    assert response.json()["detail"] == "Перевод возможен только между разными людьми"


def test_both_people_must_be_members(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    bob = make_user()
    outsider = make_user()
    group = group_factory(alice, members=[bob])
    client = api_client(alice)

    for payload in (
        {"from_user_id": str(alice.id), "to_user_id": str(outsider.id)},
        {"from_user_id": str(outsider.id), "to_user_id": str(alice.id)},
        {"from_user_id": str(uuid.uuid4()), "to_user_id": str(alice.id)},
    ):
        response = client.post(
            payments_url(group), json={**payload, "amount_cents": 500}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Оба участника должны состоять в группе"


def test_member_cannot_record_a_payment_between_two_others(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(alice, members=[bob, carol])
    client = api_client(bob)

    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(carol.id),
            "to_user_id": str(alice.id),
            "amount_cents": 2500,
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Можно записывать только свои переводы"


def test_owner_may_record_a_payment_between_two_others(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(alice, members=[bob, carol])
    client = api_client(alice)

    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(carol.id),
            "amount_cents": 2500,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["from_user"]["name"] == "Bob"


def test_non_member_is_forbidden(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    bob = make_user()
    outsider = make_user()
    group = group_factory(alice, members=[bob])
    client = api_client(outsider)

    listed = client.get(payments_url(group))
    assert listed.status_code == 403
    assert listed.json()["detail"] == "Вы не участник этой группы"

    created = client.post(
        payments_url(group),
        json={
            "from_user_id": str(outsider.id),
            "to_user_id": str(alice.id),
            "amount_cents": 500,
        },
    )
    assert created.status_code == 403


def test_anonymous_is_unauthenticated(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    anon_client: TestClient,
) -> None:
    alice = make_user()
    group = group_factory(alice)

    listed = anon_client.get(payments_url(group))
    assert listed.status_code == 401
    assert listed.json()["detail"] == "Требуется вход"

    # POST needs a CSRF pair to get past the middleware and reach authentication.
    anon_client.cookies.set(settings.csrf_cookie_name, "csrf-token")
    anon_client.headers[settings.csrf_header_name] = "csrf-token"
    created = anon_client.post(
        payments_url(group),
        json={
            "from_user_id": str(alice.id),
            "to_user_id": str(uuid.uuid4()),
            "amount_cents": 500,
        },
    )
    assert created.status_code == 401


def test_unknown_group_is_not_found(
    db: Session,
    make_user: Callable[..., User],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    client = api_client(alice)

    response = client.get(f"/api/groups/{uuid.uuid4()}/payments")
    assert response.status_code == 404
    assert response.json()["detail"] == "Группа не найдена"


def test_paid_at_defaults_to_now(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user()
    bob = make_user()
    group = group_factory(alice, members=[bob])
    client = api_client(bob)

    before = utcnow()
    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(alice.id),
            "amount_cents": 750,
        },
    )
    assert response.status_code == 201, response.text

    paid_at = datetime.fromisoformat(response.json()["paid_at"])
    assert before - timedelta(seconds=5) <= paid_at <= utcnow() + timedelta(seconds=5)
    assert response.json()["note"] is None


def test_recording_a_payment_logs_an_activity(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    api_client: Callable[[User], TestClient],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(alice, name="Trip", currency="RUB", members=[bob])
    client = api_client(bob)

    response = client.post(
        payments_url(group),
        json={
            "from_user_id": str(bob.id),
            "to_user_id": str(alice.id),
            "amount_cents": 4000,
        },
    )
    assert response.status_code == 201, response.text

    activity = db.scalar(
        select(Activity).where(
            Activity.group_id == group.id,
            Activity.type == ActivityType.PAYMENT_CREATED.value,
        )
    )
    assert activity is not None
    assert activity.actor_id == bob.id
    assert activity.entity_id == uuid.UUID(response.json()["id"])
    assert activity.meta == {
        "amount_cents": 4000,
        "currency": "RUB",
        "from_name": "Bob",
        "to_name": "Alice",
    }

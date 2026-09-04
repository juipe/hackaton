"""Dashboard analytics endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.user import User
from app.utils.time import add_months, month_key, start_of_month, utcnow

DASHBOARD_PATHS = (
    "/api/dashboard/summary",
    "/api/dashboard/spending-by-category",
    "/api/dashboard/spending-over-time",
)


def _category(categories: list[Category], slug: str) -> Category:
    return next(category for category in categories if category.slug == slug)


def _add_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    category: Category,
    amount_cents: int,
    participants: Sequence[User],
    occurred_at: datetime | None = None,
    deleted: bool = False,
    title: str = "Expense",
) -> Expense:
    """Insert an equally split expense straight through the ORM.

    The dashboard only reads the ledger, so the tests build it directly instead of
    going through the expense endpoints.
    """
    expense = Expense(
        group_id=group.id,
        created_by=payer.id,
        title=title,
        amount_cents=amount_cents,
        currency=group.currency,
        category_id=category.id,
        paid_by=payer.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=occurred_at or utcnow(),
        deleted_at=utcnow() if deleted else None,
    )
    db.add(expense)
    db.flush()
    base, leftover = divmod(amount_cents, len(participants))
    for index, participant in enumerate(participants):
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=participant.id,
                split_mode=SplitMode.EQUAL.value,
                input_value=None,
                calculated_amount_cents=base + (1 if index < leftover else 0),
            )
        )
    db.commit()
    return expense


@dataclass
class World:
    """Two groups: Alice owes 40.00 in one and is owed 100.00 in the other."""

    alice: User
    bob: User
    carol: User
    family: Group
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

    _add_expense(
        db,
        group=family,
        payer=bob,
        category=_category(categories, "groceries"),
        amount_cents=8000,
        participants=[alice, bob],
        title="Weekly shop",
    )
    _add_expense(
        db,
        group=trip,
        payer=alice,
        category=_category(categories, "travel"),
        amount_cents=20000,
        participants=[alice, carol],
        title="Flights",
    )
    return World(alice=alice, bob=bob, carol=carol, family=family, trip=trip)


def _last_month() -> datetime:
    return add_months(start_of_month(utcnow()), -1) + timedelta(days=3)


def _two_months_ago() -> datetime:
    return add_months(start_of_month(utcnow()), -2) + timedelta(days=3)


def test_summary_is_empty_but_well_formed_for_a_new_account(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    client = api_client(make_user())

    body = client.get("/api/dashboard/summary").json()

    assert body == {
        "you_owe_cents": 0,
        "owed_to_you_cents": 0,
        "net_cents": 0,
        "total_spending_cents": 0,
        "your_paid_cents": 0,
        "your_share_cents": 0,
        "group_count": 0,
        "expense_count": 0,
        "currency": "RUB",
        "groups": [],
    }


def test_category_and_time_series_are_empty_for_a_new_account(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    client = api_client(make_user())

    assert client.get("/api/dashboard/spending-by-category").json() == {
        "total_cents": 0,
        "items": [],
    }
    assert client.get("/api/dashboard/spending-over-time").json() == {
        "currency": "RUB",
        "items": [],
    }


def test_summary_never_nets_debts_across_groups(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    body = api_client(world.alice).get("/api/dashboard/summary").json()

    assert body["you_owe_cents"] == 4000
    assert body["owed_to_you_cents"] == 10000
    assert body["net_cents"] == 6000
    assert body["group_count"] == 2
    assert body["expense_count"] == 2
    assert body["total_spending_cents"] == 28000
    assert body["currency"] == "RUB"

    nets = {group["group_id"]: group["net_cents"] for group in body["groups"]}
    assert nets == {str(world.family.id): -4000, str(world.trip.id): 10000}


def test_summary_reports_the_callers_own_paid_and_share(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    alice = api_client(world.alice).get("/api/dashboard/summary").json()
    assert alice["your_paid_cents"] == 20000
    assert alice["your_share_cents"] == 14000

    bob = api_client(world.bob).get("/api/dashboard/summary").json()
    assert bob["your_paid_cents"] == 8000
    assert bob["your_share_cents"] == 4000
    assert bob["group_count"] == 1
    assert bob["owed_to_you_cents"] == 4000
    assert bob["you_owe_cents"] == 0


def test_summary_group_id_scopes_to_one_group(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    body = api_client(world.alice).get(
        "/api/dashboard/summary", params={"group_id": str(world.family.id)}
    ).json()

    assert body["group_count"] == 1
    assert body["groups"] == [
        {
            "group_id": str(world.family.id),
            "name": "Family",
            "currency": "RUB",
            "net_cents": -4000,
            "total_spending_cents": 8000,
            "your_share_cents": 4000,
            "member_count": 2,
        }
    ]
    assert body["you_owe_cents"] == 4000
    assert body["owed_to_you_cents"] == 0
    assert body["net_cents"] == -4000
    assert body["total_spending_cents"] == 8000
    assert body["your_paid_cents"] == 0
    assert body["your_share_cents"] == 4000
    assert body["expense_count"] == 1


def test_summary_rejects_a_group_the_caller_does_not_belong_to(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    response = api_client(world.carol).get(
        "/api/dashboard/summary", params={"group_id": str(world.family.id)}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Вы не участник этой группы"}


def test_summary_reports_an_unknown_group_as_not_found(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    response = api_client(world.alice).get(
        "/api/dashboard/summary", params={"group_id": str(uuid.uuid4())}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Группа не найдена"}


def test_spending_by_category_aggregates_and_ranks(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    _add_expense(
        db,
        group=world.family,
        payer=world.alice,
        category=_category(categories, "groceries"),
        amount_cents=2000,
        participants=[world.alice, world.bob],
        title="Corner shop",
    )

    body = api_client(world.alice).get("/api/dashboard/spending-by-category").json()

    assert [item["slug"] for item in body["items"]] == ["travel", "groceries"]
    assert body["total_cents"] == 30000
    assert sum(item["amount_cents"] for item in body["items"]) == body["total_cents"]
    assert abs(sum(item["percentage"] for item in body["items"]) - 100) < 0.05

    travel, groceries = body["items"]
    assert travel["amount_cents"] == 20000
    assert travel["expense_count"] == 1
    assert travel["percentage"] == 66.67
    assert groceries["amount_cents"] == 10000
    assert groceries["expense_count"] == 2
    assert groceries["percentage"] == 33.33
    assert groceries["name"] == "Продукты"
    assert groceries["icon"] == "ShoppingCart"


def test_spending_over_time_zero_fills_the_gap_month(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    _add_expense(
        db,
        group=world.family,
        payer=world.bob,
        category=_category(categories, "food"),
        amount_cents=5000,
        participants=[world.alice, world.bob],
        occurred_at=_two_months_ago(),
        title="Dinner",
    )

    body = api_client(world.alice).get(
        "/api/dashboard/spending-over-time", params={"group_id": str(world.family.id)}
    ).json()

    assert [item["month"] for item in body["items"]] == [
        month_key(_two_months_ago()),
        month_key(_last_month()),
        month_key(utcnow()),
    ]
    assert [item["amount_cents"] for item in body["items"]] == [5000, 0, 8000]
    assert [item["your_share_cents"] for item in body["items"]] == [2500, 0, 4000]
    assert body["items"][1]["label"] != ""
    assert body["currency"] == "RUB"


def test_spending_over_time_keeps_only_the_last_two_years(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    _add_expense(
        db,
        group=world.family,
        payer=world.alice,
        category=_category(categories, "rent"),
        amount_cents=1000,
        participants=[world.alice, world.bob],
        occurred_at=add_months(start_of_month(utcnow()), -30) + timedelta(days=3),
        title="Ancient history",
    )

    body = api_client(world.alice).get(
        "/api/dashboard/spending-over-time", params={"group_id": str(world.family.id)}
    ).json()

    assert len(body["items"]) == 24
    assert body["items"][0]["month"] == month_key(add_months(start_of_month(utcnow()), -23))
    assert body["items"][-1]["month"] == month_key(utcnow())


def test_currency_follows_the_most_common_group_currency(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    """The dashboard reports the mode of the caller's group currencies.

    The API only ever accepts ``RUB``, so the odd row out is written straight to
    the database: the point is the selection rule, not the codes themselves.
    """
    user = make_user()
    group_factory(user, name="Flat", currency="RUB")
    group_factory(user, name="Trip", currency="RUB")
    group_factory(user, name="Office", currency="XXX")
    client = api_client(user)

    assert client.get("/api/dashboard/summary").json()["currency"] == "RUB"
    assert client.get("/api/dashboard/spending-over-time").json() == {
        "currency": "RUB",
        "items": [],
    }

    # And the mode really is counted rather than defaulted to the only code the
    # API lets through: for a user whose rows lean the other way it flips.
    other = make_user()
    group_factory(other, name="Office", currency="XXX")
    group_factory(other, name="Studio", currency="XXX")
    group_factory(other, name="Dacha", currency="RUB")

    assert api_client(other).get("/api/dashboard/summary").json()["currency"] == "XXX"


def test_period_filter_excludes_expenses_outside_the_window(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    _add_expense(
        db,
        group=world.family,
        payer=world.alice,
        category=_category(categories, "utilities"),
        amount_cents=6000,
        participants=[world.alice, world.bob],
        occurred_at=_last_month(),
        title="Electricity",
    )
    client = api_client(world.alice)
    scope = {"group_id": str(world.family.id)}

    everything = client.get("/api/dashboard/summary", params=scope).json()
    assert everything["total_spending_cents"] == 14000
    assert everything["expense_count"] == 2
    assert everything["your_paid_cents"] == 6000

    this_month = client.get(
        "/api/dashboard/summary", params={**scope, "period": "this_month"}
    ).json()
    assert this_month["total_spending_cents"] == 8000
    assert this_month["expense_count"] == 1
    assert this_month["your_paid_cents"] == 0
    # Balances stay all-time even under a period filter: Alice's 10.00 net debt in
    # this group is the same number whether or not last month is in the window.
    assert everything["you_owe_cents"] == 1000
    assert this_month["you_owe_cents"] == 1000

    last_month = client.get(
        "/api/dashboard/summary", params={**scope, "period": "last_month"}
    ).json()
    assert last_month["total_spending_cents"] == 6000

    categories_now = client.get(
        "/api/dashboard/spending-by-category", params={**scope, "period": "this_month"}
    ).json()
    assert [item["slug"] for item in categories_now["items"]] == ["groceries"]

    series = client.get(
        "/api/dashboard/spending-over-time", params={**scope, "period": "this_month"}
    ).json()
    assert [item["month"] for item in series["items"]] == [month_key(utcnow())]


def test_custom_period_requires_both_dates(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    client = api_client(world.alice)

    for path in DASHBOARD_PATHS:
        response = client.get(path, params={"period": "custom", "date_to": "2026-09-30"})
        assert response.status_code == 400
        assert response.json() == {"detail": "Для своего периода укажите обе даты"}


def test_custom_period_windows_the_data(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    occurred = _last_month()
    _add_expense(
        db,
        group=world.family,
        payer=world.alice,
        category=_category(categories, "utilities"),
        amount_cents=6000,
        participants=[world.alice, world.bob],
        occurred_at=occurred,
        title="Electricity",
    )

    body = api_client(world.alice).get(
        "/api/dashboard/summary",
        params={
            "group_id": str(world.family.id),
            "period": "custom",
            "date_from": occurred.date().isoformat(),
            "date_to": occurred.date().isoformat(),
        },
    ).json()

    assert body["total_spending_cents"] == 6000
    assert body["expense_count"] == 1


def test_unknown_period_is_rejected(
    api_client: Callable[[User], TestClient], world: World
) -> None:
    client = api_client(world.alice)

    for path in DASHBOARD_PATHS:
        response = client.get(path, params={"period": "since_forever"})
        assert response.status_code == 400
        assert response.json() == {"detail": "Неизвестный период"}


def test_soft_deleted_expenses_are_excluded_everywhere(
    api_client: Callable[[User], TestClient],
    db: Session,
    categories: list[Category],
    world: World,
) -> None:
    _add_expense(
        db,
        group=world.family,
        payer=world.alice,
        category=_category(categories, "health"),
        amount_cents=99900,
        participants=[world.alice, world.bob],
        deleted=True,
        title="Cancelled",
    )
    client = api_client(world.alice)

    summary = client.get("/api/dashboard/summary").json()
    assert summary["total_spending_cents"] == 28000
    assert summary["expense_count"] == 2
    assert summary["your_paid_cents"] == 20000
    assert summary["your_share_cents"] == 14000

    breakdown = client.get("/api/dashboard/spending-by-category").json()
    assert breakdown["total_cents"] == 28000
    assert "health" not in {item["slug"] for item in breakdown["items"]}

    series = client.get("/api/dashboard/spending-over-time").json()
    assert [item["amount_cents"] for item in series["items"]] == [28000]
    assert [item["your_share_cents"] for item in series["items"]] == [14000]


def test_dashboard_requires_authentication(anon_client: TestClient) -> None:
    for path in DASHBOARD_PATHS:
        response = anon_client.get(path)
        assert response.status_code == 401
        assert response.json() == {"detail": "Требуется вход"}

"""Expense and category endpoint tests.

Every creation path asserts the split invariant — the shares add up to the
expense total, exactly, with no cent invented or lost — because that is the one
property the whole balance engine downstream depends on.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity import Activity
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit
from app.models.group import Group
from app.models.user import User


def _category(categories: list[Category], slug: str) -> Category:
    return next(category for category in categories if category.slug == slug)


def _payload(
    *,
    category: Category,
    paid_by: User,
    participants: list[tuple[User, Any]],
    amount_cents: int = 12000,
    split_mode: str = "equal",
    title: str = "Dinner",
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


def _shares_by_user(body: dict[str, Any]) -> dict[str, int]:
    return {split["user_id"]: split["calculated_amount_cents"] for split in body["splits"]}


def _assert_balanced(body: dict[str, Any]) -> None:
    total = sum(split["calculated_amount_cents"] for split in body["splits"])
    assert total == body["amount_cents"]


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


# --------------------------------------------------------------------------- categories


def test_categories_are_listed_in_sort_order(
    api_client: Callable[[User], TestClient], people: tuple[User, User, User]
) -> None:
    client = api_client(people[0])
    response = client.get("/api/categories")
    assert response.status_code == 200

    body = response.json()
    assert len(body) == 12
    assert body[0]["slug"] == "food"
    assert body[0]["icon"] == "UtensilsCrossed"
    assert [item["sort_order"] for item in body] == list(range(1, 13))
    assert body[-1]["slug"] == "other"


def test_categories_require_authentication(anon_client: TestClient) -> None:
    response = anon_client.get("/api/categories")
    assert response.status_code == 401
    assert response.json() == {"detail": "Требуется вход"}


# ------------------------------------------------------------------------------- create


def test_equal_split_across_three_members(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None), (cleo, None)],
            amount_cents=12000,
            title="Weekly shop",
        ),
    )
    assert response.status_code == 201

    body = response.json()
    _assert_balanced(body)
    assert body["currency"] == "RUB"
    assert body["split_mode"] == "equal"
    assert body["category"]["slug"] == "food"
    assert body["creator"]["id"] == str(ada.id)
    assert body["payer"]["name"] == "Ada"
    assert len(body["splits"]) == 3
    assert {split["calculated_amount_cents"] for split in body["splits"]} == {4000}
    assert {split["input_value"] for split in body["splits"]} == {None}

    # The payer fronted the whole bill and owes only their own third.
    assert body["my_paid_cents"] == 12000
    assert body["my_share_cents"] == 4000
    assert body["my_net_cents"] == 8000

    ben_view = api_client(ben).get(f"/api/expenses/{body['id']}").json()
    assert ben_view["my_paid_cents"] == 0
    assert ben_view["my_share_cents"] == 4000
    assert ben_view["my_net_cents"] == -4000


def test_exact_split_stores_each_amount(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "6000"), (ben, 3600), (cleo, 2400.0)],
            split_mode="exact",
        ),
    )
    assert response.status_code == 201

    body = response.json()
    _assert_balanced(body)
    assert _shares_by_user(body) == {
        str(ada.id): 6000,
        str(ben.id): 3600,
        str(cleo.id): 2400,
    }
    assert {split["input_value"] for split in body["splits"]} == {"6000", "3600", "2400"}
    assert {split["split_mode"] for split in body["splits"]} == {"exact"}


def test_input_value_column_is_wide_enough_for_cents() -> None:
    """SQLite (the test DB) doesn't enforce ``NUMERIC`` precision, so the API-level
    large-amount test above can't reproduce the real Postgres overflow on its own.
    This pins the column definition itself: it must have enough integer digits to
    hold any ``BigInteger`` cents value, not just a percentage or a share count.
    """
    numeric = ExpenseSplit.__table__.c.input_value.type
    assert (numeric.precision, numeric.scale) == (25, 6)


def test_exact_split_supports_large_cent_amounts(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    """Regression: ``expense_splits.input_value`` used to be ``NUMERIC(12, 6)``,
    which only leaves 6 integer digits — an "exact" split stores the raw cents
    amount here, so anything at or above 1 000 000 cents overflowed the column
    and the request 500'd. See ``expense_splits.input_value`` migration
    ``0004_widen_input_value``.
    """
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            amount_cents=34_000_000,
            participants=[(ada, 34_000_000), (ben, 0), (cleo, 0)],
            split_mode="exact",
        ),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    _assert_balanced(body)
    assert _shares_by_user(body)[str(ada.id)] == 34_000_000
    assert {split["input_value"] for split in body["splits"] if split["user_id"] == str(ada.id)} == {
        "34000000"
    }


def test_exact_split_must_match_the_total(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "6000"), (ben, "3600"), (cleo, "1000")],
            split_mode="exact",
        ),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Сумма частей должна совпадать с общей суммой"}


def test_percentage_split(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "50"), (ben, "30"), (cleo, "20")],
            split_mode="percentage",
        ),
    )
    assert response.status_code == 201

    body = response.json()
    _assert_balanced(body)
    assert _shares_by_user(body) == {
        str(ada.id): 6000,
        str(ben.id): 3600,
        str(cleo.id): 2400,
    }
    assert sorted(split["input_value"] for split in body["splits"]) == ["20", "30", "50"]


def test_percentages_must_total_one_hundred(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "50"), (ben, "30"), (cleo, "10")],
            split_mode="percentage",
        ),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Сумма процентов должна быть 100%"}


def test_shares_split(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "2"), (ben, "1"), (cleo, "1")],
            split_mode="shares",
        ),
    )
    assert response.status_code == 201

    body = response.json()
    _assert_balanced(body)
    assert _shares_by_user(body) == {
        str(ada.id): 6000,
        str(ben.id): 3000,
        str(cleo.id): 3000,
    }
    assert sorted(split["input_value"] for split in body["splits"]) == ["1", "1", "2"]


def test_uneven_totals_still_balance(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    """A total that does not divide evenly still adds up to the cent."""
    ada, ben, cleo = people
    client = api_client(ada)

    for split_mode, values in (
        ("equal", [None, None, None]),
        ("shares", ["1", "1", "1"]),
        ("percentage", ["33.5", "33.5", "33"]),
    ):
        response = client.post(
            f"/api/groups/{group.id}/expenses",
            json=_payload(
                category=food,
                paid_by=ada,
                participants=list(zip((ada, ben, cleo), values, strict=True)),
                amount_cents=10001,
                split_mode=split_mode,
            ),
        )
        assert response.status_code == 201, response.json()
        _assert_balanced(response.json())


def test_amount_must_be_positive(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, _ = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None)],
            amount_cents=0,
        ),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "Сумма должна быть больше нуля"}


def test_participants_cannot_be_empty(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(category=food, paid_by=ada, participants=[]),
    )
    assert response.status_code == 422
    assert "хотя бы один участник" in response.json()["detail"]


def test_unknown_category_is_rejected(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    client = api_client(ada)

    body = _payload(category=food, paid_by=ada, participants=[(ada, None)])
    body["category_id"] = str(uuid.uuid4())
    response = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert response.status_code == 400
    assert response.json() == {"detail": "Категория не найдена"}


def test_payer_must_be_a_group_member(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, _ = people
    outsider = make_user(name="Dex")
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=outsider,
            participants=[(outsider, None), (ben, None)],
        ),
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Плательщик должен состоять в группе"}


def test_participants_must_be_group_members(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    outsider = make_user(name="Dex")
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (outsider, None)],
        ),
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Участники должны состоять в группе"}


def test_payer_must_be_a_participant(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)

    response = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ben, None), (cleo, None)],
        ),
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "Плательщик должен быть среди участников"}


def test_non_members_and_anonymous_callers_are_refused(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    outsider = make_user(name="Dex")
    body = _payload(category=food, paid_by=ada, participants=[(ada, None)])

    refused = api_client(outsider).post(f"/api/groups/{group.id}/expenses", json=body)
    assert refused.status_code == 403
    assert refused.json() == {"detail": "Вы не участник этой группы"}

    client = api_client(ada)
    # Drop the session cookie but keep a matching CSRF pair, so the request reaches
    # the endpoint and fails on authentication rather than on the CSRF check.
    client.cookies.delete(settings.cookie_name)
    anonymous = client.post(f"/api/groups/{group.id}/expenses", json=body)
    assert anonymous.status_code == 401
    assert anonymous.json() == {"detail": "Требуется вход"}

    assert client.get(f"/api/groups/{group.id}/expenses").status_code == 401


def test_unknown_group_is_not_found(
    api_client: Callable[[User], TestClient], people: tuple[User, User, User]
) -> None:
    client = api_client(people[0])
    response = client.get(f"/api/groups/{uuid.uuid4()}/expenses")
    assert response.status_code == 404
    assert response.json() == {"detail": "Группа не найдена"}


# --------------------------------------------------------------------------------- list


@pytest.fixture()
def seeded(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    categories: list[Category],
) -> dict[str, Any]:
    """Four expenses spread across payers, categories, dates and titles."""
    ada, ben, cleo = people
    client = api_client(ada)
    everyone = [(ada, None), (ben, None), (cleo, None)]
    specs = [
        ("Weekly shop", "groceries", ada, "2026-06-02T09:00:00Z", 6000, "big trolley"),
        ("Taxi to airport", "transport", ben, "2026-08-14T10:00:00Z", 4500, None),
        ("Cinema night", "entertainment", ada, "2026-08-31T23:00:00Z", 3000, None),
        ("Sushi taxi run", "food", cleo, "2026-09-01T12:00:00Z", 9000, None),
    ]
    created: list[dict[str, Any]] = []
    for title, slug, payer, occurred_at, amount, description in specs:
        response = client.post(
            f"/api/groups/{group.id}/expenses",
            json=_payload(
                category=_category(categories, slug),
                paid_by=payer,
                participants=everyone,
                amount_cents=amount,
                title=title,
                occurred_at=occurred_at,
                description=description,
            ),
        )
        assert response.status_code == 201, response.json()
        created.append(response.json())
    return {"client": client, "created": created}


def test_list_is_ordered_by_occurrence_descending(seeded: dict[str, Any], group: Group) -> None:
    body = seeded["client"].get(f"/api/groups/{group.id}/expenses").json()
    assert body["total"] == 4
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert [item["title"] for item in body["items"]] == [
        "Sushi taxi run",
        "Cinema night",
        "Taxi to airport",
        "Weekly shop",
    ]


def test_list_filters(
    seeded: dict[str, Any],
    group: Group,
    people: tuple[User, User, User],
    categories: list[Category],
) -> None:
    client = seeded["client"]
    ada, ben, _ = people
    url = f"/api/groups/{group.id}/expenses"

    by_category = client.get(
        url, params={"category_id": str(_category(categories, "transport").id)}
    ).json()
    assert [item["title"] for item in by_category["items"]] == ["Taxi to airport"]
    assert by_category["total"] == 1

    by_payer = client.get(url, params={"paid_by": str(ada.id)}).json()
    assert by_payer["total"] == 2
    assert {item["payer"]["id"] for item in by_payer["items"]} == {str(ada.id)}

    august = client.get(url, params={"date_from": "2026-08-01", "date_to": "2026-08-31"}).json()
    # date_to is inclusive, so the 23:00 expense on the 31st is in scope.
    assert [item["title"] for item in august["items"]] == ["Cinema night", "Taxi to airport"]
    assert august["total"] == 2

    from_only = client.get(url, params={"date_from": "2026-09-01"}).json()
    assert [item["title"] for item in from_only["items"]] == ["Sushi taxi run"]

    text = client.get(url, params={"q": "TAXI"}).json()
    assert text["total"] == 2
    assert {item["title"] for item in text["items"]} == {"Taxi to airport", "Sushi taxi run"}

    on_description = client.get(url, params={"q": "trolley"}).json()
    assert [item["title"] for item in on_description["items"]] == ["Weekly shop"]

    combined = client.get(url, params={"q": "taxi", "paid_by": str(ben.id)}).json()
    assert [item["title"] for item in combined["items"]] == ["Taxi to airport"]

    nothing = client.get(url, params={"q": "helicopter"}).json()
    assert nothing["items"] == []
    assert nothing["total"] == 0


def test_list_pagination_reports_the_unpaged_total(
    seeded: dict[str, Any], group: Group
) -> None:
    client = seeded["client"]
    url = f"/api/groups/{group.id}/expenses"

    first = client.get(url, params={"limit": 2, "offset": 0}).json()
    assert first["total"] == 4
    assert first["limit"] == 2
    assert first["offset"] == 0
    assert [item["title"] for item in first["items"]] == ["Sushi taxi run", "Cinema night"]

    last = client.get(url, params={"limit": 2, "offset": 3}).json()
    assert last["total"] == 4
    assert last["offset"] == 3
    assert [item["title"] for item in last["items"]] == ["Weekly shop"]

    beyond = client.get(url, params={"limit": 2, "offset": 10}).json()
    assert beyond["items"] == []
    assert beyond["total"] == 4


def test_get_one_expense_carries_the_full_breakdown(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ben,
            participants=[(ada, "2"), (ben, "1"), (cleo, "1")],
            split_mode="shares",
            title="Beach house",
        ),
    ).json()

    response = client.get(f"/api/expenses/{created['id']}")
    assert response.status_code == 200

    body = response.json()
    assert body["title"] == "Beach house"
    assert body["group_id"] == str(group.id)
    assert body["paid_by"] == str(ben.id)
    assert len(body["splits"]) == 3
    for split in body["splits"]:
        assert split["user"]["id"] == split["user_id"]
        assert split["user"]["name"] in {"Ada", "Ben", "Cleo"}
        assert split["user"]["email"].endswith("@example.com")
        assert split["split_mode"] == "shares"
    _assert_balanced(body)


def test_get_unknown_expense_is_not_found(
    api_client: Callable[[User], TestClient], people: tuple[User, User, User]
) -> None:
    client = api_client(people[0])
    response = client.get(f"/api/expenses/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Расход не найден"}


def test_expense_of_another_group_is_forbidden(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    created = api_client(ada).post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(category=food, paid_by=ada, participants=[(ada, None)]),
    ).json()

    outsider = make_user(name="Dex")
    response = api_client(outsider).get(f"/api/expenses/{created['id']}")
    assert response.status_code == 403
    assert response.json() == {"detail": "Вы не участник этой группы"}


# -------------------------------------------------------------------------------- patch


def test_patching_the_amount_recomputes_every_split(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None), (cleo, None)],
            amount_cents=12000,
        ),
    ).json()

    response = client.patch(f"/api/expenses/{created['id']}", json={"amount_cents": 9000})
    assert response.status_code == 200

    body = response.json()
    assert body["amount_cents"] == 9000
    assert body["split_mode"] == "equal"
    assert {split["calculated_amount_cents"] for split in body["splits"]} == {3000}
    _assert_balanced(body)


def test_patching_the_split_mode_rewrites_the_split_rows(
    api_client: Callable[[User], TestClient],
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None), (cleo, None)],
            amount_cents=12000,
        ),
    ).json()

    response = client.patch(
        f"/api/expenses/{created['id']}",
        json={
            "split_mode": "shares",
            "participants": [
                {"user_id": str(ada.id), "value": 2},
                {"user_id": str(ben.id), "value": 1},
                {"user_id": str(cleo.id), "value": 1},
            ],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["split_mode"] == "shares"
    assert _shares_by_user(body) == {
        str(ada.id): 6000,
        str(ben.id): 3000,
        str(cleo.id): 3000,
    }
    _assert_balanced(body)

    db.expire_all()
    rows = list(
        db.scalars(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == uuid.UUID(created["id"]))
        )
    )
    assert len(rows) == 3
    assert {row.split_mode for row in rows} == {"shares"}
    assert sum(row.calculated_amount_cents for row in rows) == 12000


def test_patching_the_title_leaves_the_splits_alone(
    api_client: Callable[[User], TestClient],
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, "2"), (ben, "1"), (cleo, "1")],
            split_mode="shares",
        ),
    ).json()
    expense_id = uuid.UUID(created["id"])
    before = {
        row.id: row.calculated_amount_cents
        for row in db.scalars(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
        )
    }

    response = client.patch(
        f"/api/expenses/{created['id']}",
        json={"title": "  Ski trip  ", "description": "lift passes"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["title"] == "Ski trip"
    assert body["description"] == "lift passes"
    assert body["split_mode"] == "shares"
    assert _shares_by_user(body) == _shares_by_user(created)

    db.expire_all()
    after = {
        row.id: row.calculated_amount_cents
        for row in db.scalars(
            select(ExpenseSplit).where(ExpenseSplit.expense_id == expense_id)
        )
    }
    # Same primary keys: the rows were never deleted and re-inserted.
    assert after == before


def test_patch_can_move_the_payer_and_clear_the_description(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
    categories: list[Category],
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None), (cleo, None)],
            description="split three ways",
        ),
    ).json()

    body = client.patch(
        f"/api/expenses/{created['id']}",
        json={
            "paid_by": str(ben.id),
            "description": None,
            "category_id": str(_category(categories, "travel").id),
            "occurred_at": "2026-07-04T08:30:00Z",
        },
    ).json()
    assert body["paid_by"] == str(ben.id)
    assert body["payer"]["name"] == "Ben"
    assert body["description"] is None
    assert body["category"]["slug"] == "travel"
    assert body["occurred_at"].startswith("2026-07-04T08:30:00")


def test_patch_rejects_a_payer_outside_the_participants(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(category=food, paid_by=ada, participants=[(ada, None), (ben, None)]),
    ).json()

    response = client.patch(f"/api/expenses/{created['id']}", json={"paid_by": str(cleo.id)})
    assert response.status_code == 400
    assert response.json() == {"detail": "Плательщик должен быть среди участников"}


def test_any_member_can_edit_and_delete(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    created = api_client(ada).post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None), (cleo, None)],
        ),
    ).json()

    # Cleo neither created the expense nor paid for it.
    cleo_client = api_client(cleo)
    edited = cleo_client.patch(f"/api/expenses/{created['id']}", json={"title": "Brunch"})
    assert edited.status_code == 200
    assert edited.json()["title"] == "Brunch"

    assert cleo_client.delete(f"/api/expenses/{created['id']}").status_code == 204


# ------------------------------------------------------------------------------- delete


def test_delete_is_a_soft_delete(
    api_client: Callable[[User], TestClient],
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    keep = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None)],
            title="Kept",
        ),
    ).json()
    doomed = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (cleo, None)],
            title="Doomed",
        ),
    ).json()

    response = client.delete(f"/api/expenses/{doomed['id']}")
    assert response.status_code == 204
    assert response.content == b""

    gone = client.get(f"/api/expenses/{doomed['id']}")
    assert gone.status_code == 404
    assert gone.json() == {"detail": "Расход не найден"}

    listing = client.get(f"/api/groups/{group.id}/expenses").json()
    assert [item["title"] for item in listing["items"]] == ["Kept"]
    assert listing["total"] == 1

    db.expire_all()
    row = db.scalar(select(Expense).where(Expense.id == uuid.UUID(doomed["id"])))
    assert row is not None
    assert row.deleted_at is not None
    assert row.title == "Doomed"
    assert len(row.splits) == 2

    assert client.get(f"/api/expenses/{keep['id']}").status_code == 200


def test_deleting_twice_is_not_found(
    api_client: Callable[[User], TestClient],
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada = people[0]
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(category=food, paid_by=ada, participants=[(ada, None)]),
    ).json()

    assert client.delete(f"/api/expenses/{created['id']}").status_code == 204
    second = client.delete(f"/api/expenses/{created['id']}")
    assert second.status_code == 404
    assert second.json() == {"detail": "Расход не найден"}


def test_the_activity_trail_records_each_change(
    api_client: Callable[[User], TestClient],
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, _ = people
    client = api_client(ada)
    created = client.post(
        f"/api/groups/{group.id}/expenses",
        json=_payload(
            category=food,
            paid_by=ada,
            participants=[(ada, None), (ben, None)],
            amount_cents=8000,
            title="Pizza",
        ),
    ).json()
    client.patch(f"/api/expenses/{created['id']}", json={"amount_cents": 9000})
    client.delete(f"/api/expenses/{created['id']}")

    db.expire_all()
    events = list(
        db.scalars(
            select(Activity)
            .where(Activity.entity_id == uuid.UUID(created["id"]))
            .order_by(Activity.created_at, Activity.id)
        )
    )
    assert [event.type for event in events] == [
        "expense_created",
        "expense_updated",
        "expense_deleted",
    ]
    assert all(event.actor_id == ada.id for event in events)
    assert events[0].meta == {
        "title": "Pizza",
        "amount_cents": 8000,
        "currency": "RUB",
        "category": "food",
    }
    assert events[1].meta["amount_cents"] == 9000


def test_every_split_set_adds_up_to_its_expense(
    api_client: Callable[[User], TestClient],
    db: Session,
    people: tuple[User, User, User],
    group: Group,
    food: Category,
) -> None:
    ada, ben, cleo = people
    client = api_client(ada)
    cases: list[tuple[int, str, list[Any]]] = [
        (100, "equal", [None, None, None]),
        (12000, "exact", ["4000", "4000", "4000"]),
        (7777, "percentage", ["50", "25", "25"]),
        (5, "shares", ["1", "1", "1"]),
        (999999, "shares", ["7", "2", "1"]),
    ]
    for amount, split_mode, values in cases:
        response = client.post(
            f"/api/groups/{group.id}/expenses",
            json=_payload(
                category=food,
                paid_by=ada,
                participants=list(zip((ada, ben, cleo), values, strict=True)),
                amount_cents=amount,
                split_mode=split_mode,
            ),
        )
        assert response.status_code == 201, response.json()
        _assert_balanced(response.json())

    db.expire_all()
    for expense in db.scalars(select(Expense).where(Expense.group_id == group.id)):
        assert (
            sum(split.calculated_amount_cents for split in expense.splits)
            == expense.amount_cents
        )

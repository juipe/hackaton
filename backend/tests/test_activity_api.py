"""Activity feed endpoint tests."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.activity import Activity, ActivityType
from app.models.category import Category
from app.models.group import Group
from app.models.user import User
from app.utils.time import utcnow


def seed_feed(
    db: Session,
    *,
    group: Group,
    actor: User,
    count: int,
    activity_type: str = ActivityType.EXPENSE_CREATED.value,
) -> list[Activity]:
    """Append ``count`` rows with strictly increasing timestamps, oldest first.

    The timestamps are explicit so ordering assertions never depend on how fast
    the rows happen to be inserted.
    """
    start = utcnow() - timedelta(minutes=count)
    activities = [
        Activity(
            group_id=group.id,
            actor_id=actor.id,
            type=activity_type,
            entity_id=None,
            meta={"index": index},
            created_at=start + timedelta(minutes=index),
        )
        for index in range(count)
    ]
    db.add_all(activities)
    db.commit()
    return activities


def create_group(client: TestClient, name: str = "Trip", currency: str = "RUB") -> dict:
    response = client.post("/api/groups", json={"name": name, "currency": currency})
    assert response.status_code == 201, response.text
    return response.json()


def test_new_group_has_a_single_group_created_entry(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    owner = make_user(name="Ada Byron")
    owner_id, owner_email = owner.id, owner.email
    client = api_client(owner)
    group = create_group(client, name="Lisbon trip")

    response = client.get(f"/api/groups/{group['id']}/activity")

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["type"] == "group_created"
    assert entry["group_id"] == group["id"]
    assert entry["group_name"] == "Lisbon trip"
    assert entry["actor_id"] == str(owner_id)
    assert entry["actor"] == {
        "id": str(owner_id),
        "name": "Ada Byron",
        "email": owner_email,
        "monthly_budget_cents": None,
    }
    assert isinstance(entry["meta"], dict)
    created_at = datetime.fromisoformat(entry["created_at"])
    assert created_at.utcoffset() == timedelta(0)


def test_group_feed_is_newest_first(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    group = group_factory(owner, name="Alpha")
    seed_feed(db, group=group, actor=owner, count=4)

    response = api_client(owner).get(f"/api/groups/{group.id}/activity")

    assert response.status_code == 200
    assert [entry["meta"]["index"] for entry in response.json()] == [3, 2, 1, 0]


def test_group_feed_paginates(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    group = group_factory(owner, name="Alpha")
    seed_feed(db, group=group, actor=owner, count=5)
    client = api_client(owner)

    first = client.get(f"/api/groups/{group.id}/activity", params={"limit": 2})
    second = client.get(
        f"/api/groups/{group.id}/activity", params={"limit": 2, "offset": 2}
    )
    tail = client.get(f"/api/groups/{group.id}/activity", params={"limit": 2, "offset": 4})
    past_end = client.get(
        f"/api/groups/{group.id}/activity", params={"limit": 2, "offset": 5}
    )

    assert [entry["meta"]["index"] for entry in first.json()] == [4, 3]
    assert [entry["meta"]["index"] for entry in second.json()] == [2, 1]
    assert [entry["meta"]["index"] for entry in tail.json()] == [0]
    assert past_end.json() == []


def test_group_feed_default_page_is_twenty(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    group = group_factory(owner, name="Alpha")
    seed_feed(db, group=group, actor=owner, count=25)

    response = api_client(owner).get(f"/api/groups/{group.id}/activity")

    assert len(response.json()) == 20


@pytest.mark.parametrize(
    "params",
    [{"limit": 101}, {"limit": 0}, {"limit": -1}, {"offset": -1}],
)
def test_out_of_range_pagination_is_rejected(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    params: dict[str, int],
) -> None:
    owner = make_user()
    group = group_factory(owner, name="Alpha")
    client = api_client(owner)

    assert client.get(f"/api/groups/{group.id}/activity", params=params).status_code == 422
    assert client.get("/api/activity", params=params).status_code == 422


def test_maximum_page_size_is_accepted(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    group = group_factory(owner, name="Alpha")

    response = api_client(owner).get(
        f"/api/groups/{group.id}/activity", params={"limit": 100}
    )

    assert response.status_code == 200


def test_cross_group_feed_covers_only_my_groups(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    alex = make_user(name="Alex")
    blair = make_user(name="Blair")
    mine = group_factory(alex, name="Alpha")
    shared = group_factory(blair, name="Beta", members=[alex])
    theirs = group_factory(blair, name="Gamma")
    seed_feed(db, group=mine, actor=alex, count=2)
    seed_feed(db, group=shared, actor=blair, count=2)
    seed_feed(db, group=theirs, actor=blair, count=3)
    mine_id, shared_id, theirs_id = str(mine.id), str(shared.id), str(theirs.id)

    response = api_client(alex).get("/api/activity", params={"limit": 50})

    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 4
    assert {entry["group_id"] for entry in entries} == {mine_id, shared_id}
    assert theirs_id not in {entry["group_id"] for entry in entries}
    names = {entry["group_id"]: entry["group_name"] for entry in entries}
    assert names == {mine_id: "Alpha", shared_id: "Beta"}


def test_cross_group_feed_is_newest_first_and_paginates(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    first_group = group_factory(owner, name="Alpha")
    second_group = group_factory(owner, name="Beta")
    seed_feed(db, group=first_group, actor=owner, count=2)
    later = utcnow() + timedelta(minutes=5)
    newest = Activity(
        group_id=second_group.id,
        actor_id=owner.id,
        type=ActivityType.PAYMENT_CREATED.value,
        meta={"index": 99},
        created_at=later,
    )
    db.add(newest)
    db.commit()
    client = api_client(owner)

    head = client.get("/api/activity", params={"limit": 1})
    rest = client.get("/api/activity", params={"limit": 5, "offset": 1})

    assert [entry["meta"]["index"] for entry in head.json()] == [99]
    assert [entry["meta"]["index"] for entry in rest.json()] == [1, 0]


def test_non_member_cannot_read_a_group_feed(
    db: Session,
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    owner = make_user()
    outsider = make_user()
    group = group_factory(owner, name="Alpha")
    seed_feed(db, group=group, actor=owner, count=1)

    response = api_client(outsider).get(f"/api/groups/{group.id}/activity")

    assert response.status_code == 403
    assert response.json() == {"detail": "Вы не участник этой группы"}


def test_unknown_group_feed_is_not_found(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    response = api_client(make_user()).get(f"/api/groups/{uuid.uuid4()}/activity")

    assert response.status_code == 404
    assert response.json() == {"detail": "Группа не найдена"}


def test_anonymous_callers_are_rejected(
    anon_client: TestClient,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
) -> None:
    group = group_factory(make_user(), name="Alpha")

    group_feed = anon_client.get(f"/api/groups/{group.id}/activity")
    my_feed = anon_client.get("/api/activity")

    assert group_feed.status_code == 401
    assert group_feed.json() == {"detail": "Требуется вход"}
    assert my_feed.status_code == 401


def test_expense_activity_carries_its_meta(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    categories: list[Category],
) -> None:
    owner = make_user(name="Iris")
    owner_id = owner.id
    groceries = next(category for category in categories if category.slug == "groceries")
    category_id = str(groceries.id)
    client = api_client(owner)
    group = create_group(client, name="Flatshare")

    created = client.post(
        f"/api/groups/{group['id']}/expenses",
        json={
            "title": "Weekly shop",
            "amount_cents": 4500,
            "category_id": category_id,
            "paid_by": str(owner_id),
            "occurred_at": "2026-08-14T10:00:00Z",
            "split_mode": "equal",
            "participants": [{"user_id": str(owner_id), "value": None}],
        },
    )
    assert created.status_code == 201, created.text

    entries = client.get(f"/api/groups/{group['id']}/activity").json()

    assert [entry["type"] for entry in entries] == ["expense_created", "group_created"]
    expense_entry = entries[0]
    assert expense_entry["entity_id"] == created.json()["id"]
    assert isinstance(expense_entry["meta"], dict)
    assert expense_entry["meta"]["title"] == "Weekly shop"
    assert expense_entry["meta"]["amount_cents"] == 4500

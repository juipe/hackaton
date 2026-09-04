"""End-to-end tests for the group and membership endpoints."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.user import User
from app.repositories import group_repo
from app.utils.time import utcnow

MakeUser = Callable[..., User]
ApiClient = Callable[[User], TestClient]
GroupFactory = Callable[..., Group]


def _with_csrf_only(client: TestClient) -> TestClient:
    """A client that passes the CSRF check but carries no session cookie.

    Without this an anonymous unsafe request is rejected by ``CsrfMiddleware``
    (403) before authentication ever runs, which would hide the 401.
    """
    token = "csrf-anonymous"
    client.cookies.set(settings.csrf_cookie_name, token)
    client.headers[settings.csrf_header_name] = token
    return client


def _record_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    participants: list[User],
    amount_cents: int,
    category: Category,
) -> Expense:
    """A settled-nothing expense split evenly, written straight to the ledger."""
    share = amount_cents // len(participants)
    expense = Expense(
        group_id=group.id,
        created_by=payer.id,
        title="Groceries",
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


def test_create_group_makes_the_caller_an_owner(
    api_client: ApiClient, make_user: MakeUser
) -> None:
    alex = make_user(name="Alex")
    client = api_client(alex)

    response = client.post(
        "/api/groups",
        json={"name": "Flat 3B", "description": "Rent and bills", "currency": "RUB"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Flat 3B"
    assert body["description"] == "Rent and bills"
    assert body["currency"] == "RUB"
    assert body["owner_id"] == str(alex.id)
    assert body["member_count"] == 1
    assert body["my_role"] == "owner"
    assert body["my_net_cents"] == 0
    assert body["total_spending_cents"] == 0

    members = client.get(f"/api/groups/{body['id']}/members").json()
    assert [member["user"]["id"] for member in members] == [str(alex.id)]
    assert members[0]["role"] == "owner"


def test_create_group_defaults_description_and_currency(
    api_client: ApiClient, make_user: MakeUser
) -> None:
    client = api_client(make_user())

    body = client.post("/api/groups", json={"name": "Ski trip"}).json()

    assert body["description"] is None
    assert body["currency"] == "RUB"


def test_list_groups_returns_only_my_groups(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    mine = group_factory(alex, name="Mine")
    shared = group_factory(blake, name="Shared", members=[alex])
    group_factory(blake, name="Theirs")

    body = api_client(alex).get("/api/groups").json()

    assert {group["id"] for group in body} == {str(mine.id), str(shared.id)}
    assert {group["name"] for group in body} == {"Mine", "Shared"}
    roles = {group["id"]: group["my_role"] for group in body}
    assert roles[str(mine.id)] == "owner"
    assert roles[str(shared.id)] == "member"


def test_get_group_requires_membership(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake])

    as_member = api_client(blake).get(f"/api/groups/{group.id}")
    assert as_member.status_code == 200
    assert as_member.json()["my_role"] == "member"
    assert as_member.json()["member_count"] == 2

    outsider = api_client(make_user())
    denied = outsider.get(f"/api/groups/{group.id}")
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Вы не участник этой группы"}

    missing = outsider.get(f"/api/groups/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Группа не найдена"}


def test_owner_can_update_the_group_but_a_member_cannot(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake], description="Rent")

    updated = api_client(alex).patch(
        f"/api/groups/{group.id}",
        json={"name": "Villa", "description": "Summer house", "currency": "rub"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Villa"
    assert updated.json()["description"] == "Summer house"
    assert updated.json()["currency"] == "RUB"

    denied = api_client(blake).patch(f"/api/groups/{group.id}", json={"name": "Nope"})
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Это может сделать только владелец группы"}
    assert api_client(blake).get(f"/api/groups/{group.id}").json()["name"] == "Villa"


def test_patch_distinguishes_an_explicit_null_from_an_omitted_key(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    group = group_factory(alex, name="Flat 3B", description="Rent and bills")
    client = api_client(alex)

    kept = client.patch(f"/api/groups/{group.id}", json={"name": "Flat 4B"})
    assert kept.status_code == 200
    assert kept.json()["description"] == "Rent and bills"

    cleared = client.patch(f"/api/groups/{group.id}", json={"description": None})
    assert cleared.status_code == 200
    assert cleared.json()["description"] is None
    assert cleared.json()["name"] == "Flat 4B"


def test_currency_is_upper_cased_and_only_the_rouble_is_accepted(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    client = api_client(alex)

    created = client.post("/api/groups", json={"name": "Road trip", "currency": "rub"})
    assert created.status_code == 201
    assert created.json()["currency"] == "RUB"

    refused = client.post("/api/groups", json={"name": "Road trip", "currency": "usd"})
    assert refused.status_code == 422
    assert refused.json() == {"detail": "Сервис работает только с рублями"}

    too_short = client.post("/api/groups", json={"name": "Road trip", "currency": "us"})
    assert too_short.status_code == 422

    group = group_factory(alex)
    assert client.patch(f"/api/groups/{group.id}", json={"currency": "us"}).status_code == 422
    patched = client.patch(f"/api/groups/{group.id}", json={"currency": "eur"})
    assert patched.status_code == 422
    assert patched.json() == {"detail": "Сервис работает только с рублями"}


def test_owner_can_delete_the_group_but_a_member_cannot(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake])

    denied = api_client(blake).delete(f"/api/groups/{group.id}")
    assert denied.status_code == 403
    assert denied.json() == {"detail": "Это может сделать только владелец группы"}

    owner = api_client(alex)
    assert owner.delete(f"/api/groups/{group.id}").status_code == 204
    assert owner.get(f"/api/groups/{group.id}").status_code == 404
    assert owner.get("/api/groups").json() == []


def test_members_are_listed_in_join_order(
    db: Session,
    api_client: ApiClient,
    make_user: MakeUser,
    group_factory: GroupFactory,
) -> None:
    alex = make_user(name="Alex")
    blake = make_user(name="Blake")
    casey = make_user(name="Casey")
    group = group_factory(alex, name="Flat 3B", members=[blake, casey])

    # Pin the timestamps so the ordering assertion cannot depend on clock resolution.
    base = utcnow()
    for offset, user in enumerate((alex, blake, casey)):
        membership = group_repo.get_membership(db, group.id, user.id)
        assert membership is not None
        membership.joined_at = base + timedelta(minutes=offset)
    db.commit()

    body = api_client(casey).get(f"/api/groups/{group.id}/members").json()

    assert [member["user"]["name"] for member in body] == ["Alex", "Blake", "Casey"]
    assert [member["role"] for member in body] == ["owner", "member", "member"]
    assert body[0]["user"]["email"] == alex.email
    assert "password_hash" not in body[0]["user"]


def test_a_member_can_leave_the_group(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake])

    leaving = api_client(blake)
    assert leaving.delete(f"/api/groups/{group.id}/members/{blake.id}").status_code == 204
    assert leaving.get(f"/api/groups/{group.id}").status_code == 403

    remaining = api_client(alex).get(f"/api/groups/{group.id}").json()
    assert remaining["member_count"] == 1


def test_a_member_cannot_remove_someone_else(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    casey = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake, casey])

    response = api_client(blake).delete(f"/api/groups/{group.id}/members/{casey.id}")

    assert response.status_code == 403
    assert response.json() == {"detail": "Удалять участников может только владелец группы"}
    assert api_client(alex).get(f"/api/groups/{group.id}").json()["member_count"] == 3


def test_the_owner_cannot_be_removed(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake])

    response = api_client(alex).delete(f"/api/groups/{group.id}/members/{alex.id}")

    assert response.status_code == 400
    assert response.json() == {"detail": "Владельца группы удалить нельзя"}


def test_a_member_with_an_open_balance_cannot_be_removed(
    db: Session,
    api_client: ApiClient,
    make_user: MakeUser,
    group_factory: GroupFactory,
    categories: list[Category],
) -> None:
    alex = make_user()
    blake = make_user()
    group = group_factory(alex, name="Flat 3B", members=[blake])
    _record_expense(
        db,
        group=group,
        payer=alex,
        participants=[alex, blake],
        amount_cents=1000,
        category=categories[0],
    )

    response = api_client(alex).delete(f"/api/groups/{group.id}/members/{blake.id}")

    assert response.status_code == 400
    assert response.json() == {"detail": "Перед удалением участника закройте его баланс"}
    assert api_client(alex).get(f"/api/groups/{group.id}").json()["member_count"] == 2


def test_removing_someone_who_is_not_a_member_is_a_404(
    api_client: ApiClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    group = group_factory(alex, name="Flat 3B")

    response = api_client(alex).delete(f"/api/groups/{group.id}/members/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Участник не найден"}


def test_anonymous_callers_are_rejected(
    anon_client: TestClient, make_user: MakeUser, group_factory: GroupFactory
) -> None:
    alex = make_user()
    group = group_factory(alex, name="Flat 3B")

    unauthenticated = anon_client.get("/api/groups")
    assert unauthenticated.status_code == 401
    assert unauthenticated.json() == {"detail": "Требуется вход"}
    assert anon_client.get(f"/api/groups/{group.id}").status_code == 401
    assert anon_client.get(f"/api/groups/{group.id}/members").status_code == 401

    client = _with_csrf_only(anon_client)
    assert client.post("/api/groups", json={"name": "Nope"}).status_code == 401
    assert client.patch(f"/api/groups/{group.id}", json={"name": "Nope"}).status_code == 401
    assert client.delete(f"/api/groups/{group.id}").status_code == 401
    assert client.delete(f"/api/groups/{group.id}/members/{alex.id}").status_code == 401

"""HTTP tests for the balances and simplify-debts endpoints.

Ledger rows are written straight through the ORM rather than through the expense
and payment endpoints: these tests are about the balance surface, and building the
fixtures at model level keeps them independent of the split-mode validation rules.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.activity import Activity, ActivityType
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.payment import Payment
from app.models.user import User
from app.utils.time import utcnow


def _record_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    category: Category,
    amount_cents: int,
    splits: list[tuple[User, int]],
    title: str = "Dinner",
) -> Expense:
    expense = Expense(
        group_id=group.id,
        created_by=payer.id,
        title=title,
        amount_cents=amount_cents,
        currency=group.currency,
        category_id=category.id,
        paid_by=payer.id,
        split_mode=SplitMode.EQUAL.value,
        occurred_at=utcnow(),
    )
    db.add(expense)
    db.flush()
    for user, share_cents in splits:
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=user.id,
                split_mode=SplitMode.EQUAL.value,
                calculated_amount_cents=share_cents,
            )
        )
    db.commit()
    return expense


def _record_payment(
    db: Session,
    *,
    group: Group,
    from_user: User,
    to_user: User,
    amount_cents: int,
) -> Payment:
    payment = Payment(
        group_id=group.id,
        from_user_id=from_user.id,
        to_user_id=to_user.id,
        amount_cents=amount_cents,
        currency=group.currency,
        paid_at=utcnow(),
    )
    db.add(payment)
    db.commit()
    return payment


def _nets(payload: dict) -> dict[str, int]:
    return {entry["user_id"]: entry["net_cents"] for entry in payload["balances"]}


@pytest.fixture()
def trio(make_user: Callable[..., User]) -> tuple[User, User, User]:
    alice = make_user(email="alice@skladchina.test", name="Alice Nowak")
    bob = make_user(email="bob@skladchina.test", name="Bob Reyes")
    carol = make_user(email="carol@skladchina.test", name="Carol Fisher")
    return alice, bob, carol


@pytest.fixture()
def trio_group(
    trio: tuple[User, User, User], group_factory: Callable[..., Group]
) -> Group:
    alice, bob, carol = trio
    return group_factory(alice, name="Flat 12", currency="RUB", members=[bob, carol])


def test_empty_group_balances_are_all_zero(
    api_client: Callable[[User], TestClient],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, bob, carol = trio
    response = api_client(alice).get(f"/api/groups/{trio_group.id}/balances")

    assert response.status_code == 200
    payload = response.json()
    assert payload["group_id"] == str(trio_group.id)
    assert payload["currency"] == "RUB"
    assert payload["total_spending_cents"] == 0
    assert payload["pairwise"] == []
    assert payload["simplified"] == []

    assert {entry["user_id"] for entry in payload["balances"]} == {
        str(alice.id),
        str(bob.id),
        str(carol.id),
    }
    for entry in payload["balances"]:
        assert (entry["paid_cents"], entry["owed_cents"], entry["net_cents"]) == (0, 0, 0)

    assert payload["me"]["user_id"] == str(alice.id)
    assert payload["me"]["paid_cents"] == 0
    assert payload["me"]["owed_cents"] == 0
    assert payload["me"]["net_cents"] == 0


def test_three_way_expense_nets_and_pairwise_edges(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, bob, carol = trio
    _record_expense(
        db,
        group=trio_group,
        payer=alice,
        category=categories[0],
        amount_cents=12000,
        splits=[(alice, 4000), (bob, 4000), (carol, 4000)],
    )

    payload = api_client(alice).get(f"/api/groups/{trio_group.id}/balances").json()

    assert payload["total_spending_cents"] == 12000
    assert _nets(payload) == {
        str(alice.id): 8000,
        str(bob.id): -4000,
        str(carol.id): -4000,
    }

    alice_entry = next(e for e in payload["balances"] if e["user_id"] == str(alice.id))
    assert alice_entry["paid_cents"] == 12000
    assert alice_entry["owed_cents"] == 4000

    assert len(payload["pairwise"]) == 2
    assert {edge["to_user_id"] for edge in payload["pairwise"]} == {str(alice.id)}
    assert {edge["from_user_id"] for edge in payload["pairwise"]} == {
        str(bob.id),
        str(carol.id),
    }
    assert [edge["amount_cents"] for edge in payload["pairwise"]] == [4000, 4000]

    assert payload["me"] == alice_entry

    # `me` follows the caller, not the group.
    bob_payload = api_client(bob).get(f"/api/groups/{trio_group.id}/balances").json()
    assert bob_payload["me"]["user_id"] == str(bob.id)
    assert bob_payload["me"]["net_cents"] == -4000
    assert bob_payload["me"]["paid_cents"] == 0
    assert bob_payload["me"]["owed_cents"] == 4000


def test_balances_and_transfers_embed_user_objects(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, bob, carol = trio
    _record_expense(
        db,
        group=trio_group,
        payer=alice,
        category=categories[0],
        amount_cents=12000,
        splits=[(alice, 4000), (bob, 4000), (carol, 4000)],
    )
    expected = {
        str(user.id): {"id": str(user.id), "name": user.name, "email": user.email}
        for user in (alice, bob, carol)
    }

    payload = api_client(alice).get(f"/api/groups/{trio_group.id}/balances").json()

    for entry in [*payload["balances"], payload["me"]]:
        assert entry["user"] == expected[entry["user_id"]]

    transfers = [*payload["pairwise"], *payload["simplified"]]
    assert transfers
    for transfer in transfers:
        assert transfer["from_user"] == expected[transfer["from_user_id"]]
        assert transfer["to_user"] == expected[transfer["to_user_id"]]


def test_nets_always_sum_to_zero(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, bob, carol = trio
    _record_expense(
        db,
        group=trio_group,
        payer=alice,
        category=categories[0],
        amount_cents=12000,
        splits=[(alice, 4000), (bob, 4000), (carol, 4000)],
    )
    _record_expense(
        db,
        group=trio_group,
        payer=bob,
        category=categories[1],
        amount_cents=5001,
        splits=[(alice, 1667), (bob, 1667), (carol, 1667)],
        title="Groceries",
    )
    _record_payment(db, group=trio_group, from_user=carol, to_user=alice, amount_cents=1500)

    payload = api_client(carol).get(f"/api/groups/{trio_group.id}/balances").json()

    assert sum(_nets(payload).values()) == 0
    assert payload["total_spending_cents"] == 17001


def test_balances_reject_non_members_and_unknown_groups(
    api_client: Callable[[User], TestClient],
    make_user: Callable[..., User],
    trio_group: Group,
) -> None:
    outsider = make_user(name="Dana Outsider")

    forbidden = api_client(outsider).get(f"/api/groups/{trio_group.id}/balances")
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Вы не участник этой группы"

    missing = api_client(outsider).get(f"/api/groups/{uuid.uuid4()}/balances")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Группа не найдена"


def test_balances_reject_anonymous_callers(
    anon_client: TestClient, trio_group: Group
) -> None:
    response = anon_client.get(f"/api/groups/{trio_group.id}/balances")

    assert response.status_code == 401
    assert response.json()["detail"] == "Требуется вход"


def _build_debt_chain(
    db: Session, group: Group, categories: list[Category], trio: tuple[User, User, User]
) -> None:
    """A owes B 50.00 and B owes C 50.00 — two pairwise edges, one after simplifying."""
    alice, bob, carol = trio
    _record_expense(
        db,
        group=group,
        payer=bob,
        category=categories[0],
        amount_cents=10000,
        splits=[(alice, 5000), (bob, 5000)],
        title="Taxi",
    )
    _record_expense(
        db,
        group=group,
        payer=carol,
        category=categories[0],
        amount_cents=10000,
        splits=[(bob, 5000), (carol, 5000)],
        title="Tickets",
    )


def test_simplify_collapses_a_debt_chain(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, _bob, carol = trio
    _build_debt_chain(db, trio_group, categories, trio)

    response = api_client(alice).post(
        f"/api/groups/{trio_group.id}/simplify-debts", json={"record_activity": False}
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["current_transfer_count"] == 2
    assert payload["simplified_transfer_count"] == 1
    assert len(payload["current_transfers"]) == 2
    assert len(payload["transfers"]) == 1

    transfer = payload["transfers"][0]
    assert transfer["from_user_id"] == str(alice.id)
    assert transfer["to_user_id"] == str(carol.id)
    assert transfer["amount_cents"] == 5000
    assert transfer["from_user"]["email"] == alice.email
    assert transfer["to_user"]["name"] == carol.name


def test_simplify_never_changes_the_balances(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, _bob, _carol = trio
    _build_debt_chain(db, trio_group, categories, trio)
    client = api_client(alice)
    balances_url = f"/api/groups/{trio_group.id}/balances"

    before = client.get(balances_url).json()
    client.post(f"/api/groups/{trio_group.id}/simplify-debts", json={"record_activity": True})
    after = client.get(balances_url).json()

    assert _nets(after) == _nets(before)
    assert after["pairwise"] == before["pairwise"]
    assert after["total_spending_cents"] == before["total_spending_cents"]


def test_simplify_records_an_activity_only_when_asked(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, _bob, _carol = trio
    _build_debt_chain(db, trio_group, categories, trio)
    client = api_client(alice)
    url = f"/api/groups/{trio_group.id}/simplify-debts"

    def _count() -> int:
        return int(
            db.scalar(
                select(func.count())
                .select_from(Activity)
                .where(Activity.type == ActivityType.DEBT_SIMPLIFIED.value)
            )
            or 0
        )

    assert client.post(url, json={}).status_code == 200
    assert _count() == 0

    assert client.post(url, json={"record_activity": True}).status_code == 200
    assert _count() == 1

    activity = db.scalar(
        select(Activity).where(Activity.type == ActivityType.DEBT_SIMPLIFIED.value)
    )
    assert activity is not None
    assert activity.group_id == trio_group.id
    assert activity.actor_id == alice.id
    assert activity.meta == {"before": 2, "after": 1}


def test_simplify_requires_the_csrf_header(
    api_client: Callable[[User], TestClient],
    trio: tuple[User, User, User],
    trio_group: Group,
) -> None:
    alice, _bob, _carol = trio
    client = api_client(alice)
    client.headers.pop(settings.csrf_header_name, None)

    response = client.post(
        f"/api/groups/{trio_group.id}/simplify-debts", json={"record_activity": False}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Неверный CSRF-токен"

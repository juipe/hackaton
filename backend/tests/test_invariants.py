"""Cross-cutting financial invariants, proved over the real HTTP API.

The unit suites already pin the split engine and the balance ledger down. This
file is deliberately one level up: every mutation goes through a route, and every
assertion is made against either the database rows the API wrote or the JSON it
handed back. Nothing here calls a service directly, because the properties being
protected are properties of the *system* — a route that forgets to commit, a
serializer that turns cents into a float, or a soft delete that leaves the ledger
untouched would all pass the unit tests and still lose someone's money.

The five properties, in the order the tests assert them:

1. ``sum(expense_splits.calculated_amount_cents) == expenses.amount_cents`` for
   every expense ever written, in every split mode, read back from the database.
2. ``sum(net_cents) == 0`` for a group after every single mutation.
3. A payment moves exactly two nets, by exactly its amount.
4. Simplification preserves every net exactly and never adds transfers.
5. No monetary value crosses the wire as a float.

:func:`check_invariants` bundles 1, 2, 4 and 5 into one call so a test can re-run
the whole battery after each mutation for the cost of a single line.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit
from app.models.user import User
from app.utils.time import utcnow

Participants = list[tuple[User, Any]]

#: A ``*_cents`` key whose JSON value carries a decimal point or an exponent.
DECIMAL_CENTS = re.compile(r'"\w*_cents"\s*:\s*-?\d+(?:\.\d+|[eE][-+]?\d+)')


@dataclass(frozen=True)
class Scene:
    """A signed-in, fully populated group plus the handles to keep mutating it."""

    db: Session
    sign_in: Callable[[User], TestClient]
    group_id: str
    users: tuple[User, User, User, User]
    category_id: str

    @property
    def owner(self) -> User:
        return self.users[0]

    def api(self, user: User | None = None) -> TestClient:
        """The shared client, signed in as ``user`` (the owner by default)."""
        return self.sign_in(user or self.owner)


# --------------------------------------------------------------------------- #
# JSON walking
# --------------------------------------------------------------------------- #


def iter_cents_fields(node: Any, path: str = "") -> Iterator[tuple[str, Any]]:
    """Yield ``(json_path, value)`` for every key ending in ``_cents``, at any depth."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}"
            if key.endswith("_cents"):
                yield child, value
            yield from iter_cents_fields(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from iter_cents_fields(value, f"{path}[{index}]")


def assert_cents_are_ints(payload: Any, label: str) -> int:
    """Every ``*_cents`` value in ``payload`` must be a plain ``int``. Returns the count.

    ``type(...) is int`` rather than ``isinstance``: ``bool`` is a subclass of ``int``
    and ``true`` is not a monetary value either.
    """
    checked = 0
    for path, value in iter_cents_fields(payload):
        assert type(value) is int, (
            f"{label}{path} is {type(value).__name__} ({value!r}), not an int"
        )
        checked += 1
    return checked


# --------------------------------------------------------------------------- #
# Database-side reads
# --------------------------------------------------------------------------- #


def assert_splits_add_up(db: Session) -> int:
    """Invariant 1, read straight off the tables. Returns the number of expenses seen.

    Soft-deleted expenses are included on purpose: a deleted row must stop counting
    towards balances, but its stored shares must still be internally consistent —
    an undelete or an audit read cannot be allowed to resurrect broken arithmetic.
    """
    db.expire_all()

    unsplit = list(db.scalars(select(Expense.id).where(~Expense.splits.any())))
    assert not unsplit, f"expenses stored without any split rows: {unsplit}"

    rows = db.execute(
        select(
            Expense.id,
            Expense.amount_cents,
            func.sum(ExpenseSplit.calculated_amount_cents),
        )
        .join(ExpenseSplit, ExpenseSplit.expense_id == Expense.id)
        .group_by(Expense.id, Expense.amount_cents)
    ).all()

    for expense_id, amount_cents, total_cents in rows:
        assert type(amount_cents) is int, (
            f"expense {expense_id} stores amount_cents as {type(amount_cents).__name__}"
        )
        assert total_cents == amount_cents, (
            f"expense {expense_id}: splits total {total_cents}, amount is {amount_cents}"
        )

    for split_id, share_cents in db.execute(
        select(ExpenseSplit.id, ExpenseSplit.calculated_amount_cents)
    ):
        assert type(share_cents) is int, (
            f"split {split_id} stores calculated_amount_cents as "
            f"{type(share_cents).__name__}"
        )

    return len(rows)


def db_split_total(db: Session, expense_id: str) -> int:
    db.expire_all()
    total = db.scalar(
        select(func.sum(ExpenseSplit.calculated_amount_cents)).where(
            ExpenseSplit.expense_id == uuid.UUID(expense_id)
        )
    )
    return int(total or 0)


def db_expense_amount(db: Session, expense_id: str) -> int:
    db.expire_all()
    amount = db.scalar(
        select(Expense.amount_cents).where(Expense.id == uuid.UUID(expense_id))
    )
    assert amount is not None
    return int(amount)


# --------------------------------------------------------------------------- #
# API-side reads
# --------------------------------------------------------------------------- #


def fetch_balances(scene: Scene, viewer: User | None = None) -> dict[str, Any]:
    response = scene.api(viewer).get(f"/api/groups/{scene.group_id}/balances")
    assert response.status_code == 200, response.text
    return response.json()


def nets_of(balances: dict[str, Any]) -> dict[str, int]:
    return {row["user_id"]: row["net_cents"] for row in balances["balances"]}


def rebuild_nets(transfers: list[dict[str, Any]]) -> dict[str, int]:
    """Fold a transfer graph back into ``{user_id: net_cents}``.

    A creditor is on the receiving end of what they are owed and a debtor on the
    paying end of what they owe, so incoming minus outgoing reproduces the net.
    """
    totals: dict[str, int] = {}
    for transfer in transfers:
        amount = transfer["amount_cents"]
        assert amount > 0, f"transfer with non-positive amount: {transfer}"
        totals[transfer["from_user_id"]] = (
            totals.get(transfer["from_user_id"], 0) - amount
        )
        totals[transfer["to_user_id"]] = totals.get(transfer["to_user_id"], 0) + amount
    return totals


def check_invariants(scene: Scene, viewer: User | None = None) -> dict[str, int]:
    """Re-run the whole battery and return the current nets, keyed by user id string."""
    assert_splits_add_up(scene.db)

    balances = fetch_balances(scene, viewer)
    assert assert_cents_are_ints(balances, "balances") > 0

    for row in balances["balances"]:
        assert row["paid_cents"] - row["owed_cents"] == row["net_cents"], (
            f"net_cents is not paid - owed for user {row['user_id']}: {row}"
        )

    nets = nets_of(balances)
    assert sum(nets.values()) == 0, f"group nets do not cancel out: {nets}"

    for graph in ("pairwise", "simplified"):
        rebuilt = rebuild_nets(balances[graph])
        assert set(rebuilt) <= set(nets), f"{graph} names a user with no balance row"
        for user_id, net_cents in nets.items():
            assert rebuilt.get(user_id, 0) == net_cents, (
                f"{graph} graph does not reproduce the net of {user_id}: "
                f"{rebuilt.get(user_id, 0)} != {net_cents}"
            )

    assert len(balances["simplified"]) <= len(balances["pairwise"])
    return nets


# --------------------------------------------------------------------------- #
# API-side writes
# --------------------------------------------------------------------------- #


def expense_body(
    *,
    category_id: str,
    paid_by: User,
    split_mode: str,
    amount_cents: int,
    participants: Participants,
    title: str = "Shared cost",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "title": title,
        "amount_cents": amount_cents,
        "category_id": category_id,
        "paid_by": str(paid_by.id),
        "split_mode": split_mode,
        "participants": [
            {"user_id": str(user.id), "value": value} for user, value in participants
        ],
    }
    if occurred_at is not None:
        body["occurred_at"] = occurred_at
    return body


def create_expense(
    scene: Scene,
    *,
    paid_by: User,
    split_mode: str,
    amount_cents: int,
    participants: Participants,
    title: str = "Shared cost",
    occurred_at: str | None = None,
) -> dict[str, Any]:
    response = scene.api().post(
        f"/api/groups/{scene.group_id}/expenses",
        json=expense_body(
            category_id=scene.category_id,
            paid_by=paid_by,
            split_mode=split_mode,
            amount_cents=amount_cents,
            participants=participants,
            title=title,
            occurred_at=occurred_at,
        ),
    )
    assert response.status_code == 201, response.text
    return response.json()


def patch_expense(scene: Scene, expense_id: str, body: dict[str, Any]) -> dict[str, Any]:
    response = scene.api().patch(f"/api/expenses/{expense_id}", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def record_payment(
    scene: Scene, *, sender: User, receiver: User, amount_cents: int
) -> dict[str, Any]:
    response = scene.api().post(
        f"/api/groups/{scene.group_id}/payments",
        json={
            "from_user_id": str(sender.id),
            "to_user_id": str(receiver.id),
            "amount_cents": amount_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture()
def people(make_user: Callable[..., User]) -> tuple[User, User, User, User]:
    return (
        make_user(name="Ada", email="ada@example.com"),
        make_user(name="Bo", email="bo@example.com"),
        make_user(name="Cai", email="cai@example.com"),
        make_user(name="Dev", email="dev@example.com"),
    )


@pytest.fixture()
def empty_scene(
    db: Session,
    api_client: Callable[[User], TestClient],
    categories: list[Category],
    people: tuple[User, User, User, User],
) -> Scene:
    """Four users in one group, assembled entirely through invite links."""
    owner, *invitees = people
    response = api_client(owner).post(
        "/api/groups", json={"name": "Alpine trip", "currency": "RUB"}
    )
    assert response.status_code == 201, response.text
    group_id = response.json()["id"]

    for invitee in invitees:
        created = api_client(owner).post(
            f"/api/groups/{group_id}/invites", json={"email": invitee.email}
        )
        assert created.status_code == 201, created.text
        accepted = api_client(invitee).post(
            f"/api/invites/{created.json()['token']}/accept"
        )
        assert accepted.status_code == 200, accepted.text

    api_client(owner)
    category_id = str(next(c for c in categories if c.slug == "travel").id)
    return Scene(
        db=db,
        sign_in=api_client,
        group_id=group_id,
        users=(owner, invitees[0], invitees[1], invitees[2]),
        category_id=category_id,
    )


@pytest.fixture()
def scene(empty_scene: Scene) -> Scene:
    """The messy realistic ledger: four payers, all four split modes, two settle-ups.

    Every amount is picked so the division does not come out even — 10.00 across
    three, 100.01 across seven shares, thirds as repeating percentages — which is
    exactly where a naive implementation invents or loses a cent.
    """
    ada, bo, cai, dev = empty_scene.users
    recent = (utcnow() - timedelta(days=40)).isoformat()

    create_expense(
        empty_scene,
        title="Taxi from the station",
        paid_by=ada,
        split_mode="equal",
        amount_cents=1000,
        participants=[(ada, None), (bo, None), (cai, None)],
        occurred_at=recent,
    )
    create_expense(
        empty_scene,
        title="Cabin deposit",
        paid_by=bo,
        split_mode="shares",
        amount_cents=10001,
        participants=[(ada, "1"), (bo, "2"), (cai, "3"), (dev, "1")],
        occurred_at=recent,
    )
    create_expense(
        empty_scene,
        title="Lift passes",
        paid_by=cai,
        split_mode="percentage",
        amount_cents=10001,
        participants=[(ada, "33.333333"), (cai, "33.333333"), (dev, "33.333334")],
    )
    create_expense(
        empty_scene,
        title="Groceries run",
        paid_by=dev,
        split_mode="exact",
        amount_cents=7777,
        participants=[(ada, "1111"), (bo, "2222"), (cai, "2222"), (dev, "2222")],
    )
    create_expense(
        empty_scene,
        title="Dinner in town",
        paid_by=ada,
        split_mode="equal",
        amount_cents=4500,
        participants=[(ada, None), (bo, None), (cai, None), (dev, None)],
    )

    record_payment(empty_scene, sender=bo, receiver=ada, amount_cents=1200)
    record_payment(empty_scene, sender=dev, receiver=cai, amount_cents=777)
    return empty_scene


# --------------------------------------------------------------------------- #
# 1. Splits always add up to the expense
# --------------------------------------------------------------------------- #


ROUNDING_CASES: list[tuple[str, int, list[str | None]]] = [
    # 10.00 across three: 334 / 333 / 333.
    ("equal", 1000, [None, None, None]),
    # 100.01 across four.
    ("equal", 10001, [None, None, None, None]),
    # 100.01 across seven shares.
    ("shares", 10001, ["1", "2", "3", "1"]),
    # A single cent that only one of three people can receive.
    ("shares", 1, ["1", "1", "1"]),
    # Thirds as repeating percentages.
    ("percentage", 10001, ["33.333333", "33.333333", "33.333334"]),
    # Fractional percentages against an odd total.
    ("percentage", 333, ["16.5", "16.5", "33.5", "33.5"]),
    # Exact cents, which must be stored verbatim.
    ("exact", 7777, ["1111", "2222", "2222", "2222"]),
]


@pytest.mark.parametrize(("split_mode", "amount_cents", "values"), ROUNDING_CASES)
def test_splits_total_the_expense_amount_in_every_mode(
    empty_scene: Scene, split_mode: str, amount_cents: int, values: list[str | None]
) -> None:
    payer = empty_scene.owner
    participants: Participants = list(zip(empty_scene.users[: len(values)], values, strict=True))

    created = create_expense(
        empty_scene,
        paid_by=payer,
        split_mode=split_mode,
        amount_cents=amount_cents,
        participants=participants,
    )

    # The response is only a witness; the database is the claim being checked.
    assert db_split_total(empty_scene.db, created["id"]) == amount_cents
    assert db_expense_amount(empty_scene.db, created["id"]) == amount_cents
    assert assert_splits_add_up(empty_scene.db) == 1
    check_invariants(empty_scene)


def test_every_stored_expense_balances_across_the_whole_scenario(scene: Scene) -> None:
    assert assert_splits_add_up(scene.db) == 5


# --------------------------------------------------------------------------- #
# 2. Group nets always cancel out
# --------------------------------------------------------------------------- #


def test_nets_cancel_after_every_kind_of_mutation(scene: Scene) -> None:
    ada, bo, cai, dev = scene.users
    check_invariants(scene)

    created = create_expense(
        scene,
        title="Ski rental",
        paid_by=cai,
        split_mode="shares",
        amount_cents=8999,
        participants=[(ada, "2"), (bo, "1"), (cai, "3"), (dev, "1")],
    )
    check_invariants(scene)

    record_payment(scene, sender=ada, receiver=cai, amount_cents=1499)
    check_invariants(scene)

    patch_expense(
        scene,
        created["id"],
        {
            "amount_cents": 9001,
            "split_mode": "percentage",
            "participants": [
                {"user_id": str(ada.id), "value": "25"},
                {"user_id": str(bo.id), "value": "25"},
                {"user_id": str(cai.id), "value": "25"},
                {"user_id": str(dev.id), "value": "25"},
            ],
        },
    )
    check_invariants(scene)

    deleted = scene.api().delete(f"/api/expenses/{created['id']}")
    assert deleted.status_code == 204, deleted.text
    check_invariants(scene)


def test_nets_cancel_for_every_viewer(scene: Scene) -> None:
    """The ledger is a property of the group, not of whoever is looking at it."""
    reference = check_invariants(scene, viewer=scene.owner)
    for member in scene.users[1:]:
        assert check_invariants(scene, viewer=member) == reference


# --------------------------------------------------------------------------- #
# 3. A payment moves exactly two nets
# --------------------------------------------------------------------------- #


def test_payment_moves_exactly_the_two_nets_involved(scene: Scene) -> None:
    ada, bo, cai, dev = scene.users
    before = check_invariants(scene)
    amount_cents = 2345

    record_payment(scene, sender=bo, receiver=dev, amount_cents=amount_cents)
    after = check_invariants(scene)

    assert set(after) == set(before)
    # The sender has now paid more, so their net rises by the full amount; the
    # receiver has been made whole by the same amount.
    assert after[str(bo.id)] == before[str(bo.id)] + amount_cents
    assert after[str(dev.id)] == before[str(dev.id)] - amount_cents
    for untouched in (ada, cai):
        assert after[str(untouched.id)] == before[str(untouched.id)]


def test_payment_leaves_total_spending_alone(scene: Scene) -> None:
    """A settle-up moves money between people; it is not group spending."""
    before = fetch_balances(scene)["total_spending_cents"]
    record_payment(scene, sender=scene.users[1], receiver=scene.users[0], amount_cents=500)
    assert fetch_balances(scene)["total_spending_cents"] == before


# --------------------------------------------------------------------------- #
# 4. Simplification preserves every net
# --------------------------------------------------------------------------- #


def simplify(scene: Scene) -> dict[str, Any]:
    response = scene.api().post(
        f"/api/groups/{scene.group_id}/simplify-debts", json={"record_activity": False}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_simplify_preserves_every_net_and_never_adds_transfers(scene: Scene) -> None:
    nets = check_invariants(scene)
    indebted = [net for net in nets.values() if net != 0]
    assert len(nets) == 4
    assert len(indebted) >= 4, f"the fixture is not messy enough: {nets}"

    preview = simplify(scene)
    assert assert_cents_are_ints(preview, "simplify") > 0

    assert preview["current_transfer_count"] == len(preview["current_transfers"])
    assert preview["simplified_transfer_count"] == len(preview["transfers"])
    assert preview["simplified_transfer_count"] <= preview["current_transfer_count"]
    # Greedy matching settles at least one party per transfer.
    assert preview["simplified_transfer_count"] <= len(indebted) - 1

    for graph in ("current_transfers", "transfers"):
        rebuilt = rebuild_nets(preview[graph])
        for user_id, net_cents in nets.items():
            assert rebuilt.get(user_id, 0) == net_cents, (
                f"{graph} changed the net of {user_id}"
            )

    # The endpoint is a recommendation engine: reading it must not write anything.
    assert check_invariants(scene) == nets


def test_simplify_actually_shortens_a_messy_web(scene: Scene) -> None:
    preview = simplify(scene)
    assert preview["current_transfer_count"] > preview["simplified_transfer_count"]


def test_paying_the_simplified_plan_settles_the_group(scene: Scene) -> None:
    """The strongest form of "nets are preserved": the plan really does clear them."""
    for transfer in simplify(scene)["transfers"]:
        sender = next(u for u in scene.users if str(u.id) == transfer["from_user_id"])
        receiver = next(u for u in scene.users if str(u.id) == transfer["to_user_id"])
        record_payment(
            scene,
            sender=sender,
            receiver=receiver,
            amount_cents=transfer["amount_cents"],
        )

    nets = check_invariants(scene)
    assert set(nets.values()) == {0}
    # Nobody has anything left to pay. The raw pairwise view may still hold a
    # circular residual (A owes B owes C owes A) — that is what simplification is
    # for — but the minimised plan is what the user acts on, and it is empty.
    assert fetch_balances(scene)["simplified"] == []


# --------------------------------------------------------------------------- #
# 5. No money crosses the wire as a float
# --------------------------------------------------------------------------- #


def test_no_money_field_in_any_response_is_a_float(scene: Scene) -> None:
    expenses = scene.api().get(f"/api/groups/{scene.group_id}/expenses")
    assert expenses.status_code == 200, expenses.text
    first_expense_id = expenses.json()["items"][0]["id"]

    payloads: list[tuple[str, Any]] = [
        ("groups", scene.api().get("/api/groups")),
        ("group", scene.api().get(f"/api/groups/{scene.group_id}")),
        ("expenses", expenses),
        ("expense", scene.api().get(f"/api/expenses/{first_expense_id}")),
        ("balances", scene.api().get(f"/api/groups/{scene.group_id}/balances")),
        ("payments", scene.api().get(f"/api/groups/{scene.group_id}/payments")),
        ("summary", scene.api().get("/api/dashboard/summary")),
        ("by-category", scene.api().get("/api/dashboard/spending-by-category")),
        ("over-time", scene.api().get("/api/dashboard/spending-over-time")),
        (
            "scoped-summary",
            scene.api().get(f"/api/dashboard/summary?group_id={scene.group_id}"),
        ),
        ("activity", scene.api().get(f"/api/groups/{scene.group_id}/activity")),
    ]

    checked = 0
    for label, response in payloads:
        assert response.status_code == 200, f"{label}: {response.text}"
        found = assert_cents_are_ints(response.json(), label)
        assert found > 0, f"{label} carries no monetary field — the walk proved nothing"
        checked += found

    # A rough floor, so a payload silently losing its money fields cannot pass.
    assert checked > 50


def test_raw_response_body_never_carries_a_decimal_amount(scene: Scene) -> None:
    """Guards the bytes, not the parse.

    ``12000.0`` and ``1.2e4`` both survive ``json.loads`` as floats, so the walk in
    the previous test would catch them — but only for money that is currently
    non-zero. This looks at the serialized body directly.
    """
    for path in (
        f"/api/groups/{scene.group_id}/balances",
        f"/api/groups/{scene.group_id}/expenses",
        f"/api/groups/{scene.group_id}/payments",
        "/api/dashboard/summary",
        "/api/dashboard/spending-over-time",
    ):
        response = scene.api().get(path)
        assert response.status_code == 200, response.text
        offender = DECIMAL_CENTS.search(response.text)
        assert offender is None, f"{path} serialized money as {offender.group(0)!r}"


# --------------------------------------------------------------------------- #
# 6. Changing split mode keeps the invariants
# --------------------------------------------------------------------------- #


MODE_SWITCHES: list[tuple[str, str, list[str | None], int]] = [
    ("equal", "shares", ["3", "1", "1", "2"], 10001),
    ("shares", "percentage", ["33.333333", "33.333333", "33.333334", None], 999),
    ("percentage", "exact", ["2500", "2500", "2500", "2501"], 10001),
    ("exact", "equal", [None, None, None, None], 1000),
]


@pytest.mark.parametrize(
    ("from_mode", "to_mode", "values", "amount_cents"), MODE_SWITCHES
)
def test_switching_split_mode_keeps_the_splits_and_the_nets_honest(
    empty_scene: Scene,
    from_mode: str,
    to_mode: str,
    values: list[str | None],
    amount_cents: int,
) -> None:
    ada, bo, cai, dev = empty_scene.users
    seed_values: dict[str, list[str | None]] = {
        "equal": [None, None, None, None],
        "shares": ["1", "1", "1", "1"],
        "percentage": ["25", "25", "25", "25"],
        "exact": ["3000", "3000", "3000", "3000"],
    }
    created = create_expense(
        empty_scene,
        title="Chalet week",
        paid_by=ada,
        split_mode=from_mode,
        amount_cents=12000,
        participants=list(zip(empty_scene.users, seed_values[from_mode], strict=True)),
    )
    check_invariants(empty_scene)

    # Outside "equal", a None value means "this person drops out of the split" —
    # the other half of a real mode switch, where the participant set moves too.
    participants = [
        {"user_id": str(user.id), "value": value}
        for user, value in zip(empty_scene.users, values, strict=True)
        if value is not None or to_mode == "equal"
    ]
    updated = patch_expense(
        empty_scene,
        created["id"],
        {
            "amount_cents": amount_cents,
            "split_mode": to_mode,
            "participants": participants,
        },
    )

    assert updated["split_mode"] == to_mode
    assert updated["amount_cents"] == amount_cents
    assert db_expense_amount(empty_scene.db, created["id"]) == amount_cents
    assert db_split_total(empty_scene.db, created["id"]) == amount_cents
    assert assert_splits_add_up(empty_scene.db) == 1
    check_invariants(empty_scene)


def test_editing_an_expense_inside_a_busy_ledger_keeps_the_nets_cancelling(
    scene: Scene,
) -> None:
    ada, bo, cai, dev = scene.users
    expenses = scene.api().get(f"/api/groups/{scene.group_id}/expenses")
    assert expenses.status_code == 200, expenses.text
    target = next(
        item for item in expenses.json()["items"] if item["split_mode"] == "equal"
    )

    before = check_invariants(scene)
    updated = patch_expense(
        scene,
        target["id"],
        {
            "amount_cents": 5555,
            "paid_by": str(dev.id),
            "split_mode": "exact",
            "participants": [
                {"user_id": str(ada.id), "value": "1111"},
                {"user_id": str(bo.id), "value": "1111"},
                {"user_id": str(cai.id), "value": "1111"},
                {"user_id": str(dev.id), "value": "2222"},
            ],
        },
    )
    after = check_invariants(scene)

    assert db_split_total(scene.db, target["id"]) == 5555
    assert updated["paid_by"] == str(dev.id)
    assert after != before, "the edit should have moved the ledger"
    assert sum(after.values()) == 0


# --------------------------------------------------------------------------- #
# 7. A soft-deleted expense stops counting
# --------------------------------------------------------------------------- #


def test_soft_deleted_expense_stops_contributing_to_balances(scene: Scene) -> None:
    ada, bo, cai, dev = scene.users
    before = check_invariants(scene)
    before_spending = fetch_balances(scene)["total_spending_cents"]

    doomed = create_expense(
        scene,
        title="Cancelled tour",
        paid_by=bo,
        split_mode="shares",
        amount_cents=6001,
        participants=[(ada, "1"), (bo, "1"), (cai, "1"), (dev, "3")],
    )
    with_expense = check_invariants(scene)
    assert with_expense != before
    assert fetch_balances(scene)["total_spending_cents"] == before_spending + 6001

    response = scene.api().delete(f"/api/expenses/{doomed['id']}")
    assert response.status_code == 204, response.text

    after = check_invariants(scene)
    assert after == before, "a deleted expense still moves the ledger"
    assert fetch_balances(scene)["total_spending_cents"] == before_spending

    # Gone from the API surface, still intact in the table.
    assert scene.api().get(f"/api/expenses/{doomed['id']}").status_code == 404
    listing = scene.api().get(f"/api/groups/{scene.group_id}/expenses")
    assert doomed["id"] not in {item["id"] for item in listing.json()["items"]}
    assert db_split_total(scene.db, doomed["id"]) == 6001


def test_deleting_every_expense_and_settling_leaves_a_zero_ledger(scene: Scene) -> None:
    listing = scene.api().get(f"/api/groups/{scene.group_id}/expenses")
    assert listing.status_code == 200, listing.text
    for item in listing.json()["items"]:
        response = scene.api().delete(f"/api/expenses/{item['id']}")
        assert response.status_code == 204, response.text
        check_invariants(scene)

    balances = fetch_balances(scene)
    assert balances["total_spending_cents"] == 0
    # The two settle-ups outlive the expenses, so the nets are non-zero but still
    # cancel — deleting spending must not quietly erase money that changed hands.
    nets = nets_of(balances)
    assert sum(nets.values()) == 0
    assert any(net != 0 for net in nets.values())

    for transfer in simplify(scene)["transfers"]:
        sender = next(u for u in scene.users if str(u.id) == transfer["from_user_id"])
        receiver = next(u for u in scene.users if str(u.id) == transfer["to_user_id"])
        record_payment(
            scene, sender=sender, receiver=receiver, amount_cents=transfer["amount_cents"]
        )

    assert set(check_invariants(scene).values()) == {0}

"""Ledger tests for :mod:`app.services.balance_service`.

Rows are inserted directly rather than through the expense/payment services so the
balance engine is tested against the data shapes it actually reads, independently of
whatever validation sits above it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Sequence

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.member import GroupMember
from app.models.payment import Payment
from app.models.user import User
from app.services.balance_service import (
    GroupBalances,
    compute_group_balances,
    compute_user_group_nets,
    compute_user_totals,
    group_spending_totals,
)
from app.utils.time import utcnow


def _add_expense(
    db: Session,
    *,
    group: Group,
    payer: User,
    amount_cents: int,
    shares: Sequence[tuple[User, int]],
    category: Category,
    title: str = "Expense",
    deleted: bool = False,
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
        deleted_at=utcnow() if deleted else None,
    )
    db.add(expense)
    db.flush()
    for user, share_cents in shares:
        db.add(
            ExpenseSplit(
                expense_id=expense.id,
                user_id=user.id,
                split_mode=SplitMode.EQUAL.value,
                input_value=None,
                calculated_amount_cents=share_cents,
            )
        )
    db.commit()
    return expense


def _add_payment(
    db: Session,
    *,
    group: Group,
    sender: User,
    receiver: User,
    amount_cents: int,
) -> Payment:
    payment = Payment(
        group_id=group.id,
        from_user_id=sender.id,
        to_user_id=receiver.id,
        amount_cents=amount_cents,
        currency=group.currency,
        paid_at=utcnow(),
    )
    db.add(payment)
    db.commit()
    return payment


def _nets(result: GroupBalances) -> dict[uuid.UUID, int]:
    return {balance.user_id: balance.net_cents for balance in result.balances}


def _edges(result: GroupBalances) -> set[tuple[uuid.UUID, uuid.UUID, int]]:
    return {
        (transfer.from_user_id, transfer.to_user_id, transfer.amount_cents)
        for transfer in result.pairwise
    }


def _assert_balanced(result: GroupBalances) -> None:
    """The invariant that makes every other number trustworthy."""
    assert sum(balance.net_cents for balance in result.balances) == 0
    assert all(
        balance.net_cents == balance.paid_cents - balance.owed_cents
        for balance in result.balances
    )


def test_equal_three_way_expense_matches_the_contract_example(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(owner=alice, members=(bob, carol))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=12000,
        shares=[(alice, 4000), (bob, 4000), (carol, 4000)],
        category=categories[0],
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: 8000, bob.id: -4000, carol.id: -4000}
    by_user = {balance.user_id: balance for balance in result.balances}
    assert (by_user[alice.id].paid_cents, by_user[alice.id].owed_cents) == (12000, 4000)
    assert (by_user[bob.id].paid_cents, by_user[bob.id].owed_cents) == (0, 4000)
    assert _edges(result) == {(bob.id, alice.id, 4000), (carol.id, alice.id, 4000)}
    assert {
        (transfer.from_user_id, transfer.to_user_id, transfer.amount_cents)
        for transfer in result.simplified
    } == {(bob.id, alice.id, 4000), (carol.id, alice.id, 4000)}
    assert result.total_spending_cents == 12000


def test_payer_is_not_always_a_participant(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(owner=alice, members=(bob, carol))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=9000,
        shares=[(bob, 4500), (carol, 4500)],
        category=categories[1],
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: 9000, bob.id: -4500, carol.id: -4500}
    by_user = {balance.user_id: balance for balance in result.balances}
    assert by_user[alice.id].owed_cents == 0
    assert _edges(result) == {(bob.id, alice.id, 4500), (carol.id, alice.id, 4500)}


def test_exact_payment_clears_the_debt(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=6000,
        shares=[(alice, 3000), (bob, 3000)],
        category=categories[0],
    )
    _add_payment(db, group=group, sender=bob, receiver=alice, amount_cents=3000)

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: 0, bob.id: 0}
    assert result.pairwise == []
    assert result.simplified == []
    # The payment settles the ledger without erasing the spending history.
    assert result.total_spending_cents == 6000


def test_overpayment_flips_the_pairwise_edge(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=6000,
        shares=[(alice, 3000), (bob, 3000)],
        category=categories[0],
    )
    _add_payment(db, group=group, sender=bob, receiver=alice, amount_cents=5000)

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: -2000, bob.id: 2000}
    assert _edges(result) == {(alice.id, bob.id, 2000)}
    assert [
        (transfer.from_user_id, transfer.to_user_id, transfer.amount_cents)
        for transfer in result.simplified
    ] == [(alice.id, bob.id, 2000)]


def test_soft_deleted_expenses_leave_no_trace(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=4000,
        shares=[(alice, 2000), (bob, 2000)],
        category=categories[0],
        title="Live",
    )
    _add_expense(
        db,
        group=group,
        payer=bob,
        amount_cents=100000,
        shares=[(alice, 50000), (bob, 50000)],
        category=categories[0],
        title="Deleted",
        deleted=True,
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: 2000, bob.id: -2000}
    assert _edges(result) == {(bob.id, alice.id, 2000)}
    assert result.total_spending_cents == 4000
    assert group_spending_totals(db, [group.id]) == {group.id: 4000}


def test_opposite_expenses_net_into_a_single_edge(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=5000,
        shares=[(alice, 2500), (bob, 2500)],
        category=categories[0],
    )
    _add_expense(
        db,
        group=group,
        payer=bob,
        amount_cents=3000,
        shares=[(alice, 1500), (bob, 1500)],
        category=categories[1],
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert _nets(result) == {alice.id: 1000, bob.id: -1000}
    assert len(result.pairwise) == 1
    assert _edges(result) == {(bob.id, alice.id, 1000)}
    assert result.total_spending_cents == 8000


def test_members_without_ledger_entries_are_still_listed(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    dana = make_user(name="Dana")
    group = group_factory(owner=alice, members=(bob, dana))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=4000,
        shares=[(alice, 2000), (bob, 2000)],
        category=categories[0],
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert [balance.user_id for balance in result.balances] == [alice.id, bob.id, dana.id]
    dana_balance = result.balances[2]
    assert (dana_balance.paid_cents, dana_balance.owed_cents, dana_balance.net_cents) == (0, 0, 0)
    assert all(dana.id not in (edge[0], edge[1]) for edge in _edges(result))


def test_pairwise_is_ordered_by_descending_amount(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    group = group_factory(owner=alice, members=(bob, carol))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=30000,
        shares=[(alice, 10000), (bob, 5000), (carol, 15000)],
        category=categories[0],
    )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert [
        (transfer.from_user_id, transfer.to_user_id, transfer.amount_cents)
        for transfer in result.pairwise
    ] == [(carol.id, alice.id, 15000), (bob.id, alice.id, 5000)]


def test_a_departed_member_still_balances_the_ledger(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=4000,
        shares=[(alice, 2000), (bob, 2000)],
        category=categories[0],
    )
    membership = db.scalars(
        select(GroupMember).where(
            GroupMember.group_id == group.id, GroupMember.user_id == bob.id
        )
    ).one()
    db.delete(membership)
    db.commit()

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert [balance.user_id for balance in result.balances] == [alice.id, bob.id]
    assert _nets(result) == {alice.id: 2000, bob.id: -2000}


def test_splits_that_do_not_cover_the_expense_are_rejected(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    _add_expense(
        db,
        group=group,
        payer=alice,
        amount_cents=10000,
        shares=[(alice, 2500), (bob, 2500)],
        category=categories[0],
    )

    with pytest.raises(AssertionError, match="не сходится в ноль"):
        compute_group_balances(db, group.id)


def test_total_spending_tracks_every_live_expense(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    group = group_factory(owner=alice, members=(bob,))
    amounts = (1234, 5678, 9012)
    for index, amount in enumerate(amounts):
        payer, other = (alice, bob) if index % 2 == 0 else (bob, alice)
        half = amount // 2
        _add_expense(
            db,
            group=group,
            payer=payer,
            amount_cents=amount,
            shares=[(payer, amount - half), (other, half)],
            category=categories[index],
        )

    result = compute_group_balances(db, group.id)

    _assert_balanced(result)
    assert result.total_spending_cents == sum(amounts)


def test_user_group_nets_cover_every_membership(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    carol = make_user(name="Carol")
    with_ledger = group_factory(owner=alice, name="Trip", members=(bob,))
    empty = group_factory(owner=alice, name="Flat", members=(carol,))
    stranger_group = group_factory(owner=carol, name="Others")
    _add_expense(
        db,
        group=with_ledger,
        payer=alice,
        amount_cents=7000,
        shares=[(alice, 3500), (bob, 3500)],
        category=categories[0],
    )
    _add_payment(db, group=with_ledger, sender=bob, receiver=alice, amount_cents=1000)

    nets = compute_user_group_nets(db, alice.id)

    assert set(nets) == {with_ledger.id, empty.id}
    assert stranger_group.id not in nets
    assert nets[with_ledger.id] == 2500
    assert nets[empty.id] == 0
    assert compute_user_group_nets(db, bob.id) == {with_ledger.id: -2500}


def test_user_totals_aggregate_across_groups(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    trip = group_factory(owner=alice, name="Trip", members=(bob,))
    flat = group_factory(owner=alice, name="Flat", members=(bob,))
    _add_expense(
        db,
        group=trip,
        payer=alice,
        amount_cents=8000,
        shares=[(alice, 4000), (bob, 4000)],
        category=categories[0],
    )
    _add_expense(
        db,
        group=flat,
        payer=bob,
        amount_cents=5000,
        shares=[(alice, 2500), (bob, 2500)],
        category=categories[1],
    )
    _add_payment(db, group=flat, sender=alice, receiver=bob, amount_cents=500)

    totals = compute_user_totals(db, alice.id)

    assert totals.user_id == alice.id
    assert totals.paid_cents == 8000 + 500
    assert totals.owed_cents == 4000 + 2500
    assert totals.net_cents == 2000
    assert compute_user_totals(db, alice.id, [trip.id]).net_cents == 4000
    assert compute_user_totals(db, alice.id, []).net_cents == 0


def test_group_spending_totals_answers_for_many_groups_at_once(
    db: Session,
    make_user: Callable[..., User],
    group_factory: Callable[..., Group],
    categories: list[Category],
) -> None:
    alice = make_user(name="Alice")
    bob = make_user(name="Bob")
    trip = group_factory(owner=alice, name="Trip", members=(bob,))
    flat = group_factory(owner=alice, name="Flat", members=(bob,))
    quiet = group_factory(owner=alice, name="Quiet", members=(bob,))
    _add_expense(
        db,
        group=trip,
        payer=alice,
        amount_cents=2500,
        shares=[(alice, 2500)],
        category=categories[0],
    )
    _add_expense(
        db,
        group=trip,
        payer=bob,
        amount_cents=1500,
        shares=[(bob, 1500)],
        category=categories[0],
    )
    _add_expense(
        db,
        group=flat,
        payer=alice,
        amount_cents=9900,
        shares=[(alice, 9900)],
        category=categories[1],
    )
    _add_expense(
        db,
        group=quiet,
        payer=alice,
        amount_cents=4200,
        shares=[(alice, 4200)],
        category=categories[1],
        deleted=True,
    )

    totals = group_spending_totals(db, [trip.id, flat.id, quiet.id])

    assert totals == {trip.id: 4000, flat.id: 9900, quiet.id: 0}
    assert group_spending_totals(db, []) == {}
    unknown = uuid.uuid4()
    assert group_spending_totals(db, [unknown]) == {unknown: 0}

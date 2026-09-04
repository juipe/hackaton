"""Balance ledger.

Turns a group's expense and payment history into three views of the same numbers:

* ``balances``  — one net position per user (``paid_cents - owed_cents``),
* ``pairwise``  — the literal "who owes whom" graph, netted per pair,
* ``simplified`` — the minimal set of transfers that settles the group, produced by
  :mod:`app.services.simplify_service`.

Two rules hold everywhere in this module:

* Soft-deleted expenses (``deleted_at IS NOT NULL``) are excluded from every
  aggregate. A deleted expense must stop influencing balances immediately.
* A payment is ledger-symmetric with an expense: the sender has *paid* more, the
  receiver has *received* more, so the sum of all net positions stays zero. That
  invariant is asserted in :func:`compute_group_balances` — if it ever breaks, the
  split data is corrupt and every downstream number would be a quiet lie.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseSplit
from app.models.member import GroupMember
from app.models.payment import Payment


@dataclass(frozen=True)
class UserBalance:
    """One user's position in a group.

    ``paid_cents`` counts money that left their pocket (expenses they paid plus
    payments they sent); ``owed_cents`` counts money that was spent on them or
    handed to them (their split shares plus payments they received).
    A positive ``net_cents`` means the group owes them.
    """

    user_id: uuid.UUID
    paid_cents: int
    owed_cents: int
    net_cents: int


@dataclass(frozen=True)
class DebtTransfer:
    """A directed "``from_user`` should hand ``amount_cents`` to ``to_user``" edge."""

    from_user_id: uuid.UUID
    to_user_id: uuid.UUID
    amount_cents: int


@dataclass(frozen=True)
class GroupBalances:
    group_id: uuid.UUID
    balances: list[UserBalance]
    pairwise: list[DebtTransfer]
    simplified: list[DebtTransfer]
    total_spending_cents: int


def compute_group_balances(db: Session, group_id: uuid.UUID) -> GroupBalances:
    """Full balance picture for one group."""
    paid = _expense_paid_totals(db, group_id)
    owed = _split_owed_totals(db, group_id)
    payments = _payment_totals(db, group_id)
    edges = _expense_debt_edges(db, group_id)

    for from_user_id, to_user_id, amount_cents in payments:
        paid[from_user_id] = paid.get(from_user_id, 0) + amount_cents
        owed[to_user_id] = owed.get(to_user_id, 0) + amount_cents

    member_ids = _member_ids(db, group_id)
    # Someone who left the group can still be part of its history. They are kept in
    # the ledger (after the current members) so the zero-sum invariant holds.
    former_ids = sorted((set(paid) | set(owed)) - set(member_ids), key=str)

    balances = [
        UserBalance(
            user_id=user_id,
            paid_cents=paid.get(user_id, 0),
            owed_cents=owed.get(user_id, 0),
            net_cents=paid.get(user_id, 0) - owed.get(user_id, 0),
        )
        for user_id in (*member_ids, *former_ids)
    ]

    residual = sum(balance.net_cents for balance in balances)
    if residual != 0:
        raise AssertionError(
            f"Баланс группы {group_id} не сходится в ноль "
            f"(сумма net_cents = {residual}); доли расхода должны в сумме совпадать с его суммой"
        )

    # A payment A -> B cancels A's debt to B, so in the debt graph it is the edge
    # B -> A that grows.
    directed = [
        *edges,
        *((to_user_id, from_user_id, amount) for from_user_id, to_user_id, amount in payments),
    ]

    # Imported here, not at module scope: simplify_service needs the dataclasses
    # defined above, so a top-level import in both directions would be a cycle.
    from app.services.simplify_service import simplify

    return GroupBalances(
        group_id=group_id,
        balances=balances,
        pairwise=_net_pairs(directed),
        simplified=simplify(balances),
        total_spending_cents=group_spending_totals(db, [group_id])[group_id],
    )


def compute_user_group_nets(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """``{group_id: net_cents}`` for every group the user belongs to, zeros included."""
    group_ids = _group_ids_for_user(db, user_id)
    ledger = _user_group_ledger(db, user_id, group_ids)
    return {group_id: paid - owed for group_id, (paid, owed) in ledger.items()}


def compute_user_totals(
    db: Session,
    user_id: uuid.UUID,
    group_ids: list[uuid.UUID] | None = None,
) -> UserBalance:
    """One user's position aggregated across groups.

    ``group_ids=None`` means every group they belong to; an explicit empty list
    means no groups at all, which is an all-zero balance.
    """
    scope = _group_ids_for_user(db, user_id) if group_ids is None else list(group_ids)
    ledger = _user_group_ledger(db, user_id, scope)
    paid = sum(entry[0] for entry in ledger.values())
    owed = sum(entry[1] for entry in ledger.values())
    return UserBalance(
        user_id=user_id, paid_cents=paid, owed_cents=owed, net_cents=paid - owed
    )


def group_spending_totals(
    db: Session, group_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Live expense totals for many groups in a single query (no N+1)."""
    if not group_ids:
        return {}
    stmt = (
        select(Expense.group_id, func.sum(Expense.amount_cents))
        .where(Expense.group_id.in_(group_ids), Expense.deleted_at.is_(None))
        .group_by(Expense.group_id)
    )
    totals = _int_map(db, stmt)
    return {group_id: totals.get(group_id, 0) for group_id in group_ids}


def _member_ids(db: Session, group_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = (
        select(GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.id)
    )
    return list(db.scalars(stmt))


def _group_ids_for_user(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = (
        select(GroupMember.group_id)
        .where(GroupMember.user_id == user_id)
        .order_by(GroupMember.joined_at, GroupMember.id)
    )
    return list(db.scalars(stmt))


def _int_map(db: Session, stmt: Select[tuple[uuid.UUID, int | None]]) -> dict[uuid.UUID, int]:
    return {key: int(total or 0) for key, total in db.execute(stmt)}


def _expense_paid_totals(db: Session, group_id: uuid.UUID) -> dict[uuid.UUID, int]:
    stmt = (
        select(Expense.paid_by, func.sum(Expense.amount_cents))
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(Expense.paid_by)
    )
    return _int_map(db, stmt)


def _split_owed_totals(db: Session, group_id: uuid.UUID) -> dict[uuid.UUID, int]:
    stmt = (
        select(ExpenseSplit.user_id, func.sum(ExpenseSplit.calculated_amount_cents))
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(Expense.group_id == group_id, Expense.deleted_at.is_(None))
        .group_by(ExpenseSplit.user_id)
    )
    return _int_map(db, stmt)


def _payment_totals(
    db: Session, group_id: uuid.UUID
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """Payments collapsed to one row per (sender, receiver) pair."""
    stmt = (
        select(Payment.from_user_id, Payment.to_user_id, func.sum(Payment.amount_cents))
        .where(Payment.group_id == group_id)
        .group_by(Payment.from_user_id, Payment.to_user_id)
    )
    return [
        (from_user_id, to_user_id, int(amount or 0))
        for from_user_id, to_user_id, amount in db.execute(stmt)
    ]


def _expense_debt_edges(
    db: Session, group_id: uuid.UUID
) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
    """``(debtor, payer, amount)`` per pair: every split the payer covered for someone."""
    stmt = (
        select(
            ExpenseSplit.user_id,
            Expense.paid_by,
            func.sum(ExpenseSplit.calculated_amount_cents),
        )
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(
            Expense.group_id == group_id,
            Expense.deleted_at.is_(None),
            ExpenseSplit.user_id != Expense.paid_by,
        )
        .group_by(ExpenseSplit.user_id, Expense.paid_by)
    )
    return [
        (debtor_id, payer_id, int(amount or 0))
        for debtor_id, payer_id, amount in db.execute(stmt)
    ]


def _user_group_ledger(
    db: Session, user_id: uuid.UUID, group_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """``{group_id: (paid_cents, owed_cents)}`` for one user, four queries total."""
    if not group_ids:
        return {}

    paid_expenses = _int_map(
        db,
        select(Expense.group_id, func.sum(Expense.amount_cents))
        .where(
            Expense.group_id.in_(group_ids),
            Expense.deleted_at.is_(None),
            Expense.paid_by == user_id,
        )
        .group_by(Expense.group_id),
    )
    owed_splits = _int_map(
        db,
        select(Expense.group_id, func.sum(ExpenseSplit.calculated_amount_cents))
        .join(ExpenseSplit, ExpenseSplit.expense_id == Expense.id)
        .where(
            Expense.group_id.in_(group_ids),
            Expense.deleted_at.is_(None),
            ExpenseSplit.user_id == user_id,
        )
        .group_by(Expense.group_id),
    )
    sent = _int_map(
        db,
        select(Payment.group_id, func.sum(Payment.amount_cents))
        .where(Payment.group_id.in_(group_ids), Payment.from_user_id == user_id)
        .group_by(Payment.group_id),
    )
    received = _int_map(
        db,
        select(Payment.group_id, func.sum(Payment.amount_cents))
        .where(Payment.group_id.in_(group_ids), Payment.to_user_id == user_id)
        .group_by(Payment.group_id),
    )

    return {
        group_id: (
            paid_expenses.get(group_id, 0) + sent.get(group_id, 0),
            owed_splits.get(group_id, 0) + received.get(group_id, 0),
        )
        for group_id in group_ids
    }


def _net_pairs(
    directed: Iterable[tuple[uuid.UUID, uuid.UUID, int]],
) -> list[DebtTransfer]:
    """Net opposing edges per unordered pair and keep the positive residuals."""
    totals: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
    for debtor_id, creditor_id, amount_cents in directed:
        if debtor_id == creditor_id:
            continue
        forward = str(debtor_id) < str(creditor_id)
        key = (debtor_id, creditor_id) if forward else (creditor_id, debtor_id)
        totals[key] = totals.get(key, 0) + (amount_cents if forward else -amount_cents)

    transfers: list[DebtTransfer] = []
    for (left_id, right_id), residual in totals.items():
        if residual > 0:
            transfers.append(DebtTransfer(left_id, right_id, residual))
        elif residual < 0:
            transfers.append(DebtTransfer(right_id, left_id, -residual))

    transfers.sort(
        key=lambda transfer: (
            -transfer.amount_cents,
            str(transfer.from_user_id),
            str(transfer.to_user_id),
        )
    )
    return transfers


__all__ = [
    "DebtTransfer",
    "GroupBalances",
    "UserBalance",
    "compute_group_balances",
    "compute_user_group_nets",
    "compute_user_totals",
    "group_spending_totals",
]

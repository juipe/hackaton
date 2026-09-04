"""Dashboard analytics.

Three read-only roll-ups over the groups the caller belongs to: a headline summary,
a category breakdown and a monthly time series. Every one of them takes the same
period window, and every one of them ignores soft-deleted expenses.
"""

from __future__ import annotations

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.core.deps import assert_membership
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit
from app.models.group import Group
from app.models.user import User
from app.repositories import group_repo
from app.schemas.dashboard import (
    CategoryBreakdownItem,
    CategoryBreakdownOut,
    DashboardGroupSummary,
    DashboardSummaryOut,
    SpendingOverTimeOut,
    SpendingOverTimePoint,
)
from app.services.balance_service import compute_user_group_nets
from app.utils.time import month_key, month_label, month_range, resolve_period

#: Reported when the caller has no groups at all, so the UI always has a symbol.
DEFAULT_CURRENCY = "RUB"

#: The monthly chart is a trend, not an archive — two years of bars is plenty.
MAX_MONTH_BUCKETS = 24

_PERCENT_QUANTUM = Decimal("0.01")


@dataclass(frozen=True)
class _Scope:
    """The groups a dashboard request covers plus its ``[start, end)`` window."""

    groups: list[Group]
    start: datetime | None
    end: datetime | None

    @property
    def group_ids(self) -> list[uuid.UUID]:
        return [group.id for group in self.groups]

    @property
    def is_empty(self) -> bool:
        return not self.groups


def _resolve_scope(
    db: Session,
    *,
    user_id: uuid.UUID,
    period: str,
    date_from: date | None,
    date_to: date | None,
    group_id: uuid.UUID | None,
) -> _Scope:
    if group_id is not None:
        # Raises 404/403 itself, so the group is known to exist and to be ours.
        groups = [assert_membership(db, group_id, user_id).group]
    else:
        groups = group_repo.list_for_user(db, user_id)
    start, end = resolve_period(period, date_from, date_to)
    return _Scope(groups=groups, start=start, end=end)


def _expense_conditions(scope: _Scope) -> list[ColumnElement[bool]]:
    """Scope + period + soft-delete predicates shared by every aggregate."""
    conditions: list[ColumnElement[bool]] = [
        Expense.group_id.in_(scope.group_ids),
        Expense.deleted_at.is_(None),
    ]
    if scope.start is not None:
        conditions.append(Expense.occurred_at >= scope.start)
    if scope.end is not None:
        conditions.append(Expense.occurred_at < scope.end)
    return conditions


def _dominant_currency(groups: list[Group]) -> str:
    """The currency most of the in-scope groups use.

    Multi-currency groups are out of scope for the MVP, so the dashboard reports
    one symbol rather than refusing to add the numbers up. Ties break
    alphabetically to keep the answer stable across requests.
    """
    if not groups:
        return DEFAULT_CURRENCY
    counts = Counter((group.currency or DEFAULT_CURRENCY).upper() for group in groups)
    return min(counts.items(), key=lambda item: (-item[1], item[0]))[0]


def _percentage(amount_cents: int, total_cents: int) -> float:
    """Share of the total, rounded to 2 decimals via ``Decimal``, never float math."""
    if total_cents <= 0:
        return 0.0
    ratio = (Decimal(amount_cents) * 100 / Decimal(total_cents)).quantize(
        _PERCENT_QUANTUM, rounding=ROUND_HALF_UP
    )
    return float(ratio)


def _group_totals(db: Session, scope: _Scope) -> dict[uuid.UUID, tuple[int, int]]:
    """``{group_id: (spending_cents, expense_count)}`` inside the period."""
    if scope.is_empty:
        return {}
    stmt = (
        select(
            Expense.group_id,
            func.coalesce(func.sum(Expense.amount_cents), 0),
            func.count(Expense.id),
        )
        .where(*_expense_conditions(scope))
        .group_by(Expense.group_id)
    )
    return {
        group_id: (int(total or 0), int(count or 0))
        for group_id, total, count in db.execute(stmt)
    }


def _share_by_group(db: Session, scope: _Scope, user_id: uuid.UUID) -> dict[uuid.UUID, int]:
    """``{group_id: share_cents}`` — доля пользователя внутри периода, по группам.

    Тот же расчёт, что и :func:`_share_of_user`, но с группировкой: карточка группы
    показывает, какую часть её расходов несёт смотрящий, и без разбивки это число
    пришлось бы собирать запросом на группу.
    """
    if scope.is_empty:
        return {}
    stmt = (
        select(
            Expense.group_id,
            func.coalesce(func.sum(ExpenseSplit.calculated_amount_cents), 0),
        )
        .select_from(ExpenseSplit)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(ExpenseSplit.user_id == user_id, *_expense_conditions(scope))
        .group_by(Expense.group_id)
    )
    return {group_id: int(total or 0) for group_id, total in db.execute(stmt)}


def _paid_by_user(db: Session, scope: _Scope, user_id: uuid.UUID) -> int:
    if scope.is_empty:
        return 0
    stmt = select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(
        Expense.paid_by == user_id, *_expense_conditions(scope)
    )
    return int(db.scalar(stmt) or 0)


def _share_of_user(db: Session, scope: _Scope, user_id: uuid.UUID) -> int:
    if scope.is_empty:
        return 0
    stmt = (
        select(func.coalesce(func.sum(ExpenseSplit.calculated_amount_cents), 0))
        .select_from(ExpenseSplit)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(ExpenseSplit.user_id == user_id, *_expense_conditions(scope))
    )
    return int(db.scalar(stmt) or 0)


def summary(
    db: Session,
    *,
    user: User,
    period: str = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
) -> DashboardSummaryOut:
    scope = _resolve_scope(
        db,
        user_id=user.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )

    # Balances are deliberately all-time, unlike every other figure here: a debt
    # does not disappear because the viewer narrowed the date filter. Only the
    # spending totals and the expense count below honour the period.
    nets = compute_user_group_nets(db, user.id)

    totals = _group_totals(db, scope)
    shares = _share_by_group(db, scope, user.id)
    member_counts = group_repo.member_counts(db, scope.group_ids)

    you_owe_cents = 0
    owed_to_you_cents = 0
    groups: list[DashboardGroupSummary] = []
    total_spending_cents = 0
    expense_count = 0

    for group in scope.groups:
        # Nets are per group and are never netted across groups: being owed 100 in
        # one group does not cancel the 40 you owe in another.
        net_cents = int(nets.get(group.id, 0))
        you_owe_cents += max(0, -net_cents)
        owed_to_you_cents += max(0, net_cents)

        group_spending, group_expenses = totals.get(group.id, (0, 0))
        total_spending_cents += group_spending
        expense_count += group_expenses

        groups.append(
            DashboardGroupSummary(
                group_id=group.id,
                name=group.name,
                currency=group.currency,
                net_cents=net_cents,
                total_spending_cents=group_spending,
                your_share_cents=shares.get(group.id, 0),
                member_count=member_counts.get(group.id, 0),
            )
        )

    return DashboardSummaryOut(
        you_owe_cents=you_owe_cents,
        owed_to_you_cents=owed_to_you_cents,
        net_cents=owed_to_you_cents - you_owe_cents,
        total_spending_cents=total_spending_cents,
        your_paid_cents=_paid_by_user(db, scope, user.id),
        your_share_cents=_share_of_user(db, scope, user.id),
        group_count=len(scope.groups),
        expense_count=expense_count,
        currency=_dominant_currency(scope.groups),
        groups=groups,
    )


def spending_by_category(
    db: Session,
    *,
    user: User,
    period: str = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
) -> CategoryBreakdownOut:
    scope = _resolve_scope(
        db,
        user_id=user.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )
    if scope.is_empty:
        return CategoryBreakdownOut(total_cents=0, items=[])

    amount = func.coalesce(func.sum(Expense.amount_cents), 0).label("amount_cents")
    stmt = (
        select(
            Category.id,
            Category.slug,
            Category.name,
            Category.icon,
            amount,
            func.count(Expense.id).label("expense_count"),
        )
        .select_from(Expense)
        .join(Category, Category.id == Expense.category_id)
        .where(*_expense_conditions(scope))
        .group_by(Category.id, Category.slug, Category.name, Category.icon)
        .order_by(amount.desc(), Category.sort_order, Category.name)
    )
    rows = list(db.execute(stmt))

    total_cents = sum(int(row.amount_cents or 0) for row in rows)
    items = [
        CategoryBreakdownItem(
            category_id=row.id,
            slug=row.slug,
            name=row.name,
            icon=row.icon,
            amount_cents=int(row.amount_cents or 0),
            percentage=_percentage(int(row.amount_cents or 0), total_cents),
            expense_count=int(row.expense_count or 0),
        )
        for row in rows
    ]
    return CategoryBreakdownOut(total_cents=total_cents, items=items)


def spending_over_time(
    db: Session,
    *,
    user: User,
    period: str = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
) -> SpendingOverTimeOut:
    scope = _resolve_scope(
        db,
        user_id=user.id,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )
    currency = _dominant_currency(scope.groups)
    if scope.is_empty:
        return SpendingOverTimeOut(currency=currency, items=[])

    conditions = _expense_conditions(scope)

    # Bucketing happens in Python rather than with a SQL date function because
    # SQLite (tests) and Postgres (runtime) spell month truncation differently.
    totals: dict[str, int] = {}
    for occurred_at, amount_cents in db.execute(
        select(Expense.occurred_at, Expense.amount_cents).where(*conditions)
    ):
        key = month_key(occurred_at)
        totals[key] = totals.get(key, 0) + int(amount_cents or 0)

    shares: dict[str, int] = {}
    share_stmt = (
        select(Expense.occurred_at, ExpenseSplit.calculated_amount_cents)
        .select_from(ExpenseSplit)
        .join(Expense, Expense.id == ExpenseSplit.expense_id)
        .where(ExpenseSplit.user_id == user.id, *conditions)
    )
    for occurred_at, share_cents in db.execute(share_stmt):
        key = month_key(occurred_at)
        shares[key] = shares.get(key, 0) + int(share_cents or 0)

    populated = sorted(set(totals) | set(shares))
    if not populated:
        return SpendingOverTimeOut(currency=currency, items=[])

    keys = month_range(populated[0], populated[-1])[-MAX_MONTH_BUCKETS:]
    items = [
        SpendingOverTimePoint(
            month=key,
            label=month_label(key),
            amount_cents=totals.get(key, 0),
            your_share_cents=shares.get(key, 0),
        )
        for key in keys
    ]
    return SpendingOverTimeOut(currency=currency, items=items)


__all__ = [
    "DEFAULT_CURRENCY",
    "MAX_MONTH_BUCKETS",
    "spending_by_category",
    "spending_over_time",
    "summary",
]

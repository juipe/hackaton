from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import ColumnElement, delete, func, select
from sqlalchemy.orm import Session

from app.models.expense import Expense, ExpenseSplit

#: Escape character for LIKE patterns, so a literal ``%`` in a search box stays literal.
_LIKE_ESCAPE = "\\"


def _like_pattern(term: str) -> str:
    escaped = (
        term.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
        .replace("%", f"{_LIKE_ESCAPE}%")
        .replace("_", f"{_LIKE_ESCAPE}_")
    )
    return f"%{escaped.lower()}%"


def _conditions(
    group_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None,
    paid_by: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    q: str | None,
) -> list[ColumnElement[bool]]:
    """Shared WHERE clauses, so the page and its total can never disagree."""
    conditions: list[ColumnElement[bool]] = [
        Expense.group_id == group_id,
        Expense.deleted_at.is_(None),
    ]
    if category_id is not None:
        conditions.append(Expense.category_id == category_id)
    if paid_by is not None:
        conditions.append(Expense.paid_by == paid_by)
    if date_from is not None:
        conditions.append(Expense.occurred_at >= date_from)
    if date_to is not None:
        conditions.append(Expense.occurred_at < date_to)
    term = (q or "").strip()
    if term:
        pattern = _like_pattern(term)
        conditions.append(
            func.lower(Expense.title).like(pattern, escape=_LIKE_ESCAPE)
            | func.lower(func.coalesce(Expense.description, "")).like(
                pattern, escape=_LIKE_ESCAPE
            )
        )
    return conditions


def get(db: Session, expense_id: uuid.UUID) -> Expense | None:
    """Any expense, including soft-deleted ones."""
    return db.get(Expense, expense_id)


def get_active(db: Session, expense_id: uuid.UUID) -> Expense | None:
    """A live expense; a soft-deleted row reads as missing."""
    expense = db.get(Expense, expense_id)
    if expense is None or expense.deleted_at is not None:
        return None
    return expense


def list_for_group(
    db: Session,
    group_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Expense]:
    stmt = (
        select(Expense)
        .where(
            *_conditions(
                group_id,
                category_id=category_id,
                paid_by=paid_by,
                date_from=date_from,
                date_to=date_to,
                q=q,
            )
        )
        .order_by(Expense.occurred_at.desc(), Expense.created_at.desc(), Expense.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).unique())


def count_for_group(
    db: Session,
    group_id: uuid.UUID,
    *,
    category_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(Expense)
        .where(
            *_conditions(
                group_id,
                category_id=category_id,
                paid_by=paid_by,
                date_from=date_from,
                date_to=date_to,
                q=q,
            )
        )
    )
    return int(db.scalar(stmt) or 0)


def add(db: Session, expense: Expense) -> Expense:
    db.add(expense)
    db.flush()
    return expense


def add_splits(db: Session, expense: Expense, splits: Sequence[ExpenseSplit]) -> None:
    for split in splits:
        split.expense_id = expense.id
        db.add(split)
    db.flush()
    db.expire(expense, ["splits"])


def replace_splits(db: Session, expense: Expense, splits: Sequence[ExpenseSplit]) -> None:
    """Swap in a freshly computed set of splits.

    The old rows are deleted and flushed *before* the new ones are inserted: a
    single flush emits inserts ahead of deletes, which would trip
    ``uq_expense_splits_expense_user`` for every participant that is kept.
    """
    db.execute(delete(ExpenseSplit).where(ExpenseSplit.expense_id == expense.id))
    db.flush()
    add_splits(db, expense, splits)


__all__ = [
    "add",
    "add_splits",
    "count_for_group",
    "get",
    "get_active",
    "list_for_group",
    "replace_splits",
]

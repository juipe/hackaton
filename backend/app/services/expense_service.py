"""Expense business logic.

Nothing here divides money. Every cent that lands in ``expense_splits`` comes out
of :func:`app.services.split_engine.compute_splits`, which owns the rounding rules
and the "the parts always add up to the whole" post-condition. This module's job is
authorization-adjacent validation (category, membership, payer), persistence, and
turning ORM rows into the wire shape.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, NotFound
from app.models.activity import ActivityType
from app.models.category import Category
from app.models.expense import Expense, ExpenseSplit, SplitMode
from app.models.group import Group
from app.models.user import User
from app.repositories import category_repo, expense_repo, group_repo
from app.schemas.expense import ExpenseOut, ExpensePage, ParticipantIn, SplitOut
from app.services.activity_service import log_activity
from app.services.debt_reminder_service import create_reminders_for_expense
from app.services.split_engine import SplitInput, SplitResult, compute_splits
from app.utils.time import ensure_utc, utcnow


def build_expense_out(expense: Expense, user_id: uuid.UUID) -> ExpenseOut:
    """Serialize one expense from ``user_id``'s point of view."""
    splits = [SplitOut.model_validate(split) for split in expense.splits]
    my_share_cents = sum(
        split.calculated_amount_cents for split in splits if split.user_id == user_id
    )
    my_paid_cents = expense.amount_cents if expense.paid_by == user_id else 0
    return ExpenseOut(
        id=expense.id,
        group_id=expense.group_id,
        title=expense.title,
        description=expense.description,
        amount_cents=expense.amount_cents,
        currency=expense.currency,
        split_mode=expense.split_mode,
        category=expense.category,
        paid_by=expense.paid_by,
        payer=expense.payer,
        created_by=expense.created_by,
        creator=expense.creator,
        occurred_at=ensure_utc(expense.occurred_at),
        created_at=ensure_utc(expense.created_at),
        updated_at=ensure_utc(expense.updated_at),
        splits=splits,
        my_share_cents=my_share_cents,
        my_paid_cents=my_paid_cents,
        my_net_cents=my_paid_cents - my_share_cents,
    )


def build_expense_outs(expenses: list[Expense], user_id: uuid.UUID) -> list[ExpenseOut]:
    return [build_expense_out(expense, user_id) for expense in expenses]


def get_expense(db: Session, expense_id: uuid.UUID) -> Expense:
    """Load a live expense. A soft-deleted one is gone as far as the API is concerned."""
    expense = expense_repo.get_active(db, expense_id)
    if expense is None:
        raise NotFound("Расход не найден")
    return expense


def list_expenses(
    db: Session,
    *,
    group_id: uuid.UUID,
    user_id: uuid.UUID,
    category_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> ExpensePage:
    window_from, window_to = _resolve_window(date_from, date_to)
    filters: dict[str, Any] = {
        "category_id": category_id,
        "paid_by": paid_by,
        "date_from": window_from,
        "date_to": window_to,
        "q": q,
    }
    expenses = expense_repo.list_for_group(
        db, group_id, limit=limit, offset=offset, **filters
    )
    total = expense_repo.count_for_group(db, group_id, **filters)
    return ExpensePage(
        items=build_expense_outs(expenses, user_id),
        total=total,
        limit=limit,
        offset=offset,
    )


def create_expense(
    db: Session,
    *,
    group: Group,
    actor: User,
    title: str,
    description: str | None,
    amount_cents: int,
    category_id: uuid.UUID,
    paid_by: uuid.UUID,
    occurred_at: datetime | None,
    split_mode: SplitMode,
    participants: Sequence[ParticipantIn],
) -> Expense:
    category = _require_category(db, category_id)
    _check_people(
        db,
        group_id=group.id,
        paid_by=paid_by,
        participant_ids=[participant.user_id for participant in participants],
    )
    results = compute_splits(amount_cents, split_mode, _split_inputs(participants))

    expense = Expense(
        group_id=group.id,
        created_by=actor.id,
        title=title.strip(),
        description=description,
        amount_cents=amount_cents,
        # The group is the single source of truth for currency: an expense in a
        # foreign currency would silently corrupt every balance in the group.
        currency=group.currency,
        category=category,
        paid_by=paid_by,
        split_mode=split_mode.value,
        occurred_at=ensure_utc(occurred_at) if occurred_at else utcnow(),
    )
    expense_repo.add(db, expense)
    expense_repo.add_splits(db, expense, _split_rows(split_mode, results))

    log_activity(
        db,
        group_id=group.id,
        actor_id=actor.id,
        type=ActivityType.EXPENSE_CREATED,
        entity_id=expense.id,
        meta=_activity_meta(expense),
    )
    # Reuses the very same `results` the splits above were built from — no
    # recomputation, no second opinion on who owes what.
    create_reminders_for_expense(db, expense=expense, group=group, results=results)
    db.commit()
    return expense


def update_expense(
    db: Session,
    *,
    expense: Expense,
    actor: User,
    title: str | None = None,
    description: str | None = None,
    amount_cents: int | None = None,
    category_id: uuid.UUID | None = None,
    paid_by: uuid.UUID | None = None,
    occurred_at: datetime | None = None,
    split_mode: SplitMode | None = None,
    participants: Sequence[ParticipantIn] | None = None,
    fields_set: set[str],
) -> Expense:
    """Apply a partial edit. Any group member may edit any expense, per the spec.

    Every check runs *before* the first mutation so a rejected edit cannot leave a
    half-applied expense behind in the session.
    """
    recompute = any(
        field in fields_set and value is not None
        for field, value in (
            ("amount_cents", amount_cents),
            ("split_mode", split_mode),
            ("participants", participants),
        )
    )

    category = _require_category(db, category_id) if category_id is not None else None
    new_amount = amount_cents if amount_cents is not None else expense.amount_cents
    new_mode = split_mode if split_mode is not None else SplitMode(expense.split_mode)
    new_paid_by = paid_by if paid_by is not None else expense.paid_by
    new_participants = (
        list(participants) if participants is not None else _participants_of(expense)
    )
    participant_ids = [participant.user_id for participant in new_participants]

    # Membership is only re-checked for people the request actually names: a member
    # who settled up and left may still appear on old expenses, and editing the
    # title of one of those must not fail.
    if paid_by is not None or participants is not None:
        member_ids = set(group_repo.list_member_ids(db, expense.group_id))
        if paid_by is not None and paid_by not in member_ids:
            raise BadRequest("Плательщик должен состоять в группе")
        if participants is not None and not set(participant_ids) <= member_ids:
            raise BadRequest("Участники должны состоять в группе")
    if (paid_by is not None or recompute) and new_paid_by not in participant_ids:
        raise BadRequest("Плательщик должен быть среди участников")

    results = (
        compute_splits(new_amount, new_mode, _split_inputs(new_participants))
        if recompute
        else None
    )

    if title is not None:
        expense.title = title.strip()
    if "description" in fields_set:
        expense.description = description
    if category is not None:
        expense.category = category
    if occurred_at is not None:
        expense.occurred_at = ensure_utc(occurred_at)
    if new_paid_by != expense.paid_by:
        expense.paid_by = new_paid_by
        # ``payer`` is eagerly loaded and still points at the previous user; moving
        # the foreign key on its own does not refresh the relationship.
        db.expire(expense, ["payer"])
    if results is not None:
        expense.amount_cents = new_amount
        expense.split_mode = new_mode.value
        expense_repo.replace_splits(db, expense, _split_rows(new_mode, results))
    # Assigned explicitly: an edit that only touches split rows leaves every column
    # untouched, so ``onupdate`` would never fire.
    expense.updated_at = utcnow()

    log_activity(
        db,
        group_id=expense.group_id,
        actor_id=actor.id,
        type=ActivityType.EXPENSE_UPDATED,
        entity_id=expense.id,
        meta=_activity_meta(expense),
    )
    db.commit()
    return expense


def delete_expense(db: Session, *, expense: Expense, actor: User) -> None:
    """Soft delete. The row survives so the activity feed keeps its reference."""
    expense.deleted_at = utcnow()
    log_activity(
        db,
        group_id=expense.group_id,
        actor_id=actor.id,
        type=ActivityType.EXPENSE_DELETED,
        entity_id=expense.id,
        meta=_activity_meta(expense),
    )
    db.commit()


def _require_category(db: Session, category_id: uuid.UUID) -> Category:
    category = category_repo.get(db, category_id)
    if category is None:
        raise BadRequest("Категория не найдена")
    return category


def _check_people(
    db: Session,
    *,
    group_id: uuid.UUID,
    paid_by: uuid.UUID,
    participant_ids: Sequence[uuid.UUID],
) -> None:
    member_ids = set(group_repo.list_member_ids(db, group_id))
    if paid_by not in member_ids:
        raise BadRequest("Плательщик должен состоять в группе")
    if not set(participant_ids) <= member_ids:
        raise BadRequest("Участники должны состоять в группе")
    if paid_by not in participant_ids:
        raise BadRequest("Плательщик должен быть среди участников")


def _participants_of(expense: Expense) -> list[ParticipantIn]:
    """The current splits expressed as fresh input, for a partial edit."""
    return [
        ParticipantIn(user_id=split.user_id, value=split.input_value)
        for split in expense.splits
    ]


def _split_inputs(participants: Sequence[ParticipantIn]) -> list[SplitInput]:
    return [
        SplitInput(user_id=participant.user_id, value=participant.value)
        for participant in participants
    ]


def _split_rows(mode: SplitMode, results: Sequence[SplitResult]) -> list[ExpenseSplit]:
    return [
        ExpenseSplit(
            user_id=result.user_id,
            split_mode=mode.value,
            input_value=result.input_value,
            calculated_amount_cents=result.calculated_amount_cents,
        )
        for result in results
    ]


def _activity_meta(expense: Expense) -> dict[str, Any]:
    return {
        "title": expense.title,
        "amount_cents": expense.amount_cents,
        "currency": expense.currency,
        "category": expense.category.slug,
    }


def _resolve_window(
    date_from: date | None, date_to: date | None
) -> tuple[datetime | None, datetime | None]:
    """Inclusive dates to a half-open ``[start, end)`` UTC window.

    ``date_to`` names a whole day, so the window ends at midnight of the day after
    it — an expense timestamped 23:00 on the last day still counts.
    """
    start = ensure_utc(datetime.combine(date_from, time.min)) if date_from else None
    end = (
        ensure_utc(datetime.combine(date_to + timedelta(days=1), time.min))
        if date_to
        else None
    )
    return start, end


__all__ = [
    "build_expense_out",
    "build_expense_outs",
    "create_expense",
    "delete_expense",
    "get_expense",
    "list_expenses",
    "update_expense",
]

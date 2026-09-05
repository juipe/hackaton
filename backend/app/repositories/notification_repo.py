from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.utils.time import utcnow

#: The bell only ever shows the latest handful — see the feature contract.
MAX_NOTIFICATIONS = 10


def exists_for_expense_user(db: Session, expense_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    """Whether a reminder was already recorded for this debtor on this expense.

    Guards against a duplicate reminder if expense creation is ever retried —
    the unique constraint on the table is the hard backstop, this is the check
    that avoids ever hitting it.
    """
    stmt = select(Notification.id).where(
        Notification.expense_id == expense_id, Notification.user_id == user_id
    )
    return db.scalar(stmt) is not None


def list_available_for_user(
    db: Session, user_id: uuid.UUID, *, limit: int = MAX_NOTIFICATIONS
) -> list[Notification]:
    """The latest ``limit`` reminders whose delay has already elapsed, newest first."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id, Notification.available_at <= utcnow())
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def ids_for_expense(db: Session, expense_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(Notification.id).where(Notification.expense_id == expense_id)
    return list(db.scalars(stmt))


def mark_available_read(db: Session, user_id: uuid.UUID) -> None:
    """Mark every currently-visible reminder read — called when the panel opens.

    Does not commit — that's the caller's job, per the repository layering.
    """
    stmt = (
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.available_at <= utcnow(),
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    db.execute(stmt)


__all__ = [
    "MAX_NOTIFICATIONS",
    "exists_for_expense_user",
    "ids_for_expense",
    "list_available_for_user",
    "mark_available_read",
]

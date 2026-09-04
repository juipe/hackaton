from __future__ import annotations

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.payment import Payment
from app.models.user import User

#: Payments are a feed: the most recent settle-up first. ``created_at`` breaks ties
#: between payments backdated to the same instant, ``id`` keeps the order stable.
_NEWEST_FIRST = (Payment.paid_at.desc(), Payment.created_at.desc(), Payment.id.desc())


def get(db: Session, payment_id: uuid.UUID) -> Payment | None:
    return db.get(Payment, payment_id)


def list_for_group(
    db: Session, group_id: uuid.UUID, *, limit: int | None = None, offset: int = 0
) -> list[Payment]:
    stmt = select(Payment).where(Payment.group_id == group_id).order_by(*_NEWEST_FIRST)
    if offset:
        stmt = stmt.offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).unique())


def list_for_groups(db: Session, group_ids: Iterable[uuid.UUID]) -> list[Payment]:
    """Every payment across many groups, for the bulk ledger passes."""
    ids = list(group_ids)
    if not ids:
        return []
    stmt = select(Payment).where(Payment.group_id.in_(ids)).order_by(*_NEWEST_FIRST)
    return list(db.scalars(stmt).unique())


def list_for_user(
    db: Session, user_id: uuid.UUID, *, group_ids: Iterable[uuid.UUID] | None = None
) -> list[Payment]:
    """Payments the user sent or received, optionally narrowed to some groups."""
    stmt = select(Payment).where(
        or_(Payment.from_user_id == user_id, Payment.to_user_id == user_id)
    )
    if group_ids is not None:
        ids = list(group_ids)
        if not ids:
            return []
        stmt = stmt.where(Payment.group_id.in_(ids))
    return list(db.scalars(stmt.order_by(*_NEWEST_FIRST)).unique())


def count_for_group(db: Session, group_id: uuid.UUID) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Payment).where(Payment.group_id == group_id))
        or 0
    )


def create(
    db: Session,
    *,
    group_id: uuid.UUID,
    from_user: User,
    to_user: User,
    amount_cents: int,
    currency: str,
    note: str | None,
    paid_at: datetime,
) -> Payment:
    """Persist a settle-up.

    The two participants arrive as ORM objects rather than ids so the eagerly
    loaded ``from_user`` / ``to_user`` relationships are already populated when the
    response schema reads them back.
    """
    payment = Payment(
        group_id=group_id,
        from_user=from_user,
        to_user=to_user,
        amount_cents=amount_cents,
        currency=currency,
        note=note,
        paid_at=paid_at,
    )
    db.add(payment)
    db.flush()
    return payment


__all__ = [
    "count_for_group",
    "create",
    "get",
    "list_for_group",
    "list_for_groups",
    "list_for_user",
]

"""Settle-up payments.

A payment records money that changed hands outside the app. It feeds the same
ledger as an expense — ``from_user`` has now paid more, ``to_user`` has received
more — which is how a debt gets cleared without editing history.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Forbidden, NotFound, UnprocessableEntity
from app.models.activity import ActivityType
from app.models.member import GroupRole
from app.models.payment import Payment
from app.models.user import User
from app.repositories import group_repo, payment_repo, user_repo
from app.services.activity_service import log_activity
from app.services.budget_threshold_service import check_and_notify_many
from app.utils.time import ensure_utc, utcnow


def list_payments(
    db: Session, group_id: uuid.UUID, *, limit: int | None = None, offset: int = 0
) -> list[Payment]:
    return payment_repo.list_for_group(db, group_id, limit=limit, offset=offset)


def record_payment(
    db: Session,
    *,
    group_id: uuid.UUID,
    actor: User,
    from_user_id: uuid.UUID,
    to_user_id: uuid.UUID,
    amount_cents: int,
    note: str | None = None,
    paid_at: datetime | None = None,
) -> Payment:
    """Record ``from_user`` handing ``amount_cents`` to ``to_user`` in this group."""
    group = group_repo.get(db, group_id)
    if group is None:
        raise NotFound("Группа не найдена")

    # The request schema already rejects both of these; repeated here because the
    # service is also called from scripts and seeds that bypass it.
    if from_user_id == to_user_id:
        raise UnprocessableEntity("Перевод возможен только между разными людьми")
    if amount_cents < 1:
        raise UnprocessableEntity("Сумма должна быть больше нуля")

    member_ids = set(group_repo.list_member_ids(db, group_id))
    if from_user_id not in member_ids or to_user_id not in member_ids:
        raise BadRequest("Оба участника должны состоять в группе")

    if actor.id not in (from_user_id, to_user_id) and not _is_owner(db, group_id, actor.id):
        raise Forbidden("Можно записывать только свои переводы")

    users = user_repo.map_by_ids(db, (from_user_id, to_user_id))
    from_user = users[from_user_id]
    to_user = users[to_user_id]

    payment = payment_repo.create(
        db,
        group_id=group.id,
        from_user=from_user,
        to_user=to_user,
        amount_cents=amount_cents,
        currency=group.currency,
        note=note,
        # A client may send a naive timestamp; the ledger is UTC end to end.
        paid_at=ensure_utc(paid_at) if paid_at is not None else utcnow(),
    )

    log_activity(
        db,
        group_id=group.id,
        actor_id=actor.id,
        type=ActivityType.PAYMENT_CREATED,
        entity_id=payment.id,
        meta={
            "amount_cents": payment.amount_cents,
            "currency": payment.currency,
            "from_name": from_user.name,
            "to_name": to_user.name,
        },
    )

    db.commit()

    # Only the receiver's cross-group exposure can have grown from this payment
    # (an overpayment can push their net negative); the sender's net can only
    # improve. Runs after commit so the check reads the transaction it reacts to.
    check_and_notify_many(db, [to_user_id])
    return payment


def _is_owner(db: Session, group_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    membership = group_repo.get_membership(db, group_id, user_id)
    return membership is not None and membership.role == GroupRole.OWNER.value


__all__ = ["list_payments", "record_payment"]

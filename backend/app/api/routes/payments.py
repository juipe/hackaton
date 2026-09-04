"""Settle-up payment endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, Membership
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services import payment_service

router = APIRouter(prefix="/groups", tags=["Переводы"])


@router.get(
    "/{group_id}/payments",
    response_model=list[PaymentOut],
    summary="Переводы в группе",
)
def list_payments(
    group_id: uuid.UUID,
    db: DbSession,
    _membership: Membership,
) -> list[PaymentOut]:
    payments = payment_service.list_payments(db, group_id)
    return [PaymentOut.model_validate(payment) for payment in payments]


@router.post(
    "/{group_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Записать перевод",
)
def create_payment(
    group_id: uuid.UUID,
    payload: PaymentCreate,
    db: DbSession,
    user: CurrentUser,
    _membership: Membership,
) -> PaymentOut:
    payment = payment_service.record_payment(
        db,
        group_id=group_id,
        actor=user,
        from_user_id=payload.from_user_id,
        to_user_id=payload.to_user_id,
        amount_cents=payload.amount_cents,
        note=payload.note,
        paid_at=payload.paid_at,
    )
    return PaymentOut.model_validate(payment)


__all__ = ["router"]

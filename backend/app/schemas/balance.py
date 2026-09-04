"""Balance and debt-simplification payloads.

The ledger engine works purely in ids and integer cents; these converters attach
the ``User`` objects the UI needs. They take a pre-resolved ``{id: User}`` map
rather than a ``Session`` so a whole response can be assembled from one query.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic

if TYPE_CHECKING:
    from app.models.user import User
    from app.services.balance_service import DebtTransfer, UserBalance


class UserBalanceOut(BaseModel):
    user_id: uuid.UUID
    user: UserPublic
    paid_cents: int
    owed_cents: int
    net_cents: int


class TransferOut(BaseModel):
    """Один предлагаемый перевод: ``from_user`` отдаёт сумму ``to_user``."""

    from_user_id: uuid.UUID
    from_user: UserPublic
    to_user_id: uuid.UUID
    to_user: UserPublic
    amount_cents: int


class GroupBalancesOut(BaseModel):
    group_id: uuid.UUID
    currency: str
    balances: list[UserBalanceOut]
    pairwise: list[TransferOut]
    simplified: list[TransferOut]
    me: UserBalanceOut
    total_spending_cents: int


class SimplifyRequest(BaseModel):
    """Параметры упрощения долгов."""

    record_activity: bool = Field(
        default=False, description="Записать в ленту, что долги упрощали"
    )


class SimplifyPreviewOut(BaseModel):
    current_transfer_count: int
    simplified_transfer_count: int
    current_transfers: list[TransferOut]
    transfers: list[TransferOut]


def _public(user_id: uuid.UUID, users: dict[uuid.UUID, User]) -> UserPublic:
    # Every id in a ledger row is a live FK to ``users``, so a miss here means the
    # map handed in was built from the wrong set of ids — a bug, not a bad request.
    return UserPublic.model_validate(users[user_id])


def to_user_balance_out(balance: UserBalance, users: dict[uuid.UUID, User]) -> UserBalanceOut:
    return UserBalanceOut(
        user_id=balance.user_id,
        user=_public(balance.user_id, users),
        paid_cents=balance.paid_cents,
        owed_cents=balance.owed_cents,
        net_cents=balance.net_cents,
    )


def to_transfer_out(transfer: DebtTransfer, users: dict[uuid.UUID, User]) -> TransferOut:
    return TransferOut(
        from_user_id=transfer.from_user_id,
        from_user=_public(transfer.from_user_id, users),
        to_user_id=transfer.to_user_id,
        to_user=_public(transfer.to_user_id, users),
        amount_cents=transfer.amount_cents,
    )


__all__ = [
    "GroupBalancesOut",
    "SimplifyPreviewOut",
    "SimplifyRequest",
    "TransferOut",
    "UserBalanceOut",
    "to_transfer_out",
    "to_user_balance_out",
]

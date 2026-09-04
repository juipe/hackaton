"""Balance and debt-simplification endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.core.deps import DbSession, Membership
from app.models.activity import ActivityType
from app.repositories import user_repo
from app.schemas.balance import (
    GroupBalancesOut,
    SimplifyPreviewOut,
    SimplifyRequest,
    to_transfer_out,
    to_user_balance_out,
)
from app.services import activity_service, balance_service
from app.services.balance_service import GroupBalances, UserBalance

router = APIRouter(prefix="/groups", tags=["Балансы"])


def _referenced_user_ids(balances: GroupBalances, viewer_id: uuid.UUID) -> set[uuid.UUID]:
    """Every user id the response will embed, so one query can resolve them all."""
    user_ids = {balance.user_id for balance in balances.balances}
    user_ids.add(viewer_id)
    for transfer in (*balances.pairwise, *balances.simplified):
        user_ids.add(transfer.from_user_id)
        user_ids.add(transfer.to_user_id)
    return user_ids


@router.get(
    "/{group_id}/balances",
    response_model=GroupBalancesOut,
    summary="Балансы группы",
)
def get_group_balances(
    group_id: uuid.UUID, db: DbSession, membership: Membership
) -> GroupBalancesOut:
    viewer_id = membership.user_id
    balances = balance_service.compute_group_balances(db, group_id)
    users = user_repo.map_by_ids(db, _referenced_user_ids(balances, viewer_id))

    me = next(
        (balance for balance in balances.balances if balance.user_id == viewer_id),
        UserBalance(user_id=viewer_id, paid_cents=0, owed_cents=0, net_cents=0),
    )

    return GroupBalancesOut(
        group_id=group_id,
        currency=membership.group.currency,
        balances=[to_user_balance_out(balance, users) for balance in balances.balances],
        pairwise=[to_transfer_out(transfer, users) for transfer in balances.pairwise],
        simplified=[to_transfer_out(transfer, users) for transfer in balances.simplified],
        me=to_user_balance_out(me, users),
        total_spending_cents=balances.total_spending_cents,
    )


@router.post(
    "/{group_id}/simplify-debts",
    response_model=SimplifyPreviewOut,
    summary="Упростить долги",
)
def simplify_group_debts(
    group_id: uuid.UUID,
    db: DbSession,
    membership: Membership,
    payload: SimplifyRequest | None = None,
) -> SimplifyPreviewOut:
    """Сравнивает прямые долги «каждый каждому» с минимальным набором переводов.

    В журнал ничего не пишется: упрощение сохраняет итоговый баланс каждого
    участника без изменений, поэтому хранить рекомендацию бессмысленно — она
    устареет с первым же расходом. Запись в ленте лишь фиксирует, что кто-то
    заглянул сюда.
    """
    request = payload or SimplifyRequest()
    balances = balance_service.compute_group_balances(db, group_id)
    users = user_repo.map_by_ids(db, _referenced_user_ids(balances, membership.user_id))
    current = balances.pairwise
    transfers = balances.simplified

    if request.record_activity:
        activity_service.log_activity(
            db,
            group_id=group_id,
            actor_id=membership.user_id,
            type=ActivityType.DEBT_SIMPLIFIED,
            meta={"before": len(current), "after": len(transfers)},
        )
        db.commit()

    return SimplifyPreviewOut(
        current_transfer_count=len(current),
        simplified_transfer_count=len(transfers),
        current_transfers=[to_transfer_out(transfer, users) for transfer in current],
        transfers=[to_transfer_out(transfer, users) for transfer in transfers],
    )


__all__ = ["router"]

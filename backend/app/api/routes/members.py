"""Group membership endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, Membership
from app.repositories import group_repo
from app.schemas.member import MemberOut
from app.services import group_service

router = APIRouter(prefix="/groups", tags=["Участники"])


@router.get("/{group_id}/members", summary="Участники группы")
def list_members(group_id: uuid.UUID, membership: Membership, db: DbSession) -> list[MemberOut]:
    members = group_repo.list_members(db, group_id)
    return [MemberOut.model_validate(member) for member in members]


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Исключить участника или выйти из группы",
)
def remove_member(
    user_id: uuid.UUID, membership: Membership, db: DbSession, user: CurrentUser
) -> Response:
    group_service.remove_member(db, group=membership.group, actor=user, user_id=user_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

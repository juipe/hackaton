"""Group invitation endpoints.

The router carries no prefix because invites are addressed two different ways:
nested under a group when they are created, listed or cancelled by a member, and by
opaque token when an invitee previews or accepts one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, Membership, OptionalUser
from app.schemas.group import GroupOut
from app.schemas.invite import (
    InviteCreate,
    InviteCreatedOut,
    InviteOut,
    InvitePreviewOut,
)
from app.services import invite_service

router = APIRouter(tags=["Приглашения"])


@router.post(
    "/groups/{group_id}/invites",
    response_model=InviteCreatedOut,
    status_code=status.HTTP_201_CREATED,
    summary="Пригласить в группу",
)
def create_invite(
    payload: InviteCreate,
    db: DbSession,
    user: CurrentUser,
    membership: Membership,
) -> InviteCreatedOut:
    return invite_service.create_invite(
        db, group=membership.group, inviter=user, email=payload.email
    )


@router.get(
    "/groups/{group_id}/invites",
    response_model=list[InviteOut],
    summary="Приглашения группы",
)
def list_invites(
    group_id: uuid.UUID, db: DbSession, membership: Membership
) -> list[InviteOut]:
    return invite_service.list_group_invites(db, group_id)


@router.get(
    "/invites/{token}",
    response_model=InvitePreviewOut,
    summary="Посмотреть приглашение",
)
def preview_invite(token: str, db: DbSession, user: OptionalUser) -> InvitePreviewOut:
    return invite_service.preview_invite(db, token, user)


@router.post(
    "/invites/{token}/accept",
    response_model=GroupOut,
    summary="Принять приглашение",
)
def accept_invite(token: str, db: DbSession, user: CurrentUser) -> GroupOut:
    return invite_service.accept_invite(db, token, user)


@router.delete(
    "/invites/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Отозвать приглашение",
)
def delete_invite(invite_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    invite_service.delete_invite(db, invite_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]

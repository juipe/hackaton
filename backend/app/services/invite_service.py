"""Group invitations.

Invites are link based. A raw token is generated once, handed back in the creation
response and then forgotten — only its SHA-256 digest reaches the database. Every
later lookup hashes the incoming token and matches on ``token_hash``, so a leaked
database cannot be replayed and no internal id ever appears in an invite URL.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound
from app.core.security import generate_invite_token, hash_invite_token
from app.models.activity import ActivityType
from app.models.group import Group
from app.models.invite import GroupInvite
from app.models.member import GroupRole
from app.models.user import User
from app.repositories import group_repo, invite_repo, user_repo
from app.schemas.group import GroupOut
from app.schemas.invite import (
    InviteCreatedOut,
    InviteGroupPreview,
    InviteOut,
    InvitePreviewOut,
    InviteStatus,
)
from app.services import group_service
from app.services.activity_service import log_activity
from app.services.notification_service import build_invite_url, get_notification_service
from app.utils.time import ensure_utc, utcnow


def invite_status(invite: GroupInvite, *, now: datetime | None = None) -> InviteStatus:
    if invite.accepted_at is not None:
        return "accepted"
    if ensure_utc(invite.expires_at) <= (now or utcnow()):
        return "expired"
    return "pending"


def _to_invite_out(invite: GroupInvite, *, now: datetime) -> InviteOut:
    return InviteOut(
        id=invite.id,
        group_id=invite.group_id,
        invited_email=invite.invited_email,
        inviter=invite.inviter,
        expires_at=invite.expires_at,
        accepted_at=invite.accepted_at,
        status=invite_status(invite, now=now),
        created_at=invite.created_at,
    )


def create_invite(
    db: Session, *, group: Group, inviter: User, email: str
) -> InviteCreatedOut:
    invited_email = email.strip().lower()
    invitee = user_repo.get_by_email(db, invited_email)
    if invitee is not None and group_repo.is_member(db, group.id, invitee.id):
        raise Conflict("Этот человек уже в группе")

    token = generate_invite_token()
    invite = invite_repo.create(
        db,
        group_id=group.id,
        inviter_id=inviter.id,
        invited_email=invited_email,
        token_hash=hash_invite_token(token),
        expires_at=utcnow() + timedelta(hours=settings.invite_expire_hours),
    )
    log_activity(
        db,
        group_id=group.id,
        actor_id=inviter.id,
        type=ActivityType.INVITE_CREATED,
        entity_id=invite.id,
        meta={"invited_email": invited_email},
    )
    db.commit()

    # Notify only once the invite is durable, so nobody receives a link to a row
    # that was rolled back. The service returns the URL the invitee should open.
    invite_url = get_notification_service().send_group_invite(
        to_email=invited_email,
        group_name=group.name,
        inviter_name=inviter.name,
        invite_url=build_invite_url(token),
    )
    return InviteCreatedOut(
        id=invite.id,
        group_id=invite.group_id,
        invited_email=invite.invited_email,
        token=token,
        invite_url=invite_url,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


def list_group_invites(db: Session, group_id: uuid.UUID) -> list[InviteOut]:
    now = utcnow()
    return [
        _to_invite_out(invite, now=now)
        for invite in invite_repo.list_for_group(db, group_id)
    ]


def _require_invite(db: Session, token: str) -> GroupInvite:
    invite = invite_repo.get_by_token_hash(db, hash_invite_token(token))
    if invite is None:
        raise NotFound("Приглашение не найдено")
    return invite


def preview_invite(db: Session, token: str, viewer: User | None) -> InvitePreviewOut:
    """Unauthenticated landing-page data: enough to recognise the group, nothing more.

    An expired or spent invite still previews — the page needs the status to explain
    itself instead of showing a bare error.
    """
    invite = _require_invite(db, token)
    group = invite.group
    return InvitePreviewOut(
        group=InviteGroupPreview(
            id=group.id,
            name=group.name,
            description=group.description,
            currency=group.currency,
            member_count=group_repo.member_count(db, group.id),
        ),
        inviter=invite.inviter,
        invited_email=invite.invited_email,
        expires_at=invite.expires_at,
        status=invite_status(invite),
        already_member=viewer is not None
        and group_repo.is_member(db, group.id, viewer.id),
    )


def accept_invite(db: Session, token: str, user: User) -> GroupOut:
    """Join the invited group. The signed-in email need not match ``invited_email``
    — it is a shareable link, not an address-bound token."""
    invite = _require_invite(db, token)
    group = invite.group

    # Membership is checked before the invite's own state so that re-opening the
    # link after joining is idempotent rather than "already used".
    if group_repo.is_member(db, group.id, user.id):
        return group_service.build_group_out(db, group, user.id)

    status = invite_status(invite)
    if status == "accepted":
        raise BadRequest("Приглашение уже использовано")
    if status == "expired":
        raise BadRequest("Срок действия приглашения истёк")

    invite.accepted_at = utcnow()
    invite.accepted_by = user.id
    group_service.add_member(db, group=group, user=user)
    log_activity(
        db,
        group_id=group.id,
        actor_id=user.id,
        type=ActivityType.MEMBER_JOINED,
        entity_id=user.id,
        meta={"member_name": user.name, "invited_email": invite.invited_email},
    )
    db.commit()
    return group_service.build_group_out(db, group, user.id)


def delete_invite(db: Session, invite_id: uuid.UUID, user: User) -> None:
    invite = invite_repo.get(db, invite_id)
    if invite is None:
        raise NotFound("Приглашение не найдено")
    membership = group_repo.get_membership(db, invite.group_id, user.id)
    is_owner = membership is not None and membership.role == GroupRole.OWNER.value
    if invite.inviter_id != user.id and not is_owner:
        raise Forbidden("Отменить приглашение может только автор приглашения или владелец группы")
    invite_repo.delete(db, invite)
    db.commit()


__all__ = [
    "accept_invite",
    "create_invite",
    "delete_invite",
    "invite_status",
    "list_group_invites",
    "preview_invite",
]

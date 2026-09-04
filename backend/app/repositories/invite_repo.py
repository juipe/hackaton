from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.invite import GroupInvite


def get(db: Session, invite_id: uuid.UUID) -> GroupInvite | None:
    return db.get(GroupInvite, invite_id)


def get_by_token_hash(db: Session, token_hash: str) -> GroupInvite | None:
    """The only way to resolve an invite from a link: the raw token is never stored."""
    stmt = (
        select(GroupInvite)
        .options(joinedload(GroupInvite.inviter), joinedload(GroupInvite.group))
        .where(GroupInvite.token_hash == token_hash)
    )
    return db.scalar(stmt)


def list_for_group(db: Session, group_id: uuid.UUID) -> list[GroupInvite]:
    stmt = (
        select(GroupInvite)
        .options(joinedload(GroupInvite.inviter))
        .where(GroupInvite.group_id == group_id)
        .order_by(GroupInvite.created_at.desc(), GroupInvite.id.desc())
    )
    return list(db.scalars(stmt))


def create(
    db: Session,
    *,
    group_id: uuid.UUID,
    inviter_id: uuid.UUID,
    invited_email: str,
    token_hash: str,
    expires_at: datetime,
) -> GroupInvite:
    invite = GroupInvite(
        group_id=group_id,
        inviter_id=inviter_id,
        invited_email=invited_email,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(invite)
    db.flush()
    return invite


def delete(db: Session, invite: GroupInvite) -> None:
    db.delete(invite)
    db.flush()


__all__ = ["create", "delete", "get", "get_by_token_hash", "list_for_group"]

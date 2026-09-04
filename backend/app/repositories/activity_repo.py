from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.activity import Activity
from app.models.group import Group
from app.models.member import GroupMember


def list_for_group(
    db: Session, group_id: uuid.UUID, *, limit: int = 20, offset: int = 0
) -> list[Activity]:
    stmt = (
        select(Activity)
        .options(joinedload(Activity.actor), joinedload(Activity.group))
        .where(Activity.group_id == group_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).unique())


def list_for_user(
    db: Session, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
) -> list[Activity]:
    """Activity across every group the user currently belongs to."""
    stmt = (
        select(Activity)
        .options(joinedload(Activity.actor), joinedload(Activity.group))
        .join(GroupMember, GroupMember.group_id == Activity.group_id)
        .join(Group, Group.id == Activity.group_id)
        .where(GroupMember.user_id == user_id)
        .order_by(Activity.created_at.desc(), Activity.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).unique())


__all__ = ["list_for_group", "list_for_user"]

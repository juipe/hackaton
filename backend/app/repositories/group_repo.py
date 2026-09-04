from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.group import Group
from app.models.member import GroupMember


def get(db: Session, group_id: uuid.UUID) -> Group | None:
    return db.get(Group, group_id)


def list_for_user(db: Session, user_id: uuid.UUID) -> list[Group]:
    stmt = (
        select(Group)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.user_id == user_id)
        .order_by(Group.created_at.desc())
    )
    return list(db.scalars(stmt))


def list_group_ids_for_user(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    return list(db.scalars(stmt))


def list_members(db: Session, group_id: uuid.UUID) -> list[GroupMember]:
    stmt = (
        select(GroupMember)
        .options(joinedload(GroupMember.user))
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at, GroupMember.id)
    )
    return list(db.scalars(stmt).unique())


def list_member_ids(db: Session, group_id: uuid.UUID) -> list[uuid.UUID]:
    stmt = (
        select(GroupMember.user_id)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at)
    )
    return list(db.scalars(stmt))


def get_membership(db: Session, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember | None:
    return db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )


def is_member(db: Session, group_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return get_membership(db, group_id, user_id) is not None


def member_count(db: Session, group_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group_id)
        )
        or 0
    )


def member_counts(db: Session, group_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """One query for many groups, so group lists stay O(1) in round-trips."""
    if not group_ids:
        return {}
    stmt = (
        select(GroupMember.group_id, func.count())
        .where(GroupMember.group_id.in_(group_ids))
        .group_by(GroupMember.group_id)
    )
    counts = dict(db.execute(stmt).all())
    return {group_id: int(counts.get(group_id, 0)) for group_id in group_ids}


__all__ = [
    "get",
    "get_membership",
    "is_member",
    "list_for_user",
    "list_group_ids_for_user",
    "list_member_ids",
    "list_members",
    "member_count",
    "member_counts",
]

"""FastAPI dependencies: the session, the current user, and group authorization.

Every group-scoped endpoint depends on ``require_membership`` or ``require_owner``,
so authorization is impossible to forget in a route handler.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.group import Group
from app.models.member import GroupMember, GroupRole
from app.models.user import User

DbSession = Annotated[Session, Depends(get_db)]


def _user_from_request(request: Request, db: Session) -> User | None:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return db.get(User, user_id)


def get_optional_user(request: Request, db: DbSession) -> User | None:
    """Current user when signed in, ``None`` otherwise. Never raises."""
    return _user_from_request(request, db)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(request: Request, db: DbSession) -> User:
    user = _user_from_request(request, db)
    if user is None:
        raise Unauthorized("Требуется вход")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _get_membership(db: Session, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember | None:
    return db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id, GroupMember.user_id == user_id
        )
    )


def require_membership(group_id: uuid.UUID, db: DbSession, user: CurrentUser) -> GroupMember:
    """Membership of ``group_id``, or 404/403.

    A non-member gets 403 rather than 404 only once the group is known to exist;
    for a group that does not exist at all the answer is 404 either way, so no
    information about other people's groups leaks.
    """
    if db.get(Group, group_id) is None:
        raise NotFound("Группа не найдена")
    membership = _get_membership(db, group_id, user.id)
    if membership is None:
        raise Forbidden("Вы не участник этой группы")
    return membership


Membership = Annotated[GroupMember, Depends(require_membership)]


def require_owner(group_id: uuid.UUID, db: DbSession, user: CurrentUser) -> GroupMember:
    membership = require_membership(group_id, db, user)
    if membership.role != GroupRole.OWNER.value:
        raise Forbidden("Это может сделать только владелец группы")
    return membership


OwnerMembership = Annotated[GroupMember, Depends(require_owner)]


def assert_membership(db: Session, group_id: uuid.UUID, user_id: uuid.UUID) -> GroupMember:
    """Imperative form of :func:`require_membership`, for services."""
    if db.get(Group, group_id) is None:
        raise NotFound("Группа не найдена")
    membership = _get_membership(db, group_id, user_id)
    if membership is None:
        raise Forbidden("Вы не участник этой группы")
    return membership


__all__ = [
    "CurrentUser",
    "DbSession",
    "Membership",
    "OptionalUser",
    "OwnerMembership",
    "assert_membership",
    "get_current_user",
    "get_optional_user",
    "require_membership",
    "require_owner",
]

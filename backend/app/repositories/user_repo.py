from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def list_by_ids(db: Session, user_ids: Iterable[uuid.UUID]) -> list[User]:
    ids = list(user_ids)
    if not ids:
        return []
    return list(db.scalars(select(User).where(User.id.in_(ids))))


def map_by_ids(db: Session, user_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, User]:
    return {user.id: user for user in list_by_ids(db, user_ids)}


def create(db: Session, *, name: str, email: str, password_hash: str) -> User:
    user = User(name=name.strip(), email=email.strip().lower(), password_hash=password_hash)
    db.add(user)
    db.flush()
    return user


__all__ = ["create", "get", "get_by_email", "list_by_ids", "map_by_ids"]

from __future__ import annotations

import uuid

from app.schemas.common import ORMModel


class UserPublic(ORMModel):
    """Единственный вид, в котором пользователь уходит наружу: без хеша пароля."""

    id: uuid.UUID
    name: str
    email: str


__all__ = ["UserPublic"]

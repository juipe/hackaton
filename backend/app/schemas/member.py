"""Group membership response schema."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import field_validator

from app.schemas.common import ORMModel
from app.schemas.user import UserPublic
from app.utils.time import ensure_utc


class MemberOut(ORMModel):
    """Участник группы вместе с профилем. ``id`` — идентификатор участия, не пользователя."""

    id: uuid.UUID
    user: UserPublic
    role: str
    joined_at: datetime

    @field_validator("joined_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite hands back naive datetimes; the API always emits an offset.
        return ensure_utc(value)


__all__ = ["MemberOut"]

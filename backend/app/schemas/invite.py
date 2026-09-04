"""Invite request and response shapes.

``InviteCreatedOut`` is the only schema that ever carries the raw token, which is
why it is a separate model from ``InviteOut`` rather than an optional field on it —
the listing endpoint physically cannot leak a token.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, EmailStr, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.user import UserPublic
from app.utils.time import ensure_utc

#: ``accepted`` outranks ``expired``: a used invite never turns back into a deadline.
InviteStatus = Literal["pending", "accepted", "expired"]


def _to_utc(value: object) -> object:
    """SQLite returns ``DateTime(timezone=True)`` columns naive, so re-attach UTC
    before serialization — every timestamp on the wire carries an offset."""
    if isinstance(value, datetime):
        return ensure_utc(value)
    return value


UtcDatetime = Annotated[datetime, BeforeValidator(_to_utc)]
NullableUtcDatetime = Annotated[datetime | None, BeforeValidator(_to_utc)]


class InviteCreate(BaseModel):
    """Приглашение по адресу электронной почты."""

    email: Annotated[
        EmailStr, Field(max_length=320, description="Кого приглашаем — адрес почты")
    ]

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class InviteCreatedOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    invited_email: str
    token: str
    invite_url: str
    expires_at: UtcDatetime
    created_at: UtcDatetime


class InviteOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    invited_email: str
    inviter: UserPublic
    expires_at: UtcDatetime
    accepted_at: NullableUtcDatetime
    status: InviteStatus
    created_at: UtcDatetime


class InviteGroupPreview(ORMModel):
    """Что приглашённый видит о группе до того, как вступит в неё."""

    id: uuid.UUID
    name: str
    description: str | None
    currency: str
    member_count: int


class InvitePreviewOut(ORMModel):
    group: InviteGroupPreview
    inviter: UserPublic
    invited_email: str
    expires_at: UtcDatetime
    status: InviteStatus
    already_member: bool


__all__ = [
    "InviteCreate",
    "InviteCreatedOut",
    "InviteGroupPreview",
    "InviteOut",
    "InvitePreviewOut",
    "InviteStatus",
]

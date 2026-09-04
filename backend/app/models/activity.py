from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, uuid_pk
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User


class ActivityType(str, Enum):
    GROUP_CREATED = "group_created"
    GROUP_UPDATED = "group_updated"
    MEMBER_JOINED = "member_joined"
    MEMBER_REMOVED = "member_removed"
    EXPENSE_CREATED = "expense_created"
    EXPENSE_UPDATED = "expense_updated"
    EXPENSE_DELETED = "expense_deleted"
    PAYMENT_CREATED = "payment_created"
    INVITE_CREATED = "invite_created"
    DEBT_SIMPLIFIED = "debt_simplified"


class Activity(Base):
    """Append-only group event log powering the activity feed."""

    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # `metadata` is reserved on declarative classes, so the attribute is `meta`
    # while the database column keeps the name the contract specifies.
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )

    group: Mapped[Group] = relationship()
    actor: Mapped[User] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Activity {self.type} group={self.group_id}>"


__all__ = ["Activity", "ActivityType"]

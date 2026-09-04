from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, uuid_pk
from app.utils.time import utcnow

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User


class GroupRole(str, Enum):
    OWNER = "owner"
    MEMBER = "member"


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=GroupRole.MEMBER.value)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    group: Mapped[Group] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")

    @property
    def is_owner(self) -> bool:
        return self.role == GroupRole.OWNER.value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<GroupMember group={self.group_id} user={self.user_id} role={self.role}>"


__all__ = ["GroupMember", "GroupRole"]

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, updated_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.member import GroupMember
    from app.models.user import User


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    members: Mapped[list[GroupMember]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GroupMember.joined_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Group {self.name}>"


__all__ = ["Group"]

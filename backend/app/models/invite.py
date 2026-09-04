from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.group import Group
    from app.models.user import User


class GroupInvite(Base):
    """A link-based invitation to join a group.

    Only ``token_hash`` is stored; the raw token exists exactly once, in the HTTP
    response that created the invite. That keeps a database leak from being
    replayable and keeps internal ids out of the URL.
    """

    __tablename__ = "group_invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    inviter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invited_email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at_column()

    group: Mapped[Group] = relationship()
    inviter: Mapped[User] = relationship(foreign_keys=[inviter_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<GroupInvite {self.invited_email} group={self.group_id}>"


__all__ = ["GroupInvite"]

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, updated_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.member import GroupMember


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Disposable monthly budget/income, in cents. NULL means the critical-budget
    # feature is off for this user — see app.services.budget_threshold_service.
    monthly_budget_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Last threshold state this user was notified for: None / "approaching" /
    # "exceeded". Only a state *change* creates a new notification, so this is
    # the whole dedup mechanism — see budget_threshold_service.
    budget_alert_state: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    memberships: Mapped[list[GroupMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"


__all__ = ["User"]

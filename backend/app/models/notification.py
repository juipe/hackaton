from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class Notification(Base):
    """A debt reminder for one debtor on one expense.

    Every display field (``expense_title``, ``payer_name``, ``group_name``,
    ``amount_due_cents``) is a snapshot taken when the expense was committed,
    not a live join — the reminder describes what happened at that moment, so
    a later rename of the expense or the group must not change it. ``message``
    is filled with a deterministic fallback immediately, then may be replaced
    by a Qwen-generated one in the background (see
    ``app.services.debt_reminder_service``); either way the row exists — and
    is visible once ``available_at`` passes — the instant the expense commits.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_notifications_expense_user"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    payer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expense_title: Mapped[str] = mapped_column(String(160), nullable=False)
    payer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False)
    amount_due_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # "fallback" until the background Qwen call (if any) replaces the message —
    # not exposed over the API, just lets tests and operators see which path a
    # given reminder took.
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="fallback")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = created_at_column()
    # The reminder becomes visible to the debtor only once "now" passes this —
    # see module docstring and app.services.debt_reminder_service.
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    payer: Mapped[User] = relationship(foreign_keys=[payer_id])

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Notification user={self.user_id} expense={self.expense_id}>"


__all__ = ["Notification"]

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class Payment(Base):
    """A settle-up: ``from_user`` handed ``amount_cents`` to ``to_user``.

    This is a record of a transfer that happened outside the app — there is no
    payment provider integration. It feeds the balance ledger like an expense does.
    """

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        CheckConstraint("from_user_id <> to_user_id", name="ck_payments_distinct_users"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    to_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    note: Mapped[str | None] = mapped_column(String(280), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_column()

    from_user: Mapped[User] = relationship(foreign_keys=[from_user_id], lazy="joined")
    to_user: Mapped[User] = relationship(foreign_keys=[to_user_id], lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Payment {self.from_user_id}->{self.to_user_id} {self.amount_cents}>"


__all__ = ["Payment"]

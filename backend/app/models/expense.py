from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, created_at_column, updated_at_column, uuid_pk

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.user import User


class SplitMode(str, Enum):
    EQUAL = "equal"
    EXACT = "exact"
    PERCENTAGE = "percentage"
    SHARES = "shares"


class Expense(Base):
    """A shared cost. ``amount_cents`` is integer minor units — never a float."""

    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="ck_expenses_amount_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    group_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RUB")
    category_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False
    )
    paid_by: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    split_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SplitMode.EQUAL.value
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    splits: Mapped[list[ExpenseSplit]] = relationship(
        back_populates="expense",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
    category: Mapped[Category] = relationship(lazy="joined")
    payer: Mapped[User] = relationship(foreign_keys=[paid_by], lazy="joined")
    creator: Mapped[User] = relationship(foreign_keys=[created_by], lazy="joined")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Expense {self.title} {self.amount_cents}>"


class ExpenseSplit(Base):
    """One participant's share of an expense.

    ``input_value`` keeps whatever the user typed (cents / percent / shares) so the
    edit form can be re-hydrated exactly; ``calculated_amount_cents`` is what the
    balance engine reads. The two are recomputed together, never edited apart.
    """

    __tablename__ = "expense_splits"
    __table_args__ = (
        UniqueConstraint("expense_id", "user_id", name="uq_expense_splits_expense_user"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    expense_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("expenses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    split_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    input_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    calculated_amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)

    expense: Mapped[Expense] = relationship(back_populates="splits")
    user: Mapped[User] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<ExpenseSplit user={self.user_id} {self.calculated_amount_cents}>"


__all__ = ["Expense", "ExpenseSplit", "SplitMode"]

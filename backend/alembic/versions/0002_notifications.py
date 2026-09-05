"""Add notifications table.

Debt reminders created when an expense is committed — one row per debtor per
expense. See ``app.models.notification.Notification``.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_notifications"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expense_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("payer_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expense_title", sa.String(length=160), nullable=False),
        sa.Column("payer_name", sa.String(length=120), nullable=False),
        sa.Column("group_name", sa.String(length=120), nullable=False),
        sa.Column("amount_due_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_notifications_expense_user"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_expense_id", "notifications", ["expense_id"])
    op.create_index("ix_notifications_available_at", "notifications", ["available_at"])


def downgrade() -> None:
    op.drop_index("ix_notifications_available_at", table_name="notifications")
    op.drop_index("ix_notifications_expense_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")

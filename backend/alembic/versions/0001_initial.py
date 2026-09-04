"""Initial Skladchina schema.

Creates the nine tables the ORM declares. Category rows are deliberately not
inserted here: ``app.db.seed.ensure_categories`` owns that data and runs on every
application startup, so a migration-inserted copy would only be able to drift.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("icon", sa.String(length=40), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "groups",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "group_members",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"], unique=False)
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"], unique=False)

    op.create_table(
        "group_invites",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("inviter_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["accepted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_invites_group_id", "group_invites", ["group_id"], unique=False)
    op.create_index("ix_group_invites_token_hash", "group_invites", ["token_hash"], unique=False)

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("category_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("paid_by", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("split_mode", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount_cents > 0", name="ck_expenses_amount_positive"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_expenses_group_id", "expenses", ["group_id"], unique=False)
    op.create_index("ix_expenses_occurred_at", "expenses", ["occurred_at"], unique=False)
    op.create_index("ix_expenses_paid_by", "expenses", ["paid_by"], unique=False)

    op.create_table(
        "expense_splits",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("expense_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("split_mode", sa.String(length=16), nullable=False),
        sa.Column("input_value", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("calculated_amount_cents", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["expense_id"], ["expenses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_id", "user_id", name="uq_expense_splits_expense_user"),
    )
    op.create_index("ix_expense_splits_expense_id", "expense_splits", ["expense_id"], unique=False)
    op.create_index("ix_expense_splits_user_id", "expense_splits", ["user_id"], unique=False)

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("from_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("to_user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("note", sa.String(length=280), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive"),
        sa.CheckConstraint("from_user_id <> to_user_id", name="ck_payments_distinct_users"),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payments_group_id", "payments", ["group_id"], unique=False)

    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_activities_created_at", "activities", ["created_at"], unique=False)
    op.create_index("ix_activities_group_id", "activities", ["group_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_activities_group_id", table_name="activities")
    op.drop_index("ix_activities_created_at", table_name="activities")
    op.drop_table("activities")

    op.drop_index("ix_payments_group_id", table_name="payments")
    op.drop_table("payments")

    op.drop_index("ix_expense_splits_user_id", table_name="expense_splits")
    op.drop_index("ix_expense_splits_expense_id", table_name="expense_splits")
    op.drop_table("expense_splits")

    op.drop_index("ix_expenses_paid_by", table_name="expenses")
    op.drop_index("ix_expenses_occurred_at", table_name="expenses")
    op.drop_index("ix_expenses_group_id", table_name="expenses")
    op.drop_table("expenses")

    op.drop_index("ix_group_invites_token_hash", table_name="group_invites")
    op.drop_index("ix_group_invites_group_id", table_name="group_invites")
    op.drop_table("group_invites")

    op.drop_index("ix_group_members_user_id", table_name="group_members")
    op.drop_index("ix_group_members_group_id", table_name="group_members")
    op.drop_table("group_members")

    op.drop_table("groups")
    op.drop_table("categories")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

"""Critical budget threshold: user budget/income + generalized notifications.

Adds ``users.monthly_budget_cents`` (optional disposable-budget/income figure)
and ``users.budget_alert_state`` (dedup state for the threshold check — see
``app.services.budget_threshold_service``). Both default to NULL, so every
existing user is unaffected and gets no threshold checks until they opt in.

Also generalizes ``notifications`` beyond debt reminders: a ``type`` column
(defaulting existing rows to ``"debt_reminder"``) and nullable
``expense_id``/``group_id``/``payer_id``/``expense_title``/``payer_name``/
``group_name`` — a budget-threshold notification has no single expense, payer
or group to anchor to.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_budget_threshold"
down_revision: str | None = "0002_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("monthly_budget_cents", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("budget_alert_state", sa.String(length=16), nullable=True))

    op.add_column(
        "notifications",
        sa.Column(
            "type", sa.String(length=24), nullable=False, server_default="debt_reminder"
        ),
    )
    op.alter_column("notifications", "type", server_default=None)

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column("expense_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)
        batch_op.alter_column("group_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)
        batch_op.alter_column("payer_id", existing_type=sa.Uuid(as_uuid=True), nullable=True)
        batch_op.alter_column(
            "expense_title", existing_type=sa.String(length=160), nullable=True
        )
        batch_op.alter_column(
            "payer_name", existing_type=sa.String(length=120), nullable=True
        )
        batch_op.alter_column(
            "group_name", existing_type=sa.String(length=120), nullable=True
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.alter_column(
            "group_name", existing_type=sa.String(length=120), nullable=False
        )
        batch_op.alter_column(
            "payer_name", existing_type=sa.String(length=120), nullable=False
        )
        batch_op.alter_column(
            "expense_title", existing_type=sa.String(length=160), nullable=False
        )
        batch_op.alter_column("payer_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)
        batch_op.alter_column("group_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)
        batch_op.alter_column("expense_id", existing_type=sa.Uuid(as_uuid=True), nullable=False)

    op.drop_column("notifications", "type")
    op.drop_column("users", "budget_alert_state")
    op.drop_column("users", "monthly_budget_cents")

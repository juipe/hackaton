"""Add users.monthly_budget_cents.

«Критическая точка бюджета»: свободная сумма пользователя на месяц в копейках.
NULL — лимит не задан, проверка бюджета не выполняется.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_user_budget"
down_revision: str | None = "0002_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("monthly_budget_cents", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "monthly_budget_cents")

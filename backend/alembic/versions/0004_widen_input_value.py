"""Widen expense_splits.input_value to hold a full cents amount.

``NUMERIC(12, 6)`` only leaves 6 integer digits, but "exact" split mode stores
the raw cents amount in this column (see ``app.services.split_engine._split_exact``)
and that has to match ``calculated_amount_cents`` (``BigInteger``, up to 19
digits) — a value like 34 000 000 cents already overflowed the old column.
Widened to ``NUMERIC(25, 6)``: 19 integer digits (enough for any BigInteger
cents amount) plus the 6 fractional digits percentage mode still needs.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_widen_input_value"
down_revision: str | None = "0003_budget_threshold"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "expense_splits",
        "input_value",
        existing_type=sa.Numeric(precision=12, scale=6),
        type_=sa.Numeric(precision=25, scale=6),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "expense_splits",
        "input_value",
        existing_type=sa.Numeric(precision=25, scale=6),
        type_=sa.Numeric(precision=12, scale=6),
        existing_nullable=True,
    )

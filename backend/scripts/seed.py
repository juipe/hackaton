"""Command line entry point for the demo seed.

Works both as ``python -m scripts.seed`` and ``python scripts/seed.py`` from the
backend directory, because a reviewer will reach for whichever comes to mind first.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path


def _plural(count: int, one: str, few: str, many: str) -> str:
    """Russian plural agreement, the same rule the frontend ``plural`` uses."""
    if count % 10 == 1 and count % 100 != 11:
        return one
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return few
    return many


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="seed",
        description="Создать демо-мир «Складчины»: люди, группы, расходы, переводы.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Сначала удалить демо-пользователей и их группы, затем собрать заново.",
    )
    return parser.parse_args(argv)


def _ensure_importable() -> None:
    """Put the backend directory on ``sys.path``.

    Running the file by path starts with ``scripts/`` on the path instead of the
    project root, so ``import app`` would fail without this.
    """
    root = str(Path(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(name)s: %(message)s")
    # The summary prints currency symbols, which a legacy Windows code page cannot
    # encode; replacing them beats a traceback after the data is already committed.
    sys.stdout.reconfigure(errors="replace")
    _ensure_importable()

    # Imported after the path fix so the script also works when run by file path.
    from sqlalchemy import func, select

    from app import models  # noqa: F401  — registers every mapper for create_all
    from app.db.base import Base
    from app.db.seed import (
        DEMO_GROUP_NAMES,
        DEMO_PASSWORD,
        DEMO_USERS,
        ensure_categories,
        seed_demo_data,
    )
    from app.db.session import SessionLocal, engine
    from app.models.expense import Expense
    from app.models.group import Group
    from app.models.member import GroupMember
    from app.models.payment import Payment
    from app.utils.money import format_money

    # Migrations are the supported path; this keeps a bare `docker compose up` or a
    # throwaway SQLite file working when they have not been run.
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        ensure_categories(db)
        seed_demo_data(db, reset=args.reset)
        db.commit()

        groups = list(
            db.scalars(
                select(Group)
                .where(Group.name.in_(DEMO_GROUP_NAMES))
                .order_by(Group.created_at)
            )
        )
        rows: list[tuple[Group, int, int, int]] = []
        for group in groups:
            member_count = db.scalar(
                select(func.count())
                .select_from(GroupMember)
                .where(GroupMember.group_id == group.id)
            )
            expense_count = db.scalar(
                select(func.count())
                .select_from(Expense)
                .where(Expense.group_id == group.id, Expense.deleted_at.is_(None))
            )
            spending = db.scalar(
                select(func.coalesce(func.sum(Expense.amount_cents), 0)).where(
                    Expense.group_id == group.id, Expense.deleted_at.is_(None)
                )
            )
            rows.append(
                (group, int(member_count or 0), int(expense_count or 0), int(spending or 0))
            )
        payment_count = int(
            db.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.group_id.in_([group.id for group in groups]))
            )
            or 0
        )

    total_expenses = sum(row[2] for row in rows)
    print()
    print("Демо-данные «Складчины» готовы.")
    print()
    print(f"  Входите под любым из аккаунтов. Пароль: {DEMO_PASSWORD}")
    for spec in DEMO_USERS:
        print(f"    {spec.email:<22} {spec.name}")
    print()
    print("  Группы")
    for group, member_count, expense_count, spending in rows:
        members = _plural(member_count, "участник", "участника", "участников")
        expenses = _plural(expense_count, "расход", "расхода", "расходов")
        print(
            f"    {group.name:<21}"
            f"{member_count} {members:<11}"
            f"{expense_count:>2} {expenses:<9}"
            f"на {format_money(spending, group.currency)}"
        )
    print()
    print(
        f"  Всего {total_expenses} "
        f"{_plural(total_expenses, 'расход', 'расхода', 'расходов')} и "
        f"{payment_count} "
        f"{_plural(payment_count, 'перевод', 'перевода', 'переводов')} "
        f"в {len(rows)} {_plural(len(rows), 'группе', 'группах', 'группах')}."
    )
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

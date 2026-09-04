"""AI saving tips for the dashboard.

Deliberately does not re-implement any aggregate: it calls the existing
:mod:`app.services.dashboard_service` functions for the same period/group
scope the dashboard itself uses, trims the result down to the fields that are
actually useful for a saving recommendation, and hands that to Qwen via
``ollama_service.generate_saving_tips``. No member/debt/balance data and no
ids ever leave this module — only spending totals, category shares and a
monthly series.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.dashboard import CategoryBreakdownOut, DashboardSummaryOut, SpendingOverTimeOut
from app.schemas.saving_tips import (
    SavingTip,
    SavingTipsCategoryInput,
    SavingTipsInput,
    SavingTipsMonthInput,
    SavingTipsOut,
)
from app.services import dashboard_service, ollama_service

#: Used both when there isn't enough spending data to say anything personal,
#: and as the safety net when Ollama is unreachable or misbehaves — the
#: dashboard must never break because the local model did.
FALLBACK_TIPS = SavingTipsOut(
    tips=[
        SavingTip(
            title="Ведите учёт регулярных трат",
            text="Записывайте расходы по мере появления — так проще увидеть, куда уходит "
            "основная часть денег.",
            type="generic",
        ),
        SavingTip(
            title="Установите лимит на необязательные покупки",
            text="Определите недельный или месячный лимит на переменные расходы и "
            "старайтесь его не превышать.",
            type="generic",
        ),
        SavingTip(
            title="Сравнивайте цены перед крупной покупкой",
            text="Перед значимой тратой сравните предложения в нескольких местах — "
            "это часто позволяет сэкономить.",
            type="generic",
        ),
    ]
)


def _build_input(
    summary: DashboardSummaryOut,
    category_breakdown: CategoryBreakdownOut,
    over_time: SpendingOverTimeOut,
) -> SavingTipsInput:
    return SavingTipsInput(
        total_spending_cents=summary.total_spending_cents,
        expense_count=summary.expense_count,
        currency=summary.currency,
        categories=[
            SavingTipsCategoryInput(
                name=item.name,
                amount_cents=item.amount_cents,
                percentage=item.percentage,
                expense_count=item.expense_count,
            )
            for item in category_breakdown.items
        ],
        months=[
            SavingTipsMonthInput(
                month=point.month,
                amount_cents=point.amount_cents,
                your_share_cents=point.your_share_cents,
            )
            for point in over_time.items
        ],
    )


def generate(
    db: Session,
    *,
    user: User,
    period: str = "all",
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
) -> SavingTipsOut:
    # Each call below re-runs the dashboard's own period/group resolution — it
    # also raises the same 400/403/404 the dashboard endpoints do for a bad
    # period or a group the caller doesn't belong to.
    summary = dashboard_service.summary(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    if summary.expense_count == 0:
        return FALLBACK_TIPS

    category_breakdown = dashboard_service.spending_by_category(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    over_time = dashboard_service.spending_over_time(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )

    payload = _build_input(summary, category_breakdown, over_time)
    try:
        return ollama_service.generate_saving_tips(payload)
    except ollama_service.OllamaError:
        return FALLBACK_TIPS


__all__ = ["FALLBACK_TIPS", "generate"]

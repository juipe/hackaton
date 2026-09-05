"""AI saving tips for the dashboard.

Deliberately does not re-implement any aggregate: it calls the existing
:mod:`app.services.dashboard_service` functions for the same period/group
scope the dashboard itself uses, trims the result down to the fields that are
actually useful for a saving recommendation, and hands that to Qwen via
``ollama_service.generate_saving_tips``. No member/debt/balance data and no
ids ever leave this module — only spending totals, category shares and a
two-month trend.

Every number in that payload is pre-formatted here, in Python, before Qwen
ever sees it: cents-to-rubles conversion, percentages and the month-to-month
change are all computed with :class:`~decimal.Decimal` and
:func:`app.utils.money.format_money`, never left for the model to work out.
Qwen only copies the resulting strings into prose — it cannot mis-convert,
round, or invent a number it was never asked to calculate in the first place.
See the real-world failures this fixes: a 70 RUB change reported as "19,000
RUB", 5 RUB reported as "500 RUB", and a 220->300 RUB change reported with
the wrong units and percentage.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.dashboard import CategoryBreakdownOut, DashboardSummaryOut, SpendingOverTimeOut
from app.schemas.saving_tips import (
    SavingTip,
    SavingTipsCategoryInput,
    SavingTipsInput,
    SavingTipsOut,
    SavingTipsTrend,
)
from app.services import dashboard_service, ollama_service
from app.utils.money import format_money

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

_PERCENT_ONE_DP = Decimal("0.1")


def _format_percentage(value: float) -> str:
    """``76.92`` -> ``'76,9%'``; a whole number drops its decimal (``'100%'``)."""
    quantized = Decimal(str(value)).quantize(_PERCENT_ONE_DP, rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if text.endswith(".0"):
        text = text[:-2]
    return f"{text.replace('.', ',')}%"


def _format_signed_percentage(value: Decimal) -> str:
    """Like :func:`_format_percentage` but always shows a leading sign."""
    quantized = value.quantize(_PERCENT_ONE_DP, rounding=ROUND_HALF_UP)
    text = format(quantized, "f")
    if text.endswith(".0"):
        text = text[:-2]
    sign = "+" if quantized >= 0 else ""
    return f"{sign}{text.replace('.', ',')}%"


def _build_trend(over_time: SpendingOverTimeOut, currency: str) -> SavingTipsTrend | None:
    """Total spending, previous month vs. latest month — or ``None``.

    Only built when there are at least two months of data *and* the earlier
    month has nonzero spending (otherwise "percent change" is undefined) —
    this is exactly the condition the system prompt tells Qwen it may talk
    about a trend under, so the model is never left to decide for itself
    whether a comparison is safe to make.
    """
    items = over_time.items
    if len(items) < 2:
        return None
    previous, latest = items[-2], items[-1]
    if previous.amount_cents <= 0:
        return None
    change = Decimal(latest.amount_cents - previous.amount_cents) * 100 / Decimal(
        previous.amount_cents
    )
    return SavingTipsTrend(
        from_label=previous.label,
        to_label=latest.label,
        from_display=format_money(previous.amount_cents, currency),
        to_display=format_money(latest.amount_cents, currency),
        change_display=_format_signed_percentage(change),
    )


def _build_input(
    summary: DashboardSummaryOut,
    category_breakdown: CategoryBreakdownOut,
    over_time: SpendingOverTimeOut,
) -> SavingTipsInput:
    return SavingTipsInput(
        total_spending_display=format_money(summary.total_spending_cents, summary.currency),
        expense_count=summary.expense_count,
        currency=summary.currency,
        categories=[
            SavingTipsCategoryInput(
                name=item.name,
                amount_display=format_money(item.amount_cents, summary.currency),
                percentage_display=_format_percentage(item.percentage),
                expense_count=item.expense_count,
            )
            for item in category_breakdown.items
        ],
        trend=_build_trend(over_time, summary.currency),
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

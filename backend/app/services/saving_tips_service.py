"""AI saving tips for the dashboard.

Deliberately does not re-implement any aggregate: it calls the existing
:mod:`app.services.dashboard_service` functions for the same period/group
scope the dashboard itself uses, trims the result down to the fields that are
actually useful for a saving recommendation, and hands that to the LLM via
``gigachat_service.generate_saving_tips``. No member/debt/balance data and no
ids ever leave this module — only spending totals, category shares and a
two-month trend.

Every number in that payload is pre-formatted here, in Python, before the model
ever sees it: cents-to-rubles conversion, percentages and the month-to-month
change are all computed with :class:`~decimal.Decimal` and
:func:`app.utils.money.format_money`, never left for the model to work out.
The model only copies the resulting strings into prose — it cannot mis-convert,
round, or invent a number it was never asked to calculate in the first place.
See the real-world failures this fixes: a 70 RUB change reported as "19,000
RUB", 5 RUB reported as "500 RUB", and a 220->300 RUB change reported with
the wrong units and percentage.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.dashboard import CategoryBreakdownOut, DashboardSummaryOut, SpendingOverTimeOut
from app.schemas.saving_tips import (
    PotentialSavings,
    PotentialSavingsItem,
    SavingTip,
    SavingTipsCategoryInput,
    SavingTipsInput,
    SavingTipsOut,
    SavingTipsTrend,
)
from app.services import dashboard_service, gigachat_service
from app.utils.money import format_money

#: Every saving-tips request logs exactly one outcome line here, so which of
#: the two fallback branches fired is never a guess. Nothing secret is logged:
#: only the caller's user id, the requested scope, and aggregate counts.
logger = logging.getLogger("skladchina.saving_tips")

#: Used both when there isn't enough spending data to say anything personal,
#: and as the safety net when GigaChat is unreachable or misbehaves — the
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

#: «Необязательные» категории для блока «можно сэкономить»: кафе и рестораны,
#: развлечения, подписки и покупки. Жильё/аренда/ЖКХ/продукты/здоровье/транспорт
#: сэкономить «просто отказавшись» нельзя, поэтому их тут нет.
DISCRETIONARY_SLUGS = frozenset({"food", "entertainment", "subscriptions", "shopping"})

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
    this is exactly the condition the system prompt tells the model it may talk
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


def _build_potential_savings(
    db: Session,
    *,
    user: User,
    period: str,
    date_from: date | None,
    date_to: date | None,
    group_id: uuid.UUID | None,
    currency: str,
) -> PotentialSavings | None:
    """Личные траты по необязательным категориям — или ``None``, если их нет.

    Считается целиком в Python из долей пользователя, поэтому блок живёт и при
    fallback-советах: провайдер к этим числам отношения не имеет.
    """
    items = dashboard_service.user_share_by_category(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    discretionary = [
        item for item in items if item.slug in DISCRETIONARY_SLUGS and item.amount_cents > 0
    ]
    if not discretionary:
        return None
    return PotentialSavings(
        total_cents=sum(item.amount_cents for item in discretionary),
        currency=currency,
        items=[
            PotentialSavingsItem(
                slug=item.slug,
                name=item.name,
                icon=item.icon,
                amount_cents=item.amount_cents,
            )
            for item in discretionary
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
    scope = (
        f"user={user.id} period={period} date_from={date_from} "
        f"date_to={date_to} group_id={group_id}"
    )
    summary = dashboard_service.summary(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    if summary.expense_count == 0:
        # Branch 1 of 2: nothing to say anything personal about. GigaChat is
        # deliberately not called — this is not a provider failure.
        logger.info(
            "%s expense_count=0 total_spending_cents=%s -> FALLBACK_TIPS (no spending data)",
            scope,
            summary.total_spending_cents,
        )
        return FALLBACK_TIPS

    category_breakdown = dashboard_service.spending_by_category(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    over_time = dashboard_service.spending_over_time(
        db, user=user, period=period, date_from=date_from, date_to=date_to, group_id=group_id
    )
    # Считается локально, до похода в GigaChat: блок «можно сэкономить» должен
    # появляться и тогда, когда советы пришлось заменить на fallback.
    potential_savings = _build_potential_savings(
        db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
        currency=summary.currency,
    )

    payload = _build_input(summary, category_breakdown, over_time)
    logger.info(
        "%s expense_count=%s total_spending_cents=%s categories=%s trend=%s -> calling GigaChat",
        scope,
        summary.expense_count,
        summary.total_spending_cents,
        len(payload.categories),
        payload.trend is not None,
    )
    try:
        tips = gigachat_service.generate_saving_tips(payload)
    except gigachat_service.GigaChatError as exc:
        # Branch 2 of 2: the provider failed or returned something unusable.
        # ``GigaChatError`` messages are rendered secret-free upstream
        # (see ``gigachat_service._safe_http_message``), so this is safe to log.
        logger.warning("%s -> FALLBACK_TIPS (GigaChat failed: %s)", scope, exc)
        # model_copy, не мутация: FALLBACK_TIPS — общий модульный синглтон.
        return FALLBACK_TIPS.model_copy(update={"potential_savings": potential_savings})
    logger.info(
        "%s -> real AI tips (tips=%s, potential_savings=%s)",
        scope,
        len(tips.tips),
        potential_savings.total_cents if potential_savings else None,
    )
    return tips.model_copy(update={"potential_savings": potential_savings})


__all__ = ["DISCRETIONARY_SLUGS", "FALLBACK_TIPS", "generate"]

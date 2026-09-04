"""Dashboard analytics endpoints."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.dashboard import (
    CategoryBreakdownOut,
    DashboardSummaryOut,
    SpendingOverTimeOut,
)
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Сводка"])

# Kept as a plain string rather than an Enum so an unknown value is rejected by
# ``resolve_period`` as a 400 carrying its own message instead of a generic 422.
PeriodParam = Annotated[
    str,
    Query(
        description=(
            "Период: all — за всё время, this_month — этот месяц, "
            "last_month — прошлый месяц, last_3_months — последние 3 месяца, "
            "custom — свой период"
        )
    ),
]
DateFromParam = Annotated[
    date | None, Query(description="Начало периода — только для своего периода")
]
DateToParam = Annotated[
    date | None,
    Query(description="Конец периода включительно — только для своего периода"),
]
GroupParam = Annotated[
    uuid.UUID | None, Query(description="Считать только по одной группе")
]


@router.get("/summary", summary="Сводка по расходам")
def get_summary(
    db: DbSession,
    user: CurrentUser,
    period: PeriodParam = "all",
    date_from: DateFromParam = None,
    date_to: DateToParam = None,
    group_id: GroupParam = None,
) -> DashboardSummaryOut:
    return dashboard_service.summary(
        db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )


@router.get("/spending-by-category", summary="Расходы по категориям")
def get_spending_by_category(
    db: DbSession,
    user: CurrentUser,
    period: PeriodParam = "all",
    date_from: DateFromParam = None,
    date_to: DateToParam = None,
    group_id: GroupParam = None,
) -> CategoryBreakdownOut:
    return dashboard_service.spending_by_category(
        db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )


@router.get("/spending-over-time", summary="Расходы по месяцам")
def get_spending_over_time(
    db: DbSession,
    user: CurrentUser,
    period: PeriodParam = "all",
    date_from: DateFromParam = None,
    date_to: DateToParam = None,
    group_id: GroupParam = None,
) -> SpendingOverTimeOut:
    return dashboard_service.spending_over_time(
        db,
        user=user,
        period=period,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
    )


__all__ = ["router"]

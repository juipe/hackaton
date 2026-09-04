"""Dashboard analytics response shapes."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class DashboardGroupSummary(BaseModel):
    """Одна строка блока «ваши группы» на сводке."""

    group_id: uuid.UUID
    name: str
    currency: str
    net_cents: int
    total_spending_cents: int
    #: Доля смотрящего в расходах группы за период — на неё опирается полоса
    #: заполнения в карточке группы.
    your_share_cents: int = 0
    member_count: int


class DashboardSummaryOut(BaseModel):
    you_owe_cents: int
    owed_to_you_cents: int
    net_cents: int
    total_spending_cents: int
    your_paid_cents: int
    your_share_cents: int
    group_count: int
    expense_count: int
    currency: str
    groups: list[DashboardGroupSummary]


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID
    slug: str
    name: str
    icon: str
    amount_cents: int
    percentage: float
    expense_count: int


class CategoryBreakdownOut(BaseModel):
    total_cents: int
    items: list[CategoryBreakdownItem]


class SpendingOverTimePoint(BaseModel):
    month: str
    label: str
    amount_cents: int
    your_share_cents: int


class SpendingOverTimeOut(BaseModel):
    currency: str
    items: list[SpendingOverTimePoint]


__all__ = [
    "CategoryBreakdownItem",
    "CategoryBreakdownOut",
    "DashboardGroupSummary",
    "DashboardSummaryOut",
    "SpendingOverTimeOut",
    "SpendingOverTimePoint",
]

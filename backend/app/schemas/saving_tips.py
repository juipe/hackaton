"""AI saving-tips schemas.

``SavingTipsInput`` is the trimmed slice of the dashboard's own analytics
(:mod:`app.services.dashboard_service`) handed to the LLM — spending totals,
category shares and a two-month trend, nothing else. No ids, no member/debt
data, no auth details ever go into it; see ``app.services.saving_tips_service``
for how it's assembled.

Every number the model could get wrong (cents-to-rubles conversion, percentages,
month-to-month change) is pre-calculated and pre-formatted by the backend
into a ``*_display`` string using :mod:`app.utils.money` — the model only
ever copies these strings into its prose, it never sees a raw cents integer or a
raw ratio to convert or round itself. ``SavingTipsOut`` is both what the model
must return and what the API responds with — the same shape, so no extra
mapping step, and it carries no numeric fields at all: only free-text title/
text strings and a type label, so a wrong number the model might type inside
``text`` can never be parsed back out and used anywhere else in the app.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SavingTipsCategoryInput(BaseModel):
    name: str
    amount_display: str
    percentage_display: str
    expense_count: int


class SavingTipsTrend(BaseModel):
    """Total spending compared between the two most recent months with data.

    Only ever built when a safe comparison exists (see
    ``app.services.saving_tips_service._build_trend``) — absent otherwise, so
    the model is never tempted to invent a trend out of a single data point.
    """

    from_label: str
    to_label: str
    from_display: str
    to_display: str
    change_display: str


class SavingTipsInput(BaseModel):
    """Exactly the fields useful for a saving recommendation — see module docstring."""

    total_spending_display: str
    expense_count: int
    currency: str
    categories: list[SavingTipsCategoryInput] = Field(default_factory=list)
    trend: SavingTipsTrend | None = None


TipType = Literal["data_driven", "generic"]


class SavingTip(BaseModel):
    title: str
    text: str
    type: TipType


class PotentialSavingsItem(BaseModel):
    """Одна «необязательная» категория в блоке «можно сэкономить»."""

    slug: str
    name: str
    icon: str
    amount_cents: int


class PotentialSavings(BaseModel):
    """Сумма личных трат по необязательным категориям за выбранный период.

    Считается в Python из долей пользователя
    (:func:`app.services.dashboard_service.user_share_by_category`) — модель к
    этим числам не прикасается, поэтому поле дополняет ответ и при fallback.
    """

    total_cents: int
    currency: str
    items: list[PotentialSavingsItem]


class SavingTipsOut(BaseModel):
    tips: list[SavingTip]
    #: Заполняется сервисом после ответа модели (или поверх fallback) — LLM
    #: это поле не возвращает, поэтому оно опционально и без него ответ валиден.
    potential_savings: PotentialSavings | None = None

    @field_validator("tips")
    @classmethod
    def _exactly_two_to_three(cls, value: list[SavingTip]) -> list[SavingTip]:
        if not 2 <= len(value) <= 3:
            raise ValueError("expected 2 to 3 saving tips")
        return value


__all__ = [
    "PotentialSavings",
    "PotentialSavingsItem",
    "SavingTip",
    "SavingTipsCategoryInput",
    "SavingTipsInput",
    "SavingTipsOut",
    "SavingTipsTrend",
    "TipType",
]

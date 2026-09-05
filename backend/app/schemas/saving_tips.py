"""AI saving-tips schemas.

``SavingTipsInput`` is the trimmed slice of the dashboard's own analytics
(:mod:`app.services.dashboard_service`) handed to Qwen — spending totals,
category shares and a two-month trend, nothing else. No ids, no member/debt
data, no auth details ever go into it; see ``app.services.saving_tips_service``
for how it's assembled.

Every number Qwen could get wrong (cents-to-rubles conversion, percentages,
month-to-month change) is pre-calculated and pre-formatted by the backend
into a ``*_display`` string using :mod:`app.utils.money` — Qwen only ever
copies these strings into its prose, it never sees a raw cents integer or a
raw ratio to convert or round itself. ``SavingTipsOut`` is both what Qwen
must return and what the API responds with — the same shape, so no extra
mapping step, and it carries no numeric fields at all: only free-text title/
text strings and a type label, so a wrong number Qwen might type inside
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
    Qwen is never tempted to invent a trend out of a single data point.
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


class SavingTipsOut(BaseModel):
    tips: list[SavingTip]

    @field_validator("tips")
    @classmethod
    def _exactly_two_to_three(cls, value: list[SavingTip]) -> list[SavingTip]:
        if not 2 <= len(value) <= 3:
            raise ValueError("expected 2 to 3 saving tips")
        return value


__all__ = [
    "SavingTip",
    "SavingTipsCategoryInput",
    "SavingTipsInput",
    "SavingTipsOut",
    "SavingTipsTrend",
    "TipType",
]

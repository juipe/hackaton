"""AI saving-tips schemas.

``SavingTipsInput`` is the trimmed slice of the dashboard's own analytics
(:mod:`app.services.dashboard_service`) handed to Qwen — spending totals,
category shares and a monthly series, nothing else. No ids, no member/debt
data, no auth details ever go into it; see ``app.services.saving_tips_service``
for how it's assembled. ``SavingTipsOut`` is both what Qwen must return and
what the API responds with — the same shape, so no extra mapping step.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SavingTipsCategoryInput(BaseModel):
    name: str
    amount_cents: int
    percentage: float
    expense_count: int


class SavingTipsMonthInput(BaseModel):
    month: str
    amount_cents: int
    your_share_cents: int


class SavingTipsInput(BaseModel):
    """Exactly the fields useful for a saving recommendation — see module docstring."""

    total_spending_cents: int
    expense_count: int
    currency: str
    categories: list[SavingTipsCategoryInput] = Field(default_factory=list)
    months: list[SavingTipsMonthInput] = Field(default_factory=list)


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
    "SavingTipsMonthInput",
    "SavingTipsOut",
    "TipType",
]

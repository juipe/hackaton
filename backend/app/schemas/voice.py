"""Voice-to-expense-draft schemas.

The LLM extraction schema (:class:`LLMExpenseExtraction`) is deliberately
UUID-free — Qwen only ever produces names and free text. Every id that ends up
in the draft comes from resolving that text against the group's real members
and categories in ``app.services.voice_service``, never from the model itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.category import CategoryOut
from app.schemas.member import MemberOut

ResolutionStatus = Literal["resolved", "ambiguous", "unresolved"]


class FieldResolution[T](BaseModel):
    """One extracted field, resolved against real group data — or not.

    ``resolved`` carries ``value``; ``ambiguous`` carries ``candidates`` (more
    than one plausible match); ``unresolved`` carries neither — the model said
    something that matched no one. The frontend must ask the user to pick
    explicitly in the last two cases; nothing here ever guesses.
    """

    status: ResolutionStatus
    value: T | None = None
    candidates: list[T] = Field(default_factory=list)
    raw_text: str | None = None


class AmbiguousParticipant(BaseModel):
    raw_text: str
    candidates: list[MemberOut]


class ParticipantsResolution(BaseModel):
    resolved: list[MemberOut] = Field(default_factory=list)
    ambiguous: list[AmbiguousParticipant] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class LLMExpenseExtraction(BaseModel):
    """Raw structured output from Qwen. Names and free text only, never ids."""

    title: str | None = None
    amount: str | None = Field(
        default=None, description="Сумма в рублях, например '1200' или '1200.50'"
    )
    occurred_at: str | None = Field(
        default=None, description="Дата расхода в формате YYYY-MM-DD, если названа явно"
    )
    category_slug: str | None = Field(
        default=None,
        description="Slug одной из категорий, переданных модели — никогда не выдуманный",
    )
    payer_name: str | None = Field(
        default=None, description="Кто заплатил — имя или 'я', если сам говорящий"
    )
    participant_names: list[str] = Field(default_factory=list)


class VoiceExpenseDraftOut(BaseModel):
    """Ephemeral draft returned to the frontend for confirmation.

    Nothing here is persisted — this is not an :class:`app.schemas.expense.ExpenseOut`
    and never touches the database. The frontend turns it into a normal
    ``ExpenseCreate`` payload only after the user has confirmed (and resolved
    any ambiguity) and posts it through the existing expense creation route.
    """

    transcript: str
    title: str | None
    amount_cents: int | None
    occurred_at: datetime | None
    split_mode: Literal["equal"] = "equal"
    payer: FieldResolution[MemberOut]
    participants: ParticipantsResolution
    category: FieldResolution[CategoryOut]
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "AmbiguousParticipant",
    "FieldResolution",
    "LLMExpenseExtraction",
    "ParticipantsResolution",
    "ResolutionStatus",
    "VoiceExpenseDraftOut",
]

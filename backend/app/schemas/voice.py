"""Voice-to-expense-draft schemas.

The LLM extraction schema (:class:`LLMExpenseExtraction`) is deliberately
UUID-free — Qwen only ever produces names, free text and plain numbers. Every
id that ends up in the draft comes from resolving that text against the
group's real members and categories in ``app.services.voice_service``, never
from the model itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.expense import SplitMode
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


class ResolvedParticipant(BaseModel):
    """A participant matched unambiguously to a real member, with their share.

    ``value`` is ``None`` for an ``equal`` split or when the transcript never
    stated that participant's share; otherwise its unit follows
    ``VoiceExpenseDraftOut.split_mode`` exactly like ``ParticipantIn.value``
    does for a manually entered expense: rubles for ``exact``, a percentage
    for ``percentage``, a share count for ``shares``.
    """

    member: MemberOut
    value: str | None = None


class ParticipantsResolution(BaseModel):
    resolved: list[ResolvedParticipant] = Field(default_factory=list)
    ambiguous: list[AmbiguousParticipant] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class LLMParticipantShare(BaseModel):
    """One participant's share exactly as Qwen heard it — a name and a raw
    number whose unit depends on the extraction's ``split_mode``."""

    name: str = Field(description="Имя участника как в речи, или 'я' для себя")
    value: str | None = Field(
        default=None, description="Доля участника — единицы зависят от split_mode"
    )


class LLMExpenseExtraction(BaseModel):
    """Raw structured output from Qwen. Names, text and plain numbers only,
    never ids — see ``voice_service`` for how each field is resolved and
    validated against real data before it reaches the frontend."""

    title: str | None = None
    description: str | None = Field(
        default=None, description="Короткая заметка к расходу, если явно упомянута"
    )
    amount: str | None = Field(
        default=None, description="Общая сумма в рублях, например '1200' или '1200.50'"
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
    split_mode: str | None = Field(
        default=None, description="Один из 'equal', 'exact', 'percentage', 'shares'"
    )
    participants: list[LLMParticipantShare] = Field(default_factory=list)


class VoiceExpenseDraftOut(BaseModel):
    """Ephemeral draft returned to the frontend for confirmation.

    Nothing here is persisted — this is not an :class:`app.schemas.expense.ExpenseOut`
    and never touches the database. The frontend turns it into a normal
    ``ExpenseCreate`` payload only after the user has confirmed (and resolved
    any ambiguity, and fixed any warning) and posts it through the existing
    expense creation route. Split-total validation is never enforced here a
    second time — the same ``ExpenseForm`` that renders a manually entered
    expense already rejects a mismatched exact/percentage/shares split on
    submit, so a bad voice draft can be reviewed and fixed with the exact
    same UI, never silently persisted.
    """

    transcript: str
    title: str | None
    description: str | None
    amount_cents: int | None
    occurred_at: datetime | None
    split_mode: SplitMode = SplitMode.EQUAL
    payer: FieldResolution[MemberOut]
    participants: ParticipantsResolution
    category: FieldResolution[CategoryOut]
    warnings: list[str] = Field(default_factory=list)


__all__ = [
    "AmbiguousParticipant",
    "FieldResolution",
    "LLMExpenseExtraction",
    "LLMParticipantShare",
    "ParticipantsResolution",
    "ResolutionStatus",
    "ResolvedParticipant",
    "VoiceExpenseDraftOut",
]

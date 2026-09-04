"""Expense request and response payloads.

The wire format for a participant's ``value`` is deliberately loose — a JSON
string, a number or ``null`` — because it carries three different kinds of input
(cents, percent, share count) and browsers happily send any of those shapes. It is
normalised to ``Decimal | None`` on the way in and back to a trimmed decimal
string on the way out, so no float ever touches split arithmetic.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.expense import SplitMode
from app.schemas.category import CategoryOut
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic


def decimal_to_str(value: Decimal | None) -> str | None:
    """``Decimal('2.000000')`` -> ``'2'``; ``None`` stays ``None``.

    ``normalize`` alone would render round numbers in exponent form
    (``Decimal('100')`` -> ``1E+2``), hence the explicit fixed-point format.
    """
    if value is None:
        return None
    return format(value.normalize(), "f")


def _to_decimal(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        raise ValueError("Доля участника должна быть числом")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        # str() first: Decimal(0.1) would carry the binary representation error.
        return Decimal(str(raw))
    if isinstance(raw, str):
        cleaned = raw.strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation as exc:
            raise ValueError("Доля участника должна быть числом") from exc
    raise ValueError("Доля участника должна быть числом")


def _clean_title(raw: str) -> str:
    title = raw.strip()
    if not title:
        raise ValueError("Укажите название расхода")
    return title


def _check_participants(value: list[ParticipantIn] | None) -> list[ParticipantIn] | None:
    if value is not None and not value:
        raise ValueError("В расходе должен быть хотя бы один участник")
    return value


class ParticipantIn(BaseModel):
    """Доля одного участника: копейки для «точных сумм», процент, доли или ничего."""

    user_id: uuid.UUID = Field(description="Участник расхода")
    value: Decimal | None = Field(
        default=None, description="Значение доли — смысл зависит от способа деления"
    )

    @field_validator("value", mode="before")
    @classmethod
    def _normalise_value(cls, raw: Any) -> Decimal | None:
        return _to_decimal(raw)


class ExpenseCreate(BaseModel):
    title: str = Field(max_length=160, description="Название расхода")
    description: str | None = Field(default=None, description="Заметка к расходу")
    amount_cents: int = Field(description="Сумма расхода в копейках")
    category_id: uuid.UUID = Field(description="Категория расхода")
    paid_by: uuid.UUID = Field(description="Кто заплатил")
    occurred_at: datetime | None = Field(
        default=None, description="Дата расхода — по умолчанию текущий момент"
    )
    split_mode: SplitMode = Field(
        default=SplitMode.EQUAL, description="Способ деления расхода"
    )
    participants: list[ParticipantIn] = Field(description="Между кем делится расход")

    @field_validator("title")
    @classmethod
    def _strip_title(cls, raw: str) -> str:
        return _clean_title(raw)

    @field_validator("participants")
    @classmethod
    def _non_empty(cls, value: list[ParticipantIn]) -> list[ParticipantIn]:
        _check_participants(value)
        return value


class ExpenseUpdate(BaseModel):
    """Все поля необязательные. Пропущенное поле и явный ``null`` — не одно и то же."""

    title: str | None = Field(
        default=None, max_length=160, description="Название расхода"
    )
    description: str | None = Field(default=None, description="Заметка к расходу")
    amount_cents: int | None = Field(default=None, description="Сумма расхода в копейках")
    category_id: uuid.UUID | None = Field(default=None, description="Категория расхода")
    paid_by: uuid.UUID | None = Field(default=None, description="Кто заплатил")
    occurred_at: datetime | None = Field(default=None, description="Дата расхода")
    split_mode: SplitMode | None = Field(
        default=None, description="Способ деления расхода"
    )
    participants: list[ParticipantIn] | None = Field(
        default=None, description="Между кем делится расход"
    )

    @field_validator("title")
    @classmethod
    def _strip_title(cls, raw: str | None) -> str | None:
        return None if raw is None else _clean_title(raw)

    @field_validator("participants")
    @classmethod
    def _non_empty(cls, value: list[ParticipantIn] | None) -> list[ParticipantIn] | None:
        return _check_participants(value)


class SplitOut(ORMModel):
    user_id: uuid.UUID
    user: UserPublic
    split_mode: str
    input_value: str | None
    calculated_amount_cents: int

    @field_validator("input_value", mode="before")
    @classmethod
    def _render_input_value(cls, raw: Any) -> str | None:
        if isinstance(raw, Decimal):
            return decimal_to_str(raw)
        return raw


class ExpenseOut(ORMModel):
    """Расход со всеми долями и суммами, посчитанными для запросившего."""

    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    description: str | None
    amount_cents: int
    currency: str
    split_mode: str
    category: CategoryOut
    paid_by: uuid.UUID
    payer: UserPublic
    created_by: uuid.UUID
    creator: UserPublic
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
    splits: list[SplitOut]
    #: All three are relative to the requesting user, not to the group.
    my_share_cents: int
    my_paid_cents: int
    my_net_cents: int


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    total: int
    limit: int
    offset: int


__all__ = [
    "ExpenseCreate",
    "ExpenseOut",
    "ExpensePage",
    "ExpenseUpdate",
    "ParticipantIn",
    "SplitOut",
    "decimal_to_str",
]

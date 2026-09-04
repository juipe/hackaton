"""Group request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.utils.time import ensure_utc

#: Three upper-case letters, i.e. an ISO-4217 alphabetic code.
CURRENCY_PATTERN = r"^[A-Z]{3}$"

#: The only currency the ledger speaks.
DEFAULT_CURRENCY = "RUB"

#: Refusal text for any other code, fixed by the localisation contract.
CURRENCY_NOT_SUPPORTED = "Сервис работает только с рублями"

DESCRIPTION_MAX_LENGTH = 2000

NAME_MAX_LENGTH = 120

NAME_DESCRIPTION = "Название группы — до 120 символов"
DESCRIPTION_DESCRIPTION = "Описание группы — до 2000 символов"
CURRENCY_DESCRIPTION = "Валюта группы — всегда RUB"


def clean_name(value: object) -> object:
    """Trim the name and own the wording: Pydantic's length errors are English."""
    if not isinstance(value, str):
        return value
    name = value.strip()
    if not name:
        raise ValueError("Укажите название группы")
    if len(name) > NAME_MAX_LENGTH:
        raise ValueError(f"Название не длиннее {NAME_MAX_LENGTH} символов")
    return name


def clean_currency(value: object) -> object:
    """Upper-case on the way in, so ``"rub"`` and ``"RUB"`` are the same group."""
    if isinstance(value, str):
        return value.strip().upper()
    return value


def ensure_rub(value: object) -> object:
    """Normalise the case, then refuse anything that is not the rouble.

    The whole product is denominated in roubles — balances, splits and settle-ups
    alike — so a foreign code could only ever produce a ledger nobody can read.
    ``None`` passes through: on a PATCH it means "leave the currency alone".
    """
    cleaned = clean_currency(value)
    if isinstance(cleaned, str) and cleaned != DEFAULT_CURRENCY:
        raise ValueError(CURRENCY_NOT_SUPPORTED)
    return cleaned


def clean_description(value: object) -> object:
    """A blank description becomes ``None``.

    The UI sends ``""`` when the user empties the textarea, which means the same
    thing as never having written one.
    """
    if isinstance(value, str):
        return value.strip() or None
    return value


class GroupCreate(BaseModel):
    name: str = Field(
        min_length=1, max_length=NAME_MAX_LENGTH, description=NAME_DESCRIPTION
    )
    description: str | None = Field(
        default=None,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=DESCRIPTION_DESCRIPTION,
    )
    currency: str = Field(
        default=DEFAULT_CURRENCY,
        min_length=3,
        max_length=3,
        pattern=CURRENCY_PATTERN,
        description=CURRENCY_DESCRIPTION,
    )

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        return clean_name(value)

    @field_validator("description", mode="before")
    @classmethod
    def _normalise_description(cls, value: object) -> object:
        return clean_description(value)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: object) -> object:
        return ensure_rub(value)


class GroupUpdate(BaseModel):
    """Тело PATCH-запроса.

    Все поля необязательные, а ``model_fields_set`` подсказывает сервису, поле
    пропустили или прислали явный ``null``.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=NAME_MAX_LENGTH,
        description=NAME_DESCRIPTION,
    )
    description: str | None = Field(
        default=None,
        max_length=DESCRIPTION_MAX_LENGTH,
        description=DESCRIPTION_DESCRIPTION,
    )
    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=CURRENCY_PATTERN,
        description=CURRENCY_DESCRIPTION,
    )

    @field_validator("name", mode="before")
    @classmethod
    def _strip_name(cls, value: object) -> object:
        return clean_name(value)

    @field_validator("description", mode="before")
    @classmethod
    def _normalise_description(cls, value: object) -> object:
        return clean_description(value)

    @field_validator("currency", mode="before")
    @classmethod
    def _normalise_currency(cls, value: object) -> object:
        return ensure_rub(value)


class GroupOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    currency: str
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    member_count: int
    my_role: str
    my_net_cents: int
    total_spending_cents: int

    @field_validator("created_at", "updated_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite hands back naive datetimes; the API always emits an offset.
        return ensure_utc(value)


__all__ = [
    "CURRENCY_NOT_SUPPORTED",
    "CURRENCY_PATTERN",
    "DEFAULT_CURRENCY",
    "DESCRIPTION_MAX_LENGTH",
    "NAME_MAX_LENGTH",
    "GroupCreate",
    "GroupOut",
    "GroupUpdate",
    "clean_currency",
    "clean_description",
    "clean_name",
    "ensure_rub",
]

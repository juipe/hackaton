"""Settle-up payment schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.user import UserPublic
from app.utils.time import ensure_utc

NOTE_MAX_LENGTH = 280


class PaymentCreate(BaseModel):
    """Тело запроса ``POST /api/groups/{group_id}/payments``.

    Валюты здесь намеренно нет: перевод всегда идёт в валюте группы, поэтому
    присланный клиентом код мог бы только разойтись с журналом, в который перевод
    попадает.
    """

    from_user_id: uuid.UUID = Field(description="Кто переводит")
    to_user_id: uuid.UUID = Field(description="Кому переводят")
    # No `ge=1` constraint here: a field-level constraint would render as
    # "amount_cents: Input should be ..." while the contract fixes the wording of
    # this message, so the check lives in the model validator below instead.
    amount_cents: int = Field(description="Сумма перевода в копейках")
    note: str | None = Field(
        default=None,
        max_length=NOTE_MAX_LENGTH,
        description="Комментарий к переводу — до 280 символов",
    )
    paid_at: datetime | None = Field(
        default=None, description="Дата перевода — по умолчанию текущий момент"
    )

    @field_validator("note", mode="before")
    @classmethod
    def _normalise_note(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def _validate_transfer(self) -> PaymentCreate:
        # Raised at model level so ``app.main`` renders the message on its own,
        # without a field-name prefix.
        if self.amount_cents < 1:
            raise ValueError("Сумма должна быть больше нуля")
        if self.from_user_id == self.to_user_id:
            raise ValueError("Перевод возможен только между разными людьми")
        return self


class PaymentOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    from_user_id: uuid.UUID
    from_user: UserPublic
    to_user_id: uuid.UUID
    to_user: UserPublic
    amount_cents: int
    currency: str
    note: str | None = None
    paid_at: datetime
    created_at: datetime

    @field_validator("paid_at", "created_at", mode="after")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite returns naive datetimes for tz-aware columns; the API only ever
        # emits UTC carrying an explicit offset.
        return ensure_utc(value)


__all__ = ["NOTE_MAX_LENGTH", "PaymentCreate", "PaymentOut"]

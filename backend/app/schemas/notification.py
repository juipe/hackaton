"""Debt-reminder notification schemas.

``DebtReminderInput``/``DebtReminderOut`` are the minimal Qwen contract for
wording a reminder — see ``app.services.ollama_service.generate_debt_reminder``.
Only the facts needed to phrase one sentence go in; the backend never reads a
number back out of Qwen's answer, so it cannot invent an amount or a name.
``NotificationOut`` is the API shape, built straight off the (denormalized)
``Notification`` row — the amount, payer and expense name in it always come
from the backend, never from ``message``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.utils.time import ensure_utc


class DebtReminderInput(BaseModel):
    """Exactly what Qwen needs to phrase one sentence — see module docstring."""

    expense: str
    amount_due: str
    currency: str
    payer: str
    group: str


class DebtReminderOut(BaseModel):
    message: str = Field(min_length=1, max_length=400)


class NotificationOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    expense_id: uuid.UUID
    expense_title: str
    payer_name: str
    amount_due_cents: int
    currency: str
    message: str
    is_read: bool
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite hands back naive datetimes; the API always emits an offset.
        return ensure_utc(value)


__all__ = ["DebtReminderInput", "DebtReminderOut", "NotificationOut"]

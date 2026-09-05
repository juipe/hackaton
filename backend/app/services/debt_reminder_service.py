"""Debt-reminder notifications.

Created from the split the expense flow already computed — this module never
divides money and never re-derives who owes what; it only reads
``SplitResult`` rows handed to it by :func:`app.services.expense_service.create_expense`.

Two separate concerns, run at two different times:

- :func:`create_reminders_for_expense` runs synchronously, inside the same
  transaction as the expense, with a deterministic fallback message already
  filled in. This is what makes the reminder restart-safe: the row (and its
  text) exist in the database before the request ever returns, so a crash
  before the background step below ever runs loses nothing but a nicer
  sentence. The 10-second delay is a plain ``available_at`` column, not a
  timer or a scheduled job — nothing has to survive in memory across a
  restart for it to work.
- :func:`enhance_with_qwen` runs afterwards, as a ``BackgroundTasks`` job with
  its own DB session (the request's session is already closed by the time
  background tasks run), and best-effort replaces the fallback message with
  one from Qwen. Its failure is invisible to both the expense request and the
  notification's availability — see module docstring above.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.expense import Expense
from app.models.group import Group
from app.models.notification import Notification
from app.repositories import notification_repo
from app.schemas.notification import DebtReminderInput, NotificationOut
from app.services import ollama_service
from app.services.split_engine import SplitResult
from app.utils.money import cents_to_str, format_money
from app.utils.time import utcnow

logger = logging.getLogger("skladchina.debt_reminders")

FALLBACK_SOURCE = "fallback"
QWEN_SOURCE = "qwen"


def _fallback_message(
    *, payer_name: str, amount_due_cents: int, currency: str, expense_title: str, group_name: str
) -> str:
    return (
        f"Вы должны {payer_name} {format_money(amount_due_cents, currency)} "
        f"за «{expense_title}» в группе «{group_name}»."
    )


def create_reminders_for_expense(
    db: Session,
    *,
    expense: Expense,
    group: Group,
    results: Sequence[SplitResult],
) -> list[Notification]:
    """One reminder per debtor on ``expense`` — reusing ``results`` as-is.

    A debtor is any participant whose calculated share is greater than zero,
    excluding the payer. Joins the caller's transaction (like
    ``activity_service.log_activity``): it flushes but never commits, so a
    reminder can never be recorded for an expense that gets rolled back.
    """
    payer_id = expense.paid_by
    debtors = [
        result
        for result in results
        if result.user_id != payer_id and result.calculated_amount_cents > 0
    ]
    if not debtors:
        return []

    payer_name = expense.payer.name
    available_at = utcnow() + timedelta(seconds=settings.debt_reminder_delay_seconds)

    created: list[Notification] = []
    for result in debtors:
        if notification_repo.exists_for_expense_user(db, expense.id, result.user_id):
            continue
        notification = Notification(
            user_id=result.user_id,
            expense_id=expense.id,
            group_id=group.id,
            payer_id=payer_id,
            expense_title=expense.title,
            payer_name=payer_name,
            group_name=group.name,
            amount_due_cents=result.calculated_amount_cents,
            currency=expense.currency,
            message=_fallback_message(
                payer_name=payer_name,
                amount_due_cents=result.calculated_amount_cents,
                currency=expense.currency,
                expense_title=expense.title,
                group_name=group.name,
            ),
            source=FALLBACK_SOURCE,
            available_at=available_at,
        )
        db.add(notification)
        created.append(notification)

    if created:
        db.flush()
    return created


def enhance_with_qwen(notification_ids: Sequence[uuid.UUID]) -> None:
    """Best-effort: replace each reminder's fallback message with a Qwen one.

    Runs as a background task, after the expense response has already been
    sent — it opens its own session because the request's is gone by then.
    Never raises: an unreachable/misbehaving Ollama leaves the deterministic
    fallback in place, which is already a complete, correct notification, and
    a broken Ollama reply (or anything else going wrong per-notification)
    is caught and logged rather than left to fail the background task —
    the expense request this runs after has already succeeded and must never
    be affected by it.
    """
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        for notification_id in notification_ids:
            try:
                notification = db.get(Notification, notification_id)
                if notification is None:
                    continue
                payload = DebtReminderInput(
                    expense=notification.expense_title,
                    amount_due=cents_to_str(notification.amount_due_cents),
                    currency=notification.currency,
                    payer=notification.payer_name,
                    group=notification.group_name,
                )
                result = ollama_service.generate_debt_reminder(payload)
                notification.message = result.message
                notification.source = QWEN_SOURCE
                db.commit()
            except ollama_service.OllamaError:
                db.rollback()
            except Exception:  # a background job must never crash the process
                logger.exception("Failed to word debt reminder %s via Qwen", notification_id)
                db.rollback()


def list_for_user(db: Session, user_id: uuid.UUID) -> list[NotificationOut]:
    """The latest available reminders for ``user_id`` — see the repo for ordering/limit."""
    notifications = notification_repo.list_available_for_user(db, user_id)
    return [NotificationOut.model_validate(notification) for notification in notifications]


def mark_all_read(db: Session, user_id: uuid.UUID) -> None:
    notification_repo.mark_available_read(db, user_id)
    db.commit()


__all__ = [
    "create_reminders_for_expense",
    "enhance_with_qwen",
    "list_for_user",
    "mark_all_read",
]

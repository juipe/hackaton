"""Critical budget threshold: warns a user their cross-group debt is closing in
on (or has passed) the monthly budget/income they configured on their profile.

Deliberately isolated from the rest of the notification/debt machinery:

* It never computes a balance itself — :func:`app.services.balance_service.
  compute_user_group_nets` is the single source of truth for "how much does
  this user owe", all-time and across every group they belong to, exactly the
  number already surfaced as "you owe" on the dashboard.
* It reuses the existing ``Notification`` model/table/API/UI, tagged with
  ``type="budget_threshold"`` — see the model docstring. Those rows have no
  single expense/payer/group to point at, so those columns stay null; the
  fields the notification bell actually renders (``message``,
  ``amount_due_cents``, ``currency``) are always filled in.
* Dedup is a two-value state machine stored right on the user
  (``budget_alert_state``), not a new table: a notification is created only
  when the state changes, so staying above (or below) a threshold across many
  further expenses/payments never spams the user.

Called after an expense or a payment has already been committed, once per
user whose debt the transaction could have *increased* (see the call sites in
``expense_service`` and ``payment_service``) — a user who only became owed
more, or paid off debt, cannot have crossed a threshold upward.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.user import User
from app.services.balance_service import compute_user_group_nets
from app.utils.money import DEFAULT_CURRENCY, format_money
from app.utils.time import utcnow

logger = logging.getLogger("skladchina.budget_threshold")

NOTIFICATION_TYPE = "budget_threshold"

APPROACHING_STATE = "approaching"
EXCEEDED_STATE = "exceeded"

APPROACHING_RATIO = 80
EXCEEDED_RATIO = 100


def _current_exposure_cents(db: Session, user_id: uuid.UUID) -> int:
    """Total cross-group debt: the same "you owe" sum the dashboard reports.

    ``compute_user_group_nets`` returns ``{group_id: net_cents}``; a negative
    net means the user owes that group. Being owed money in one group never
    offsets debt in another (see ``dashboard_service.summary``), so this sums
    only the negative nets.
    """
    nets = compute_user_group_nets(db, user_id)
    return sum(max(0, -net_cents) for net_cents in nets.values())


def _classify(exposure_cents: int, limit_cents: int) -> str | None:
    """Integer-only threshold check: ``exposure / limit >= ratio / 100``."""
    if exposure_cents * 100 >= limit_cents * EXCEEDED_RATIO:
        return EXCEEDED_STATE
    if exposure_cents * 100 >= limit_cents * APPROACHING_RATIO:
        return APPROACHING_STATE
    return None


def _message(state: str, *, exposure_cents: int, limit_cents: int) -> str:
    amount = format_money(exposure_cents, DEFAULT_CURRENCY)
    limit = format_money(limit_cents, DEFAULT_CURRENCY)
    if state == EXCEEDED_STATE:
        return (
            f"Критический порог бюджета превышен: ваш текущий долг по всем группам "
            f"составляет {amount} при лимите {limit}."
        )
    return (
        f"Вы приближаетесь к критическому порогу бюджета: ваш текущий долг по всем "
        f"группам составляет {amount} — это уже не меньше 80% от лимита {limit}."
    )


def check_and_notify(db: Session, *, user_id: uuid.UUID) -> Notification | None:
    """Re-evaluate one user's exposure against their configured budget.

    A no-op (no query beyond loading the user) if they never configured a
    budget. Always persists the latest state on the user even when no
    notification is due, so a later call has the right state to diff against.
    """
    user = db.get(User, user_id)
    if user is None or user.monthly_budget_cents is None or user.monthly_budget_cents <= 0:
        return None

    exposure_cents = _current_exposure_cents(db, user_id)
    new_state = _classify(exposure_cents, user.monthly_budget_cents)

    if new_state == user.budget_alert_state:
        return None

    user.budget_alert_state = new_state
    if new_state is None:
        # Dropped back below 80% — record it silently, no "all clear" spam.
        db.commit()
        return None

    notification = Notification(
        user_id=user_id,
        type=NOTIFICATION_TYPE,
        amount_due_cents=exposure_cents,
        currency=DEFAULT_CURRENCY,
        message=_message(
            new_state, exposure_cents=exposure_cents, limit_cents=user.monthly_budget_cents
        ),
        available_at=utcnow(),
    )
    db.add(notification)
    db.commit()
    return notification


def check_and_notify_many(db: Session, user_ids: Iterable[uuid.UUID]) -> list[Notification]:
    """:func:`check_and_notify` for several users, never letting one failure
    hide another and never letting this best-effort feature break the
    transaction (expense/payment creation) it was called after.
    """
    created: list[Notification] = []
    for user_id in dict.fromkeys(user_ids):  # de-duplicate, keep call order
        try:
            notification = check_and_notify(db, user_id=user_id)
        except Exception:  # a side-check must never break the caller's response
            logger.exception("Budget threshold check failed for user %s", user_id)
            db.rollback()
            continue
        if notification is not None:
            created.append(notification)
    return created


__all__ = [
    "APPROACHING_STATE",
    "EXCEEDED_STATE",
    "NOTIFICATION_TYPE",
    "check_and_notify",
    "check_and_notify_many",
]

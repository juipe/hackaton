"""Data access layer.

Each module is a flat namespace of query functions taking a ``Session`` first.
They are imported as modules (``from app.repositories import group_repo``) so call
sites read as ``group_repo.list_for_user(db, user.id)``.
"""

from app.repositories import (
    activity_repo,
    category_repo,
    expense_repo,
    group_repo,
    invite_repo,
    payment_repo,
    user_repo,
)

__all__ = [
    "activity_repo",
    "category_repo",
    "expense_repo",
    "group_repo",
    "invite_repo",
    "payment_repo",
    "user_repo",
]

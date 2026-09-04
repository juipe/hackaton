"""Account lifecycle: registration, sign-in, profile edits and password changes.

The service owns the transaction boundary — ``get_db`` never commits — and it is the
only place that touches ``User.password_hash``.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Conflict, Unauthorized
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories import user_repo

_EMAIL_TAKEN = "Этот адрес электронной почты уже зарегистрирован"


def register(db: Session, *, name: str, email: str, password: str) -> User:
    if user_repo.get_by_email(db, email) is not None:
        raise Conflict(_EMAIL_TAKEN)
    user = user_repo.create(
        db, name=name, email=email, password_hash=hash_password(password)
    )
    _commit_unique_email(db)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = user_repo.get_by_email(db, email)
    if user is None or not verify_password(password, user.password_hash):
        # One message for both branches: answering differently for an unknown
        # address would turn sign-in into an account-existence oracle.
        raise Unauthorized("Неверный адрес электронной почты или пароль")
    return user


def update_profile(
    db: Session, *, user: User, name: str | None = None, email: str | None = None
) -> User:
    """Apply the supplied profile fields. ``None`` means "leave as it is"."""
    if name is not None:
        user.name = name
    if email is not None and email != user.email:
        owner = user_repo.get_by_email(db, email)
        if owner is not None and owner.id != user.id:
            raise Conflict(_EMAIL_TAKEN)
        user.email = email
    _commit_unique_email(db)
    return user


def change_password(
    db: Session, *, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise BadRequest("Текущий пароль неверен")
    user.password_hash = hash_password(new_password)
    db.commit()


def _commit_unique_email(db: Session) -> None:
    """Commit, translating the email unique index into the domain conflict.

    Two simultaneous registrations for the same address both pass the read-time
    check, so the index is the real arbiter and this is the branch that catches it.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise Conflict(_EMAIL_TAKEN) from exc


__all__ = ["authenticate", "change_password", "register", "update_profile"]

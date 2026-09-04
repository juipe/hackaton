"""Request bodies for the authentication endpoints."""

from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

NAME_MAX_LENGTH = 120
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

NAME_DESCRIPTION = "Имя — до 120 символов"
EMAIL_DESCRIPTION = "Адрес электронной почты"
NEW_PASSWORD_DESCRIPTION = "Пароль — не короче 8 символов"
PASSWORD_DESCRIPTION = "Пароль"


def _check_name(value: object) -> object:
    """Own the wording: Pydantic's own length errors are English."""
    if not isinstance(value, str):
        return value
    name = value.strip()
    if not name:
        raise ValueError("Укажите имя")
    if len(name) > NAME_MAX_LENGTH:
        raise ValueError("Имя не длиннее 120 символов")
    return name


def _check_new_password(value: object) -> object:
    if not isinstance(value, str):
        return value
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError("Пароль должен быть не короче 8 символов")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError("Пароль не длиннее 128 символов")
    return value


def _check_secret(value: object) -> object:
    # Only emptiness is reported: the length of a *guess* is none of the caller's
    # business, see ``SecretField`` below.
    if isinstance(value, str) and not value:
        raise ValueError("Введите пароль")
    return value


#: 1..120 characters *after* stripping, matching ``users.name``. Pydantic strips
#: before it measures, so the bounds already reject whitespace-only names.
NameField = Annotated[
    str,
    BeforeValidator(_check_name),
    StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX_LENGTH),
]

#: New secrets get a strength floor. bcrypt's 72-byte ceiling is absorbed inside
#: ``app.core.security``, which folds longer secrets through SHA-256 first, so the
#: upper bound here only exists to keep request bodies bounded.
NewPasswordField = Annotated[
    str,
    BeforeValidator(_check_new_password),
    StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH),
]

#: A secret being *checked* rather than *set*. Deliberately unconstrained beyond
#: "non-empty": a 422 on a too-short guess would tell an attacker their guess was
#: the wrong shape, and it would lock out anyone whose password predates a rule
#: change. Wrong secrets belong to the service layer's 401/400, not to validation.
SecretField = Annotated[
    str,
    BeforeValidator(_check_secret),
    StringConstraints(min_length=1, max_length=PASSWORD_MAX_LENGTH),
]


class _EmailBody(BaseModel):
    """Shared normalisation: emails are compared and stored lowercased."""

    @field_validator("email", mode="after", check_fields=False)
    @classmethod
    def _normalise_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()


class RegisterIn(_EmailBody):
    """Регистрация нового пользователя."""

    name: NameField = Field(description=NAME_DESCRIPTION)
    email: EmailStr = Field(description=EMAIL_DESCRIPTION)
    password: NewPasswordField = Field(description=NEW_PASSWORD_DESCRIPTION)


class LoginIn(_EmailBody):
    """Вход по адресу электронной почты и паролю."""

    email: EmailStr = Field(description=EMAIL_DESCRIPTION)
    password: SecretField = Field(description=PASSWORD_DESCRIPTION)


class UpdateMeIn(_EmailBody):
    """Частичное изменение профиля. Пропущенное поле остаётся как было."""

    name: NameField | None = Field(default=None, description=NAME_DESCRIPTION)
    email: EmailStr | None = Field(default=None, description=EMAIL_DESCRIPTION)


class ChangePasswordIn(BaseModel):
    """Смена пароля: сначала текущий, затем новый."""

    current_password: SecretField = Field(description="Текущий пароль")
    new_password: NewPasswordField = Field(description=NEW_PASSWORD_DESCRIPTION)


__all__ = ["ChangePasswordIn", "LoginIn", "RegisterIn", "UpdateMeIn"]

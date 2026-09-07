from __future__ import annotations

import uuid

from app.schemas.common import ORMModel


class UserPublic(ORMModel):
    """Единственный вид, в котором пользователь уходит наружу: без хеша пароля."""

    id: uuid.UUID
    name: str
    email: str


class UserPrivate(UserPublic):
    """Собственный профиль — только для ответов ``/auth/*``.

    «Критическая точка бюджета» — личная настройка: согруппники не должны
    видеть её в каждом расходе, поэтому в :class:`UserPublic` (плательщик,
    участник, автор) её нет.
    """

    #: Свободная сумма на месяц в копейках, ``None`` пока не задана.
    monthly_budget_cents: int | None = None


__all__ = ["UserPrivate", "UserPublic"]

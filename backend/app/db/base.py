"""Declarative base and shared column conventions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.time import utcnow


class Base(DeclarativeBase):
    """Base class for every ORM model."""


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


def updated_at_column() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )


__all__ = ["Base", "created_at_column", "updated_at_column", "uuid_pk"]

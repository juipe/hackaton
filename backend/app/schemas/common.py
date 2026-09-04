"""Shared schema plumbing."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    """Base for response models read straight off ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    """Сообщение об ошибке в том виде, в каком его показывает интерфейс."""

    detail: str


__all__ = ["MessageOut", "ORMModel"]

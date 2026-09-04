from __future__ import annotations

import uuid

from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: uuid.UUID
    slug: str
    name: str
    icon: str
    sort_order: int


__all__ = ["CategoryOut"]

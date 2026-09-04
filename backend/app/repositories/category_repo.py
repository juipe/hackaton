from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.category import Category


def list_all(db: Session) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.sort_order, Category.name)))


def get(db: Session, category_id: uuid.UUID) -> Category | None:
    return db.get(Category, category_id)


def get_by_slug(db: Session, slug: str) -> Category | None:
    return db.scalar(select(Category).where(Category.slug == slug))


def map_by_slug(db: Session) -> dict[str, Category]:
    return {category.slug: category for category in list_all(db)}


__all__ = ["get", "get_by_slug", "list_all", "map_by_slug"]

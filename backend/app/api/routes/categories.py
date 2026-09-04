"""Expense category endpoints.

The category set is fixed seed data (``app.db.seed.ensure_categories``), so this is
a read-only list the client caches for the lifetime of a session.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.repositories import category_repo
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["Категории"])


@router.get("", response_model=list[CategoryOut], summary="Список категорий")
def list_categories(db: DbSession, _user: CurrentUser) -> list[CategoryOut]:
    return [CategoryOut.model_validate(category) for category in category_repo.list_all(db)]


__all__ = ["router"]

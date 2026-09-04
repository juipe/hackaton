"""Activity feed endpoints."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession, Membership
from app.schemas.activity import ActivityOut, to_activity_outs
from app.services import activity_service

router = APIRouter(tags=["Лента событий"])

#: The feed is a scrolling list, not a bulk export — a page is capped.
MAX_PAGE_SIZE = 100

Limit = Annotated[
    int, Query(ge=1, le=MAX_PAGE_SIZE, description="Сколько событий вернуть")
]
Offset = Annotated[int, Query(ge=0, description="Сколько событий пропустить")]


@router.get("/groups/{group_id}/activity", summary="Лента событий группы")
def list_group_activity(
    group_id: uuid.UUID,
    db: DbSession,
    _membership: Membership,
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[ActivityOut]:
    activities = activity_service.list_group_activity(
        db, group_id, limit=limit, offset=offset
    )
    return to_activity_outs(activities)


@router.get("/activity", summary="Лента событий по всем вашим группам")
def list_my_activity(
    db: DbSession,
    user: CurrentUser,
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[ActivityOut]:
    activities = activity_service.list_user_activity(
        db, user.id, limit=limit, offset=offset
    )
    return to_activity_outs(activities)


__all__ = ["router"]

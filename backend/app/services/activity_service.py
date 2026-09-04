"""Group activity log.

Every mutating service calls :func:`log_activity` so the feed stays complete.
The call never commits — it joins the caller's transaction, so an event can never
be recorded for work that was rolled back.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.activity import Activity, ActivityType
from app.repositories import activity_repo


def log_activity(
    db: Session,
    *,
    group_id: uuid.UUID,
    actor_id: uuid.UUID,
    type: ActivityType | str,
    entity_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
) -> Activity:
    activity = Activity(
        group_id=group_id,
        actor_id=actor_id,
        type=type.value if isinstance(type, ActivityType) else str(type),
        entity_id=entity_id,
        meta=meta or {},
    )
    db.add(activity)
    db.flush()
    return activity


def list_group_activity(
    db: Session, group_id: uuid.UUID, *, limit: int = 20, offset: int = 0
) -> list[Activity]:
    return activity_repo.list_for_group(db, group_id, limit=limit, offset=offset)


def list_user_activity(
    db: Session, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
) -> list[Activity]:
    return activity_repo.list_for_user(db, user_id, limit=limit, offset=offset)


__all__ = ["list_group_activity", "list_user_activity", "log_activity"]

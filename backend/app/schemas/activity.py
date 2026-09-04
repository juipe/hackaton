"""Activity feed schemas.

``ActivityOut`` is assembled by :func:`to_activity_out` rather than validated
straight off the ORM instance: the feed flattens ``activity.group.name`` into
``group_name`` and renames the ``metadata`` column (exposed as ``meta`` on the
model) so the wire shape stays stable regardless of storage details.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.models.activity import Activity
from app.schemas.common import ORMModel
from app.schemas.user import UserPublic
from app.utils.time import ensure_utc


class ActivityOut(ORMModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group_name: str
    actor_id: uuid.UUID
    actor: UserPublic
    type: str
    entity_id: uuid.UUID | None
    meta: dict[str, Any]
    created_at: datetime


def to_activity_out(activity: Activity) -> ActivityOut:
    return ActivityOut(
        id=activity.id,
        group_id=activity.group_id,
        group_name=activity.group.name,
        actor_id=activity.actor_id,
        actor=activity.actor,
        type=activity.type,
        entity_id=activity.entity_id,
        meta=activity.meta or {},
        created_at=ensure_utc(activity.created_at),
    )


def to_activity_outs(activities: list[Activity]) -> list[ActivityOut]:
    return [to_activity_out(activity) for activity in activities]


__all__ = ["ActivityOut", "to_activity_out", "to_activity_outs"]

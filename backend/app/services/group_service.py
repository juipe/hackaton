"""Group lifecycle and membership rules.

Nothing here commits: every function joins the caller's transaction so a route (or
another service, such as invite acceptance) decides when the unit of work is done.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BadRequest, Forbidden, NotFound
from app.models.activity import ActivityType
from app.models.group import Group
from app.models.member import GroupMember, GroupRole
from app.models.user import User
from app.repositories import group_repo
from app.schemas.group import GroupOut
from app.services import balance_service
from app.services.activity_service import log_activity


def _roles_for_user(
    db: Session, user_id: uuid.UUID, group_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """The caller's role in each of ``group_ids``, in a single query.

    Reading it off ``Group.members`` instead would lazy-load one collection per
    group, which is exactly the N+1 the group list has to avoid.
    """
    if not group_ids:
        return {}
    stmt = select(GroupMember.group_id, GroupMember.role).where(
        GroupMember.user_id == user_id, GroupMember.group_id.in_(group_ids)
    )
    return dict(db.execute(stmt).all())


def build_group_outs(db: Session, groups: list[Group], user_id: uuid.UUID) -> list[GroupOut]:
    """Serialize many groups with their counts, roles, nets and totals.

    Four bulk queries regardless of how many groups are passed in.
    """
    if not groups:
        return []
    group_ids = [group.id for group in groups]
    counts = group_repo.member_counts(db, group_ids)
    roles = _roles_for_user(db, user_id, group_ids)
    nets = balance_service.compute_user_group_nets(db, user_id)
    totals = balance_service.group_spending_totals(db, group_ids)
    return [
        GroupOut(
            id=group.id,
            name=group.name,
            description=group.description,
            currency=group.currency,
            owner_id=group.owner_id,
            created_at=group.created_at,
            updated_at=group.updated_at,
            member_count=counts.get(group.id, 0),
            my_role=roles.get(group.id, GroupRole.MEMBER.value),
            my_net_cents=nets.get(group.id, 0),
            total_spending_cents=totals.get(group.id, 0),
        )
        for group in groups
    ]


def build_group_out(db: Session, group: Group, user_id: uuid.UUID) -> GroupOut:
    return build_group_outs(db, [group], user_id)[0]


def add_member(
    db: Session, *, group: Group, user: User, role: str = GroupRole.MEMBER.value
) -> GroupMember:
    """Attach ``user`` to ``group``. Idempotent, so joining twice is harmless."""
    existing = group_repo.get_membership(db, group.id, user.id)
    if existing is not None:
        return existing
    membership = GroupMember(group_id=group.id, user_id=user.id, role=role)
    db.add(membership)
    db.flush()
    return membership


def create_group(
    db: Session,
    *,
    owner: User,
    name: str,
    description: str | None,
    currency: str,
) -> Group:
    group = Group(
        name=name.strip(),
        description=description,
        owner_id=owner.id,
        currency=currency.strip().upper(),
    )
    db.add(group)
    db.flush()
    add_member(db, group=group, user=owner, role=GroupRole.OWNER.value)
    log_activity(
        db,
        group_id=group.id,
        actor_id=owner.id,
        type=ActivityType.GROUP_CREATED,
        entity_id=group.id,
        meta={"name": group.name},
    )
    return group


def update_group(
    db: Session,
    *,
    group: Group,
    actor: User,
    name: str | None,
    description: str | None,
    currency: str | None,
    fields_set: set[str],
) -> Group:
    """Apply a PATCH.

    ``fields_set`` is the schema's ``model_fields_set``: it is the only way to tell
    ``{"description": null}`` (clear it) from an omitted key (leave it alone).
    ``name`` and ``currency`` are not nullable, so an explicit null is ignored.
    """
    changed: list[str] = []

    if "name" in fields_set and name is not None:
        cleaned = name.strip()
        if cleaned != group.name:
            group.name = cleaned
            changed.append("name")

    if "description" in fields_set and description != group.description:
        group.description = description
        changed.append("description")

    if "currency" in fields_set and currency is not None:
        upper = currency.strip().upper()
        if upper != group.currency:
            # Existing expenses keep the currency they were recorded in.
            group.currency = upper
            changed.append("currency")

    db.flush()
    log_activity(
        db,
        group_id=group.id,
        actor_id=actor.id,
        type=ActivityType.GROUP_UPDATED,
        entity_id=group.id,
        meta={"name": group.name, "changed": changed},
    )
    return group


def delete_group(db: Session, *, group: Group) -> None:
    """Delete a group; members, expenses, payments, invites and activity cascade."""
    db.delete(group)
    db.flush()


def remove_member(db: Session, *, group: Group, actor: User, user_id: uuid.UUID) -> None:
    """Remove ``user_id`` from ``group``, either as the owner or as a self-leave."""
    membership = group_repo.get_membership(db, group.id, user_id)
    if membership is None:
        raise NotFound("Участник не найден")

    if user_id != actor.id:
        actor_membership = group_repo.get_membership(db, group.id, actor.id)
        if actor_membership is None or actor_membership.role != GroupRole.OWNER.value:
            raise Forbidden("Удалять участников может только владелец группы")

    if membership.role == GroupRole.OWNER.value or user_id == group.owner_id:
        # The group would be left without an owner, and `groups.owner_id` is RESTRICT.
        raise BadRequest("Владельца группы удалить нельзя")

    net_cents = balance_service.compute_user_totals(db, user_id, [group.id]).net_cents
    if net_cents != 0:
        # Dropping them would silently move their debt onto everyone else.
        raise BadRequest("Перед удалением участника закройте его баланс")

    member_name = membership.user.name
    db.delete(membership)
    db.flush()
    log_activity(
        db,
        group_id=group.id,
        actor_id=actor.id,
        type=ActivityType.MEMBER_REMOVED,
        entity_id=user_id,
        meta={"name": member_name, "left": user_id == actor.id},
    )


__all__ = [
    "add_member",
    "build_group_out",
    "build_group_outs",
    "create_group",
    "delete_group",
    "remove_member",
    "update_group",
]

"""Group CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession, Membership, OwnerMembership
from app.repositories import group_repo
from app.schemas.group import GroupCreate, GroupOut, GroupUpdate
from app.services import group_service

router = APIRouter(prefix="/groups", tags=["Группы"])


@router.get("", summary="Список ваших групп")
def list_groups(db: DbSession, user: CurrentUser) -> list[GroupOut]:
    groups = group_repo.list_for_user(db, user.id)
    return group_service.build_group_outs(db, groups, user.id)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Создать группу")
def create_group(payload: GroupCreate, db: DbSession, user: CurrentUser) -> GroupOut:
    group = group_service.create_group(
        db,
        owner=user,
        name=payload.name,
        description=payload.description,
        currency=payload.currency,
    )
    db.commit()
    return group_service.build_group_out(db, group, user.id)


@router.get("/{group_id}", summary="Открыть группу")
def get_group(membership: Membership, db: DbSession, user: CurrentUser) -> GroupOut:
    return group_service.build_group_out(db, membership.group, user.id)


@router.patch("/{group_id}", summary="Изменить группу")
def update_group(
    payload: GroupUpdate, membership: OwnerMembership, db: DbSession, user: CurrentUser
) -> GroupOut:
    group = group_service.update_group(
        db,
        group=membership.group,
        actor=user,
        name=payload.name,
        description=payload.description,
        currency=payload.currency,
        fields_set=payload.model_fields_set,
    )
    db.commit()
    return group_service.build_group_out(db, group, user.id)


@router.delete(
    "/{group_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить группу"
)
def delete_group(membership: OwnerMembership, db: DbSession) -> Response:
    group_service.delete_group(db, group=membership.group)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

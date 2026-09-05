"""Debt-reminder notification endpoints. Always scoped to the caller."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.notification import NotificationOut
from app.services import debt_reminder_service

router = APIRouter(prefix="/notifications", tags=["Уведомления"])


@router.get("", response_model=list[NotificationOut], summary="Мои уведомления")
def list_notifications(db: DbSession, user: CurrentUser) -> list[NotificationOut]:
    return debt_reminder_service.list_for_user(db, user.id)


@router.post(
    "/read",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Отметить уведомления прочитанными",
)
def mark_notifications_read(db: DbSession, user: CurrentUser) -> Response:
    debt_reminder_service.mark_all_read(db, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]

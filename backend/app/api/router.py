"""Every route in the application, mounted under ``/api``."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    activity,
    auth,
    balances,
    categories,
    dashboard,
    expenses,
    groups,
    invites,
    members,
    notifications,
    payments,
    voice,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(auth.router)
api_router.include_router(groups.router)
api_router.include_router(members.router)
api_router.include_router(invites.router)
api_router.include_router(categories.router)
api_router.include_router(expenses.router)
api_router.include_router(voice.router)
api_router.include_router(balances.router)
api_router.include_router(payments.router)
api_router.include_router(dashboard.router)
api_router.include_router(activity.router)
api_router.include_router(notifications.router)


@api_router.get("/health", tags=["Служебное"], summary="Проверка работоспособности")
def health() -> dict[str, str]:
    return {"status": "ok"}


__all__ = ["api_router"]

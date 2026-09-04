"""Outbound notifications.

The MVP deliberately ships no email provider. The abstraction exists so wiring one
up later is a single new implementation plus a change to
:func:`get_notification_service` — nothing in the invite flow has to move.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("skladchina.notifications")


class NotificationService(ABC):
    @abstractmethod
    def send_group_invite(
        self,
        *,
        to_email: str,
        group_name: str,
        inviter_name: str,
        invite_url: str,
    ) -> str:
        """Deliver an invite and return the URL the invitee should open."""


class ConsoleNotificationService(NotificationService):
    """Development implementation: logs the invite and hands the URL back.

    The API returns that URL so the UI can show it and offer "copy link".
    """

    def send_group_invite(
        self,
        *,
        to_email: str,
        group_name: str,
        inviter_name: str,
        invite_url: str,
    ) -> str:
        logger.info(
            "Приглашение для %s в группу «%s» от %s: %s",
            to_email,
            group_name,
            inviter_name,
            invite_url,
        )
        return invite_url


_default_service: NotificationService = ConsoleNotificationService()


def get_notification_service() -> NotificationService:
    """Resolve the active implementation. FastAPI-dependency friendly."""
    return _default_service


def build_invite_url(token: str) -> str:
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}/invite/{token}"


__all__ = [
    "ConsoleNotificationService",
    "NotificationService",
    "build_invite_url",
    "get_notification_service",
]

"""Application error hierarchy.

Services raise these; ``app.main`` installs a handler that renders every one of them
as ``{"detail": "..."}`` with the right status code.
"""

from __future__ import annotations


class ApiError(Exception):
    """Base class for every error that should reach the client as a clean message."""

    status_code: int = 400

    def __init__(self, detail: str, status_code: int | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.detail


class BadRequest(ApiError):
    status_code = 400


class Unauthorized(ApiError):
    status_code = 401


class Forbidden(ApiError):
    status_code = 403


class NotFound(ApiError):
    status_code = 404


class Conflict(ApiError):
    status_code = 409


class UnprocessableEntity(ApiError):
    status_code = 422


__all__ = [
    "ApiError",
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "Conflict",
    "UnprocessableEntity",
]

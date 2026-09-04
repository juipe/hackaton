"""Auth cookie handling.

Two cookies work together:

* ``settings.cookie_name`` — the JWT session. **HttpOnly**, so script on the page
  can never read it, which is what makes XSS unable to steal the session.
* ``settings.csrf_cookie_name`` — a random token that is deliberately *not*
  HttpOnly. The SPA reads it and echoes it back in the ``X-CSRF-Token`` header;
  ``CsrfMiddleware`` requires the two to match on every unsafe request. A
  cross-site attacker can cause the browser to send the cookie but cannot read it
  to set the header, so the double-submit check holds.
"""

from __future__ import annotations

import uuid

from fastapi import Response

from app.core.config import settings
from app.core.security import create_access_token, generate_csrf_token


def set_auth_cookies(response: Response, user_id: uuid.UUID) -> str:
    """Issue a fresh session + CSRF cookie pair. Returns the CSRF token."""
    max_age = settings.access_token_expire_minutes * 60
    response.set_cookie(
        key=settings.cookie_name,
        value=create_access_token(user_id),
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
    return csrf_token


def clear_auth_cookies(response: Response) -> None:
    for key in (settings.cookie_name, settings.csrf_cookie_name):
        response.delete_cookie(
            key=key,
            path="/",
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
        )


__all__ = ["clear_auth_cookies", "set_auth_cookies"]

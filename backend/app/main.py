"""Application factory, middleware and error rendering."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings
from app.core.errors import ApiError
from app.core.security import tokens_match
from app.db.seed import ensure_categories
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger("skladchina")

#: Endpoints that cannot require a CSRF token because the caller has no cookies yet.
CSRF_EXEMPT_PATHS = frozenset(
    {
        "/api/auth/register",
        "/api/auth/login",
        "/api/auth/logout",
        "/api/health",
    }
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CsrfMiddleware(BaseHTTPMiddleware):
    """Double-submit CSRF check for every unsafe ``/api`` request.

    The session cookie is HttpOnly and ``SameSite=Lax``, which already blocks
    cross-site POSTs in modern browsers; this is the second, explicit layer.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        needs_check = (
            request.method not in SAFE_METHODS
            and path.startswith("/api")
            and path not in CSRF_EXEMPT_PATHS
        )
        if needs_check:
            cookie_token = request.cookies.get(settings.csrf_cookie_name)
            header_token = request.headers.get(settings.csrf_header_name)
            if not tokens_match(cookie_token, header_token):
                return JSONResponse({"detail": "Неверный CSRF-токен"}, status_code=403)
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Keep the category set in sync on boot.

    Wrapped in a try/except so the API still starts (and reports a clear error)
    when migrations have not been applied yet.
    """
    try:
        with SessionLocal() as session:
            ensure_categories(session)
            session.commit()
    except Exception as exc:  # pragma: no cover - depends on deployment state
        logger.warning("Could not ensure categories on startup: %s", exc)
    yield


#: Pydantic's own messages are English and not self-describing, so they are
#: rendered from the machine-readable error type instead of translated by text.
#: Anything unknown falls back to :data:`_FALLBACK_MESSAGE`.
_MESSAGE_BY_ERROR_TYPE: dict[str, str] = {
    "missing": "обязательное поле",
    "extra_forbidden": "лишнее поле",
    "string_type": "нужна строка",
    "string_too_short": "слишком короткое значение",
    "string_too_long": "слишком длинное значение",
    "string_pattern_mismatch": "значение не подходит по формату",
    "int_type": "нужно целое число",
    "int_parsing": "нужно целое число",
    "int_from_float": "нужно целое число",
    "float_type": "нужно число",
    "float_parsing": "нужно число",
    "decimal_type": "нужно число",
    "decimal_parsing": "нужно число",
    "bool_type": "нужно «да» или «нет»",
    "bool_parsing": "нужно «да» или «нет»",
    "uuid_type": "нужен идентификатор",
    "uuid_parsing": "нужен идентификатор",
    "datetime_type": "нужны дата и время",
    "datetime_parsing": "нужны дата и время",
    "date_type": "нужна дата",
    "date_parsing": "нужна дата",
    "date_from_datetime_parsing": "нужна дата",
    "list_type": "нужен список",
    "dict_type": "нужен объект",
    "enum": "недопустимое значение",
    "literal_error": "недопустимое значение",
    "greater_than": "значение слишком маленькое",
    "greater_than_equal": "значение слишком маленькое",
    "less_than": "значение слишком большое",
    "less_than_equal": "значение слишком большое",
    "too_short": "слишком мало элементов",
    "too_long": "слишком много элементов",
    "json_invalid": "тело запроса не разобрать",
}

_FALLBACK_MESSAGE = "некорректное значение"

#: Field names as a person reads them. Unknown names are shown as they are.
_FIELD_LABELS: dict[str, str] = {
    "amount_cents": "сумма",
    "category_id": "категория",
    "currency": "валюта",
    "current_password": "текущий пароль",
    "description": "описание",
    "email": "адрес электронной почты",
    "from_user_id": "отправитель",
    "group_id": "группа",
    "invited_email": "адрес электронной почты",
    "limit": "количество",
    "month": "месяц",
    "name": "имя",
    "new_password": "новый пароль",
    "note": "комментарий",
    "occurred_at": "дата",
    "offset": "смещение",
    "paid_at": "дата",
    "paid_by": "кто платил",
    "participants": "участники",
    "password": "пароль",
    "percentage": "процент",
    "role": "роль",
    "split_mode": "способ деления",
    "title": "название",
    "to_user_id": "получатель",
    "token": "токен",
    "user_id": "участник",
    "value": "значение",
}


def _field_label(parts: list[object]) -> str:
    return ".".join(_FIELD_LABELS.get(str(part), str(part)) for part in parts)


def _capitalised(text: str) -> str:
    return text[:1].upper() + text[1:]


def _first_validation_message(exc: RequestValidationError) -> str:
    """Turn Pydantic's error list into one human sentence.

    Messages raised by our own validators are already written for a person
    («Сумма процентов должна быть 100%»), so they are passed through untouched —
    the field name would only get in the way. Pydantic's built-in messages are
    English and not self-describing, so those are rendered from the error type
    and get the field prefixed.
    """
    errors = exc.errors()
    if not errors:
        return "Некорректный запрос"
    error = errors[0]
    message = str(error.get("msg", ""))
    if message.startswith("Value error, "):
        return message[len("Value error, ") :]
    if message.startswith("Assertion failed, "):
        return message[len("Assertion failed, ") :]
    if message.startswith("value is not a valid email address"):
        return "Неверный адрес электронной почты"
    error_type = str(error.get("type", ""))
    translated = _MESSAGE_BY_ERROR_TYPE.get(error_type, _FALLBACK_MESSAGE)
    location = [part for part in error.get("loc", ()) if part not in ("body", "query", "path")]
    if not location:
        return _capitalised(translated)
    return _capitalised(f"{_field_label(location)}: {translated}")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Учёт общих расходов для семьи, соседей по квартире, поездок и команд. "
            "Все суммы хранятся целыми числами в копейках — от базы до ответа API."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(CsrfMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ApiError)
    async def _api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(HTTPException)
    async def _http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Запрос не выполнен"
        return JSONResponse({"detail": detail}, status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse({"detail": _first_validation_message(exc)}, status_code=422)

    app.include_router(api_router)

    return app


app = create_app()

__all__ = ["CsrfMiddleware", "app", "create_app"]

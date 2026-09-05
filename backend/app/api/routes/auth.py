"""Authentication endpoints: registration, sign-in, profile and password changes."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.deps import CurrentUser, DbSession
from app.schemas.auth import ChangePasswordIn, LoginIn, RegisterIn, UpdateMeIn
from app.schemas.user import UserPublic
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Вход и профиль"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрироваться",
)
def register(payload: RegisterIn, response: Response, db: DbSession) -> UserPublic:
    user = auth_service.register(
        db, name=payload.name, email=payload.email, password=payload.password
    )
    set_auth_cookies(response, user.id)
    return UserPublic.model_validate(user)


@router.post("/login", summary="Войти")
def login(payload: LoginIn, response: Response, db: DbSession) -> UserPublic:
    user = auth_service.authenticate(db, email=payload.email, password=payload.password)
    set_auth_cookies(response, user.id)
    return UserPublic.model_validate(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Выйти",
)
def logout(response: Response) -> None:
    """Работает всегда — и для вошедшего, и для гостя: выход идемпотентен."""
    clear_auth_cookies(response)


@router.get("/me", summary="Мой профиль")
def read_me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@router.patch("/me", summary="Изменить профиль")
def update_me(payload: UpdateMeIn, user: CurrentUser, db: DbSession) -> UserPublic:
    updated = auth_service.update_profile(
        db,
        user=user,
        name=payload.name,
        email=payload.email,
        monthly_budget_cents=payload.monthly_budget_cents,
        fields_set=payload.model_fields_set,
    )
    return UserPublic.model_validate(updated)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Сменить пароль",
)
def change_password(
    payload: ChangePasswordIn, user: CurrentUser, db: DbSession
) -> None:
    auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )


__all__ = ["router"]

"""End-to-end coverage for the authentication endpoints."""

from __future__ import annotations

from collections.abc import Callable

import httpx
from fastapi.testclient import TestClient

from app.core.config import settings
from app.models.user import User

PASSWORD = "Passw0rd!"


def _register(
    client: TestClient,
    *,
    name: str = "Ada Lovelace",
    email: str = "ada@example.com",
    password: str = PASSWORD,
) -> httpx.Response:
    return client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password},
    )


def _set_cookie_header(response: httpx.Response, name: str) -> str:
    """The raw ``Set-Cookie`` line for ``name``, so flags can be asserted on."""
    for header in response.headers.get_list("set-cookie"):
        if header.startswith(f"{name}="):
            return header
    raise AssertionError(f"no Set-Cookie for {name!r}")


def _use_csrf_cookie(client: TestClient) -> str:
    """Echo the readable CSRF cookie back as the header, like the SPA does."""
    token = client.cookies.get(settings.csrf_cookie_name)
    assert token
    client.headers[settings.csrf_header_name] = token
    return token


def test_register_returns_public_user_and_sets_both_cookies(client: TestClient) -> None:
    response = _register(client, email="  Ada@Example.COM  ")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "name", "email"}
    assert body["name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"

    session_cookie = _set_cookie_header(response, settings.cookie_name)
    csrf_cookie = _set_cookie_header(response, settings.csrf_cookie_name)
    assert "httponly" in session_cookie.lower()
    assert "httponly" not in csrf_cookie.lower()
    assert client.cookies.get(settings.cookie_name)
    assert client.cookies.get(settings.csrf_cookie_name)


def test_register_rejects_a_duplicate_email(client: TestClient) -> None:
    assert _register(client).status_code == 201

    response = _register(client, name="Someone Else")

    assert response.status_code == 409
    assert response.json() == {"detail": "Этот адрес электронной почты уже зарегистрирован"}


def test_register_rejects_a_duplicate_email_in_another_case(client: TestClient) -> None:
    assert _register(client, email="ada@example.com").status_code == 201

    response = _register(client, email="ADA@Example.Com")

    assert response.status_code == 409
    assert response.json() == {"detail": "Этот адрес электронной почты уже зарегистрирован"}


def test_register_rejects_a_short_password(client: TestClient) -> None:
    assert _register(client, password="short7!").status_code == 422


def test_register_rejects_a_malformed_email(client: TestClient) -> None:
    assert _register(client, email="not-an-email").status_code == 422


def test_register_rejects_a_blank_name(client: TestClient) -> None:
    assert _register(client, name="   ").status_code == 422


def test_login_returns_the_user_and_signs_them_in(client: TestClient) -> None:
    created = _register(client).json()
    client.post("/api/auth/logout")

    response = client.post(
        "/api/auth/login", json={"email": "ADA@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert client.cookies.get(settings.cookie_name)
    assert client.get("/api/auth/me").json()["id"] == created["id"]


def test_login_with_a_wrong_password_is_rejected(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/api/auth/login", json={"email": "ada@example.com", "password": "Wr0ngPassw0rd!"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Неверный адрес электронной почты или пароль"}


def test_login_with_an_unknown_email_gives_the_same_answer(client: TestClient) -> None:
    _register(client)

    response = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Неверный адрес электронной почты или пароль"}


def test_me_is_unauthorised_while_anonymous(anon_client: TestClient) -> None:
    response = anon_client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Требуется вход"}


def test_me_returns_the_signed_in_user(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user(email="bea@example.com", name="Bea Rivers", password=PASSWORD)

    response = api_client(user).get("/api/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "name": "Bea Rivers",
        "email": "bea@example.com",
    }


def test_logout_clears_the_session(client: TestClient) -> None:
    _register(client)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/api/auth/me").status_code == 401


def test_update_me_changes_the_name(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user(name="Old Name", password=PASSWORD)
    signed_in = api_client(user)

    response = signed_in.patch("/api/auth/me", json={"name": "  New Name  "})

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert signed_in.get("/api/auth/me").json()["name"] == "New Name"


def test_update_me_rejects_an_email_owned_by_someone_else(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    make_user(email="taken@example.com", password=PASSWORD)
    user = make_user(email="mine@example.com", password=PASSWORD)

    response = api_client(user).patch("/api/auth/me", json={"email": "Taken@example.com"})

    assert response.status_code == 409
    assert response.json() == {"detail": "Этот адрес электронной почты уже зарегистрирован"}


def test_change_password_rejects_a_wrong_current_password(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user(password=PASSWORD)

    response = api_client(user).post(
        "/api/auth/change-password",
        json={"current_password": "Not-the-one1", "new_password": "BrandNew1!"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Текущий пароль неверен"}


def test_change_password_swaps_the_credentials(
    api_client: Callable[[User], TestClient], make_user: Callable[..., User]
) -> None:
    user = make_user(email="cara@example.com", password=PASSWORD)
    signed_in = api_client(user)

    response = signed_in.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "BrandNew1!"},
    )
    assert response.status_code == 204

    signed_in.post("/api/auth/logout")
    old = signed_in.post(
        "/api/auth/login", json={"email": "cara@example.com", "password": PASSWORD}
    )
    assert old.status_code == 401

    new = signed_in.post(
        "/api/auth/login", json={"email": "cara@example.com", "password": "BrandNew1!"}
    )
    assert new.status_code == 200
    assert new.json()["id"] == str(user.id)


def test_a_password_longer_than_bcrypts_limit_round_trips(client: TestClient) -> None:
    """bcrypt reads only 72 bytes, so longer secrets are pre-hashed in security.py."""
    long_password = "L" + "o" * 97 + "ng"
    assert len(long_password) == 100

    assert _register(client, email="dev@example.com", password=long_password).status_code == 201
    client.post("/api/auth/logout")

    truncated = client.post(
        "/api/auth/login",
        json={"email": "dev@example.com", "password": long_password[:72]},
    )
    assert truncated.status_code == 401

    response = client.post(
        "/api/auth/login", json={"email": "dev@example.com", "password": long_password}
    )
    assert response.status_code == 200


def test_unsafe_request_without_the_csrf_header_is_forbidden(client: TestClient) -> None:
    _register(client)
    client.headers.pop(settings.csrf_header_name, None)

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "BrandNew1!"},
    )

    assert response.status_code == 403


def test_unsafe_request_with_a_mismatched_csrf_header_is_forbidden(
    client: TestClient,
) -> None:
    _register(client)
    _use_csrf_cookie(client)
    client.headers[settings.csrf_header_name] = "not-the-cookie-value"

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "BrandNew1!"},
    )

    assert response.status_code == 403


def test_change_password_succeeds_with_the_echoed_csrf_token(client: TestClient) -> None:
    _register(client)
    _use_csrf_cookie(client)

    response = client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "BrandNew1!"},
    )

    assert response.status_code == 204

"""Shared pytest fixtures.

The environment is configured *before* any ``app.*`` import so the settings
singleton and the engine pick up the SQLite test database.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator

os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-not-real")
os.environ.setdefault("FRONTEND_BASE_URL", "http://testserver")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.seed import ensure_categories  # noqa: E402
from app.db.session import SessionLocal, engine, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.group import Group  # noqa: E402
from app.models.member import GroupMember, GroupRole  # noqa: E402
from app.models.user import User  # noqa: E402

DEFAULT_PASSWORD = "Passw0rd!"


@pytest.fixture()
def db() -> Iterator[Session]:
    """A clean schema plus seeded categories, per test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    ensure_categories(session)
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> Iterator[TestClient]:
    """TestClient wired to the test session.

    ``raise_server_exceptions=False`` is deliberately *not* set: an unexpected
    exception should fail the test loudly rather than turn into a 500 assertion.
    """

    def _override_get_db() -> Iterator[Session]:
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    with TestClient(fastapi_app, base_url="http://testserver") as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()


@pytest.fixture()
def categories(db: Session) -> list[Category]:
    from app.repositories import category_repo

    return category_repo.list_all(db)


@pytest.fixture()
def make_user(db: Session) -> Callable[..., User]:
    counter = {"n": 0}

    def _make(
        email: str | None = None,
        name: str | None = None,
        password: str = DEFAULT_PASSWORD,
    ) -> User:
        counter["n"] += 1
        index = counter["n"]
        user = User(
            name=name or f"User {index}",
            email=(email or f"user{index}-{uuid.uuid4().hex[:6]}@example.com").strip().lower(),
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture()
def api_client(client: TestClient) -> Callable[[User], TestClient]:
    """Sign the shared TestClient in as ``user``.

    Returns the same client with swapped cookies, so a test can hop between
    identities simply by calling it again.
    """

    def _authenticate(user: User) -> TestClient:
        csrf_token = f"csrf-{uuid.uuid4().hex}"
        client.cookies.set(settings.cookie_name, create_access_token(user.id))
        client.cookies.set(settings.csrf_cookie_name, csrf_token)
        client.headers[settings.csrf_header_name] = csrf_token
        return client

    return _authenticate


@pytest.fixture()
def anon_client(client: TestClient) -> TestClient:
    client.cookies.clear()
    client.headers.pop(settings.csrf_header_name, None)
    return client


@pytest.fixture()
def group_factory(db: Session) -> Callable[..., Group]:
    def _make(
        owner: User,
        name: str = "Test group",
        currency: str = "RUB",
        members: tuple[User, ...] | list[User] = (),
        description: str | None = None,
    ) -> Group:
        group = Group(
            name=name, currency=currency, owner_id=owner.id, description=description
        )
        db.add(group)
        db.flush()
        db.add(GroupMember(group_id=group.id, user_id=owner.id, role=GroupRole.OWNER.value))
        for member in members:
            if member.id == owner.id:
                continue
            db.add(
                GroupMember(group_id=group.id, user_id=member.id, role=GroupRole.MEMBER.value)
            )
        db.commit()
        db.refresh(group)
        return group

    return _make

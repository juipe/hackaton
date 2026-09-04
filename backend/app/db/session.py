"""Engine and session factory.

Postgres is the runtime database. SQLite is supported so the test suite can run
without any external service, which is why the engine arguments branch on the URL.
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings


def _engine_kwargs(url: str) -> dict[str, Any]:
    if url.startswith("sqlite"):
        # A single shared connection keeps an in-memory database alive across
        # sessions and threads (TestClient runs handlers in a worker thread).
        return {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    return {"pool_pre_ping": True}


engine: Engine = create_engine(
    settings.database_url, future=True, **_engine_kwargs(settings.database_url)
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
    """SQLite ignores foreign keys unless asked; we rely on ON DELETE CASCADE."""
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = ["SessionLocal", "engine", "get_db"]

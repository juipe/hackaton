"""Application settings, loaded from the environment (and an optional ``.env``)."""

from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Складчина"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://skladchina:skladchina@localhost:5432/skladchina"

    secret_key: str = "dev-secret-change-me-please-32-chars-minimum"
    access_token_expire_minutes: int = 60 * 24 * 7

    cookie_name: str = "skladchina_session"
    csrf_cookie_name: str = "skladchina_csrf"
    csrf_header_name: str = "X-CSRF-Token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    frontend_base_url: str = "http://localhost:5173"

    invite_expire_hours: int = 24 * 14

    # Voice expense pipeline — Whisper and Qwen both run locally, no external
    # AI API is ever called. See services/whisper_service.py and
    # services/ollama_service.py.
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout_seconds: int = 120
    voice_max_upload_bytes: int = 15 * 1024 * 1024

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept both a JSON array and a plain comma separated string."""
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("["):
                import json

                return json.loads(raw)
            return [part.strip() for part in raw.split(",") if part.strip()]
        return value

    @field_validator("cookie_samesite", mode="before")
    @classmethod
    def _normalise_samesite(cls, value: object) -> object:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"lax", "strict", "none"}:
                return lowered
        return "lax"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()

__all__ = ["Settings", "settings"]

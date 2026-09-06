"""Application settings, loaded from the environment (and an optional ``.env``)."""

from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "СберВместе"
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

    # AI pipeline — GigaAM (speech-to-text) runs locally, GigaChat (structured
    # extraction, saving tips, debt-reminder wording) is a remote API. See
    # services/gigaam_service.py and services/gigachat_service.py.
    #
    # GigaAM runs in-process (transformers + torch); the weights are pulled
    # from Hugging Face on first use and cached under HF_HOME.
    gigaam_model: str = "ai-sage/GigaAM-v3"
    gigaam_revision: str = "e2e_rnnt"
    gigaam_device: str = "cpu"
    gigaam_ffmpeg_binary: str = "ffmpeg"

    # GigaChat — the LLM provider. `gigachat_credentials` is the base64
    # Authorization Key and is a SECRET: it lives in .env only, never in the
    # image, the repo or a log line. It is exchanged at `gigachat_auth_url`
    # for a 30-minute access token, which the service caches and refreshes on
    # its own; inference goes to `gigachat_base_url` + /v1/chat/completions.
    # Empty credentials are not a crash — every AI caller already degrades
    # gracefully, so the app still runs (without AI) with no key configured.
    gigachat_credentials: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_model: str = "GigaChat-3-Ultra"
    gigachat_base_url: str = "https://api.giga.chat"
    # The only documented token endpoint; api.giga.chat does not serve one.
    gigachat_auth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    # A remote API, not local inference: seconds, not minutes. Must stay below
    # the reverse proxy's proxy_read_timeout (see frontend/nginx.conf).
    gigachat_timeout_seconds: int = 45
    gigachat_auth_timeout_seconds: int = 15
    gigachat_temperature: float = 0.1
    #: Ask for `response_format: json_schema`. On by default; an escape hatch
    #: for a deployment whose model build does not accept the parameter.
    gigachat_structured_output: bool = True
    #: Extra CA bundle for GigaChat's TLS chain. Empty means the copy of the
    #: Russian Trusted CA shipped in app/certs — see gigachat_service.
    gigachat_ca_bundle: str = ""
    #: Never turn this off outside a broken corporate-proxy emergency.
    gigachat_verify_ssl: bool = True

    voice_max_upload_bytes: int = 15 * 1024 * 1024

    # Debt-reminder notifications — see services/debt_reminder_service.py. The
    # delay is a plain column value (``available_at``), not a scheduled job, so
    # it survives a process restart with no extra machinery.
    debt_reminder_delay_seconds: int = 10

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

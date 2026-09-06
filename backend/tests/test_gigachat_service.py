"""Unit tests for ``gigachat_service`` — the LLM transport, auth and parser.

No real GigaChat API (and no real key) is ever contacted: ``httpx.post`` is
monkeypatched at the module level to return canned responses. The sections
below pin, in order: the OAuth token exchange and its caching/refresh rules,
the completions request wire format, and response parsing plus every failure
mode of ``extract_expense``, ``generate_saving_tips`` and
``generate_debt_reminder``.

The one rule that outranks the rest: no test here may make a network call, and
no assertion may need a credential — ``conftest`` blanks
``GIGACHAT_CREDENTIALS`` for the whole suite, so a request that escaped the
monkeypatch would fail loudly rather than quietly bill someone.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.schemas.notification import DebtReminderInput
from app.schemas.saving_tips import SavingTipsInput
from app.services import gigachat_service

_AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
_BASE_URL = "https://api.giga.chat"


@pytest.fixture(autouse=True)
def _provider_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Real-looking config plus an empty token cache for every test.

    The cache is process-wide by design (see ``_TokenCache``), so a test that
    inherited a token from the previous one would silently stop exercising the
    auth path.
    """
    monkeypatch.setattr(settings, "gigachat_credentials", "dGVzdDp0ZXN0")
    monkeypatch.setattr(settings, "gigachat_base_url", _BASE_URL)
    monkeypatch.setattr(settings, "gigachat_auth_url", _AUTH_URL)
    monkeypatch.setattr(settings, "gigachat_model", "GigaChat-3-Ultra")
    monkeypatch.setattr(settings, "gigachat_scope", "GIGACHAT_API_PERS")
    gigachat_service._token_cache.invalidate()


# ------------------------------------------------------------------- plumbing


class _FakeResponse:
    def __init__(self, body: Any, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                str(self.status_code),
                request=httpx.Request("POST", _BASE_URL),
                response=self,  # type: ignore[arg-type]
            )

    def json(self) -> Any:
        return self._body


def _completion(content: str) -> dict[str, Any]:
    """The envelope the OpenAI-compatible /v1/chat/completions returns."""
    return {
        "choices": [{"message": {"role": "assistant", "content": content}, "index": 0}],
        "model": "GigaChat-3-Ultra",
        "object": "chat.completion",
    }


def _token_body(expires_in_seconds: float = 1800.0) -> dict[str, Any]:
    """The auth envelope — note ``expires_at`` is epoch **milliseconds**."""
    return {
        "access_token": "test-access-token",
        "expires_at": int((time.time() + expires_in_seconds) * 1000),
    }


def _patch_post(
    monkeypatch: pytest.MonkeyPatch,
    response_text: str,
    *,
    token_body: dict[str, Any] | None = None,
    completion_statuses: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Route auth calls and completion calls to canned answers.

    Returns the list recording every request, so a test can assert on both
    what was sent and how many of each kind happened. ``completion_statuses``
    supplies a status code per completion call, for the 401-retry tests.
    """
    calls: list[dict[str, Any]] = []
    statuses = list(completion_statuses or [])

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        calls.append({"url": url, **kwargs})
        if url == settings.gigachat_auth_url:
            return _FakeResponse(token_body if token_body is not None else _token_body())
        status = statuses.pop(0) if statuses else 200
        return _FakeResponse(_completion(response_text), status_code=status)

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)
    return calls


def _patch_completion_body(monkeypatch: pytest.MonkeyPatch, body: Any) -> None:
    """Return an arbitrary (possibly malformed) completion envelope."""

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        return _FakeResponse(body)

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)


def _auth_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for call in calls if call["url"] == settings.gigachat_auth_url]


def _completion_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for call in calls if call["url"] != settings.gigachat_auth_url]


def _reminder_input() -> DebtReminderInput:
    return DebtReminderInput(
        expense="Ужин",
        amount_due="1250.00",
        currency="RUB",
        payer="Алиса",
        group="Квартира",
    )


def _payload() -> SavingTipsInput:
    return SavingTipsInput(
        total_spending_display="500,00 ₽",
        expense_count=5,
        currency="RUB",
        categories=[],
        trend=None,
    )


# ------------------------------------------------------------ authentication


def test_token_request_uses_basic_key_scope_and_rquid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the documented OAuth exchange: form-encoded scope, the base64
    Authorization Key as Basic auth, and a per-request uuid4 RqUID."""
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    auth = _auth_calls(calls)
    assert len(auth) == 1
    assert auth[0]["url"] == _AUTH_URL
    assert auth[0]["data"] == {"scope": "GIGACHAT_API_PERS"}
    assert auth[0]["timeout"] == settings.gigachat_auth_timeout_seconds
    headers = auth[0]["headers"]
    assert headers["Authorization"] == "Basic dGVzdDp0ZXN0"
    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    # uuid4, freshly generated per request.
    assert len(headers["RqUID"]) == 36


def test_token_is_reused_across_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 30-minute token must be cached — one auth request, not one per
    completion, however many completions are made."""
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())
    gigachat_service.generate_debt_reminder(_reminder_input())
    gigachat_service.generate_debt_reminder(_reminder_input())

    assert len(_auth_calls(calls)) == 1
    assert len(_completion_calls(calls)) == 3
    assert _completion_calls(calls)[0]["headers"]["Authorization"] == "Bearer test-access-token"


def test_expired_token_is_refreshed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A token already past its expiry is replaced before the next call."""
    calls = _patch_post(
        monkeypatch, '{"message": "ок"}', token_body=_token_body(expires_in_seconds=-1)
    )

    gigachat_service.generate_debt_reminder(_reminder_input())
    gigachat_service.generate_debt_reminder(_reminder_input())

    assert len(_auth_calls(calls)) == 2


def test_token_expiring_within_the_skew_is_refreshed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token with seconds left must not be sent — it would expire in flight."""
    calls = _patch_post(
        monkeypatch, '{"message": "ок"}', token_body=_token_body(expires_in_seconds=30)
    )

    gigachat_service.generate_debt_reminder(_reminder_input())
    gigachat_service.generate_debt_reminder(_reminder_input())

    assert len(_auth_calls(calls)) == 2


def test_401_from_completions_refreshes_the_token_and_retries_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A token can lapse between the cache check and the server; one retry
    with a fresh token is the fix, and it must not become a loop."""
    calls = _patch_post(
        monkeypatch, '{"message": "ок"}', completion_statuses=[401, 200]
    )

    result = gigachat_service.generate_debt_reminder(_reminder_input())

    assert result.message == "ок"
    assert len(_completion_calls(calls)) == 2
    assert len(_auth_calls(calls)) == 2


def test_repeated_401_is_an_error_not_an_endless_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_post(
        monkeypatch, '{"message": "ок"}', completion_statuses=[401, 401]
    )

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())

    assert len(_completion_calls(calls)) == 2


def test_missing_credentials_fail_without_any_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No key configured must fail immediately and locally — never as a
    request that leaks an empty Authorization header to Sber."""
    monkeypatch.setattr(settings, "gigachat_credentials", "  ")
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())

    assert calls == []


def test_auth_failure_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(url: str, **_kwargs: Any) -> _FakeResponse:
        return _FakeResponse({"message": "Unauthorized"}, status_code=401)

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_auth_response_without_a_token_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(monkeypatch, '{"message": "ок"}', token_body={"expires_at": 0})

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_errors_never_leak_the_key_or_the_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Authorization Key and the bearer token must not reach a log line or
    an exception message by any path — httpx puts the full URL (and offers the
    body) on its own exceptions, which is exactly why they are not reused."""
    monkeypatch.setattr(settings, "gigachat_credentials", "SUPERSECRETKEY==")

    def _post(url: str, **_kwargs: Any) -> _FakeResponse:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        return _FakeResponse({"message": "no"}, status_code=403)

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError) as excinfo:
        gigachat_service.generate_debt_reminder(_reminder_input())

    rendered = str(excinfo.value)
    assert "SUPERSECRETKEY==" not in rendered
    assert "test-access-token" not in rendered
    assert "Bearer" not in rendered
    assert "403" in rendered


# ------------------------------------------------------------------ transport


def test_request_targets_chat_completions_with_the_configured_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the wire format: the OpenAI-compatible path on the configured base
    URL, the configured model, the system/user message split, non-streaming,
    and a bearer token rather than the raw key."""
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    call = _completion_calls(calls)[0]
    assert call["url"] == "https://api.giga.chat/v1/chat/completions"
    assert call["timeout"] == settings.gigachat_timeout_seconds
    assert call["headers"]["Authorization"] == "Bearer test-access-token"

    body = call["json"]
    assert body["model"] == "GigaChat-3-Ultra"
    assert body["stream"] is False
    assert [message["role"] for message in body["messages"]] == ["system", "user"]
    assert body["messages"][0]["content"]
    assert body["messages"][1]["content"]


def test_base_url_trailing_slash_does_not_double_up(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "gigachat_base_url", "https://api.giga.chat/")
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    assert _completion_calls(calls)[0]["url"] == "https://api.giga.chat/v1/chat/completions"


def test_structured_output_is_requested_with_a_strict_json_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    response_format = _completion_calls(calls)[0]["json"]["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert response_format["schema"]["required"] == ["message"]


def test_structured_output_can_be_switched_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """The escape hatch for a deployment whose model build rejects the
    parameter — the prompts already demand bare JSON on their own."""
    monkeypatch.setattr(settings, "gigachat_structured_output", False)
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    assert "response_format" not in _completion_calls(calls)[0]["json"]


def test_tls_verification_uses_the_bundled_russian_ca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both GigaChat hosts chain to a CA no mainstream trust store carries, so
    verification must stay on *and* know about it — never be switched off."""
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    gigachat_service.generate_debt_reminder(_reminder_input())

    for call in calls:
        assert call["verify"] is not False
    assert gigachat_service._CA_BUNDLE.is_file()


def test_missing_choices_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 with no completion in it must not become an empty draft."""
    _patch_completion_body(monkeypatch, {"object": "chat.completion", "choices": []})

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_empty_content_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion_body(monkeypatch, _completion("   "))

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_unexpected_envelope_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_completion_body(monkeypatch, {"error": "model not found"})

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


@pytest.mark.parametrize("status", [400, 403, 404, 422, 429, 500, 503])
def test_http_error_statuses_are_errors(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    """Every documented provider failure — bad request, forbidden, unknown
    model, validation, rate limit, provider outage — reaches callers as the
    one error type they already know how to degrade on."""
    _patch_post(monkeypatch, '{"message": "ок"}', completion_statuses=[status])

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_timeout_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(url: str, **_kwargs: Any) -> Any:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        raise httpx.ReadTimeout("model is still thinking")

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_connection_error_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _post(url: str, **_kwargs: Any) -> Any:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


# ----------------------------------------------------------- expense extraction


class _FakeCategory:
    """Just the two attributes the prompt builder reads off a Category."""

    def __init__(self, slug: str, name: str) -> None:
        self.slug = slug
        self.name = name


_CATEGORIES = [_FakeCategory("food", "Еда"), _FakeCategory("other", "Другое")]


def test_extract_expense_parses_the_model_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _patch_post(
        monkeypatch,
        '{"title": "Обед", "description": null, "amount": "500", "occurred_at": null, '
        '"category_slug": "food", "payer_name": "я", "split_mode": "equal", '
        '"participants": [{"name": "Максим", "value": null}]}',
    )

    result = gigachat_service.extract_expense("Заплатил за обед 500 рублей", _CATEGORIES)

    assert result.title == "Обед"
    assert result.amount == "500"
    assert result.category_slug == "food"
    assert result.split_mode == "equal"
    assert [p.name for p in result.participants] == ["Максим"]
    # The transcript is the user message; the real categories go in the system
    # prompt so the model can only ever pick a slug that exists.
    messages = _completion_calls(calls)[0]["json"]["messages"]
    assert messages[1]["content"] == "Заплатил за обед 500 рублей"
    assert "food: Еда" in messages[0]["content"]
    assert "other: Другое" in messages[0]["content"]


def test_extract_expense_sends_the_extraction_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The schema handed to the provider must match the fields
    ``LLMExpenseExtraction`` declares — nothing more, nothing less."""
    calls = _patch_post(monkeypatch, "{}")

    gigachat_service.extract_expense("кхм", _CATEGORIES)

    schema = _completion_calls(calls)[0]["json"]["response_format"]["schema"]
    from app.schemas.voice import LLMExpenseExtraction

    assert set(schema["properties"]) == set(LLMExpenseExtraction.model_fields)


def test_extract_expense_coerces_numeric_answers_to_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GigaChat answers ``"amount": 1200`` often enough to matter, schema or
    not. The contract types it as a string and the money code parses it as
    one, so a JSON number is the same answer in the wrong wire type — coerced,
    never rounded or recomputed."""
    _patch_post(
        monkeypatch,
        '{"title": "Такси", "amount": 1200, "category_slug": "other", '
        '"payer_name": "я", "split_mode": "exact", '
        '"participants": [{"name": "Максим", "value": 500}, '
        '{"name": "я", "value": 700.5}]}',
    )

    result = gigachat_service.extract_expense("Заплатил 1200 за такси", _CATEGORIES)

    assert result.amount == "1200"
    assert [p.value for p in result.participants] == ["500", "700.5"]


def test_extract_expense_unwraps_a_markdown_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fence is a formatting artefact, not a different answer."""
    _patch_post(monkeypatch, '```json\n{"title": "Обед", "amount": "500"}\n```')

    result = gigachat_service.extract_expense("Заплатил за обед", _CATEGORIES)

    assert result.title == "Обед"
    assert result.amount == "500"


def test_extract_expense_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, "конечно, вот расход:")

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_rejects_wrong_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid JSON of the wrong type — a list where an object is required.
    _patch_post(monkeypatch, '[{"title": "Обед"}]')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_rejects_wrong_field_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``participants`` must stay a list of name/value objects — a bare list of
    strings is exactly the shape the resolution logic downstream cannot read."""
    _patch_post(monkeypatch, '{"title": "Обед", "participants": ["Максим", "я"]}')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_accepts_an_all_null_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """"Nothing recognisable was said" is a legitimate answer, not an error —
    every field is optional, and the draft is then filled in by the user."""
    _patch_post(monkeypatch, "{}")

    result = gigachat_service.extract_expense("кхм", _CATEGORIES)

    assert result.title is None
    assert result.amount is None
    assert result.participants == []


# ------------------------------------------------------------------ saving tips


def test_generate_saving_tips_returns_parsed_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _patch_post(
        monkeypatch,
        '{"tips": ['
        '{"title": "Еда", "text": "Еда — 31% расходов.", "type": "data_driven"}, '
        '{"title": "Лимит", "text": "Установите недельный лимит.", "type": "generic"}'
        "]}",
    )

    result = gigachat_service.generate_saving_tips(_payload())

    assert len(result.tips) == 2
    assert result.tips[0].type == "data_driven"
    assert result.tips[1].type == "generic"
    # The backend's already-formatted numbers are what the model is given.
    assert json.loads(_completion_calls(calls)[0]["json"]["messages"][1]["content"]) == {
        "total_spending_display": "500,00 ₽",
        "expense_count": 5,
        "currency": "RUB",
        "categories": [],
        "trend": None,
    }


def test_generate_saving_tips_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(monkeypatch, "not json at all")

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_saving_tips(_payload())


def test_generate_saving_tips_rejects_wrong_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Valid JSON, but no "tips" key at all.
    _patch_post(monkeypatch, '{"advice": "sure"}')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_saving_tips(_payload())


def test_generate_saving_tips_rejects_wrong_tip_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only one tip — the schema requires 2 or 3.
    _patch_post(
        monkeypatch,
        '{"tips": [{"title": "Еда", "text": "Еда — 31%.", "type": "data_driven"}]}',
    )

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_saving_tips(_payload())


def test_generate_saving_tips_wraps_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _post(url: str, **_kwargs: Any) -> Any:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_saving_tips(_payload())


# --------------------------------------------------------------- debt reminders


def test_generate_debt_reminder_returns_parsed_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(
        monkeypatch,
        '{"message": "Не забудьте вернуть Алисе 1250 ₽ за «Ужин»."}',
    )

    result = gigachat_service.generate_debt_reminder(_reminder_input())

    assert result.message == "Не забудьте вернуть Алисе 1250 ₽ за «Ужин»."


def test_generate_debt_reminder_rejects_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(monkeypatch, "not json at all")

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_wrong_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Valid JSON, but no "message" key at all.
    _patch_post(monkeypatch, '{"text": "sure"}')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_empty_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_post(monkeypatch, '{"message": ""}')

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_wraps_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _post(url: str, **_kwargs: Any) -> Any:
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)

    with pytest.raises(gigachat_service.GigaChatError):
        gigachat_service.generate_debt_reminder(_reminder_input())


# ----------------------------------------------------------------- TLS config


def _reset_ssl_cache() -> None:
    """``_verify`` memoises its context process-wide; drop it between tests."""
    gigachat_service._ssl_context = None


def test_verify_defaults_to_a_real_ssl_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The secure default: verification stays on, with the Russian CA loaded."""
    import ssl

    monkeypatch.setattr(settings, "gigachat_verify_ssl", True)
    _reset_ssl_cache()

    verify = gigachat_service._verify()

    assert isinstance(verify, ssl.SSLContext)
    assert verify.verify_mode == ssl.CERT_REQUIRED
    assert verify.check_hostname is True
    _reset_ssl_cache()


def test_verify_ssl_false_disables_certificate_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The documented escape hatch returns ``False``, not a lax context."""
    monkeypatch.setattr(settings, "gigachat_verify_ssl", False)
    _reset_ssl_cache()

    assert gigachat_service._verify() is False
    _reset_ssl_cache()


def test_verify_ssl_false_is_scoped_to_the_gigachat_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Disabling it must not touch global/default SSL for anyone else.

    Both GigaChat calls (auth and completions) pick the flag up, while
    ``ssl.create_default_context`` — what every unrelated client builds from —
    still verifies.
    """
    import ssl

    monkeypatch.setattr(settings, "gigachat_verify_ssl", False)
    _reset_ssl_cache()

    seen: list[Any] = []

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        seen.append(kwargs.get("verify"))
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        return _FakeResponse(_completion('{"message": "ок"}'))

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)
    gigachat_service.generate_debt_reminder(_reminder_input())

    assert seen == [False, False]

    # An unrelated client is unaffected: the process-wide default still verifies.
    default = ssl.create_default_context()
    assert default.verify_mode == ssl.CERT_REQUIRED
    assert default.check_hostname is True
    _reset_ssl_cache()


def test_verify_ssl_true_passes_a_context_to_both_gigachat_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ssl

    monkeypatch.setattr(settings, "gigachat_verify_ssl", True)
    _reset_ssl_cache()

    seen: list[Any] = []

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        seen.append(kwargs.get("verify"))
        if url == settings.gigachat_auth_url:
            return _FakeResponse(_token_body())
        return _FakeResponse(_completion('{"message": "ок"}'))

    monkeypatch.setattr(gigachat_service.httpx, "post", _post)
    gigachat_service.generate_debt_reminder(_reminder_input())

    assert len(seen) == 2
    assert all(isinstance(v, ssl.SSLContext) for v in seen)
    _reset_ssl_cache()

"""Unit tests for ``ollama_service`` — the local LLM transport and parser.

No real Ollama server (and no model) is ever contacted: ``httpx.post`` is
monkeypatched at the module level to return canned responses. The first
section pins the request this module sends to Ollama; the rest exercises
response parsing and every failure mode of ``extract_expense``,
``generate_saving_tips`` and ``generate_debt_reminder``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.core.config import settings
from app.schemas.notification import DebtReminderInput
from app.schemas.saving_tips import SavingTipsInput
from app.services import ollama_service

# ------------------------------------------------------------------- transport


def test_request_targets_the_generate_endpoint_with_json_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pins the wire format: Ollama's /api/generate, the configured model, the
    system/prompt split, non-streaming, and ``format: "json"``. ``think: False``
    matters because a hybrid-reasoning Qwen otherwise puts the whole answer in a
    separate "thinking" field and leaves "response" empty."""
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    ollama_service.generate_debt_reminder(_reminder_input())

    assert len(calls) == 1
    call = calls[0]
    assert call["url"] == f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    assert call["timeout"] == settings.ollama_timeout_seconds

    body = call["json"]
    assert body["model"] == settings.ollama_model
    assert body["format"] == "json"
    assert body["stream"] is False
    assert body["think"] is False
    assert body["system"] and body["prompt"]


def test_base_url_trailing_slash_does_not_double_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ollama_base_url", "http://host.docker.internal:11434/")
    calls = _patch_post(monkeypatch, '{"message": "ок"}')

    ollama_service.generate_debt_reminder(_reminder_input())

    assert calls[0]["url"] == "http://host.docker.internal:11434/api/generate"


def test_missing_response_field_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 200 with no completion in it must not become an empty draft."""
    _patch_body(monkeypatch, {"model": "qwen3.5:9b", "done": True})

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_unexpected_envelope_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    # Right status, but not the shape Ollama documents.
    _patch_body(monkeypatch, {"error": "model not found"})

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_http_error_status_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ErrorResponse(_FakeResponse):
        def raise_for_status(self) -> None:
            raise httpx.HTTPStatusError(
                "503",
                request=httpx.Request("POST", "http://localhost:11434"),
                response=None,  # type: ignore[arg-type]
            )

    monkeypatch.setattr(
        ollama_service.httpx, "post", lambda *args, **kwargs: _ErrorResponse({})
    )

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_timeout_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise httpx.ReadTimeout("model is still thinking")

    monkeypatch.setattr(ollama_service.httpx, "post", _raise)

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


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

    result = ollama_service.extract_expense("Заплатил за обед 500 рублей", _CATEGORIES)

    assert result.title == "Обед"
    assert result.amount == "500"
    assert result.category_slug == "food"
    assert result.split_mode == "equal"
    assert [p.name for p in result.participants] == ["Максим"]
    # The transcript is the prompt; the real categories go in the system prompt
    # so the model can only ever pick a slug that exists.
    body = calls[0]["json"]
    assert body["prompt"] == "Заплатил за обед 500 рублей"
    assert "food: Еда" in body["system"]
    assert "other: Другое" in body["system"]


def test_extract_expense_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, "конечно, вот расход:")

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_rejects_wrong_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid JSON of the wrong type — a list where an object is required.
    _patch_post(monkeypatch, '[{"title": "Обед"}]')

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_rejects_wrong_field_types(monkeypatch: pytest.MonkeyPatch) -> None:
    """``participants`` must stay a list of name/value objects — a bare list of
    strings is exactly the shape the resolution logic downstream cannot read."""
    _patch_post(monkeypatch, '{"title": "Обед", "participants": ["Максим", "я"]}')

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.extract_expense("Заплатил за обед", _CATEGORIES)


def test_extract_expense_accepts_an_all_null_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """"Nothing recognisable was said" is a legitimate answer, not an error —
    every field is optional, and the draft is then filled in by the user."""
    _patch_post(monkeypatch, "{}")

    result = ollama_service.extract_expense("кхм", _CATEGORIES)

    assert result.title is None
    assert result.amount is None
    assert result.participants == []


# ------------------------------------------------------------------ saving tips


def _payload() -> SavingTipsInput:
    return SavingTipsInput(
        total_spending_display="500,00 ₽",
        expense_count=5,
        currency="RUB",
        categories=[],
        trend=None,
    )


class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


def _completion(content: str) -> dict[str, Any]:
    """The envelope Ollama's /api/generate actually returns."""
    return {"model": "qwen3.5:9b", "done": True, "response": content}


def _patch_post(monkeypatch: pytest.MonkeyPatch, response_text: str) -> list[dict[str, Any]]:
    """Patch the HTTP call and return the list that records what was sent."""
    calls: list[dict[str, Any]] = []

    def _post(url: str, **kwargs: Any) -> _FakeResponse:
        calls.append({"url": url, **kwargs})
        return _FakeResponse(_completion(response_text))

    monkeypatch.setattr(ollama_service.httpx, "post", _post)
    return calls


def _patch_body(monkeypatch: pytest.MonkeyPatch, body: Any) -> None:
    """Patch the HTTP call to return an arbitrary (possibly malformed) envelope."""
    monkeypatch.setattr(
        ollama_service.httpx, "post", lambda *args, **kwargs: _FakeResponse(body)
    )


def test_generate_saving_tips_returns_parsed_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(
        monkeypatch,
        '{"tips": ['
        '{"title": "Еда", "text": "Еда — 31% расходов.", "type": "data_driven"}, '
        '{"title": "Лимит", "text": "Установите недельный лимит.", "type": "generic"}'
        "]}",
    )

    result = ollama_service.generate_saving_tips(_payload())

    assert len(result.tips) == 2
    assert result.tips[0].type == "data_driven"
    assert result.tips[1].type == "generic"


def test_generate_saving_tips_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, "not json at all")

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_saving_tips(_payload())


def test_generate_saving_tips_rejects_wrong_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid JSON, but no "tips" key at all.
    _patch_post(monkeypatch, '{"advice": "sure"}')

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_saving_tips(_payload())


def test_generate_saving_tips_rejects_wrong_tip_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # Only one tip — the schema requires 2 or 3.
    _patch_post(
        monkeypatch,
        '{"tips": [{"title": "Еда", "text": "Еда — 31%.", "type": "data_driven"}]}',
    )

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_saving_tips(_payload())


def test_generate_saving_tips_wraps_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(ollama_service.httpx, "post", _raise)

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_saving_tips(_payload())


# --------------------------------------------------------------- debt reminders


def _reminder_input() -> DebtReminderInput:
    return DebtReminderInput(
        expense="Ужин",
        amount_due="1250.00",
        currency="RUB",
        payer="Алиса",
        group="Квартира",
    )


def test_generate_debt_reminder_returns_parsed_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(
        monkeypatch,
        '{"message": "Не забудьте вернуть Алисе 1250 ₽ за «Ужин»."}',
    )

    result = ollama_service.generate_debt_reminder(_reminder_input())

    assert result.message == "Не забудьте вернуть Алисе 1250 ₽ за «Ужин»."


def test_generate_debt_reminder_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, "not json at all")

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_wrong_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    # Valid JSON, but no "message" key at all.
    _patch_post(monkeypatch, '{"text": "sure"}')

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_post(monkeypatch, '{"message": ""}')

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_wraps_http_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*_args: Any, **_kwargs: Any) -> Any:
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(ollama_service.httpx, "post", _raise)

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())

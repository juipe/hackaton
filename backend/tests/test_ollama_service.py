"""Unit tests for the saving-tips half of ``ollama_service``.

Mirrors how the voice pipeline is tested elsewhere: no real Ollama server is
ever contacted — ``httpx.post`` is monkeypatched at the module level to
return canned responses. This file only exercises
``generate_saving_tips``; ``extract_expense`` is untouched and covered by
``test_voice_api.py``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.schemas.saving_tips import SavingTipsInput
from app.services import ollama_service


def _payload() -> SavingTipsInput:
    return SavingTipsInput(
        total_spending_cents=50000,
        expense_count=5,
        currency="RUB",
        categories=[],
        months=[],
    )


class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._body


def _patch_post(monkeypatch: pytest.MonkeyPatch, response_text: str) -> None:
    monkeypatch.setattr(
        ollama_service.httpx,
        "post",
        lambda *args, **kwargs: _FakeResponse({"response": response_text}),
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

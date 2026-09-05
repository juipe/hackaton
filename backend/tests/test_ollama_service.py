"""Unit tests for the saving-tips and debt-reminder halves of ``ollama_service``.

Mirrors how the voice pipeline is tested elsewhere: no real Ollama server is
ever contacted — ``httpx.post`` is monkeypatched at the module level to
return canned responses. This file exercises ``generate_saving_tips`` and
``generate_debt_reminder``; ``extract_expense`` is untouched and covered by
``test_voice_api.py``.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.schemas.notification import DebtReminderInput
from app.schemas.saving_tips import SavingTipsInput
from app.services import ollama_service
from app.utils.money import format_money


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
    amount = format_money(125000, "RUB")
    message = f"Не забудьте вернуть Алисе {amount} за «Ужин» в группе «Квартира»."
    _patch_post(monkeypatch, json.dumps({"message": message}))

    result = ollama_service.generate_debt_reminder(_reminder_input())

    assert result.message == message


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


def test_generate_debt_reminder_rejects_malformed_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    # A real observed failure mode: valid JSON envelope (Ollama's
    # ``format: "json"`` guarantees that much), but the "message" string
    # itself contains leftover markdown/JSON/meta-text.
    garbage_message = (
        'Напомнить Алисе вернуть 1250 ₽ за «Ужин» в группе «Квартира».}"}** '
        "❌ (Too long and contains errors) ->"
    )
    _patch_post(monkeypatch, json.dumps({"message": garbage_message}))

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_exact_reported_bug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The exact malformed notification reported in production, reproduced
    # with this file's own facts: valid JSON, but the message text itself is
    # "Напомнить Оле вернуть 5000 ₽ за «раоава» в группе «Хакатон
    # Сбер12».}"}** ❌ (Too long and contains errors) ->".
    reported_bug_data = DebtReminderInput(
        expense="раоава", amount_due="5000.00", currency="RUB", payer="Оля", group="Хакатон Сбер12"
    )
    garbage_message = (
        'Напомнить Оле вернуть 5000 ₽ за «раоава» в группе «Хакатон Сбер12».}"}** '
        "❌ (Too long and contains errors) ->"
    )
    _patch_post(monkeypatch, json.dumps({"message": garbage_message}))

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(reported_bug_data)


def test_generate_debt_reminder_accepts_desired_style_for_reported_bug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The clean equivalent of the message above must still be accepted,
    # correctly preserving debtor, amount, expense title and group.
    reported_bug_data = DebtReminderInput(
        expense="раоава", amount_due="5000.00", currency="RUB", payer="Оля", group="Хакатон Сбер12"
    )
    amount = format_money(500000, "RUB")
    clean_message = f"Напомнить Оле вернуть {amount} за «раоава» в группе «Хакатон Сбер12»."
    _patch_post(monkeypatch, json.dumps({"message": clean_message}))

    result = ollama_service.generate_debt_reminder(reported_bug_data)

    assert result.message == clean_message


def test_generate_debt_reminder_rejects_wrong_money_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Otherwise-clean sentence, but the amount isn't rendered the way the
    # rest of the app renders money ("1250 ₽" instead of "1 250,00 ₽").
    _patch_post(
        monkeypatch,
        '{"message": "Не забудьте вернуть Алисе 1250 ₽ за «Ужин» в группе «Квартира»."}',
    )

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_missing_fact(monkeypatch: pytest.MonkeyPatch) -> None:
    # Correct format, but drops the group entirely.
    _patch_post(
        monkeypatch,
        '{"message": "Не забудьте вернуть Алисе 1 250,00 ₽ за «Ужин»."}',
    )

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())


def test_generate_debt_reminder_rejects_overly_long_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    padding = " ".join(["слово"] * 40)
    long_message = f"Не забудьте вернуть Алисе 1 250,00 ₽ за «Ужин» в группе «Квартира». {padding}"
    _patch_post(monkeypatch, json.dumps({"message": long_message}))

    with pytest.raises(ollama_service.OllamaError):
        ollama_service.generate_debt_reminder(_reminder_input())

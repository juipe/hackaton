"""Local structured extraction via Ollama, running Qwen entirely on-machine.

No external LLM API and no API key — this only ever talks to
``settings.ollama_base_url``, which defaults to a local Ollama instance.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from app.core.config import settings
from app.models.category import Category
from app.schemas.voice import LLMExpenseExtraction

_SYSTEM_PROMPT_TEMPLATE = """\
Ты извлекаешь структурированные данные о расходе из русской речи.
Верни ТОЛЬКО JSON-объект без пояснений и без markdown, со следующими полями:

{{
  "title": короткое название расхода строкой или null,
  "amount": сумма в рублях строкой, например "1200" или "1200.50", или null,
  "occurred_at": дата расхода в формате YYYY-MM-DD, если названа явно, иначе null,
  "category_slug": slug категории расхода — см. правила ниже,
  "payer_name": имя того, кто заплатил, или "я", если платил сам говорящий, или null,
  "participant_names": список имён участников, между которыми делится расход
}}

Имена в "payer_name" и "participant_names" всегда приводи к именительному
падежу («кто?» — Саша, Костя), даже если в речи они звучат в другом падеже
(«с Сашей» -> "Саша", «Косте» -> "Костя") — они сверяются со списком участников
группы по словарной форме.

Доступные категории расхода (используй ТОЛЬКО "slug" из этого списка для поля
"category_slug"):
{categories}

Правила выбора категории:
- Выбирай категорию по смыслу трат, а не по точному совпадению слов в речи —
  например, «такси» относится к категории с slug "transport", хотя слово
  «такси» нигде в списке категорий не встречается.
- Если ни одна категория явно не подходит по смыслу, выбери "other".
- "category_slug" всегда должен быть одним из slug из списка выше — никогда не
  придумывай свой slug и никогда не оставляй это поле пустым.

Никогда не придумывай идентификаторы (UUID, числа-id) — только имена, текст и
slug категории ровно в том виде, в каком они даны выше. Если что-то не
упомянуто в речи, верни null или пустой список для этого поля (кроме
"category_slug", который заполняется всегда по правилам выше).
"""


class OllamaError(Exception):
    """Ollama was unreachable, or returned something that doesn't parse."""


def _format_categories(categories: Sequence[Category]) -> str:
    return "\n".join(f"- {category.slug}: {category.name}" for category in categories)


def extract_expense(transcript: str, categories: Sequence[Category]) -> LLMExpenseExtraction:
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(categories=_format_categories(categories))
    base_url = settings.ollama_base_url.rstrip("/")
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": system_prompt,
                "prompt": transcript,
                "format": "json",
                "stream": False,
                # Hybrid-reasoning models (Qwen3 and later) otherwise dump the
                # whole answer into a separate "thinking" field and leave
                # "response" empty.
                "think": False,
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        raw = response.json().get("response", "")
        parsed = json.loads(raw)
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise OllamaError(f"Ollama недоступна или вернула некорректный ответ: {exc}") from exc

    try:
        return LLMExpenseExtraction.model_validate(parsed)
    except ValidationError as exc:
        raise OllamaError(f"Модель вернула данные неожиданной формы: {exc}") from exc


__all__ = ["OllamaError", "extract_expense"]

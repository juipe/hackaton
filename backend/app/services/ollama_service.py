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
from app.schemas.notification import DebtReminderInput, DebtReminderOut
from app.schemas.saving_tips import SavingTipsInput, SavingTipsOut
from app.schemas.voice import LLMExpenseExtraction

_SYSTEM_PROMPT_TEMPLATE = """\
Ты извлекаешь структурированные данные о расходе из русской речи для
приложения совместных расходов. Верни ТОЛЬКО JSON-объект без пояснений и без
markdown, со следующими полями:

{{
  "title": короткое название расхода строкой или null,
  "description": короткая заметка к расходу, если явно упомянута, иначе null,
  "amount": общая сумма расхода в рублях строкой, например "1200" или "1200.50", или null,
  "occurred_at": дата расхода в формате YYYY-MM-DD, если названа явно, иначе null,
  "category_slug": slug категории расхода — см. правила ниже,
  "payer_name": имя того, кто заплатил, или "я", если платил сам говорящий, или null,
  "split_mode": один из "equal", "exact", "percentage", "shares" — см. правила ниже,
  "participants": список долей участников — массив объектов вида
    {{"name": ..., "value": ...}}, см. правила ниже
}}

## Имена

Имена в "payer_name" и в "participants[].name" всегда приводи к именительному
падежу («кто?» — Саша, Максим), даже если в речи они звучат в другом падеже:
«с Сашей» -> "Саша", «Максиму» -> "Максим", «у Пети» -> "Петя", «должен
Максим» -> "Максим" — они сверяются со списком участников группы по словарной
форме. Себя говорящий называет по-разному — «я», «мне», «меня», «на меня»,
«с меня» — во всех случаях подставляй имя "я".

## split_mode и participants

Определи ОДИН из четырёх режимов деления по смыслу речи:

- "equal" — расход делится поровну. Используй, если способ деления явно не
  назван и по каждому участнику не названо число. participants — список
  имён с value: null у каждого.

- "exact" — каждому участнику названа ЕГО СОБСТВЕННАЯ СУММА В РУБЛЯХ. Признаки
  такой фразы: «должен 500», «мне 500», «с меня 500», «я 1000», «на меня
  1000», «Максим платит 500», «Максим должен 500» — то есть у каждого
  человека своя сумма в рублях, а не процент и не доля. value каждого
  участника — его сумма в рублях строкой ("500"). Если общая сумма явно не
  названа, но названы суммы всех участников — сложи их и подставь как
  "amount".

- "percentage" — участникам названы ПРОЦЕНТЫ («60 процентов», «60%», а также
  просто «60», если по контексту это доля вслед за процентом другого
  участника — слово «процентов»/«%» у второго и следующих участников часто
  пропускают). Фраза «Х процентов, остальные — Y» означает, что Y получает
  100 минус X процентов. Фраза «делим A на B между Х и Y» означает Х = A
  процентов, Y = B процентов, в том же порядке, в каком названы имена. value
  каждого участника — его процент числом строкой ("60").

- "shares" — участникам названы доли/паи («2 доли», «в два раза больше»).
  value — число долей строкой ("2").

## Категория

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

## Общие правила

Никогда не придумывай идентификаторы (UUID, числа-id) — только имена, текст,
числа и slug категории ровно в том виде, в каком они даны выше или прозвучали
в речи. Никогда не выдумывай суммы, проценты или доли, которых нет в речи, и
никогда не подгоняй числа так, чтобы они сходились, даже если названные суммы
или проценты не сходятся с общей суммой или со 100% — верни то, что реально
сказано; это отдельно проверит и покажет пользователю приложение. Если
что-то не упомянуто в речи, верни null или пустой список для этого поля
(кроме "category_slug", который заполняется всегда по правилам выше).

## Примеры

Речь: «Я заплатил за пиццу 1500, Максим должен 500, я 1000.»
{{"title": "Пицца", "description": null, "amount": "1500", "occurred_at": null,
"category_slug": "food", "payer_name": "я", "split_mode": "exact",
"participants": [{{"name": "Максим", "value": "500"}}, {{"name": "я", "value": "1000"}}]}}

Речь: «Я заплатил 3000, я 60 процентов, Максим 40 процентов.»
{{"title": null, "description": null, "amount": "3000", "occurred_at": null,
"category_slug": "other", "payer_name": "я", "split_mode": "percentage",
"participants": [{{"name": "я", "value": "60"}}, {{"name": "Максим", "value": "40"}}]}}

Речь: «Максим 40 процентов, остальные я.»
{{"title": null, "description": null, "amount": null, "occurred_at": null,
"category_slug": "other", "payer_name": null, "split_mode": "percentage",
"participants": [{{"name": "Максим", "value": "40"}}, {{"name": "я", "value": "60"}}]}}

Речь: «Делим 70 на 30 между мной и Максимом.»
{{"title": null, "description": null, "amount": null, "occurred_at": null,
"category_slug": "other", "payer_name": null, "split_mode": "percentage",
"participants": [{{"name": "я", "value": "70"}}, {{"name": "Максим", "value": "30"}}]}}
"""


_SAVING_TIPS_SYSTEM_PROMPT = """\
Ты финансовый ассистент приложения совместных расходов. Тебе дан JSON с
расходами пользователя за выбранный период: общая сумма, число трат, валюта,
разбивка по категориям (название, сумма, доля от общей суммы, число трат) и
расходы по месяцам (месяц, сумма за месяц, доля пользователя за месяц).
Никаких других данных о пользователе у тебя нет — это НЕ данные о долгах
между участниками, а только сумма их собственных трат.

Верни ТОЛЬКО JSON-объект без пояснений и без markdown, ровно такой формы:

{"tips": [{"title": "...", "text": "...", "type": "data_driven"}, ...]}

Правила:

- Верни РОВНО 2 или РОВНО 3 совета — не больше и не меньше.
- "type" — "data_driven", если совет опирается на конкретные цифры из
  переданных данных, иначе "generic".
- Никогда не выдумывай суммы, категории, проценты или тренды, которых нет в
  данных. Каждое число в "text" должно быть взято из данных или быть их
  прямым пересчётом (например, округлением процента).
- Сравнение или тренд («выросли», «стало больше, чем в прошлом месяце»)
  допустимы, только если в "months" есть хотя бы два месяца, позволяющих его
  посчитать. Если месяц один или данных о месяцах нет — не говори об
  изменении, росте или тренде.
- Если категорий или месяцев мало для персональных выводов, часть советов
  может быть общими рекомендациями по экономии (type "generic") — они не
  должны звучать так, будто основаны на данных пользователя.
- Каждый совет — короткий title (2-6 слов) и text (1-2 предложения) на
  русском языке.

## Примеры

Данные: {"total_spending_cents": 500000, "expense_count": 12, "currency": "RUB",
"categories": [{"name": "Еда", "amount_cents": 155000, "percentage": 31.0,
"expense_count": 8}, {"name": "Аренда", "amount_cents": 250000,
"percentage": 50.0, "expense_count": 1}], "months": [{"month": "2026-07",
"amount_cents": 500000, "your_share_cents": 250000}]}
{"tips": [{"title": "Аренда — крупнейшая категория", "text": "Аренда
составляет 50% всех расходов за период.", "type": "data_driven"},
{"title": "Еда — треть расходов", "text": "На еду уходит 31% всех трат —
8 покупок за период.", "type": "data_driven"}, {"title": "Планируйте
покупки заранее", "text": "Список покупок перед походом в магазин помогает
избежать незапланированных трат.", "type": "generic"}]}
"""


_DEBT_REMINDER_SYSTEM_PROMPT = """\
Ты формулируешь короткое вежливое напоминание о долге для приложения
совместных расходов. Тебе дан JSON с фактами о долге:

{
  "expense": название расхода,
  "amount_due": сумма долга в рублях строкой,
  "currency": код валюты (всегда "RUB"),
  "payer": имя того, кому нужно вернуть долг,
  "group": название группы, в которой возник расход
}

Верни ТОЛЬКО JSON-объект без пояснений и без markdown, ровно такой формы:

{"message": "..."}

Правила:

- "message" — одно короткое вежливое предложение на русском языке (не длиннее
  20 слов), которое напоминает о долге.
- Обязательно упомяни сумму, кому нужно вернуть долг ("payer") и название
  расхода или группы.
- Никогда не меняй, не округляй и не выдумывай сумму, имя или название —
  используй только то, что дано в JSON, дословно.
- Не добавляй извинений, эмодзи, приветствий и других лишних фраз — только
  напоминание по делу.

## Пример

Данные: {"expense": "Ужин", "amount_due": "1250.00", "currency": "RUB",
"payer": "Алиса", "group": "Квартира"}
{"message": "Не забудьте вернуть Алисе 1250 ₽ за «Ужин» в группе «Квартира»."}
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


def generate_saving_tips(data: SavingTipsInput) -> SavingTipsOut:
    """2-3 saving tips from the trimmed spending data in ``data``.

    Independent of :func:`extract_expense` — separate prompt, separate schema,
    same Ollama call shape. Raises :class:`OllamaError` on any failure
    (unreachable, bad JSON, wrong shape, wrong tip count) so the caller can
    fall back to generic tips instead of breaking the dashboard.
    """
    base_url = settings.ollama_base_url.rstrip("/")
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": _SAVING_TIPS_SYSTEM_PROMPT,
                "prompt": data.model_dump_json(),
                "format": "json",
                "stream": False,
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
        return SavingTipsOut.model_validate(parsed)
    except ValidationError as exc:
        raise OllamaError(f"Модель вернула данные неожиданной формы: {exc}") from exc


def generate_debt_reminder(data: DebtReminderInput) -> DebtReminderOut:
    """One short, polite Russian sentence reminding a debtor of a debt.

    Independent of :func:`extract_expense` and :func:`generate_saving_tips` —
    separate prompt, separate schema, same Ollama call shape. Only the facts in
    ``data`` (already resolved by the caller) go into the prompt, and Qwen is
    asked for wording only — the caller never reads a number back out of the
    response. Raises :class:`OllamaError` on any failure (unreachable, bad
    JSON, wrong shape, empty message) so the caller can fall back to a
    deterministic message instead of losing the reminder.
    """
    base_url = settings.ollama_base_url.rstrip("/")
    try:
        response = httpx.post(
            f"{base_url}/api/generate",
            json={
                "model": settings.ollama_model,
                "system": _DEBT_REMINDER_SYSTEM_PROMPT,
                "prompt": data.model_dump_json(),
                "format": "json",
                "stream": False,
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
        return DebtReminderOut.model_validate(parsed)
    except ValidationError as exc:
        raise OllamaError(f"Модель вернула данные неожиданной формы: {exc}") from exc


__all__ = [
    "OllamaError",
    "extract_expense",
    "generate_debt_reminder",
    "generate_saving_tips",
]

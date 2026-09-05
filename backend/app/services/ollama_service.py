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
from app.utils.money import format_money, str_to_cents

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

## Название (title)

Так же, как категория выше, определяй "title" по смыслу расхода, а не только
по отдельно названному имени. Если из речи понятно, на что потрачены деньги
(«такси», «обед», «продукты», «кино»), сформулируй короткое естественное
название (1-3 слова) по этому смыслу, даже если говорящий не произносил его
как отдельное название расхода. Не возвращай null только из-за того, что
название не было названо явной отдельной фразой. Возвращай null только тогда,
когда из речи нельзя надёжно понять, на что был расход — например, названы
только суммы или доли участников без единого слова о предмете траты.

## Общие правила

Никогда не придумывай идентификаторы (UUID, числа-id) — только имена, текст,
числа и slug категории ровно в том виде, в каком они даны выше или прозвучали
в речи. Никогда не выдумывай суммы, проценты или доли, которых нет в речи, и
никогда не подгоняй числа так, чтобы они сходились, даже если названные суммы
или проценты не сходятся с общей суммой или со 100% — верни то, что реально
сказано; это отдельно проверит и покажет пользователю приложение. Если
что-то не упомянуто в речи, верни null или пустой список для этого поля
(кроме "category_slug" и "title", которые заполняются по смыслу расхода по
правилам выше).

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

Речь: «Заплатил 1200 рублей за такси.»
{{"title": "Такси", "description": null, "amount": "1200", "occurred_at": null,
"category_slug": "transport", "payer_name": "я", "split_mode": "equal",
"participants": []}}

Речь: «Заплатил за обед 500 рублей.»
{{"title": "Обед", "description": null, "amount": "500", "occurred_at": null,
"category_slug": "food", "payer_name": "я", "split_mode": "equal",
"participants": []}}

Речь: «Купил продукты в магазине на 2000 рублей.»
{{"title": "Продукты", "description": null, "amount": "2000", "occurred_at": null,
"category_slug": "groceries", "payer_name": "я", "split_mode": "equal",
"participants": []}}
"""


_SAVING_TIPS_SYSTEM_PROMPT = """\
Ты финансовый ассистент приложения совместных расходов. Тебе дан JSON с
расходами пользователя за выбранный период: общая сумма (уже отформатирована
строкой, например "1 234,56 ₽"), число трат, валюта, разбивка по категориям
(название, уже отформатированная сумма, уже отформатированная доля в
процентах, число трат) и, если есть данные минимум за два месяца, "trend" —
сравнение общей суммы расходов за предыдущий и последний месяц (названия
месяцев, уже отформатированные суммы обоих месяцев и уже отформатированное
изменение в процентах со знаком). Если сравнить два месяца нельзя, поле
"trend" отсутствует (null). Никаких других данных о пользователе у тебя нет
— это НЕ данные о долгах между участниками, а только сумма их собственных
трат.

ВСЕ числа в этом JSON уже посчитаны и отформатированы бэкендом — рубли уже
переведены из копеек, проценты уже вычислены и округлены, изменение между
месяцами уже посчитано. Твоя единственная задача — красиво и по-русски
пересказать эти готовые числа. Тебе НИКОГДА не нужно самому:
- переводить копейки в рубли;
- считать или округлять проценты;
- считать разницу между месяцами;
- складывать или пересчитывать суммы.

Верни ТОЛЬКО JSON-объект без пояснений и без markdown, ровно такой формы:

{"tips": [{"title": "...", "text": "...", "type": "data_driven"}, ...]}

Правила:

- Верни РОВНО 2 или РОВНО 3 совета — не больше и не меньше.
- "type" — "data_driven", если совет опирается на конкретные цифры из
  переданных данных, иначе "generic".
- Каждое число, которое ты пишешь в "text" (сумма, процент, дата/месяц),
  должно быть СКОПИРОВАНО ДОСЛОВНО из готовых строк во входных данных —
  символ в символ, включая единицы измерения (₽, %). Никогда не меняй,
  не округляй, не пересчитывай и не выдумывай число самостоятельно — если
  нужного тебе числа нет готовым во входных данных, не пиши это число
  вообще, сформулируй совет без него.
- Никогда не выдумывай категории, суммы, проценты или тренды, которых нет в
  данных.
- Говорить о росте, падении или сравнении с предыдущим месяцем можно ТОЛЬКО
  если во входных данных присутствует поле "trend" — и только используя его
  готовые "from_label"/"to_label"/"from_display"/"to_display"/
  "change_display" как есть. Если поля "trend" нет — не говори об
  изменении, росте, падении или тренде вообще, ни с какими числами.
- Если категорий мало или нет "trend" для персональных выводов, часть
  советов может быть общими рекомендациями по экономии (type "generic") —
  они не должны содержать чисел и не должны звучать так, будто основаны на
  данных пользователя.
- Каждый совет — короткий title (2-6 слов) и text (1-2 предложения) на
  русском языке.

## Примеры

Данные: {"total_spending_display": "5 000,00 ₽", "expense_count": 12,
"currency": "RUB", "categories": [{"name": "Еда", "amount_display":
"1 550,00 ₽", "percentage_display": "31%", "expense_count": 8}, {"name":
"Аренда", "amount_display": "2 500,00 ₽", "percentage_display": "50%",
"expense_count": 1}], "trend": {"from_label": "июн 2026", "to_label":
"июл 2026", "from_display": "4 200,00 ₽", "to_display": "5 000,00 ₽",
"change_display": "+19%"}}
{"tips": [{"title": "Аренда — крупнейшая категория", "text": "Аренда
составляет 50% всех расходов за период — это 2 500,00 ₽.", "type":
"data_driven"}, {"title": "Расходы выросли за месяц", "text": "С июн 2026
по июл 2026 общие траты увеличились с 4 200,00 ₽ до 5 000,00 ₽ (+19%).",
"type": "data_driven"}, {"title": "Планируйте покупки заранее", "text":
"Список покупок перед походом в магазин помогает избежать незапланированных
трат.", "type": "generic"}]}

Данные без "trend" (сравнение за месяц невозможно — нельзя говорить о росте
или падении, только о текущей картине):
{"total_spending_display": "5,00 ₽", "expense_count": 1, "currency": "RUB",
"categories": [{"name": "Кафе и рестораны", "amount_display": "5,00 ₽",
"percentage_display": "100%", "expense_count": 1}], "trend": null}
{"tips": [{"title": "Все траты — в одной категории", "text": "Все 5,00 ₽ за
период ушли на категорию «Кафе и рестораны».", "type": "data_driven"},
{"title": "Пока рано делать выводы", "text": "Данных за один период мало,
чтобы сравнивать динамику — добавьте больше расходов для персональных
рекомендаций.", "type": "generic"}]}
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


#: The prompt asks for "не длиннее 20 слов"; this leaves some slack before
#: rejecting rather than enforcing that exact number.
_DEBT_REMINDER_MAX_WORDS = 30
_DEBT_REMINDER_MAX_LENGTH = 320
#: Markdown/JSON/meta-text fragments that have leaked into a raw model answer
#: in practice (e.g. a trailing "}"}** ❌ (Too long and contains errors) ->"
#: after the actual sentence) — a clean one-sentence reminder never needs any
#: of these.
_DEBT_REMINDER_FORBIDDEN_SUBSTRINGS = ("**", "```", "->", "❌", "{", "}")


def _name_stem(name: str) -> str:
    """Drop the last letter of a Russian name, e.g. "Алиса" -> "Алис".

    The debt-reminder prompt's own example inflects the payer's name for
    grammar ("Алиса" -> "верните Алисе ...", dative case), so checking for the
    name verbatim would reject perfectly good Qwen output. Comparing stems
    instead still catches a message that dropped or swapped the person
    entirely, without rejecting ordinary Russian case endings.
    """
    return name[:-1] if len(name) > 2 else name


def _is_clean_debt_reminder_message(message: str, *, data: DebtReminderInput) -> bool:
    """Whether ``message`` is safe to show a user as-is.

    Ollama's ``format: "json"`` only guarantees the *response* parses as JSON
    matching :class:`DebtReminderOut` — it says nothing about the *content* of
    the "message" string, which is where garbage like leftover markdown, stray
    JSON punctuation, or the model's own commentary about its answer ends up.
    Qwen is asked for wording only (see the prompt above), so a trustworthy
    message must still be a short, clean sentence that actually contains the
    facts it was given — the money amount rendered exactly as the app renders
    it everywhere else, not however Qwen chose to write the number, and the
    same debtor, expense and group it was asked to word a reminder for.
    """
    text = message.strip()
    if not text or len(text) > _DEBT_REMINDER_MAX_LENGTH:
        return False
    if len(text.split()) > _DEBT_REMINDER_MAX_WORDS:
        return False
    if any(marker in text for marker in _DEBT_REMINDER_FORBIDDEN_SUBSTRINGS):
        return False
    try:
        amount_display = format_money(str_to_cents(data.amount_due), data.currency)
    except ValueError:
        return False
    if amount_display not in text or data.expense not in text or data.group not in text:
        return False
    return _name_stem(data.payer) in text


def generate_debt_reminder(data: DebtReminderInput) -> DebtReminderOut:
    """One short, polite Russian sentence reminding a debtor of a debt.

    Independent of :func:`extract_expense` and :func:`generate_saving_tips` —
    separate prompt, separate schema, same Ollama call shape. Only the facts in
    ``data`` (already resolved by the caller) go into the prompt, and Qwen is
    asked for wording only — the caller never reads a number back out of the
    response. Raises :class:`OllamaError` on any failure (unreachable, bad
    JSON, wrong shape, empty message, or a message that fails
    :func:`_is_clean_debt_reminder_message`) so the caller can fall back to a
    deterministic message instead of losing the reminder or showing garbage.
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
        result = DebtReminderOut.model_validate(parsed)
    except ValidationError as exc:
        raise OllamaError(f"Модель вернула данные неожиданной формы: {exc}") from exc

    if not _is_clean_debt_reminder_message(result.message, data=data):
        raise OllamaError("Модель вернула повреждённый или неподходящий текст напоминания")
    return result


__all__ = [
    "OllamaError",
    "extract_expense",
    "generate_debt_reminder",
    "generate_saving_tips",
]

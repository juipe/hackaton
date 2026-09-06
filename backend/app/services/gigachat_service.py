"""Structured extraction and text generation via the GigaChat API.

The only module in the app that talks to an LLM provider. It exposes exactly
three operations — :func:`extract_expense`, :func:`generate_saving_tips` and
:func:`generate_debt_reminder` — and one error type, :class:`GigaChatError`.
Everything above this layer (``voice_service``, ``saving_tips_service``,
``debt_reminder_service``) only knows those four names, so swapping the
provider again never reaches business logic.

Wire protocol
-------------

Two hosts are involved, because GigaChat splits auth from inference:

- **auth** — ``POST {gigachat_auth_url}`` (``ngw.devices.sberbank.ru:9443``)
  exchanges the base64 Authorization Key for a 30-minute access token. This
  is still the only documented token endpoint; ``api.giga.chat`` does not
  serve one.
- **inference** — ``POST {gigachat_base_url}/v1/chat/completions``, the
  OpenAI-compatible surface, with ``Authorization: Bearer <access token>``.

Tokens are cached process-wide until shortly before ``expires_at`` (see
:class:`_TokenCache`), so a completion normally costs one HTTP round trip, not
two. A 401 from the completions endpoint invalidates the cache and is retried
exactly once — that is the only retry here.

TLS
---

Both hosts present a chain issued by the "Russian Trusted Root CA", which no
mainstream trust store carries. Verification is therefore done against
certifi **plus** the bundled copy of that CA (``app/certs``) — enabled, never
skipped. ``gigachat_verify_ssl=false`` exists as a deliberate, documented
escape hatch and is off by default.

Secrets
-------

The Authorization Key lives only in ``settings.gigachat_credentials`` and only
ever leaves this module inside an ``Authorization`` header. No error message,
log line or exception raised here contains the key, the access token, or any
header — see :func:`_safe_http_message`.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import certifi
import httpx
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.models.category import Category
from app.schemas.notification import DebtReminderInput, DebtReminderOut
from app.schemas.saving_tips import SavingTipsInput, SavingTipsOut
from app.schemas.voice import LLMExpenseExtraction

#: Public CA bundle shipped with the app — see the module docstring.
_CA_BUNDLE = Path(__file__).resolve().parent.parent / "certs" / "russian_trusted_ca.pem"

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


class GigaChatError(Exception):
    """GigaChat was unreachable, refused the request, or answered unusably.

    The single error type this module raises, for every failure mode: missing
    credentials, token acquisition failure, 401/403/429, any other 4xx/5xx,
    timeout, connection error, malformed JSON, and structured output that
    doesn't match the expected schema. Callers (``voice_service``,
    ``saving_tips_service``, ``debt_reminder_service``) each degrade on it in
    their own already-tested way, so no endpoint fails because of the LLM.

    Never carries credentials, tokens or request headers — see
    :func:`_safe_http_message`.
    """


# --------------------------------------------------------------------- TLS


_ssl_lock = threading.Lock()
_ssl_context: Any | None = None


def _verify() -> Any:
    """certifi's roots plus the Russian Trusted CA — verification stays on.

    ``gigachat_verify_ssl=false`` returns ``False`` instead, which disables
    certificate checks entirely. That is an explicit, documented escape hatch
    for a broken corporate proxy; it is off by default and should stay off.
    """
    global _ssl_context
    if not settings.gigachat_verify_ssl:
        return False
    with _ssl_lock:
        if _ssl_context is None:
            import ssl

            context = ssl.create_default_context(cafile=certifi.where())
            configured = settings.gigachat_ca_bundle
            bundle = Path(configured) if configured else _CA_BUNDLE
            if bundle.is_file():
                context.load_verify_locations(cafile=str(bundle))
            _ssl_context = context
        return _ssl_context


# ------------------------------------------------------------------- tokens


class _TokenCache:
    """The 30-minute access token, shared by every caller in the process.

    Both the voice route (a sync ``def``, so FastAPI runs it in a threadpool)
    and the debt-reminder background task can ask for a token at the same
    time, hence the lock: without it a burst of expenses would fire a burst of
    token requests. ``expires_at`` comes from the auth response in epoch
    milliseconds; a token is treated as expired ``_SKEW_SECONDS`` early so it
    cannot lapse mid-flight.
    """

    _SKEW_SECONDS = 60

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get(self, *, force_refresh: bool = False) -> str:
        with self._lock:
            if force_refresh:
                self._token = None
            if self._token is not None and time.time() < self._expires_at - self._SKEW_SECONDS:
                return self._token
            token, expires_at = _request_access_token()
            self._token = token
            self._expires_at = expires_at
            return token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0


_token_cache = _TokenCache()


def _request_access_token() -> tuple[str, float]:
    """Exchange the Authorization Key for an access token and its expiry.

    Returns the token and its absolute expiry as a UNIX timestamp in seconds.
    """
    credentials = settings.gigachat_credentials.strip()
    if not credentials:
        raise GigaChatError(
            "GIGACHAT_CREDENTIALS не задан — AI функции недоступны без ключа авторизации"
        )

    try:
        response = httpx.post(
            settings.gigachat_auth_url,
            data={"scope": settings.gigachat_scope},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                # Required by the OAuth endpoint: a fresh uuid4 per request.
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {credentials}",
            },
            verify=_verify(),
            timeout=settings.gigachat_auth_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise GigaChatError(
            f"GigaChat отклонил ключ авторизации: {_safe_http_message(exc)}"
        ) from exc
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
        raise GigaChatError(
            f"Не удалось получить токен GigaChat: {_safe_http_message(exc)}"
        ) from exc

    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise GigaChatError("Ответ GigaChat не содержит access_token")

    # Documented as epoch milliseconds. Anything unusable falls back to the
    # documented 30-minute lifetime rather than to "never expires".
    raw_expiry = payload.get("expires_at")
    if isinstance(raw_expiry, (int, float)) and raw_expiry > 0:
        expires_at = float(raw_expiry) / 1000.0
    else:
        expires_at = time.time() + 30 * 60
    return token, expires_at


# ---------------------------------------------------------------- transport


def _safe_http_message(exc: Exception) -> str:
    """A short description of ``exc`` that can never contain a secret.

    httpx puts the full request URL in its exception strings, and an
    ``HTTPStatusError`` can be asked for the response body — neither is
    allowed anywhere near a log line here, because the request carries the
    Authorization Key (auth) or the bearer token (completions). Only the
    exception's class name and, for an HTTP error, the status code are used.
    """
    if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


def _post_completion(
    *,
    system_prompt: str,
    user_content: str,
    schema: dict[str, Any] | None,
    token: str,
) -> str:
    """One ``/v1/chat/completions`` call; returns the assistant's raw content."""
    body: dict[str, Any] = {
        "model": settings.gigachat_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        # The task is extraction and re-phrasing of given facts, never
        # invention, so decoding stays near-deterministic.
        "temperature": settings.gigachat_temperature,
    }
    if schema is not None and settings.gigachat_structured_output:
        body["response_format"] = {
            "type": "json_schema",
            "schema": schema,
            "strict": True,
        }

    url = f"{settings.gigachat_base_url.rstrip('/')}/v1/chat/completions"
    response = httpx.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        verify=_verify(),
        timeout=settings.gigachat_timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GigaChatError("Ответ GigaChat не содержит текста завершения") from exc
    if not isinstance(content, str) or not content.strip():
        raise GigaChatError("GigaChat вернул пустой ответ")
    return content


def _complete_json(
    *, system_prompt: str, user_content: str, schema: dict[str, Any] | None
) -> Any:
    """Call the model and parse its answer as JSON.

    Retries exactly once on a 401 — the token can expire between the cache
    check and the request reaching the server, and a stale token must not
    surface as a user-visible failure. Every other error is final.
    """
    token = _token_cache.get()
    try:
        try:
            raw = _post_completion(
                system_prompt=system_prompt,
                user_content=user_content,
                schema=schema,
                token=token,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                _token_cache.invalidate()
                raw = _post_completion(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    schema=schema,
                    token=_token_cache.get(force_refresh=True),
                )
            else:
                raise
    except httpx.HTTPStatusError as exc:
        raise GigaChatError(f"GigaChat вернул ошибку: {_safe_http_message(exc)}") from exc
    except httpx.HTTPError as exc:
        raise GigaChatError(f"GigaChat недоступен: {_safe_http_message(exc)}") from exc

    try:
        return json.loads(_strip_code_fence(raw))
    except json.JSONDecodeError as exc:
        raise GigaChatError("GigaChat вернул не-JSON ответ") from exc


def _strip_code_fence(raw: str) -> str:
    """Unwrap a ```json fenced block if the model added one anyway.

    The prompts all forbid markdown and structured output makes it unlikely,
    but a fence is a formatting artefact, not a different answer — unwrapping
    it costs nothing and avoids discarding an otherwise perfect extraction.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return text
    without_open = text[3:]
    if without_open[:4].lower().startswith("json"):
        without_open = without_open[4:]
    return without_open.rsplit("```", 1)[0].strip()


def _validate[T: BaseModel](model: type[T], payload: Any) -> T:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise GigaChatError(f"Модель вернула данные неожиданной формы: {exc}") from exc


# ------------------------------------------------------------------ schemas


def _nullable_string(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


#: JSON Schema for ``LLMExpenseExtraction`` — the same fields, same units and
#: the same "a string or null" typing the Pydantic model already declares. It
#: is written out here rather than generated from the model because the
#: provider needs a flat, self-describing schema (no ``$defs``/``$ref``), and
#: because the descriptions are prompt text, tuned per field.
_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": _nullable_string("Короткое название расхода"),
        "description": _nullable_string("Короткая заметка к расходу"),
        "amount": _nullable_string("Общая сумма в рублях, например '1200' или '1200.50'"),
        "occurred_at": _nullable_string("Дата расхода в формате YYYY-MM-DD"),
        "category_slug": _nullable_string("Slug одной из переданных категорий"),
        "payer_name": _nullable_string("Кто заплатил — имя или 'я'"),
        "split_mode": {
            "type": ["string", "null"],
            "enum": ["equal", "exact", "percentage", "shares", None],
            "description": "Режим деления расхода",
        },
        "participants": {
            "type": "array",
            "description": "Доли участников; единицы value зависят от split_mode",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Имя участника или 'я'"},
                    "value": _nullable_string("Доля участника в единицах split_mode"),
                },
                "required": ["name", "value"],
            },
        },
    },
    "required": [
        "title",
        "description",
        "amount",
        "occurred_at",
        "category_slug",
        "payer_name",
        "split_mode",
        "participants",
    ],
}

_SAVING_TIPS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "tips": {
            "type": "array",
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Заголовок совета, 2-6 слов"},
                    "text": {"type": "string", "description": "Совет, 1-2 предложения"},
                    "type": {"type": "string", "enum": ["data_driven", "generic"]},
                },
                "required": ["title", "text", "type"],
            },
        }
    },
    "required": ["tips"],
}

_DEBT_REMINDER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "Одно короткое вежливое напоминание о долге на русском",
        }
    },
    "required": ["message"],
}

#: Fields of the extraction contract that are strings in ``LLMExpenseExtraction``.
#: GigaChat answers ``"amount": 1200`` for these often enough to matter even
#: with a schema that types them as strings — see :func:`_stringify_numbers`.
_EXTRACTION_STRING_FIELDS = frozenset(
    {"title", "description", "amount", "occurred_at", "category_slug", "payer_name", "split_mode"}
)


def _as_string(value: Any) -> Any:
    """``1200`` -> ``"1200"``, ``1200.5`` -> ``"1200.5"``; anything else as-is."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _stringify_numbers(payload: Any) -> Any:
    """Coerce the extraction's numeric answers to the strings the schema wants.

    Purely a provider adapter: ``LLMExpenseExtraction`` types every one of
    these fields as ``str | None`` and the split/money code downstream parses
    the string, so a JSON number is the same answer in the wrong wire type,
    not a different answer. Nothing is rounded, reformatted or recomputed
    here — ``str()`` of the number the model returned, and only for the fields
    the contract already declares as strings.
    """
    if not isinstance(payload, dict):
        return payload

    normalised = dict(payload)
    for field in _EXTRACTION_STRING_FIELDS:
        if field in normalised:
            normalised[field] = _as_string(normalised[field])

    participants = normalised.get("participants")
    if isinstance(participants, list):
        normalised["participants"] = [
            {**item, "value": _as_string(item.get("value"))} if isinstance(item, dict) else item
            for item in participants
        ]
    return normalised


# --------------------------------------------------------------- operations


def _format_categories(categories: Sequence[Category]) -> str:
    return "\n".join(f"- {category.slug}: {category.name}" for category in categories)


def extract_expense(transcript: str, categories: Sequence[Category]) -> LLMExpenseExtraction:
    """Structured expense fields heard in ``transcript``.

    The group's real categories go into the system prompt so the model can
    only ever pick a slug that exists; everything it returns is names, text
    and plain numbers, never ids — see ``app.services.voice_service`` for how
    each field is resolved against real members and categories afterwards.
    Raises :class:`GigaChatError` on any failure, which ``voice_service``
    turns into an empty draft plus a warning rather than a failed request.
    """
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(categories=_format_categories(categories))
    parsed = _complete_json(
        system_prompt=system_prompt,
        user_content=transcript,
        schema=_EXTRACTION_SCHEMA,
    )
    return _validate(LLMExpenseExtraction, _stringify_numbers(parsed))


def generate_saving_tips(data: SavingTipsInput) -> SavingTipsOut:
    """2-3 saving tips from the trimmed spending data in ``data``.

    Independent of :func:`extract_expense` — separate prompt, separate schema,
    same call shape. Every number in ``data`` is already computed and
    formatted by the caller; the model only copies those strings into prose.
    Raises :class:`GigaChatError` on any failure (unreachable, bad JSON, wrong
    shape, wrong tip count) so the caller can fall back to generic tips
    instead of breaking the dashboard.
    """
    parsed = _complete_json(
        system_prompt=_SAVING_TIPS_SYSTEM_PROMPT,
        user_content=data.model_dump_json(),
        schema=_SAVING_TIPS_SCHEMA,
    )
    return _validate(SavingTipsOut, parsed)


def generate_debt_reminder(data: DebtReminderInput) -> DebtReminderOut:
    """One short, polite Russian sentence reminding a debtor of a debt.

    Independent of :func:`extract_expense` and :func:`generate_saving_tips` —
    separate prompt, separate schema, same call shape. Only the facts in
    ``data`` (already resolved by the caller) go into the prompt, and the
    model is asked for wording only — the caller never reads a number back out
    of the response. Raises :class:`GigaChatError` on any failure
    (unreachable, bad JSON, wrong shape, empty message) so the caller can fall
    back to a deterministic message instead of losing the reminder.
    """
    parsed = _complete_json(
        system_prompt=_DEBT_REMINDER_SYSTEM_PROMPT,
        user_content=data.model_dump_json(),
        schema=_DEBT_REMINDER_SCHEMA,
    )
    return _validate(DebtReminderOut, parsed)


__all__ = [
    "GigaChatError",
    "extract_expense",
    "generate_debt_reminder",
    "generate_saving_tips",
]

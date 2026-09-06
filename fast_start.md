# Быстрый старт

## 1. Первоначальная настройка (один раз)

```bash
git clone <repo-url>
cd hackaton-main

cp .env.example .env

cd backend
# Python 3.12 — обязательно, не «желательно»: колёса torch 2.8 (нужен GigaAM)
# собраны для cp39-cp313, а образ и CI используют 3.12. На 3.13+/3.14
# `pip install` просто не найдёт torch. Версия зафиксирована в
# backend/.python-version и backend/pyproject.toml (requires-python).
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env   # или свой backend/.env с DATABASE_URL и SECRET_KEY
alembic upgrade head
python -m scripts.seed
cd ..

cd frontend
npm install
cd ..
```

Модели скачивать вручную не нужно:

- **GigaChat-3-Ultra** (LLM) — облачный API Сбера, ничего ставить и запускать
  не надо. Нужен только ключ: скопируйте «Ключ авторизации» из
  https://developers.sber.ru/studio и положите его в `.env` (файл в
  `.gitignore`, в репозиторий он не попадает):

  ```
  GIGACHAT_CREDENTIALS=<ключ авторизации>
  GIGACHAT_SCOPE=GIGACHAT_API_PERS
  ```

  Backend сам меняет ключ на access-токен (живёт 30 минут) и обновляет его.
- **GigaAM-v3** (распознавание речи) — ставится вместе с зависимостями
  backend'а (`requirements.txt`: torch, torchaudio, transformers, torchcodec),
  а веса (~2 ГБ) скачиваются автоматически при первом голосовом запросе и
  кешируются в `HF_HOME`.

Для работы с аудио нужен `ffmpeg` — в Docker он уже в образе backend'а; для
локального запуска без Docker поставьте его сам (`brew install ffmpeg`,
`apt install ffmpeg`).

Backend требует именно Python 3.12 (см. выше).

## 2. Ежедневный запуск

```bash
# Postgres + миграции + сид + API (:8000) + фронтенд (:3000)
docker compose up --build

# либо разработка с hot-reload поверх той же compose-инфраструктуры:
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

cd frontend && npm run dev
```

Отдельно запускать теперь нечего: LLM — это внешний API.
Первый голосовой запрос дольше обычного: скачиваются веса GigaAM.

## 3. Адреса

- Frontend (Docker): http://localhost:3000
- Frontend (Vite dev): http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/api/docs
- Postgres: localhost:5433
- GigaChat API: https://api.giga.chat (внешний, ключ в `.env`)

## 4. Проверка

```bash
curl http://localhost:8000/api/health

# Ключ рабочий и токен выдаётся (ключ не печатаем — он секрет):
cd backend && set -a && . ../.env && set +a && \
  SKLADCHINA_AI_SMOKE=1 python -m pytest tests/test_ai_smoke.py -v
```

Открыть в браузере http://localhost:3000 (или http://localhost:5173).

## 5. Если AI недоступен

Приложение не падает без AI и не ждёт его: голосовой черновик вернёт только
распознанный текст с предупреждением, советы по экономии покажут общий набор,
а напоминания о долге останутся с обычной формулировкой. Так же приложение
ведёт себя и без ключа вообще — пустой `GIGACHAT_CREDENTIALS` это рабочая
конфигурация, а не ошибка.

Голосовая заметка должна быть не длиннее 25 секунд — столько принимает GigaAM
за один проход; более длинную запись приложение отклонит с понятным
сообщением, а не молча.

Требования по памяти: ~2 ГБ под GigaAM. LLM памяти не занимает — он в облаке.

Оба хоста GigaChat отдают сертификат «Russian Trusted Root CA», которого нет в
системных хранилищах, поэтому backend проверяет TLS по certifi плюс копии
этого CA в `backend/app/certs` — отключать проверку не нужно.

---

## Quick Start

```bash
docker compose up --build
```

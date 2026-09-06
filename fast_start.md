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

- **Qwen** (LLM) — работает в локальной Ollama на хосте, а не в контейнере:
  поставьте Ollama и один раз скачайте модель `ollama pull qwen3.5:9b` (~6.6 ГБ).
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

ollama serve                    # если Ollama ещё не запущена как сервис

# либо разработка с hot-reload поверх той же compose-инфраструктуры:
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

cd frontend && npm run dev
```

Ollama нужно запускать отдельно — `docker compose up` её не поднимает.
Первый голосовой запрос дольше обычного: скачиваются веса GigaAM.

## 3. Адреса

- Frontend (Docker): http://localhost:3000
- Frontend (Vite dev): http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/api/docs
- Postgres: localhost:5433
- Ollama (Qwen): http://localhost:11434

## 4. Проверка

```bash
curl http://localhost:8000/api/health

# Ollama запущена и модель на месте:
curl http://localhost:11434/api/tags
```

Открыть в браузере http://localhost:3000 (или http://localhost:5173).

## 5. Если модель ещё не поднялась

Приложение не падает без AI и не ждёт его: голосовой черновик вернёт только
распознанный текст с предупреждением, советы по экономии покажут общий набор,
а напоминания о долге останутся с обычной формулировкой. Поэтому backend
стартует, не дожидаясь Ollama.

Голосовая заметка должна быть не длиннее 25 секунд — столько принимает GigaAM
за один проход; более длинную запись приложение отклонит с понятным
сообщением, а не молча.

Требования по памяти: ~7 ГБ RAM под Qwen в Ollama плюс ~2 ГБ под GigaAM.
Если памяти мало, возьмите модель поменьше (`OLLAMA_MODEL` в `.env`).

Ollama работает на хосте, а не в контейнере — backend внутри Docker обращается
к ней через `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

---

## Quick Start

```bash
docker compose up --build
ollama serve
```

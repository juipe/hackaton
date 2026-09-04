# Быстрый старт

## 1. Первоначальная настройка (один раз)

```bash
git clone <repo-url>
cd hackaton-main

cp .env.example .env

cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example .env   # или свой backend/.env с DATABASE_URL и SECRET_KEY
alembic upgrade head
python -m scripts.seed
cd ..

cd frontend
npm install
cd ..

ollama pull qwen3.5:9b
```

Whisper отдельной установки не требует — `faster-whisper` ставится вместе с
зависимостями backend'а (`requirements.txt`), а модель (`WHISPER_MODEL=small`
по умолчанию) скачивается автоматически при первом запросе.

## 2. Ежедневный запуск

```bash
docker compose up --build      # Postgres + миграции + сид + API (:8000) + фронтенд (:3000)

ollama serve                    # если Ollama ещё не запущена как сервис

cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

cd frontend && npm run dev
```

## 3. Адреса

- Frontend (Docker): http://localhost:3000
- Frontend (Vite dev): http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/api/docs
- Postgres: localhost:5433
- Ollama: http://localhost:11434

## 4. Проверка

```bash
curl http://localhost:8000/api/health
```

Открыть в браузере http://localhost:3000 (или http://localhost:5173).

## 5. Про Ollama и Docker

Ollama работает на хосте, а не в контейнере — backend внутри Docker обращается
к ней через `OLLAMA_BASE_URL=http://host.docker.internal:11434`.

---

## Quick Start

```bash
docker compose up --build
ollama serve
```

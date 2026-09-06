# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"СберВместе" (Skladchina) — a shared-expense tracker (Splitwise-style), built for a Sberbank
hackathon. FastAPI + PostgreSQL backend, React + TypeScript + Tailwind frontend. All UI text,
demo data, and commit messages are in Russian; the service handles a single currency (RUB).
It also has a voice-to-expense feature: record a note, get back a draft expense to confirm.

## Commands

### Run everything

```bash
docker compose up --build          # Postgres + migrations + seed + API (:8000) + frontend (:3000)
docker compose down -v             # stop and wipe the DB volume
```

The seed creates five demo users (`olya@`, `sasha@`, `kostya@`, `maksim@`, `zhora@`
`skladchina.ru`), all with password `Demo1234!` — `sasha@` is in all three demo groups and is
the account to log in as when checking a change by hand. `docs/` referenced in the README does
not exist in this repo; ignore those links.

### Backend (`backend/`)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

export DATABASE_URL="postgresql+psycopg://skladchina:skladchina@localhost:5433/skladchina"
export SECRET_KEY="any-string-at-least-32-chars"   # or put both in backend/.env

alembic upgrade head
python -m scripts.seed             # demo data; --reset to wipe and rebuild it
uvicorn app.main:app --reload --port 8000
```

Tests and linting:

```bash
python -m pytest                          # full suite — runs on in-memory SQLite, no DB needed
python -m pytest tests/test_split_engine.py -v
python -m pytest tests/test_split_engine.py::test_name -v   # single test
python -m pytest --cov=app
ruff check .
ruff check . --fix
```

Migrations:

```bash
alembic upgrade head
alembic downgrade base
alembic revision --autogenerate -m "what changed"
```

### Frontend (`frontend/`)

```bash
npm install
npm run dev             # Vite dev server on :5173, proxies /api -> :8000
npm run build            # tsc -b + production build
npm run typecheck
npm run test             # Vitest, run once
npm run test:watch
```

If the API isn't on 8000: `VITE_API_PROXY_TARGET=http://127.0.0.1:8010 npm run dev`.

### Before pushing

```bash
cd backend  && python -m pytest && ruff check .
cd frontend && npm run typecheck && npm run test && npm run build
```

## Architecture

### Backend layering (`backend/app/`)

Strict three-layer separation, enforced by convention — routes never contain business logic:

- **`api/routes/`** — parses the HTTP request, calls a service, shapes the response. No rules here.
- **`services/`** — all business logic. Pure enough to unit-test without HTTP (see
  `tests/test_split_engine.py`, `tests/test_balance_service.py`, `tests/test_invariants.py`).
- **`repositories/`** — the only layer that talks to the DB (SQLAlchemy queries).
- **`schemas/`** — Pydantic request/response models, one file per domain concept, mirroring `models/`.
- **`core/`** — config (`config.py`), auth dependencies (`deps.py`), cookie handling (`cookies.py`),
  password/JWT (`security.py`), typed HTTP errors (`errors.py`).

Key services worth knowing before touching money logic:

- **`services/split_engine.py`** — pure function turning an expense total + per-participant
  input into exact integer-cent shares for all four split modes (equal / exact / percentage /
  shares). Every proportional mode uses largest-remainder distribution so shares always sum
  exactly to the total — no float ever touches a monetary value anywhere in the codebase.
- **`services/balance_service.py`** — computes per-user net balances for a group from expenses
  + payments. The invariant "sum of a group's balances is always zero" is enforced and tested
  (`tests/test_invariants.py`) — don't break it.
- **`services/simplify_service.py`** — debt simplification: greedily matches the largest debtor
  against the largest creditor (a max-heap on each side) to produce at most `n-1` transfers for
  `n` participants, without changing anyone's net balance. Tie-breaking is by user id string, so
  output is deterministic.
- **`utils/money.py`** — all monetary values are integer cents end-to-end. Conversion to/from
  decimal strings (Russian formatting: `"1 234,56 ₽"`, comma decimal separator, non-breaking
  space thousands grouping) happens only here, only for display/parsing.

Auth: session JWT in an HttpOnly cookie (`skladchina_session`) plus a separate readable CSRF
cookie (`skladchina_csrf`) that the frontend must echo back as an `X-CSRF-Token` header on
unsafe methods (see `core/cookies.py`, `core/deps.py`, and `frontend/src/lib/api.ts`). No token
ever lives in `localStorage`. Every group-scoped route depends on `require_membership` /
`require_owner` from `core/deps.py` — authorization is structurally hard to forget.

Expense deletion is soft (`deleted_at`), so group history and the activity feed stay intact.

#### The two local AI runtimes

Both models run on your own machines — no external AI API, no API key, anywhere:

- **`services/gigaam_service.py`** — speech-to-text with `ai-sage/GigaAM-v3`, loaded
  **in-process** through `transformers.AutoModel` (`trust_remote_code`, revision `e2e_rnnt` by
  default). `transformers`/`torch` are imported inside `_model()`, not at module import, so the
  test suite and every non-voice endpoint never pay for torch; the model is `lru_cache`d for the
  process. GigaAM wants 16 kHz mono WAV and takes a *file path*, so each upload is transcoded
  with the `ffmpeg` binary into a `TemporaryDirectory` that is removed on every exit path.
  `transcribe(audio_bytes) -> str` is the whole contract — the pipeline above it doesn't know
  which STT model is running. GigaAM's `transcribe` refuses audio over **25 seconds**
  (`transcribe_longform` would need pyannote.audio and a gated HF model behind a token — not a
  dependency here), so the duration is checked before inference and raises `AudioTooLongError`,
  the one STT failure whose message `voice_service` passes through to the user verbatim.
- **`services/ollama_service.py`** — Qwen (`ollama_model`, default `qwen3.5:9b`) on a local
  **Ollama server running on the host**, not in a container: `docker compose up` does not start
  it, so `ollama serve` has to be running separately. Reached over `/api/generate` with
  `format: "json"` and `think: False` (a hybrid-reasoning Qwen otherwise puts the whole answer
  in a separate "thinking" field and leaves "response" empty). All three LLM use cases
  (`extract_expense`, `generate_saving_tips`, `generate_debt_reminder`) go through it and raise
  one error type, `OllamaError`.

Nothing waits on Ollama: each of the three callers degrades on `OllamaError` (see the fallbacks
below). Config lives in `core/config.py` under `gigaam_*` / `ollama_*`.

Measured latency on this machine (Apple Silicon, Ollama, `qwen3.5:9b`): see the verification
notes — a cold expense extraction is the slowest path, saving tips and debt reminders are
quicker. GigaAM transcribes a 3-second clip in well under a second once loaded; the first call
after a restart also pays the model load (~1 min including the first download).

#### Voice-to-expense pipeline (`services/voice_service.py`)

`POST /groups/{group_id}/voice-expenses` (`api/routes/voice.py`) takes an audio upload and
returns an ephemeral **draft** — it never writes to the database. The route handler is a sync
`def`, not `async`, so FastAPI runs it in a threadpool: both GigaAM transcription and the
Ollama call are blocking. Pipeline: local GigaAM transcription (`gigaam_service.py`) → local
Qwen structured extraction over Ollama (`ollama_service.py`,
prompted to return JSON) → `voice_service.build_draft` resolves the extracted payer/participant
names and category slug against the group's *real* members/categories (exact match, then
substring/first-name match; ambiguous or no-match names come back as `ambiguous`/`unresolved`
in the draft rather than being guessed at) and validates whatever split the model thought it
heard. `ExpenseCreate` requires a title, so `_resolve_title` falls back to the *resolved
category's* name (e.g. "Продукты") when the model returned none, and leaves it `None` when there
is no category either — it never invents a title client-side; the prompt in
`ollama_service.py` is where title wording is taught, so change it there rather than
post-processing in `voice_service.py`.

Split-total validation here never blocks the request — a mismatch only adds a `warnings` entry
on the draft. The real safety net is the same one manual entry already has: `ExpenseForm` (via
`split_engine` on submit) refuses to save an exact/percentage/shares split that doesn't add up,
so a bad voice draft is caught by the same, already-tested path either way.

#### AI saving tips (`services/saving_tips_service.py`)

`POST /dashboard/saving-tips` (`api/routes/dashboard.py`, params: `period`/`date_from`/
`date_to`/`group_id`, same as the rest of the dashboard endpoints) powers the "AI советы" block
on both the main dashboard and a single group's analytics tab. It deliberately does **not**
recompute anything: it calls the existing `dashboard_service` aggregates for the same scope,
trims them down to spending totals / category shares / a monthly series, and hands only that to
`ollama_service.generate_saving_tips` — no member names, debts, or ids are ever sent to the
model. If Ollama is unreachable or returns something unusable, it falls back to a fixed
`FALLBACK_TIPS` list rather than failing the request; the dashboard must never break because the
local model did.

#### Debt-reminder notifications (`services/debt_reminder_service.py`, `models/notification.py`)

Not to be confused with `services/notification_service.py` (a group-invite emailer stub with no
provider wired up — see its docstring). This is the in-app bell: `api/routes/notifications.py`
exposes `GET /notifications` and `POST /notifications/read`, backed by
`frontend/src/hooks/useNotifications.ts` (polls every 30s — no websocket) and
`components/layout/NotificationBell.tsx`.

One `Notification` row per debtor is created synchronously, in the same transaction as the
expense, by `debt_reminder_service.create_reminders_for_expense` — called from
`expense_service.create_expense` with the `SplitResult`s it already computed (this module never
re-derives who owes what). Every display field (`expense_title`, `payer_name`, `group_name`,
`amount_due_cents`) is a snapshot at commit time, not a live join, and a deterministic fallback
`message` is filled in immediately so the row is complete even if nothing else ever runs. The
row only becomes visible once `available_at` (`created_at` + `debt_reminder_delay_seconds`,
default 10s) passes — a plain column, not a timer, so a restart can't lose it.

Afterwards, `enhance_with_qwen` runs as a `BackgroundTasks` job (its own DB session — the
request's is already closed) and best-effort replaces the fallback message with one worded by
Qwen via `ollama_service.generate_debt_reminder`; failure is silently swallowed and the
deterministic fallback stands. `source` (`"fallback"` vs `"qwen"`) records which path won but
isn't exposed over the API.

### Frontend (`frontend/src/`)

- **`pages/`** — route-level screens, wired up in `routes.tsx`. Authenticated routes are nested
  under `RequireAuth` + `AppLayout` in `components/layout/`.
- **`hooks/`** — one file per API resource (`useGroups.ts`, `useExpenses.ts`, `useBalances.ts`,
  `useVoiceExpense.ts`, `useNotifications.ts`, etc.), each a thin TanStack Query wrapper. There is
  no manual `useEffect(fetch...)` anywhere — all server state goes through these hooks, and
  mutations invalidate the relevant query keys so screens refresh themselves.
- **`lib/api.ts`** — the only place that calls `fetch`. Handles the CSRF header, cookie-based
  auth, and error unwrapping (`ApiError`, `errorMessage()`). Route handlers/hooks should never
  call `fetch` directly.
- **`lib/money.ts`** / **`lib/format.ts`** — client-side mirrors of the backend's money/formatting
  rules for consistent display; the server is still the authority on calculated splits.
- **`components/ui/`** — design-system primitives (button, dialog, tabs, etc.), built on Radix.
  **`components/common/`, `layout/`, `balances/`, `expenses/`, `groups/`, `dashboard/`, `charts/`**
  — feature-grouped components. `expenses/VoiceExpenseDialog.tsx` records/uploads audio and
  renders the returned draft (including any ambiguous/unresolved fields) into `ExpenseForm`
  for the user to confirm before it's actually submitted.
- **`types/api.ts`** — TypeScript types mirroring the backend's Pydantic schemas.

Design tokens (colors, radii, shadows) live as CSS variables in `src/index.css` and as keys in
`tailwind.config.js` — don't hardcode colors; use the existing tokens (`bg-app`, `text-dim`,
`text-positive`, `text-negative`, `rounded-card`, `shadow-card`, etc.). Tailwind silently drops a
class that isn't in the config instead of erroring, so a new token has to be added to
`tailwind.config.js` before it will take effect.

## Conventions and decisions worth knowing

- **Money is always integer cents**, never a float, anywhere in the stack. See `split_engine.py`
  and `money.py` above.
- **Group balances always sum to zero** — an invariant enforced in tests and in the seed script.
- **Only `RUB`** is accepted server-side; the `currency` field on schemas exists for compatibility
  only.
- Commits are in Russian, imperative mood, one change per commit (repo convention — not enforced
  by tooling).
- Where to make common changes:
  - New endpoint → `api/routes/` + `schemas/` + `services/`
  - Change a calculation rule → `services/` (with a test alongside)
  - New/changed table → `models/` + a new Alembic revision
  - New screen → `pages/` + a route in `routes.tsx`
  - New API call → `hooks/` + a type in `types/api.ts`
  - Visual changes → tokens in `index.css` / `tailwind.config.js`, primitives in `components/ui/`

## Gotchas

- Postgres from the host is on **port 5433**, not 5432 (avoids clashing with a local Postgres).
- Backend tests run against in-memory SQLite (`StaticPool`, single shared connection) — fine for
  tests, but SQLite is *not* viable for actually running the app (concurrent requests raise
  `InterfaceError`). Use Postgres for real runs.
- The CSRF cookie name is duplicated in two places that must stay in sync: `COOKIE_NAME` /
  `CSRF_COOKIE_NAME` (backend env) and the constant in `frontend/src/lib/api.ts`.
- A voice note must be **25 seconds or shorter** — GigaAM's single-shot `transcribe` limit.
  `gigaam_service` checks the decoded WAV's duration before inference and raises
  `AudioTooLongError`, which `voice_service` turns into a 400 whose Russian message the dialog
  shows verbatim. `voice_max_upload_bytes` (15 MB) is a separate, much looser guard on size.
- The voice pipeline, saving tips, and debt-reminder wording all need Ollama running separately
  (`ollama serve`, with `ollama_model` pulled) — it is **not** started by `docker compose up`.
  If Ollama is unreachable: voice drafting still succeeds but returns an empty extraction with a
  `warnings` entry, saving tips fall back to a fixed generic list, and debt reminders keep their
  deterministic fallback message — none of the three endpoints fails outright.
- In Docker, `OLLAMA_BASE_URL` defaults to `http://host.docker.internal:11434` because Ollama
  runs on the host; on the host itself the default `http://localhost:11434` is right. GigaAM
  additionally needs `ffmpeg` on PATH.
- **The backend requires Python 3.12**, not merely 3.12+: torch 2.8.0 (which GigaAM's model code
  needs) publishes cp39-cp313 wheels only. Pinned in `backend/pyproject.toml`
  (`requires-python = ">=3.12,<3.13"`) and `backend/.python-version`. The unit suite still runs
  on a newer interpreter because `gigaam_service` imports torch lazily — a real transcription
  won't, and `pip install -r requirements.txt` fails outright there.
- User-facing copy never names a model: the UI says "твой AI помощник" (see
  `VoiceExpenseDialog.tsx`, `SavingTipsCard.tsx`, and the warning text in `voice_service.py`).
- **`npm run typecheck` emits compiled output next to the sources.** The script overrides the
  tsconfigs' `noEmit`, so it writes `Foo.js`/`Foo.d.ts` beside every `Foo.tsx` (plus
  `vite.config.js` beside `vite.config.ts`). A batch of those got committed and some are now
  stale — and they are not inert: Vite resolves an extensionless import (`@/components/.../Foo`)
  through `.mjs, .js, .mts, .ts, .jsx, .tsx`, so a stale `Foo.js` shadows the `Foo.tsx` you just
  edited, and `vite.config.js` wins over `vite.config.ts`. If a change appears to have no effect,
  check for a `.js` sibling first. `npm run build` / `tsc -b` alone do not emit; after running
  `typecheck`, `git status` and clean up what it produced.
- `services/notification_service.py` (group-invite email) and `services/debt_reminder_service.py`
  + `models/notification.py` (in-app bell) are two unrelated systems that both use the word
  "notification" — don't conflate them.

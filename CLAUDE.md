# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Working style, editing conventions, and testing guidelines are in [CORE.md](./CORE.md).

## Commands

### Backend (FastAPI + Python)

The project venv is at `.venv/` in the repo root. All Python/pytest commands run from the repo root without activating the venv — just invoke `.venv/bin/python` or `.venv/bin/pytest` directly, or rely on the shell PATH if the venv is already active. Do NOT `cd backend` or `source .venv/bin/activate`.

```bash
# Run dev server (from repo root)
./backend/run.sh
# or: .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Run MCP server (stdio)
.venv/bin/python -m backend.app.mcp_server --stdio

# Run all Python tests
.venv/bin/pytest temperance/tests -q

# Run a single test file
.venv/bin/pytest temperance/tests/test_activity_parsing.py -v

# Run backend-specific tests
.venv/bin/python -m unittest backend.tests.test_mcp_server -v
```

### Frontend (React + Vite + TypeScript)

```bash
cd frontend

npm install        # install deps
npm run dev        # dev server at http://127.0.0.1:5173 (proxies /api/* to :8000)
npm run build      # production build (includes tsc type check)
npm run preview    # preview production build
```

### Operations

```bash
# Restart keepalive services after backend changes (required on Temperance v2)
./temperance/scripts/install_keepalive.sh restart

# Run database migrations
python -m temperance.migrate
```

## Architecture

Temperance is a local-first training and recovery app for endurance athletes, backed by a Garmin-synced SQLite archive.

### Three-tier layout

| Layer | Location | Role |
|-------|----------|------|
| Frontend | `frontend/` | React 18 + TypeScript SPA; feature modules under `src/features/` |
| Backend API | `backend/app/main.py` | FastAPI REST endpoints; auth, sync, planning, analytics |
| Shared library | `temperance/` | Domain logic: SQLite, analytics, Garmin sync, planning engine |

### Shared library (`temperance/`)

- **`db.py`** — SQLite schema and all CRUD; owner-scoped databases at `temperance/data/private/users/<owner>.db`
- **`analytics.py`** — Training metrics: CTL/ATL/TSB/ACWR, daily summaries, EMA helpers
- **`activity_parsing.py`** — Canonical workout string parsing and normalization
- **`garmin_client.py`** — Garmin API sync, FIT file parsing, wellness extraction
- **`planning/`** — Workout recommendation engine (state builder, policy, session selector)
- **`guidelines/`** — Training doctrine YAML/Markdown; workout catalog and templates

### Backend (`backend/app/`)

- **`main.py`** — ~30+ REST endpoints covering auth, Garmin sync, wellness, planning, analytics
- **`mcp_server.py`** — Model Context Protocol interface; tools: `plan_next_day`, `get_today_status`, `judge_training_history`; must stay in sync with dashboard analytics
- **`garmin_oauth.py`** — OAuth flow management for Garmin connections

### Frontend (`frontend/src/features/`)

Feature modules: `auth`, `dashboard`, `athlete-progression`, `weekly-outlook`, `plan-activities`, `custom-activities`, `week-planner`, `data-extract`, `wellness`, `settings`.  
API base path: `/api`. Session token stored in localStorage under `temperance.session`.

## Key contracts and invariants

### Workout text format

Workout strings are canonical and reparseable (not free-form prose). Examples:
- Date prefixes: `today:`, `T+1:`, `2026-03-26:`
- Duration: `45min`, `1h30m`
- Distance: `42.2km`, `6x1km`, `8x400m`
- Pace: `@4:40/km`, `@mp`, `@10k`
- HR/intensity: `@138bpm`, `@78%`

All generated text is re-emitted in normalized form so it can be re-parsed. Any change to parsing or generation must preserve round-trip fidelity.

### Weekly baseline alignment (critical)

The MCP `get_fitness_form.weekly_baseline` **must match** the dashboard "Athlete Progression" baseline. Path: LT-derived weekly capacity → 21/63/365-day load blend → modeled baseline → Monday weekly rollup. Divergence is a bug.

### After backend changes

Always run `./temperance/scripts/install_keepalive.sh restart` after backend code changes that need a process restart.

### Database

Base DB: `temperance/data/private/temperance.db`. Owner-scoped: `temperance/data/private/users/<owner>.db`. Schema migrations managed by `temperance/migrate.py`.

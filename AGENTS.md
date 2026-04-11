# AGENTS.md

This file provides guidance to AI coding agents working in this repository.

> Shared working style, editing conventions, and testing expectations are in [CORE.md](./CORE.md). Follow those first for collaboration and change discipline.

## Project Overview

Temperance is a local-first training and recovery app for endurance athletes, backed by a Garmin-synced SQLite archive.

## Commands

### Backend (FastAPI + Python)

```bash
cd backend && source .venv/bin/activate

# Run dev server
./run.sh
# or: python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

# Run MCP server (stdio)
python3 -m backend.app.mcp_server --stdio

# Run all Python tests
pytest temperance/tests -q

# Run a single test file
pytest temperance/tests/test_activity_parsing.py -v

# Run backend-specific tests
python -m unittest backend.tests.test_mcp_server -v
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
# Restart keepalive services after backend changes that need a process restart
./temperance/scripts/install_keepalive.sh restart

# Run database migrations
python -m temperance.migrate
```

## Architecture

| Layer | Location | Role |
|-------|----------|------|
| Frontend | `frontend/` | React 18 + TypeScript SPA; feature modules under `src/features/` |
| Backend API | `backend/app/main.py` | FastAPI REST endpoints; auth, sync, planning, analytics |
| Shared library | `temperance/` | Domain logic: SQLite, analytics, Garmin sync, planning engine |

## Shared Library (`temperance/`)

- `db.py` - SQLite schema and all CRUD; owner-scoped databases at `temperance/data/private/users/<owner>.db`
- `analytics.py` - Training metrics: CTL/ATL/TSB/ACWR, daily summaries, EMA helpers
- `activity_parsing.py` - Canonical workout string parsing and normalization
- `garmin_client.py` - Garmin API sync, FIT file parsing, wellness extraction
- `planning/` - Workout recommendation engine: state builder, policy, session selector
- `guidelines/` - Training doctrine YAML/Markdown; workout catalog and templates

## Backend (`backend/app/`)

- `main.py` - REST endpoints covering auth, Garmin sync, wellness, planning, analytics
- `mcp_server.py` - Model Context Protocol interface; tools include `plan_next_day`, `get_today_status`, and `judge_training_history`; keep MCP analytics aligned with dashboard analytics
- `garmin_oauth.py` - OAuth flow management for Garmin connections

## Frontend (`frontend/src/features/`)

Feature modules include `auth`, `dashboard`, `athlete-progression`, `weekly-outlook`, `plan-activities`, `custom-activities`, `week-planner`, `data-extract`, `wellness`, and `settings`.

Frontend API base path: `/api`. Session token storage key: `temperance.session` in localStorage.

## Key Contracts and Invariants

### Workout Text Format

Workout strings are canonical and reparseable, not free-form prose.

Examples:

- Date prefixes: `today:`, `T+1:`, `2026-03-26:`
- Duration: `45min`, `1h30m`
- Distance: `42.2km`, `6x1km`, `8x400m`
- Pace: `@4:40/km`, `@mp`, `@10k`
- HR/intensity: `@138bpm`, `@78%`

All generated workout text is re-emitted in normalized form so it can be re-parsed. Any change to parsing or generation must preserve round-trip fidelity.

### Weekly Baseline Alignment

The MCP `get_fitness_form.weekly_baseline` must match the dashboard "Athlete Progression" baseline. The expected path is:

```text
LT-derived weekly capacity -> 21/63/365-day load blend -> modeled baseline -> Monday weekly rollup
```

Divergence between MCP baseline values and dashboard baseline values is a bug.

### Database

Base database: `temperance/data/private/temperance.db`.

Owner-scoped databases: `temperance/data/private/users/<owner>.db`.

Schema migrations are managed by `temperance/migrate.py`.

### Backend Process Restarts

After backend code changes that need a process restart, run:

```bash
./temperance/scripts/install_keepalive.sh restart
```

## Validation Expectations

- For parser, planning, analytics, MCP, or API behavior changes, add or update focused regression tests when practical.
- For frontend changes, run `npm run build` from `frontend/` when the change affects TypeScript, routing, API calls, or rendered UI logic.
- For backend/shared-library changes, run the narrowest relevant Python tests first, then broaden to `pytest temperance/tests -q` when risk warrants it.

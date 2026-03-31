# Temperance

Temperance is a local-first training and recovery app built around a Garmin-backed SQLite archive.

The project now has one supported product surface:

- `backend/`: FastAPI API for auth, dashboard, wellness, planning, and Garmin sync flows
- `frontend/`: React/Vite client
- `temperance/`: shared Python domain logic, SQLite schema, migrations, Garmin extraction, assets, and ops scripts
- `temperance/data/private/`: local databases, logs, and private exports; gitignored by default

## Repo layout

```text
Temperance/
├── backend/         FastAPI app
├── frontend/        React + Vite app
└── temperance/
    ├── analytics.py
    ├── auth.py
    ├── config.py
    ├── db.py
    ├── garmin_client.py
    ├── migrate.py
    └── scripts/     launchd and maintenance helpers
```

## Quick start

### 1. Run the backend

```bash
cd /Users/matheus/Temperance/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Backend URL: `http://127.0.0.1:8000`

### 2. Run the frontend

```bash
cd /Users/matheus/Temperance/frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

The frontend proxies `/api/*` and `/health` to the backend during local development.

### 3. Configure Garmin credentials when you need sync

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

You can also keep these in `temperance/.env` for local use.

## Data model and storage

- Default base DB: `temperance/data/private/temperance.db`
- Owner-scoped DBs: `temperance/data/private/users/<owner>.db`
- Private logs: `temperance/data/private/logs/`
- Private exports and imports stay under `temperance/data/` and are gitignored

The backend resolves owner-scoped databases first and falls back to the base DB for the default owner when needed.

## Garmin sync modes

- Comprehensive Garmin sync: full backfill path for activities, details, FIT records, sleep, and wellness
- Embedded auto-sync in the backend: lightweight incremental activity sync only

The embedded auto-sync does not fetch sleep, HRV, training readiness, or other wellness endpoints. If recovery data for the current day is blank, run a comprehensive sync before assuming the UI is wrong.

## Operations

- `temperance/scripts/install_keepalive.sh`: macOS `launchd` setup for the backend, frontend, and Cloudflare tunnel
- `temperance/scripts/install_autoupdate.sh`: hourly fast-forward updater for machines that should track `origin/main`
- `temperance/README.md`: shared Python package notes, data locations, and migration entry points

## Tests

Python tests:

```bash
cd /Users/matheus/Temperance
pytest temperance/tests -q
```

Frontend build check:

```bash
cd /Users/matheus/Temperance/frontend
npm run build
```

## Follow-up

The API remains on `/api/v1` during this consolidation. A future cleanup can flatten that prefix to `/api` once the unified layout is stable.

# Temperance v2 (Parallel Stack)

This folder hosts the v2 migration track while Streamlit v1 remains unchanged.

## Ports

- Streamlit v1: `8504` (existing keepalive flow)
- v2 backend (FastAPI): `8000`
- v2 frontend (React/Vite): `5173`

## Run v2 backend

```bash
cd /Users/matheus/Temperance/v2/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Backend health check: `http://127.0.0.1:8000/health`

## Run v2 frontend

```bash
cd /Users/matheus/Temperance/v2/frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

The frontend proxies `/health` and `/api/*` to `http://127.0.0.1:8000`.

## Initial API surface

- `GET /health`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/owners`
- `GET /api/v1/overview`
- `GET /api/v1/dashboard?days=42&owner=<owner>&sport=run&start_day=YYYY-MM-DD&end_day=YYYY-MM-DD`
- `GET /api/v1/weekly-summary?days=84&owner=<owner>&sport=run&start_day=YYYY-MM-DD&end_day=YYYY-MM-DD`
- `GET /api/v1/week-outlook?days=84&owner=<owner>&metric=tss&compare=planned&week_start=YYYY-MM-DD`
- `GET /api/v1/activities/{activity_id}?owner=<owner>`

`/api/v1/overview` reads from the existing Streamlit SQLite DB by default:

`/Users/matheus/Temperance/temperance/data/private/temperance.db`

Override with:

```bash
export TEMPERANCE_DB_PATH="/absolute/path/to/temperance.db"
```

`/api/v1/dashboard` reuses existing business logic from:

- `temperance/db.py#get_runs_df`
- `temperance/analytics.py#compute_metrics`
- `temperance/analytics.py#build_daily_summary`
- `temperance/analytics.py#display_table`

## Auth and owner scope behavior

- Matches v1 rules:
  - If `TEMPERANCE_AUTH_ENABLED=1` (default), API requires login token.
  - Viewer role is restricted to their own owner scope.
  - Admin role can switch owner scope.
- Tokens are returned by `POST /api/v1/auth/login` and sent as:
  - `Authorization: Bearer <token>`
- Owner-scoped DB resolution:
  - `<base_db_dir>/users/<owner_slug>.db`
  - fallback to base DB for `default` owner if scoped DB is missing
- v1/v2 DB compatibility contract:
  - v2 resolves the base DB using the same v1 config loader (`temperance/config.py#load_config`) unless `TEMPERANCE_DB_PATH` is explicitly set.
  - Current v2 endpoints are read-only, so v2 will not create or fork DB content.

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
    ├── activity_parsing.py
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
The public app is served at `https://app.temperance-rtl.work/v2`, while the API is mounted at `/api` with `/api/v1` kept as a backward-compatible alias.

### 3. Configure Garmin credentials when you need sync

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

You can also keep these in `temperance/.env` for local use.

### 4. Configure Garmin OAuth when you want non-admin user pairing

Garmin OAuth is optional, but required if non-admin users should pair their own Garmin accounts instead of relying only on memory-only session credentials.

Minimum OAuth connection config:

```bash
export GARMIN_OAUTH_CLIENT_ID="your_client_id"
export GARMIN_OAUTH_CLIENT_SECRET="your_client_secret"
export GARMIN_OAUTH_REDIRECT_URI="http://127.0.0.1:8000/api/v1/garmin/oauth/callback"
export GARMIN_OAUTH_AUTHORIZE_URL="https://<garmin-authorize-endpoint>"
export GARMIN_OAUTH_TOKEN_URL="https://<garmin-token-endpoint>"
export TEMPERANCE_OAUTH_TOKEN_ENCRYPTION_KEY="replace_with_a_long_random_secret"
```

Optional, but needed if OAuth-connected users should actually run Garmin data extract through the app:

```bash
export GARMIN_OAUTH_USERINFO_URL="https://<garmin-userinfo-endpoint>"
export GARMIN_OAUTH_ACTIVITIES_URL="https://<garmin-activities-endpoint>"
export GARMIN_OAUTH_WELLNESS_URL="https://<garmin-wellness-endpoint>"
export GARMIN_OAUTH_SCOPES="activities wellness profile"
```

If the activities/wellness URLs are missing, Garmin OAuth connect/disconnect will work, but the UI will keep OAuth-backed extract capability-gated and users will need the legacy session-credential fallback to actually sync data.

## Data model and storage

- Default base DB: `temperance/data/private/temperance.db`
- Owner-scoped DBs: `temperance/data/private/users/<owner>.db`
- Private logs: `temperance/data/private/logs/`
- Private exports and imports stay under `temperance/data/` and are gitignored

The backend resolves owner-scoped databases first and falls back to the base DB for the default owner when needed.

## Main product features

- Auth with local admin/viewer users and owner-scoped data access
- Dashboard, wellness, athlete progression, and weekly outlook views
- Planned activities ingestion, parsing, editing, and manual completion
- Custom activities ingestion and generated activity suggestions
- Garmin sync, Garmin auth reset, and incremental auto-sync
- Shared SQLite-backed metrics, migrations, and activity detail retrieval

## Planning text rules

Temperance relies on compact workout strings for planned activities, custom activities, and some generated suggestions. Future changes should preserve these rules unless the parser and tests are updated together.

- Dated entries use `[date]:[activity]`
- Bulk entry separators can be newline, comma, or semicolon
- Accepted date forms include `today`, `tomorrow`, `yesterday`, `T`, `T+1`, `T-1`, `2026-03-26`, `26/03/2026`, and `26Mar26`
- Whitespace is normalized before storage and duplicate planned rows are detected from normalized text plus day
- Duration tokens accept `45min`, `45'`, `1h`, `1h30m`, `20s`, and `20"`
- Distance tokens accept `42.2km`, `400m`, and repeated-distance forms like `6x1km` or `8x400m`
- Running pace tokens accept forms like `@4:40`, `@4:40/km`, plus named pace shorthands `@mp`, `@hmp`, and `@10k`
- Intensity tokens accept `%IF` such as `@78%`, heart rate such as `@138bpm`, and TSS such as `@80tss`
- Interval recovery blocks can use slash syntax or parentheses, for example `3x8' @ 3:45 / 2' @ 4:40` or `3x8' @ 3:45 (2' @ 4:40)`
- Elliptical aliases include `elliptical`, `xtrain`, `x-train`, `cross train`, and `cross-train`
- Distance-only running segments require pace context; non-running segments should use minutes plus `bpm` or `%IF`

## Generated string rules

Generated activity suggestions intentionally emit normalized strings that are easy to parse again later.

- Duration is emitted as `NhMmin` or `Nmin`, for example `1h5min` or `40min`
- Running and treadmill suggestions prefer pace output such as `Run 40min @4:40/km`
- Non-running suggestions prefer heart-rate output such as `Elliptical 70min @138bpm`
- The generated text is derived from structured segments, so preserving the parser and formatter contract keeps suggestion reuse stable
- API clients should treat `activity_text` and `workout_text` as canonical display-plus-roundtrip strings, not free-form prose

## Garmin sync modes

- Comprehensive Garmin sync: full backfill path for activities, details, FIT records, sleep, and wellness
- Embedded auto-sync in the backend: lightweight incremental activity sync only

The embedded auto-sync does not fetch sleep, HRV, training readiness, or other wellness endpoints. If recovery data for the current day is blank, run a comprehensive sync before assuming the UI is wrong.

## Data Extract modes

Temperance now supports multiple ways to use the Data Extract page. The mode that runs depends on who is logged in and which Garmin connection is available.

### Admin on own scope

- If `GARMIN_EMAIL` and `GARMIN_PASSWORD` are set, the admin user can open **Data Extract** and run Garmin extract immediately.
- The backend treats environment credentials as the primary source for the admin’s own owner scope.
- `Reset Garmin auth` clears the cached Garmin session for the backend process, but does not remove the env vars.

### Admin viewing another owner

- Admin can switch owner scope in the UI and enter that owner’s Garmin email/password in the **Garmin Credentials** card.
- Those credentials are stored in backend memory only and are not persisted to SQLite.
- This is useful when OAuth is not available for that owner, or when you need a temporary legacy sync path.

### Non-admin with Garmin OAuth

- The non-admin user opens **Data Extract** and clicks `Connect Garmin`.
- The app redirects through Garmin OAuth and returns to `/app/data-extract` after the callback succeeds or fails.
- Once connected, Data Extract prefers the persisted Garmin OAuth token over memory-only session credentials.
- If `GARMIN_OAUTH_ACTIVITIES_URL` and `GARMIN_OAUTH_WELLNESS_URL` are configured, `Run extract` uses the OAuth-backed Garmin path.
- If those URLs are not configured, the UI will show Garmin as connected but keep extract capability-gated unless the user also provides legacy session credentials.

### Non-admin without OAuth, using legacy session credentials

- The non-admin user can still use the existing **Garmin Credentials** card.
- Entered Garmin email/password are kept in backend memory only for that active backend session.
- This remains the fallback path if OAuth is unavailable or if Garmin OAuth connection exists but extract endpoints are not configured.

### No Garmin connection

- Users can skip Garmin entirely and still use the app for:
  - custom activities
  - planning and generated activities
  - dashboard/wellness views backed by previously synced data
- In this mode, Data Extract will not run Garmin sync until either OAuth or legacy session credentials are available.

### What `Run extract` does

- `Activities` enabled: fetch activity rows and related activity detail payloads when supported by the active sync source.
- `Wellness` enabled: fetch sleep and wellness rows when supported by the active sync source.
- `Incremental` enabled: only refetch missing days plus the current freshness window.
- The current connection mode is surfaced in the Data Extract page as `oauth`, `session`, `env`, or `missing`.

## Operations

- `temperance/scripts/install_keepalive.sh`: macOS `launchd` setup for the backend, frontend, and Cloudflare tunnel
- `temperance/scripts/install_autoupdate.sh`: hourly fast-forward updater for machines that should track `origin/main`
- `temperance/README.md`: shared Python package notes, data locations, and migration entry points

After backend or frontend path changes, reinstall or restart the keepalive services so launch agents stop pointing at stale workspace paths.

## MCP experiment

There is now an initial MCP server prototype at `backend/app/mcp_server.py`.

Current MVP tools:
- `get_today_status`
- `get_recent_activities`
- `get_planned_activities`
- `get_week_outlook`
- `get_load_trend`
- `get_recovery_trend`
- `recommend_training`
- `explain_recommendation`
- `get_activity_detail`

Run it over stdio from the repo root:

```bash
cd /Users/matheus/Temperance
python3 -m backend.app.mcp_server --stdio
```

This first pass intentionally reuses existing Temperance analytics and payload builders instead of adding a second data layer. It is a thin wrapper meant to prove the chat-to-metrics workflow before we harden the interface.

### Why the server now imports more cleanly

`backend/app/mcp_server.py` now keeps its pure JSON-RPC and recommendation helpers importable without importing `backend.app.main` at module import time. That means you can run lightweight helper tests even on machines that do not currently have the FastAPI stack installed, as long as the tests avoid the data-backed tool handlers.

### Lightweight helper tests

These tests only cover pure formatting / recommendation / JSON-RPC helpers and are meant to be runnable without live API dependencies:

```bash
cd /Users/matheus/Temperance
python3 -m unittest backend.tests.test_mcp_server -v
```

### Minimal MCP client smoke example

You can manually speak JSON-RPC over stdio to confirm the handshake shape:

```bash
cd /Users/matheus/Temperance
python3 -m backend.app.mcp_server --stdio <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"manual-smoke","version":"0.0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list"}
EOF
```

### Example `recommend_training` request

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "recommend_training",
    "arguments": {
      "owner": "admin",
      "activity_type": "running"
    }
  }
}
```

Response shape now includes:
- `headline`: short human-facing summary
- `rationale`: primary decision reason
- `explanation`: compact metric trace explaining the call
- `suggestion`: workout wording tuned to the chosen activity family
- `decision_trace`: explanation-oriented signal breakdown for clients that want to show *why* the choice was made

That split is deliberate: chat clients can show the short summary first, then expose the detailed explanation when needed.

### Example `explain_recommendation` request

Use this when the client wants the same recommendation context, but with the explanation surfaced first:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "explain_recommendation",
    "arguments": {
      "owner": "admin",
      "activity_type": "running"
    }
  }
}
```

### Example `get_activity_detail` request

This tool delegates to the existing Temperance activity-detail backend path and returns the same high-value payload shape for real, planned, or custom activities:

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "get_activity_detail",
    "arguments": {
      "owner": "admin",
      "activity_id": "run-123",
      "include_records": true,
      "records_limit": 300
    }
  }
}
```

### Dependency note for MCP-only setups

`backend/requirements-mcp.txt` currently just includes `requirements.txt`. If we want a truly standalone MCP environment later, the next step is to break out a smaller optional dependency set around pandas/pydantic plus Temperance core imports while keeping FastAPI optional.

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

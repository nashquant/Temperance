# Temperance legacy Python stack

This directory contains the original Streamlit app and the shared Python modules that still power much of the current data model.

If you are looking for the main project entry point, start with the repo root `README.md`. The active product surface now lives in `../v2/`.

## What lives here

- `app.py`: original Streamlit UI
- `garmin_client.py`: Garmin activity and wellness extraction
- `db.py`: SQLite schema, queries, and upserts
- `analytics.py`: training-load and daily summary logic
- `auth.py`: local auth helpers
- `migrate.py`: schema migration runner
- `scripts/`: local ops helpers for keepalive, auto-update, and background services
- `tests/`: Python test suite

## What this folder is still used for

- Running the legacy Streamlit app
- Managing the SQLite archive and migrations
- Syncing Garmin activity and recovery data
- Supplying shared business logic that the v2 backend reuses

## Run the legacy Streamlit app

```bash
cd /Users/matheus/Temperance/temperance
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Use the legacy app only when you specifically want the older Streamlit workflow. For the current UI, run the v2 backend and frontend from the repo root instructions.

## Data locations

- Base DB: `data/private/temperance.db`
- Owner-scoped DBs: `data/private/users/<owner>.db`
- Private logs: `data/private/logs/`
- Imports: `data/imports/`

These paths are private and gitignored.

## Garmin sync notes

- Comprehensive sync is the deep path for activities, activity details, FIT records, sleep, and wellness.
- The lightweight embedded v2 auto-sync is activity-only and does not populate HRV, sleep, training readiness, or other daily wellness metrics.
- If current-day recovery data looks blank, verify that a comprehensive sync has run before debugging the frontend.

## Operations

- `scripts/install_keepalive.sh` manages the v2 backend, v2 frontend, and Cloudflare tunnel through macOS `launchd`
- `scripts/install_autoupdate.sh` installs the optional fast-forward auto-update job
- `run_remote.sh` is the older helper for running the Streamlit app in the background

## Migrations

```bash
cd /Users/matheus/Temperance/temperance
python migrate.py
```

## Tests

```bash
cd /Users/matheus/Temperance
pytest temperance/tests -q
```

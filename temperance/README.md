# Temperance Shared Python Package

This directory contains the shared Python modules that power the backend data model, Garmin sync flows, and SQLite archive.

If you are looking for the main project entry point, start with the repo root [README](../README.md).

## What lives here

- `garmin_client.py`: Garmin activity and wellness extraction
- `db.py`: SQLite schema, queries, upserts, and migrations
- `analytics.py`: training-load and daily summary logic
- `auth.py`: local auth helpers
- `migrate.py`: schema migration runner
- `scripts/`: local ops helpers for keepalive, auto-update, and background services
- `tests/`: Python test suite

## What this folder is used for

- Managing the SQLite archive and migrations
- Syncing Garmin activity and recovery data
- Supplying shared business logic that the backend reuses

## Data locations

- Base DB: `data/private/temperance.db`
- Owner-scoped DBs: `data/private/users/<owner>.db`
- Private logs: `data/private/logs/`
- Imports: `data/imports/`

These paths are private and gitignored.

## Garmin sync notes

- Comprehensive sync is the deep path for activities, activity details, FIT records, sleep, and wellness.
- The lightweight embedded backend auto-sync is activity-only and does not populate HRV, sleep, training readiness, or other daily wellness metrics.
- If current-day recovery data looks blank, verify that a comprehensive sync has run before debugging the frontend.

## Operations

- `scripts/install_keepalive.sh` manages the backend, frontend, and Cloudflare tunnel through macOS `launchd`
- `scripts/install_autoupdate.sh` installs the optional fast-forward auto-update job

## Migrations

```bash
cd /Users/matheus/Temperance/temperance
python -m temperance.migrate
```

## Tests

```bash
cd /Users/matheus/Temperance
pytest temperance/tests -q
```

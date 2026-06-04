# Temperance Shared Python Package

This directory contains the shared Python modules that power the backend data model, Garmin sync flows, and SQLite archive.

If you are looking for the main project entry point, start with the repo root [README](../README.md).

## What lives here

- `garmin_client.py`: Garmin activity and wellness extraction
- `db.py`: SQLite schema, queries, upserts, and migrations
- `analytics.py`: training-load and daily summary logic
- `activity_parsing.py`: shared workout-text normalization, date parsing, interval parsing, and signature logic
- `auth.py`: local auth helpers
- `migrate.py`: schema migration runner
- `scripts/`: local ops helpers for keepalive, auto-update, and background services
- `tests/`: Python test suite

## What this folder is used for

- Managing the SQLite archive and migrations
- Syncing Garmin activity and recovery data
- Supplying shared business logic that the backend reuses
- Defining the canonical text parsing and normalization rules for planned and generated activities

## Data locations

- Base DB: `data/private/temperance.db`
- Owner-scoped DBs: `data/private/users/<owner>.db`
- Private logs: `data/private/logs/`
- Imports: `data/imports/`

These paths are private and gitignored.

Local credentials should live in `~/.config/temperance/temperance.env`, not in
this package directory. Use `temperance/.env.example` as the template.

## Garmin sync notes

- Comprehensive sync is the deep path for activities, activity details, FIT records, sleep, and wellness.
- The lightweight embedded backend auto-sync is activity-only and does not populate HRV, sleep, training readiness, or other daily wellness metrics.
- If current-day recovery data looks blank, verify that a comprehensive sync has run before debugging the frontend.

## Parsing and generation contracts

These rules matter because workout strings are both user-facing and machine-reparsed later for metrics, dedupe, and generated suggestions.

### Planning input rules

- Canonical dated-entry form is `[date]:[activity]`
- Valid relative dates: `today`, `tomorrow`, `yesterday`, `T`, `T+N`, `T-N`
- Valid absolute dates: ISO `YYYY-MM-DD`, slash `DD/MM/YYYY`, compact `26Mar26`
- Entry blocks split on newline, comma, or semicolon
- Text normalization collapses whitespace and normalizes units like `45 min` -> `45min`, `20"` -> `20s`, `4:40 / km` -> `4:40/km`
- Repeated intervals support forms like `6x20" @ 3:10` and `3x8' @ 3:45 (2' @ 4:40)`
- Running segments can use pace, HR, IF, or TSS context; non-running segments should use minutes with `bpm` or `%IF`
- Supported kind aliases intentionally map `xtrain`, `x-train`, and `cross-train` to `elliptical`

### Generated output rules

- Generated text is emitted in a normalized, reparseable form
- Duration formatter emits `Nmin`, `Nh`, or `NhMmin`
- Running outputs prefer `Kind Duration @pace/km`
- Non-running outputs prefer `Kind Duration @hrbpm`
- Existing tests in `temperance/tests/test_activity_parsing.py` and `temperance/tests/test_generated_activity.py` should be updated with any parser or formatter change

## Operations

- `scripts/install_keepalive.sh` manages the backend, frontend, and Cloudflare tunnel through macOS `launchd`
- `scripts/install_autoupdate.sh` installs the optional fast-forward auto-update job

The current unified keepalive setup expects the repo-level `backend/` and `frontend/` apps. If services start pointing at stale paths, reinstall the keepalive jobs from the current workspace.

## Migrations

```bash
# from repo root
.venv/bin/python -m temperance.migrate
```

## Tests

```bash
# from repo root
.venv/bin/pytest temperance/tests -q
```

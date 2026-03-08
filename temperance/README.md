# Temperance (MVP)

Local-first app to track running load and extract your own Garmin data archive (activities + wellness) into a local SQLite database.

## What it does now
- Streamlit local app.
- Garmin Connect sync (`garminconnect`) using env vars (`GARMIN_EMAIL`, `GARMIN_PASSWORD`).
- **Comprehensive extraction** from a chosen start date (default: **2025-01-01**):
  - Activity summaries (all sports)
  - Per-activity detail endpoints (details/splits/weather/hr zones)
  - Per-activity FIT download cache + per-record time series (when available)
  - Sleep + daily wellness (body battery, stress, HRV, RHR, readiness, stats/body)
- Expanded run-level metrics when available:
  - elevation gain/loss, cadence, stride length, vertical ratio/oscillation
  - running power avg/max, stamina start/end, training effect (aerobic/anaerobic)
  - performance condition, device name
  - HR zone times, elapsed/moving durations, average speed, intensity minutes
  - activity UUID/type, PR flag, owner metadata, split summaries, BMR calories
- Garmin-first dashboard for training-load, calories, and intensity-minute trend analysis with SMA/EMA overlays.
- Local SQLite caching and upsert logic.
- File import fallback for runs (`.FIT` / `.TCX`).

## Primary stored Garmin metrics (v1)
Per activity, Temperance stores first-class Garmin metrics:
- `training_load_garmin` (raw Garmin value from `activityTrainingLoad` or fallback `trainingLoad`)
- `training_load_garmin_field_name` + `training_load_garmin_units` (provenance/units metadata)
- `calories_active`, `calories_total`
- `intensity_minutes_vigorous`, `intensity_minutes_moderate`

Daily aggregates are stored in `daily_summary`:
- `training_load_garmin`
- `calories_active`, `calories_total`
- `intensity_minutes_vigorous`, `intensity_minutes_moderate`

## Privacy / local-only
Personal data is stored locally only:
- DB: `temperance/data/private/temperance.db`
- JSON snapshots: `temperance/data/private/exports/`
- Structured raw endpoint archive: `temperance/data/private/exports/raw/`
- Manual imports: `temperance/data/imports/`

These paths are gitignored to avoid publishing personal Garmin data.

## Project structure
- `app.py`: Streamlit UI
- `garmin_client.py`: Garmin activity + wellness extraction
- `db.py`: SQLite schema and persistence
- `migrate.py`: schema migration runner
- `models.py`: load formulas
- `analytics.py`: aggregations and comparison columns
- `tests/`: basic model unit tests

## Setup
1. Create and activate a virtual environment (Python 3.9+):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure Garmin credentials:

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

Or `.env` file in `temperance/`:

```env
GARMIN_EMAIL=you@example.com
GARMIN_PASSWORD=your_password
```

If app auth is enabled, you can also sign in to Temperance first and then enter Garmin API credentials from the sidebar (**Garmin API Credentials**). Those sidebar values are session-only and override env vars for that browser session.

Auth behavior for Garmin credentials:
- Admin users can use env Garmin credentials or session sidebar credentials.
- Non-admin authenticated users must provide Garmin credentials in the sidebar (env Garmin credentials are not used for them).
- Garmin sync now enforces a single Garmin owner scope per local DB to avoid mixing multiple accounts in the same dataset.

Temperance auth users (optional, when `TEMPERANCE_AUTH_ENABLED=1`):
- Single admin: `TEMPERANCE_ADMIN_USER`, `TEMPERANCE_ADMIN_PASSWORD` (or `TEMPERANCE_ADMIN_PASSWORD_SHA256`)
- Single viewer (legacy): `TEMPERANCE_VIEWER_USER`, `TEMPERANCE_VIEWER_PASSWORD` (or `TEMPERANCE_VIEWER_PASSWORD_SHA256`)
- Multiple viewers:
  - Plain: `TEMPERANCE_VIEWER_USERS=sirpoc:pw1,guest:pw2`
  - Hash: `TEMPERANCE_VIEWER_USERS_SHA256=sirpoc:sha256:<hash>,guest:sha256:<hash>`

## Run
From `temperance/`:

```bash
streamlit run app.py
```

## Remote Run
Use the helper script to keep Streamlit running in the background with logs:

```bash
cd temperance
./run_remote.sh start
```

Useful commands:

```bash
./run_remote.sh status
./run_remote.sh logs
./run_remote.sh stop
./run_remote.sh restart
```

Default local URL:
- `http://127.0.0.1:8501`

Logs and pid files:
- `temperance/data/private/logs/streamlit_remote.log`
- `temperance/data/private/logs/streamlit_remote.pid`

## KeepAlive (macOS launchd)
For auto-restart and auto-start after reboot/login, use launchd services:

```bash
cd temperance
chmod +x scripts/install_keepalive.sh scripts/service_streamlit.sh scripts/service_cloudflared.sh
./scripts/install_keepalive.sh install
```

Useful commands:

```bash
./scripts/install_keepalive.sh status
./scripts/install_keepalive.sh logs
./scripts/install_keepalive.sh restart
./scripts/install_keepalive.sh stop
./scripts/install_keepalive.sh uninstall
```

Defaults:
- Streamlit: `http://127.0.0.1:8504`
- Public host label: `https://app.temperance-rtl.work`
- Named Cloudflare tunnel: `temperance`

Optional overrides (before `install`/`restart`):

```bash
PORT=8504 CLOUDFLARE_TUNNEL=temperance TUNNEL_HOSTNAME=app.temperance-rtl.work ./scripts/install_keepalive.sh restart
```

## Auto-update from Git main (hourly)
If you want this machine to pick up fixes pushed from another computer, enable the auto-update job:

```bash
cd temperance
chmod +x scripts/install_autoupdate.sh scripts/service_autoupdate.sh
./scripts/install_autoupdate.sh install
```

What it does:
- Runs every 3600s (1h) by default.
- Tracks `origin/main`.
- Pulls **only** fast-forward updates.
- Skips pull if working tree is dirty or branch is not `main`.
- Restarts keepalive services after a successful update.

Commands:

```bash
./scripts/install_autoupdate.sh status
./scripts/install_autoupdate.sh logs
./scripts/install_autoupdate.sh run-now
./scripts/install_autoupdate.sh stop
./scripts/install_autoupdate.sh uninstall
```

Optional interval override:

```bash
INTERVAL_SECONDS=1800 ./scripts/install_autoupdate.sh restart
```

## Migrations
Run schema migrations manually (non-destructive, preserves existing rows):

```bash
python migrate.py
```

## Main workflow for your archive
1. Open app.
2. Go to **Data Extract**.
3. In **Comprehensive Garmin Extract**:
- start date: `2025-01-01`
- keep **Incremental only** enabled to fetch only new windows from latest local activity
- activity details are optional (off by default)
- enable sleep + wellness
4. Click **Run comprehensive extract**.

After extraction, use:
- **Dashboard** for TradingView-lite metric plots with overlays and compare mode.
- **Activity Detail** for per-run deep payloads.
- **Recovery Data** for sleep/wellness tables.

## Which sync to use (important)
Use this exactly:

1. **Comprehensive Garmin Extract**: for historical backfill and deep data.
- Pulls activity summaries in range.
- Can pull activity detail endpoints (if enabled).
- Attempts FIT download/cache per activity (`raw/fit/<activity_id>.fit`) when missing.
- Parses FIT per-record series into `activity_records` when FIT is available.
- Can pull sleep + daily wellness (if enabled).

2. **Sync activities (Quick Sync)**: for daily maintenance.
- Supports larger ranges (up to 3650 days) when needed.
- **Quick (activities only)** profile: fast incremental activity summaries.
- **Deep (activities + details + wellness)** profile: pulls activity details, splits, FIT records (when available), sleep, and wellness directly from the sync action.
- For day-to-day upkeep use Quick; for “important data” backfill use Deep.

Recommended pattern:
- Run **Comprehensive** initially (or occasionally) for full archive + FIT/wellness backfill.
- Run **Quick Sync** regularly for daily updates.

## User Inputs (curve-based thresholds)
- Temperance uses two date-based threshold curves for load calculations:
  - `LTHR curve` (date -> bpm), used in `TSS` as `IF_hr = avg_hr / LTHR_at_date`.
  - `LT pace curve` (date -> sec/km), used in `rTSS` as `IF_pace = LT_pace_at_date / avg_pace`.
- You edit both curves in **User Inputs**.
- Max HR is not required for `TSS` / `rTSS`.

### SMA / EMA calculations
- SMA(N): simple rolling mean over N daily points.
- EMA(N): exponential moving average with `alpha = 2 / (N + 1)`.
- Missing days: chart logic can use either:
  - `zero` fill (default), or
  - `ffill` (forward fill then leading zeros)

These are practical v1 proxies, not lab-grade physiology/biomechanics.

## Planned Activities Input Guide
Temperance parses planned activities from free text using:

- One entry format: `[date]:[activity]`
- Multiple entries: separate with newline, `;`, or `,`

Date formats supported:
- `today`, `tomorrow`, `yesterday`
- `T`, `T+N`, `T-N` (relative to today)
- `3Mar26`
- `2026-03-26`
- `26/03/2026`

Activity kinds recognized:
- Running-like: `run`, `running`, `treadmill`
- Non-running: `elliptical`, `bike`, `cycling`

Duration / distance tokens:
- `90min`, `1h`, `45s`
- `10km`, `400m` (distance-only requires running/treadmill + pace)

Intensity tokens (at least one is required per segment):
- `@140bpm`
- `@70%` (IF percent)
- `@4:50/km` (pace; running/treadmill only)
- `@70TSS`

Composition / intervals:
- Combine segments with `+`
  - Example: `30min run @5:00/km + 20min elliptical @135bpm`
- Reps by time:
  - `5x6min @3:40/km`
- Reps by distance (running/treadmill):
  - `10x400m @3:35/km`
  - `6x1km @3:45/km`

### AM/PM planned expiry rule
You can place `AM` or `PM` anywhere as a standalone token (space-separated) in the date or activity text.

Examples:
- `T: 90min elliptical @70TSS AM`
- `T AM: 90min elliptical @70TSS`
- `T-1: 90min AM elliptical @70TSS`
- `T+3: 90min elliptical AM @70TSS`

Behavior:
- `AM` plan expires at `12:00` local time.
- `PM` plan expires at `21:00` local time.
- After expiry, the planned row is automatically treated as done (no manual check needed).
- Without `AM/PM`, the plan expires at local day rollover (end of day).

### TSS semantics for non-running plans
For non-running segments with explicit `@...TSS`:
- The typed TSS is treated as the final delivered TSS target.
- IF is back-solved internally using sport specificity so the displayed final TSS matches the user input target.

## Tests
```bash
pytest -q
```

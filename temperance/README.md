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
- `trimp` (model-derived, stored per activity)

Daily aggregates are stored in `daily_summary`:
- `trimp_total`
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

## Run
From `temperance/`:

```bash
streamlit run app.py
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
- Fast incremental update of activity summaries.
- Good for day-to-day upkeep.
- Does **not** do full deep backfill behavior of comprehensive extract.
- Does **not** perform the comprehensive wellness/detail extraction flow.

Recommended pattern:
- Run **Comprehensive** initially (or occasionally) for full archive + FIT/wellness backfill.
- Run **Quick Sync** regularly for daily updates.

## Load model notes
- Aerobic load:
  - Bannister TRIMP (if resting HR + max HR available)
  - Edwards fallback when needed
- Mechanical load: simple distance + pace (+ optional elevation modifier)
  - v1.5 adds optional cadence-step proxy, stride length, elevation, and running power factors

### SMA / EMA calculations
- SMA(N): simple rolling mean over N daily points.
- EMA(N): exponential moving average with `alpha = 2 / (N + 1)`.
- Missing days: chart logic can use either:
  - `zero` fill (default), or
  - `ffill` (forward fill then leading zeros)

These are practical v1 proxies, not lab-grade physiology/biomechanics.

## Tests
```bash
pytest -q
```

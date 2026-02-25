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
- Running dashboard with your model estimates vs Garmin-reported training-load fields.
- Local SQLite caching and upsert logic.
- File import fallback for runs (`.FIT` / `.TCX`).

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
2. Go to **Sync**.
3. In **Comprehensive Garmin Extract**:
- start date: `2025-01-01`
- keep **Incremental only** enabled to fetch only new windows from latest local activity
- enable activity details
- enable sleep + wellness
4. Click **Run comprehensive extract**.

After extraction, use:
- **Dashboard** to compare your estimated aerobic load vs Garmin training load.
- **Activity Detail** for per-run deep payloads.
- **Recovery Data** for sleep/wellness tables.

## Load model notes
- Aerobic load:
  - Bannister TRIMP (if resting HR + max HR available)
  - Edwards fallback when needed
- Mechanical load: simple distance + pace (+ optional elevation modifier)
  - v1.5 adds optional cadence-step proxy, stride length, elevation, and running power factors

These are practical v1 proxies, not lab-grade physiology/biomechanics.

## Tests
```bash
pytest -q
```

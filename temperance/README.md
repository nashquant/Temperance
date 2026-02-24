# Temperance (MVP)

Local-first app to track running aerobic load and mechanical load from Garmin activities.

## Features (v1)
- Streamlit local web app.
- Garmin Connect sync (`garminconnect`) using credentials from env vars.
- Local SQLite caching + upsert by `activity_id`.
- Fallback import from `.FIT`/`.TCX` files in `temperance/data/imports`.
- Aerobic load:
  - Bannister TRIMP (when resting HR + max HR are available)
  - Edwards TRIMP fallback
- Mechanical load proxy from distance + pace + optional elevation gain.
- Dashboard table, weekly aggregations, and basic plots.
- Activity detail view.

## Project structure
- `app.py`: Streamlit app/UI
- `garmin_client.py`: Garmin API fetch + file import fallback
- `db.py`: SQLite schema and persistence
- `models.py`: load model formulas
- `analytics.py`: metric computation + weekly summaries
- `tests/`: unit tests for load models

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

3. Configure Garmin credentials (optional but recommended).

Environment variables:
- `GARMIN_EMAIL`
- `GARMIN_PASSWORD`

You can set them in shell:

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

Or create a local `.env` file in `temperance/`:

```env
GARMIN_EMAIL=you@example.com
GARMIN_PASSWORD=your_password
```

## Run
From `temperance/` folder:

```bash
streamlit run app.py
```

## Sync behavior
- Default sync pulls last 90 days.
- App uses latest stored activity to reduce unnecessary re-fetch (starts roughly from latest-2 days).
- Activities are upserted by `activity_id` in SQLite.

## File import fallback
If Garmin login/API fails:
1. Place exported `.FIT` or `.TCX` files in `temperance/data/imports/`.
2. In app Sync section, choose `File Import` or `Both`.
3. Click `Sync activities`.

## Troubleshooting Garmin login
- Verify `GARMIN_EMAIL` and `GARMIN_PASSWORD` values.
- Try logging into Garmin Connect in a browser to confirm credentials and no account lock.
- If Garmin requires extra verification or API behavior changes, use file import fallback.

## Load model notes
- **Bannister TRIMP** (HR reserve) is used when resting HR and max HR are set.
- **Edwards TRIMP fallback** is used when resting HR is missing; this v1 approximation uses average HR zone for the full activity.
- **Mechanical Load Score** is a pragmatic proxy:
  - distance is primary,
  - faster pace increases score,
  - elevation gain adds a modest multiplier.

These are v1 approximations and not direct biomechanical force measurements.

## Tests
Run unit tests from `temperance/`:

```bash
pytest -q
```

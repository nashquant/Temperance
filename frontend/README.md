# Temperance Frontend

The frontend is your daily interface to the training archive. Open it to see the dashboard, check recovery and wellness, review what's planned, drill into activity detail, and run a Garmin sync.

## Open the app

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://127.0.0.1:5173`. The backend must be running at `http://127.0.0.1:8000` for data to load.

## What you can do

- **Dashboard** — see this week's completed and planned activities side by side, with load, pace, and recovery signals per day. Tap any activity for splits and detail.
- **Athlete Progression** — fitness, fatigue, form, and weekly baseline over time.
- **Weekly Outlook** — structured week view with load and spacing context.
- **Plan Activities** — add or edit planned workouts in compact workout text.
- **Wellness** — daily sleep, HRV, resting HR, and body battery.
- **Data Extract** — connect Garmin, run a comprehensive or incremental sync, and inspect sync state.
- **Settings** — configure owner scope, thresholds, and display preferences.

## Build for production

```bash
npm run build    # type-checks and bundles
npm run preview  # serves the bundle locally
```

## Notes for developers

API calls go to `/api/*`, proxied to the backend during local dev via `vite.config.ts`. Auth is cookie-based. Session context lives in `src/features/auth/`.

Workout strings displayed or submitted by the frontend are the same normalized strings the backend parses — don't mutate them for display purposes without checking `temperance/activity_parsing.py` first.

Contract touchpoints:
- `src/api/config.ts` — endpoint paths
- `src/features/auth/services/auth-api.ts` — login and `me` response types
- `src/features/weekly-outlook/types/weekly-outlook.ts` — raw payload shape
- `src/features/weekly-outlook/utils/weekly-outlook-mapper.ts` — backend-specific mapping

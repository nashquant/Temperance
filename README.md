# Temperance

Temperance is a local-first training and recovery app for endurance athletes. It turns a Garmin-backed SQLite archive into a practical answer to four daily questions:

- What did I actually do?
- How recovered do I look?
- What is planned next?
- Does this week still make sense?

The app is built for an athlete who wants coaching-quality context without giving up local control of the data. Garmin provides the activity and wellness archive, SQLite keeps it local, the backend computes training signals and planning state, and the frontend gives you the day-to-day interface.

## Who This Is For

Use Temperance when you want more than a training log but less than a black-box coach. It is useful when you are balancing running with support modalities, watching durability and injury-risk pressure, or trying to keep a weekly plan coherent after real life changes the day.

Temperance is not a social app, marketplace, or cloud coaching platform. The default workflow is local: your activity archive, wellness data, owner-scoped databases, generated plans, and private guideline overlays stay on your machine unless you deliberately move them elsewhere.

## First Run Checklist

1. Start the backend.
2. Start the frontend.
3. Open `http://127.0.0.1:5173`.
4. Log in and choose the owner scope you want to inspect.
5. Run Data Extract if you need fresh Garmin activity or wellness data.
6. Review Dashboard, Wellness, Athlete Progression, and Weekly Outlook before editing the plan.
7. Add or adjust planned workouts in Plan Activities or Week Planner.
8. Re-run Data Extract after new Garmin activity is available.

If the app opens but looks empty, the usual cause is that no Garmin data has been synced for the selected owner. If activities are present but sleep, HRV, or body battery are blank, run a comprehensive Data Extract; the lightweight background sync focuses on activity updates.

## What You Can Do

- Review recent training, recovery, wellness, and weekly outlook in one place.
- Sync Garmin activities and wellness data into a local archive.
- Plan workouts with compact text that the app can parse, normalize, edit, and re-use.
- Compare planned work with completed activity history.
- Track fitness, fatigue, form, durability, pounding, overreach, injury-risk burden, and weekly baseline.
- Use doctrine-aware MCP coaching tools to inspect the active build, judge recent history, plan tomorrow, and critique proposed changes.
- Keep multiple owner-scoped local databases while still running a single local app.

## Main Screens

**Dashboard**

Use this first. It shows the current week with completed and planned training side by side, plus the day-level signals that explain whether a workout is landing as intended.

**Athlete Progression**

Use this to understand trend, not just today's score. It shows fitness, fatigue, form, weekly baseline, durability, pounding, overreach burden, and injury-risk burden over time.

**Weekly Outlook**

Use this when the question is structure. It helps spot a week that has too much load, poor spacing, or a mismatch between intended training and actual training.

**Plan Activities and Week Planner**

Use these to write or edit future workouts. Workout text is compact on purpose, because the same text is displayed to you, parsed by the backend, compared with actuals, and reused by planning tools.

**Wellness**

Use this to check sleep, HRV, resting HR, body battery, and other recovery context imported from Garmin.

**Data Extract**

Use this to connect Garmin, run comprehensive or incremental syncs, and see which connection mode is active.

**Settings**

Use this to adjust owner scope, thresholds, and display preferences.

## The Mental Model

Temperance treats training as a control problem, not just a calendar.

The first question is what the current build is trying to protect and progress. The app separates total load from the load that is most specific to the event or current risk. For a running-limited block, total aerobic work may be high while run-specific mechanical load still needs careful progression.

The second question is whether the structure is absorbable. A week can hit a load target and still be a bad week if hard work is clustered too tightly, if moderate work drifts into hidden hard work, or if support modalities quietly become another stressor instead of creating space.

The third question is what to do next. Planning tools combine weekly anchors, recent actual training, recovery context, Garmin data, and doctrine resources so tomorrow's recommendation is judged against the week and build, not in isolation.

## Core Concepts

**Local-first archive**

Temperance stores the canonical data in SQLite under `temperance/data/private/`. The default database is `temperance/data/private/temperance.db`, and owner-scoped databases live under `temperance/data/private/users/<owner>.db`. Private data, logs, exports, and imports are gitignored by default.

**Garmin sync**

Garmin is the main source for completed activities and wellness. A comprehensive sync can backfill activities, activity details, FIT records, sleep, and wellness. The lightweight backend auto-sync is activity-only, so blank current-day recovery data usually means a comprehensive sync has not populated the wellness endpoints yet.

**Planned vs actual training**

Planned activities are compact workout strings. Actual activities come from Garmin or custom entries. Temperance keeps the planned text parseable so the same workout can be displayed, edited, estimated, compared with history, and re-used by generated suggestions.

**Load: TSS and rTSS**

`TSS` is the broad training-load signal. `rTSS` is the run-specific or specificity-adjusted load signal used when the app needs to reason about mechanical or event-specific burden. Support modalities can preserve aerobic load while carrying less of the primary specific cost.

**Weekly baseline**

The weekly baseline is the app's modeled expectation for sustainable weekly load. It starts from LT-derived weekly capacity, blends in trailing 21/63/365-day load history, and is exported as Monday-labeled weekly points. MCP `get_fitness_form.weekly_baseline` is expected to match the Athlete Progression `Base` line as closely as rounding allows.

**Fitness, fatigue, and form**

The dashboard and MCP expose CTL/ATL/TSB-style signals. In current terms, fitness is a 42-day TSS EMA, fatigue is a 7-day TSS EMA, and form is fitness minus fatigue. These are planning context, not commands.

**Durability, pounding, overreach, and injury risk**

Durability tracks longer-term running robustness with a 100-day rTSS EMA. Pounding tracks acute running mechanical load with a 7-day rTSS EMA. Overreach and injury risk are accumulated burden signals from excess load above the daily target: overreach uses broad TSS pressure, while injury risk uses rTSS pressure.

**Support modalities and specificity**

A support modality is work that supports load, spacing, or fitness without carrying the same specific cost as the primary load. Elliptical and cycling may help preserve aerobic load, but they are not always one-for-one substitutes for running durability.

**Doctrine, active build, and workout templates**

Temperance planning is doctrine-aware. The invariant doctrine defines concepts such as `total_load`, `primary_specific_load`, `specificity_ratio`, `support_modality`, local spacing, rolling density, and progression alerts. The active build maps those ideas to the current athlete state and event context. Workout templates provide reusable session families, such as recovery, easy, support, steady aerobic, threshold, long run, specific endurance, VO2, hills, and x-train support.

See the guideline docs for the deeper model:

- [Training control system doctrine](temperance/guidelines/temperance-guidelines/training-control-system-doctrine.md)
- [Durability-first threshold/support philosophy](temperance/guidelines/temperance-guidelines/training-philosophy-durability-threshold-support.md)
- [Workout quick reference](temperance/guidelines/temperance-workouts/quick-reference.md)

## A Normal Day

1. Sync Garmin if new activity or wellness data is missing.
2. Check Dashboard for the week as executed so far.
3. Check Wellness if recovery or sleep may change the plan.
4. Check Weekly Outlook before moving hard sessions or adding load.
5. Edit planned activities only after looking at actuals and recovery.
6. Use MCP coaching tools when you want a doctrine-aware brief, next-day plan, history judgment, or plan critique.

Main frontend surfaces are documented in [frontend/README.md](frontend/README.md).

## Run It Locally

### Backend

```bash
cd /Users/matheus/Temperance/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Backend URL: `http://127.0.0.1:8000`

Equivalent uvicorn form:

```bash
cd /Users/matheus/Temperance
python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend

```bash
cd /Users/matheus/Temperance/frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

The frontend proxies `/api/*` and `/health` to the backend during local development. The public app is served at `https://app.temperance-rtl.work`, and the API is mounted at `/api`.

## Garmin Data And Sync

For local admin sync with environment credentials:

```bash
export GARMIN_EMAIL="you@example.com"
export GARMIN_PASSWORD="your_password"
```

You can also keep these in `temperance/.env` for local use.

Garmin OAuth is optional, but required if non-admin users should pair their own Garmin accounts instead of relying on memory-only session credentials.

Minimum OAuth connection config:

```bash
export GARMIN_OAUTH_CLIENT_ID="your_client_id"
export GARMIN_OAUTH_CLIENT_SECRET="your_client_secret"
export GARMIN_OAUTH_REDIRECT_URI="http://127.0.0.1:8000/api/v1/garmin/oauth/callback"
export GARMIN_OAUTH_AUTHORIZE_URL="https://<garmin-authorize-endpoint>"
export GARMIN_OAUTH_TOKEN_URL="https://<garmin-token-endpoint>"
export TEMPERANCE_OAUTH_TOKEN_ENCRYPTION_KEY="replace_with_a_long_random_secret"
```

Optional, but needed if OAuth-connected users should run Garmin Data Extract through the app:

```bash
export GARMIN_OAUTH_USERINFO_URL="https://<garmin-userinfo-endpoint>"
export GARMIN_OAUTH_ACTIVITIES_URL="https://<garmin-activities-endpoint>"
export GARMIN_OAUTH_WELLNESS_URL="https://<garmin-wellness-endpoint>"
export GARMIN_OAUTH_SCOPES="activities wellness profile"
```

Data Extract chooses the active sync mode from the logged-in user and available connection:

- Admin on the admin scope can use `GARMIN_EMAIL` and `GARMIN_PASSWORD`.
- Admin viewing another owner can provide that owner's Garmin credentials in the UI; they stay in backend memory only.
- Non-admin users can connect Garmin through OAuth when OAuth endpoints are configured.
- Non-admin users can fall back to session credentials when OAuth is unavailable.
- Without a Garmin connection, the app still works with existing synced data, custom activities, planning, and generated activities.

`Run extract` can fetch activity rows, activity details, sleep, and wellness when the active sync source supports them. Incremental mode only refetches missing days plus the current freshness window. The Data Extract page surfaces the current connection mode as `oauth`, `session`, `env`, or `missing`.

More shared package and sync notes live in [temperance/README.md](temperance/README.md).

## Planning Text

Temperance workout text is intentionally compact and reparseable. Treat `activity_text` and `workout_text` as canonical display-plus-roundtrip strings, not free-form prose.

Examples:

```text
today: Run 45min @4:40/km
T+1: Elliptical 70min @138bpm
2026-03-26: Run 3x8' @3:45/km / 2' @4:40/km
```

Useful rules:

- Dated entries use `[date]:[activity]`.
- Relative dates include `today`, `tomorrow`, `yesterday`, `T`, `T+1`, and `T-1`.
- Absolute dates include `2026-03-26`, `26/03/2026`, and `26Mar26`.
- Bulk entry separators can be newline, comma, or semicolon.
- Duration tokens include `45min`, `45'`, `1h`, `1h30m`, `20s`, and `20"`.
- Distance tokens include `42.2km`, `400m`, `6x1km`, and `8x400m`.
- Intensity tokens include pace such as `@4:40/km`, named paces such as `@mp`, heart rate such as `@138bpm`, IF such as `@78%`, and TSS such as `@80tss`.
- Interval recovery can use slash or parentheses, such as `3x8' @3:45 / 2' @4:40`.
- Elliptical aliases include `elliptical`, `xtrain`, `x-train`, `cross train`, and `cross-train`.

Generated activity suggestions emit normalized strings such as `Run 40min @4:40/km` or `Elliptical 70min @138bpm` so they can be parsed again later. Full parsing and generation contracts live in [temperance/README.md](temperance/README.md).

## MCP And Coaching Tools

Temperance exposes one canonical stdio MCP server at `backend/app/mcp_server.py`.

Run it from the repo root:

```bash
cd /Users/matheus/Temperance
python3 -m backend.app.mcp_server --stdio
```

The MCP server is a thin interface over backend logic, not a separate analytics engine. It exposes:

- resources for doctrine read order, core guideline bundles, active build context, workout overview, and workout catalog
- planning tools such as `plan_next_day`, `preview_cycle`, and `explain_planning_decision`
- analytics/status tools such as `get_coaching_brief`, `get_today_status`, `get_fitness_form`, `get_week_outlook`, and `get_activity_detail`
- history tools such as `judge_training_history` and `explain_history_judgment`
- load analysis tools such as `estimate_workout_tss`, `simulate_plan_week`, `critique_day_plan`, `estimate_xtrain_tss`, and `search_workouts`
- write/admin tools for planned activities, custom activities, sync, settings, and invalid activity marking

For the full tool/resource list, request examples, and baseline contract details, see [backend/README.md](backend/README.md).

Minimal MCP smoke example:

```bash
cd /Users/matheus/Temperance
python3 -m backend.app.mcp_server --stdio <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"manual-smoke","version":"0.0.1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"resources/list"}
{"jsonrpc":"2.0","id":3,"method":"resources/read","params":{"uri":"temperance://guidelines/read-order"}}
{"jsonrpc":"2.0","id":4,"method":"tools/list"}
EOF
```

## Project Structure

```text
Temperance/
|-- backend/         FastAPI app and MCP server
|-- frontend/        React + Vite app
`-- temperance/      Shared Python domain logic, data, migrations, sync, scripts
```

Key modules:

- `backend/app/main.py`: REST API for auth, dashboard, wellness, planning, analytics, and Garmin sync.
- `backend/app/mcp_server.py`: MCP resources and tools over the backend/domain model.
- `temperance/db.py`: SQLite schema, owner-scoped storage, CRUD, and migrations.
- `temperance/analytics.py`: training metrics, daily summaries, CTL/ATL/TSB-style helpers.
- `temperance/activity_parsing.py`: workout string parsing and normalization.
- `temperance/garmin_client.py`: Garmin API sync, FIT parsing, wellness extraction.
- `temperance/planning/`: recommendation state, policy, and session selection.
- `frontend/src/features/`: feature modules for auth, dashboard, athlete progression, weekly outlook, planning, Data Extract, wellness, and settings.

## Developer Reference

Run migrations:

```bash
cd /Users/matheus/Temperance
python -m temperance.migrate
```

Restart keepalive services after backend or frontend path changes:

```bash
cd /Users/matheus/Temperance
./temperance/scripts/install_keepalive.sh restart
```

Related docs:

- [Backend and MCP guide](backend/README.md)
- [Frontend guide](frontend/README.md)
- [Shared Python package guide](temperance/README.md)

## Tests

Python tests:

```bash
cd /Users/matheus/Temperance
pytest temperance/tests -q
```

Backend MCP tests:

```bash
cd /Users/matheus/Temperance
backend/.venv/bin/python -m unittest backend.tests.test_mcp_server temperance.tests.test_mcp_server -v
```

Frontend build check:

```bash
cd /Users/matheus/Temperance/frontend
npm run build
```

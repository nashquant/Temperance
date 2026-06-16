# Temperance

Temperance is a local-first training and recovery app for endurance athletes. It turns a Garmin-backed SQLite archive into a practical answer to four daily questions:

- What did I actually do?
- How recovered do I look?
- What is planned next?
- Does this week still make sense?

It is built for an athlete who wants coaching-quality context without handing the training archive to a black-box cloud coach. Garmin provides activity and wellness data, SQLite keeps the archive local, the backend computes training signals and planning state, and the frontend gives you the day-to-day interface.

## Why It Exists

Most training tools are either passive logs or full coaching platforms. Temperance sits between those poles: it keeps the athlete in control while making the training state easier to reason about.

The app is especially useful when training is not just a list of runs. It understands completed work, planned work, wellness data, support modalities, durability pressure, and weekly structure as parts of the same system. The goal is not to produce a magic score. The goal is to make the next decision less blind.

Temperance is local-first by default. Activity archives, owner-scoped databases, generated plans, private overlays, logs, and imports stay on your machine unless you deliberately move them elsewhere.

## The Model

Temperance treats training as a control problem, not just a calendar.

The first control question is load: how much work is the athlete carrying, and how does that compare with the modeled baseline for sustainable training? The second is specificity: which part of that load is specific to the event or current limitation? A week can contain plenty of aerobic work while still requiring caution around run-specific mechanical stress.

The third question is absorbability. A week can hit the right total load and still be poorly structured if hard work is clustered, moderate work quietly becomes hidden intensity, or support modalities add stress instead of creating space.

The fourth question is action. Planning tools judge tomorrow against the active week, recent actuals, recovery context, and doctrine resources rather than treating a workout as an isolated entry.

## What You Can Do

- Review recent training, recovery, wellness, and weekly outlook in one place.
- Sync Garmin activities and wellness data into a local archive.
- Compare planned work with completed activity history.
- Edit future training with compact workout strings that remain parseable by the app.
- Track TSS, rTSS, weekly baseline, performance trend, readiness, tissue-load risk, durability, and wellness context.
- Use optional MCP coaching tools to inspect the active build, judge recent history, plan tomorrow, and critique proposed changes.
- Keep multiple owner-scoped local databases while running one local app.

## Core Concepts

**Local-first archive**

The canonical data lives in SQLite under `temperance/data/private/`. The base database is `temperance/data/private/temperance.db`; owner-scoped databases live under `temperance/data/private/users/<owner>.db`. Private data, logs, exports, and imports are gitignored by default.

**Garmin sync**

Garmin is the main source for completed activities and wellness. A comprehensive sync can backfill activities, activity details, FIT records, sleep, and wellness. The app can still work from existing local data when no Garmin connection is available.

**Planned vs actual training**

Actual activities come from Garmin or custom entries. Planned activities are compact workout strings such as `today: Run 45min @4:40/km` or `T+1: Elliptical 70min @138bpm`. The text is intentionally reparseable so it can be displayed, edited, estimated, compared with actuals, and reused by generated suggestions.

**Load and specificity**

`TSS` is the broad training-load signal. `rTSS` is the run-specific or specificity-adjusted load signal used when reasoning about mechanical or event-specific burden. Support modalities can preserve aerobic work without being one-for-one substitutes for running durability.

**Weekly baseline**

The weekly baseline is Temperance's modeled expectation for sustainable weekly load. It starts from LT-derived weekly capacity, blends trailing 21/63/365-day load history, and is exposed as Monday-labeled weekly points. The dashboard Athlete Progression `Base` line and MCP `get_fitness_form.weekly_baseline` are expected to agree to within rounding.

**Progression signals**

Athlete Progression separates related but different questions. `performance_trend` is evidence of run-performance movement. `readiness` is short-horizon strain and recovery context. `tissue_load_risk` is running-specific mechanical-risk pressure. `durability` estimates how repeatable running-specific load is becoming.

**Doctrine-aware planning**

Temperance planning uses doctrine resources, active-build context, workout templates, recent history, and recovery context. The MCP server exposes those same concepts to agentic coaching workflows without becoming a separate analytics engine.

## Main Screens

- **Dashboard**: current week, completed and planned training, and day-level signals.
- **Athlete Progression**: load, baseline, performance trend, readiness, tissue-load risk, durability, and wellness context over time.
- **Weekly Outlook**: weekly structure, load, spacing, and planned-vs-actual context.
- **Plan Activities and Week Planner**: compact workout editing for future training.
- **Wellness**: sleep, HRV, resting HR, body battery, and other Garmin recovery context.
- **Data Extract**: Garmin connection state and comprehensive or incremental sync controls.
- **Settings**: owner scope, thresholds, and display preferences.

## Run Locally

Start the backend from the repo root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
./backend/run.sh
```

Backend URL: `http://127.0.0.1:8000`

Start the frontend in a second shell:

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://127.0.0.1:5173`

If the app opens but looks empty, the usual cause is that no Garmin data has been synced for the selected owner. If activities are present but sleep, HRV, or body battery are blank, run a comprehensive Data Extract.

## Project Map

```text
Temperance/
|-- backend/     FastAPI REST API and MCP server
|-- frontend/    React + TypeScript SPA
`-- temperance/  Shared SQLite, Garmin sync, analytics, parsing, and planning logic
```

Layer contracts:

- Frontend API calls use `/api` and are documented in [frontend/README.md](frontend/README.md).
- Backend auth, Garmin sync, analytics, planning, settings, and MCP surfaces are documented in [backend/README.md](backend/README.md).
- Shared domain behavior belongs in `temperance/` when more than one surface uses it. Data paths, sync notes, parser contracts, migrations, and tests are documented in [temperance/README.md](temperance/README.md).

## More Detail

- [Backend and MCP guide](backend/README.md)
- [Frontend guide](frontend/README.md)
- [Shared Python package guide](temperance/README.md)
- [Architecture findings](docs/architecture-findings.md)
- [Training control system doctrine](temperance/guidelines/temperance-guidelines/training-control-system-doctrine.md)
- [Durability-first threshold/support philosophy](temperance/guidelines/temperance-guidelines/training-philosophy-durability-threshold-support.md)
- [Workout quick reference](temperance/guidelines/temperance-workouts/quick-reference.md)

## Validation

Backend or shared-library changes should pass:

```bash
.venv/bin/pytest temperance/tests backend/tests -q
```

Frontend TypeScript, routing, API, or rendered UI changes should pass from `frontend/`:

```bash
npm run build
```

Documentation-only changes do not require app tests.

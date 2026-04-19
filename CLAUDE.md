# CLAUDE.md

> Working style, editing conventions, and testing guidelines: [CORE.md](./CORE.md)

## Commands

**Backend:** venv at `.venv/`; run from repo root — never `cd backend` or activate venv.
```bash
./backend/run.sh                                          # dev server (:8000)
.venv/bin/pytest temperance/tests -q                      # all tests
.venv/bin/python -m unittest backend.tests.test_mcp_server -v
./temperance/scripts/install_keepalive.sh restart         # after backend changes
python -m temperance.migrate                              # migrations
```

**Frontend:**
```bash
cd frontend
npm run dev    # http://127.0.0.1:5173, proxies /api/* to :8000
npm run build  # production + tsc typecheck
```

## Architecture

Local-first endurance training app; Garmin-synced SQLite backend.

| Layer | Path | Notes |
|-------|------|-------|
| Frontend | `frontend/src/features/` | React 18 + TS; modules: auth, dashboard, athlete-progression, weekly-outlook, plan-activities, custom-activities, week-planner, wellness, settings |
| Backend | `backend/app/main.py` | FastAPI; 30+ endpoints. `mcp_server.py` MCP tools must stay in sync with dashboard analytics |
| Shared lib | `temperance/` | `db.py` SQLite CRUD, `analytics.py` CTL/ATL/TSB, `activity_parsing.py`, `garmin_client.py`, `planning/`, `guidelines/` |

DBs: `temperance/data/private/temperance.db`; owner-scoped: `users/<owner>.db`. Migrations: `temperance/migrate.py`.  
API base: `/api`. Session token: localStorage key `temperance.session`.

## Invariants

**Workout strings** are canonical and reparseable — not prose. Round-trip fidelity required on any parsing/generation change.  
Format: `today: 45min @4:40/km` · `T+1: 6x1km @10k` · `2026-03-26: 1h30m @138bpm`

**Weekly baseline:** MCP `get_fitness_form.weekly_baseline` must match "Athlete Progression" dashboard. Path: LT-derived capacity → 21/63/365-day load blend → modeled baseline → Monday rollup. Divergence is a bug.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, save state, save my work → invoke context-save
- Resume, where was I, pick up where I left off → invoke context-restore
- Code quality, health check → invoke health

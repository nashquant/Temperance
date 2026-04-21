# CORE.md

Canonical project contract for AI agents working in Temperance.

## Precedence

Follow system and runtime instructions first. Then follow this file as the
stable Temperance source of truth. Runtime bridge files such as `AGENTS.md` and
`CLAUDE.md` may add tool-specific operational notes, but should not duplicate or
override this contract unless a runtime constraint requires it.

## Product Contract

Temperance is a local-first training and recovery app for endurance athletes. It
is backed by a Garmin-synced SQLite archive and should continue to work from
local project state without assuming hosted services.

Base database: `temperance/data/private/temperance.db`.

Owner-scoped databases: `temperance/data/private/users/<owner>.db`.

Schema migrations live in `temperance/migrate.py`.

## Architecture Boundaries

| Layer | Location | Contract |
|-------|----------|----------|
| Frontend | `frontend/` | React 18 + TypeScript SPA. Feature modules live under `frontend/src/features/`. API calls use the `/api` base path. Session token storage key is `temperance.session`. |
| Backend API | `backend/app/` | FastAPI REST surface for auth, Garmin sync, wellness, planning, analytics, and settings. |
| MCP server | `backend/app/mcp_server.py` | Model Context Protocol interface for agent-facing training tools. Its analytics must stay aligned with dashboard analytics. |
| Shared library | `temperance/` | Domain logic: SQLite persistence, analytics, Garmin sync, activity parsing, planning, guidelines, and reusable training calculations. |

Keep domain behavior in the shared library when it is used by more than one
surface. Avoid copying analytics, parsing, or planning rules independently into
frontend, backend endpoint, and MCP code paths.

## Hard Invariants

### Workout strings

Workout strings are canonical and reparseable, not free-form prose.

Accepted forms include date prefixes, durations, distances, pace, and intensity:

```text
today: 45min @4:40/km
T+1: 6x1km @10k
2026-03-26: 1h30m @138bpm
```

All generated workout text must be emitted in normalized form so it can be
parsed again. Any change to parsing or generation must preserve round-trip
fidelity.

### Weekly baseline

MCP `get_fitness_form.weekly_baseline` must match the dashboard "Athlete
Progression" baseline. The expected path is:

```text
LT-derived weekly capacity -> 21/63/365-day load blend -> modeled baseline -> Monday weekly rollup
```

Divergence between MCP baseline values and dashboard baseline values is a bug.

## Change Discipline

- Prefer small, reviewable diffs that respect existing module boundaries.
- For non-trivial work, state the goal, constraints, and intended approach
  before editing.
- Ask focused questions before risky changes when the answer cannot be inferred
  from local context.
- Preserve existing style, imports, error handling, and data ownership patterns.
- Do not silently rename, move, or create files that change project structure.

## Validation Expectations

- Parser, planning, analytics, MCP, or API behavior changes should get focused
  regression coverage when practical.
- Frontend TypeScript, routing, API, or rendered UI changes should be checked
  with `npm run build` from `frontend/`.
- Backend or shared-library changes should start with the narrowest relevant
  Python tests, then broaden to `.venv/bin/pytest temperance/tests backend/tests -q`
  when risk warrants it.
- Documentation-only changes do not require app tests.

## Operations

Run backend and test commands from the repository root. Do not `cd backend` or
activate the virtualenv manually.

Backend and Python commands:

```bash
./backend/run.sh
.venv/bin/python -m backend.app.mcp_server --stdio
.venv/bin/pytest temperance/tests backend/tests -q
.venv/bin/pytest temperance/tests/test_activity_parsing.py -v
.venv/bin/python -m unittest backend.tests.test_mcp_server -v
python -m temperance.migrate
./temperance/scripts/install_keepalive.sh restart
```

Frontend commands run from `frontend/`:

```bash
npm install
npm run dev      # http://127.0.0.1:5173, proxies /api/* to :8000
npm run build    # production build plus TypeScript check
npm run preview
```

After backend changes that need a process restart, use the keepalive restart
command above.

Use the `/browse` skill from the gstack install for web browsing.

# AGENTS.md

Agent contract for Temperance. System and runtime instructions still take
precedence over this repository file.

## Product Contract

Temperance is a local-first training and recovery app for endurance athletes.
It is backed by Garmin-synced SQLite archives and must continue to work from
local project state without assuming hosted services.

Base database: `temperance/data/private/temperance.db`.

Owner-scoped databases: `temperance/data/private/users/<owner>.db`.

Schema migrations live in `temperance/migrate.py`.

## Architecture Boundaries

| Layer | Location | Contract |
|-------|----------|----------|
| Frontend | `frontend/` | React 18 + TypeScript SPA. API calls use `/api`. |
| Backend API | `backend/app/` | FastAPI REST surface for auth, Garmin sync, wellness, planning, analytics, and settings. |
| MCP server | `backend/app/mcp_server.py` | Agent-facing training tools. Analytics must stay aligned with dashboard analytics. |
| Shared library | `temperance/` | SQLite persistence, analytics, Garmin sync, parsing, planning, guidelines, and reusable training calculations. |

Keep reusable domain behavior in `temperance/` when more than one surface uses
it. Avoid copying analytics, parsing, or planning rules independently into the
frontend, backend endpoints, and MCP code paths.

## Hard Invariants

### Workout Strings

Workout strings are canonical and reparseable, not free-form prose.

Accepted examples:

```text
today: 45min @4:40/km
T+1: 6x1km @10k
2026-03-26: 1h30m @138bpm
```

Generated workout text must be normalized enough to parse again. Any parser or
generator change must preserve round-trip fidelity.

### Weekly Baseline

MCP `get_fitness_form.weekly_baseline` must match the dashboard Athlete
Progression `Base` line as closely as rounding allows.

Expected path:

```text
LT-derived weekly capacity -> 21/63/365-day load blend -> modeled baseline -> Monday weekly rollup
```

Divergence is a bug.

## Validation

Backend or shared-library changes should start with the narrowest relevant
tests, then broaden to:

```bash
.venv/bin/pytest temperance/tests backend/tests -q
```

Frontend TypeScript, routing, API, or rendered UI changes should be checked from
`frontend/` with:

```bash
npm run build
```

Documentation-only changes do not require app tests.

## Canonical Docs

- Product and local run docs: `README.md`
- Backend and MCP docs: `backend/README.md`
- Frontend docs: `frontend/README.md`
- Refactor findings and next slices: `docs/architecture-findings.md`

# CLAUDE.md

Guidance for AI assistants working in this repository.

## Project Overview

Temperance is a local-first endurance training analytics and planning application. It syncs activity and wellness data from Garmin, calculates training metrics, and generates structured weekly training plans. It also exposes an MCP (Model Context Protocol) server for AI-assisted coaching.

**Key characteristics:**
- Local SQLite database per user (no cloud backend required)
- Three-layer architecture: shared Python domain library (`temperance/`), FastAPI backend (`backend/`), React frontend (`frontend/`)
- Garmin integration via either session-based auth (email/password) or OAuth 2.0
- MCP server for LLM tool access to training data and planning

---

## Repository Structure

```
Temperance/
├── backend/              # FastAPI REST API server
│   ├── app/
│   │   ├── main.py       # All API endpoints (~350KB, intentionally monolithic)
│   │   ├── mcp_server.py # MCP server (stdio transport, JSON-RPC 2.0)
│   │   ├── planning_parsing.py  # Planned-activity text parser
│   │   ├── garmin_oauth.py      # OAuth token management
│   │   └── date_parsing.py      # Utility date parsing
│   ├── tests/
│   ├── requirements.txt
│   └── run.sh            # Launch script (handles venv detection)
├── frontend/             # React + Vite + TypeScript SPA
│   ├── src/
│   │   ├── features/     # Feature modules (12 features, see below)
│   │   ├── components/   # Shared UI components
│   │   ├── api/          # HTTP client and endpoint wrappers
│   │   ├── app/          # Router, providers, app shell
│   │   └── lib/          # Utilities
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── package.json
├── temperance/           # Shared Python domain logic (importable package)
│   ├── db.py             # SQLite schema, migrations, all CRUD queries
│   ├── garmin_client.py  # Garmin API wrapper and FIT file parser
│   ├── analytics.py      # TSS, TRIMP, acute/chronic load, training metrics
│   ├── activity_parsing.py  # Compact workout text parser/normalizer
│   ├── models.py         # Shared dataclasses
│   ├── auth.py           # Authentication helpers
│   ├── tss.py            # Training Stress Score calculations
│   ├── migrate.py        # Schema migration runner
│   ├── config.py         # Environment config loader
│   ├── planning/         # Training plan generation subsystem
│   │   ├── policy.py           # Planning constraints and rules
│   │   ├── session_selector.py # Selects next workout from library
│   │   ├── state_builder.py    # Builds athlete state from history
│   │   ├── methodologies.py    # Planning algorithm registry
│   │   ├── day_type_sampler.py # Day-type distribution sampling
│   │   └── stress.py           # Stress calculations
│   ├── guidelines/       # Training doctrine markdown docs + workout templates
│   │   ├── temperance-guidelines/  # 17 markdown files (philosophy, phases, events)
│   │   └── temperance-workouts/    # 20 workout categories, 50+ templates
│   ├── scripts/          # Operations scripts (keepalive, autoupdate)
│   └── tests/            # 24 pytest test files
├── AGENTS.md             # Working style guidelines
├── CLAUDE.md             # This file
└── README.md             # Project overview and architecture
```

---

## Development Workflow

### Backend

```bash
# First-time setup
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start dev server (auto-reload, port 8000)
./run.sh
# OR directly:
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

`run.sh` auto-detects `backend/.venv` or root `.venv` and falls back to system Python. Override via env vars: `PORT`, `HOST`, `BACKEND_PYTHON_BIN`.

### Frontend

```bash
cd frontend
npm install
npm run dev      # Vite dev server on http://127.0.0.1:5173
npm run build    # TypeScript type-check + production build
npm run preview  # Serve production build locally
```

Vite proxies `/api/*` and `/health` to `http://127.0.0.1:8000` by default. Override with `VITE_API_TARGET`.

### Database Migrations

```bash
python -m temperance.migrate
```

### MCP Server

```bash
# stdio transport (for Claude Desktop / MCP client config)
python3 -m backend.app.mcp_server --stdio
```

---

## Running Tests

```bash
# All temperance unit tests
pytest temperance/tests -q

# Backend MCP tests
pytest backend/tests -q

# Specific test file
pytest temperance/tests/test_activity_parsing.py -v

# All tests
pytest temperance/tests backend/tests -q
```

Tests use `conftest.py` fixtures that mock FastAPI, Pydantic, and dotenv — the full backend does not need to be running. Test data is self-contained.

---

## Environment Variables

Place overrides in `temperance/.env` (gitignored) or export in your shell.

| Variable | Purpose | Required |
|---|---|---|
| `GARMIN_EMAIL` | Garmin session auth email | One of the two auth modes |
| `GARMIN_PASSWORD` | Garmin session auth password | One of the two auth modes |
| `GARMIN_OAUTH_CLIENT_ID` | OAuth app client ID | For OAuth mode |
| `GARMIN_OAUTH_CLIENT_SECRET` | OAuth app secret | For OAuth mode |
| `GARMIN_OAUTH_REDIRECT_URI` | OAuth callback URL | For OAuth mode |
| `GARMIN_OAUTH_AUTHORIZE_URL` | Garmin authorize endpoint | For OAuth mode |
| `GARMIN_OAUTH_TOKEN_URL` | Garmin token endpoint | For OAuth mode |
| `TEMPERANCE_OAUTH_TOKEN_ENCRYPTION_KEY` | Token encryption secret | For OAuth mode |
| `VITE_API_TARGET` | Override backend URL for Vite dev proxy | Optional |
| `TEMPERANCE_DB_MAX_BYTES` | SQLite size limit (default: 1GB) | Optional |
| `TEMPERANCE_DB_EXECUTEMANY_CHUNK_SIZE` | Batch insert size (default: 10) | Optional |

Data directories are auto-created at first run (all gitignored):
- `temperance/data/private/temperance.db` — base SQLite database
- `temperance/data/private/users/<owner>.db` — owner-scoped databases
- `temperance/data/private/logs/` — debug logs
- `temperance/data/imports/` — import staging

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend language | Python 3.11+ |
| Backend framework | FastAPI + Uvicorn |
| Database | SQLite3 (embedded, local-first) |
| Frontend language | TypeScript 5.8 |
| Frontend framework | React 18 + Vite 5 |
| CSS | Tailwind CSS 3 (dark mode, CSS variables) |
| HTTP / state | TanStack React Query 5 |
| Charts | Recharts 2 |
| UI primitives | Radix UI |
| Test runner | pytest |
| Build tool | Vite (frontend), uvicorn (backend) |

---

## Code Conventions

### Python

- **Type hints everywhere**: use `from __future__ import annotations` for forward refs.
- **snake_case** for functions and variables; **PascalCase** for classes and dataclasses.
- **Frozen dataclasses** for immutable config (e.g., `AppConfig`).
- **Raw parameterized SQL** for all database queries — no ORM.
- **Custom exception types** for domain errors (e.g., `GarminOAuthError`).
- Group imports: stdlib → third-party → local, alphabetically sorted within each group.
- `backend/app/main.py` is intentionally monolithic; do not break it into sub-routers without explicit discussion.

### TypeScript / React

- **Functional components only** with hooks; no class components.
- **PascalCase** for components and interfaces; **camelCase** for files and functions.
- **`@/` path alias** maps to `src/` — always use it for cross-feature imports.
- **TanStack React Query** for all server state; avoid `useEffect` for data fetching.
- **Tailwind utility classes** with dark mode variants; use CSS variables for theming.
- Auth token stored in `localStorage` under the key `temperance.session`.

### Feature module layout (frontend)

```
features/<name>/
├── components/   # Feature-specific UI
├── pages/        # Route-level components
├── services/     # API calls
├── hooks/        # Custom hooks
├── types/        # TypeScript interfaces
└── utils/        # Helpers
```

---

## Activity Text Format (Critical Contract)

Workout entries use a compact, strictly parseable notation. Generated or edited text **must** round-trip through the parser.

**Entry format:** `[date]:[activity description]`

```
2026-03-25:45' run @ 4:40
2026-03-26:70' elliptical @ 138bpm
2026-03-27:6x1km @ 3:45 (2' @ 4:40) + 20' easy
```

**Tokens:**
| Syntax | Meaning |
|---|---|
| `45'`, `45min`, `1h`, `1h30m` | Duration |
| `42.2km`, `400m` | Distance |
| `@ 4:40` | Pace per km |
| `@ mp`, `@ 10k` | Named pace |
| `@ 138bpm` | Heart rate |
| `@ 78%` | Intensity factor |
| `@ 80tss` | TSS target |
| `6x20" @ 3:10` | Interval (reps × duration) |
| `(2' @ 4:40)` | Recovery interval |

When writing or modifying planning output, verify it is reparseable. The canonical test is `temperance/tests/test_activity_parsing.py` and `temperance/tests/test_planning_parsing.py`.

---

## Key Files to Know

| File | Why it matters |
|---|---|
| `temperance/db.py` | All schema definitions and CRUD; change here for data model changes |
| `temperance/garmin_client.py` | Garmin API integration; carefully tested, change with caution |
| `temperance/analytics.py` | TSS, TRIMP, load calculations; numerical logic, changes need test coverage |
| `temperance/activity_parsing.py` | Core parsing contract; any format change breaks planner + frontend |
| `backend/app/main.py` | All REST endpoints; large file, locate the relevant endpoint before editing |
| `backend/app/mcp_server.py` | MCP resources and tools; resources map to `guidelines/` docs |
| `frontend/src/app/` | Router, providers, and app shell; touch sparingly |
| `temperance/planning/policy.py` | Training constraints; changes affect generated plan quality |
| `temperance/guidelines/` | Doctrine and workout templates loaded at runtime by MCP server |

---

## Git Conventions

- **Commit style**: imperative mood, concise, no emoji, no trailing period.
  - Good: `Fix weekly outlook planned comparison cutoff`
  - Good: `Add LT2 interval variant for track sessions`
  - Avoid: `Fixed the bug`, `WIP`, `misc changes`
- Work on the current feature branch; push to `origin/<branch>`.
- No CI/CD pipeline — validate locally with `pytest` and `npm run build` before pushing.
- There is no Docker setup; tests and dev servers run directly on the host.

---

## Working Style (from AGENTS.md)

- Restate goal and constraints before starting non-trivial tasks.
- Prefer small, reviewable diffs over full-file rewrites.
- Ask 1–3 focused questions if requirements are unclear before making risky changes.
- When changing behavior, add or update tests when practical; explain what to validate if not.
- At task end, summarize what changed, why, and how to verify it.

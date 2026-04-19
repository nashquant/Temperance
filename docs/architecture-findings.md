# Architecture Findings

Audit date: 2026-04-19. Covers backend, frontend, shared lib, tests.

## Current architecture map

Temperance is now split into three practical layers:

- `frontend/` is the React/Vite SPA. It talks to the backend through `/api` and stores the session token in `temperance.session`.
- `backend/app/` is the FastAPI layer. `main.py` still owns app setup, startup/background jobs, dense compatibility helpers, and many endpoint implementations. Route registration has been moved into `backend/app/routers/`, with most routers delegating back to `main.py` during the transition.
- `temperance/` is the shared domain library. It owns SQLite persistence, analytics, Garmin sync, planning doctrine, parsing, and recommendation logic used by both the backend API and MCP server.

The backend is in a transitional architecture: route registration is modular, but service ownership is not yet modular. Treat `main.py` as a compatibility boundary until helper extraction is done slice-by-slice with regression tests.

## Priority stack

| # | Finding | Priority | Size | Status |
|---|---------|----------|------|--------|
| 1 | God file: `backend/app/main.py` | P1 | XL | In progress: route registration split + owner path service extracted |
| 2 | In-process dashboard cache not multi-worker safe | P2 | S | Done: single-worker constraint documented |
| 3 | `AUTO_SYNC_TEMPORARILY_DISABLED = True` hardcoded | P2 | XS | Done: env-controlled |
| 4 | Test-layer coupling: `temperance/tests/` imports `backend.app` | P2 | S | Done: backend-coupled tests moved |
| 5 | Dual Garmin auth paths undocumented | P2 | XS | Done: relationship documented |
| 6 | Dual schema source of truth in `db.py` | P3 | M | Guarded: schema bootstrap test added |
| 7 | Planning parser partially extracted | P3 | S | Guarded: shared-parser adapter test added |
| 8 | No per-owner DB fixture in test suite | P3 | M | Done: real owner path coverage added |
| 9 | `merge_asof` per-activity on bulk import | P3 | M | Guarded: prepared LT curve frames supported |
| 10 | Dashboard cache key completeness unverified | P3 | S | Done: cache components tested |

---

## P1 — God file: `backend/app/main.py`

**Location:** `backend/app/main.py` — still roughly 12k lines after the route split.

**Problem:** Everything lives in one file — Pydantic models, auth helpers, business logic, analytics helpers, planning parsers, activity merge logic, and all route handlers. Routes start at line 10,086.

### Session 2026-04-19 progress

Files created and wired into `main.py`:

- `backend/app/models.py` — 13 Pydantic request models extracted
- `backend/app/cache.py` — `_dashboard_payload_cache`, lock, `dashboard_cache_key()`
- `backend/app/auth_service.py` — auth constants (`TOKEN_TTL_S`, `AUTH_COOKIE_NAME`), `AuthConfigurationError`, all auth helpers (`auth_enabled`, `auth_users`, `build_token`, `parse_token`, `auth_context`, `resolve_owner`, cookie helpers, etc.)
- `backend/app/routers/__init__.py` — empty package
- `backend/app/routers/auth.py` — 4 auth routes using `APIRouter`: login, logout, me, owners
- `backend/app/routers/settings.py` — settings and VDOT routes using `APIRouter`
- `backend/app/routers/dashboard.py` — overview, dashboard, week outlook, athlete progression, and wellness routes using `APIRouter`
- `backend/app/routers/activities.py` — activity merge create/delete implementation plus activity detail route registration using `APIRouter`
- `backend/app/routers/planning.py` — planned, custom, and generated activity route registration using `APIRouter`
- `backend/app/routers/garmin.py` — Garmin OAuth and data-extract route registration using `APIRouter`

`main.py` state: first-pass route registration extraction is complete. Inline model/cache/auth helper definitions and inline auth route decorators were removed; all route groups are included via routers, leaving only `/health` and `/` directly registered in `main.py`. Activity merge create/delete implementation now lives in `routers/activities.py`; dense compatibility functions remain in `main.py` for tests, MCP tools, and follow-up service extraction. `_dashboard_cache_key` remains as a thin compatibility wrapper so existing tests that patch `backend.app.main` cache-key dependencies still work while cache storage lives in `cache.py`.

Verification completed:

- `python3 -m py_compile backend/app/main.py backend/app/auth_service.py backend/app/cache.py backend/app/models.py backend/app/routers/auth.py backend/app/routers/settings.py backend/app/routers/dashboard.py backend/app/routers/activities.py backend/app/routers/planning.py backend/app/routers/garmin.py temperance/tests/conftest.py`
- `pytest temperance/tests -q` — 146 passed, 4 warnings
- `PORT=8799 HOST=127.0.0.1 BACKEND_PYTHON_BIN=python3 ./backend/run.sh` — application startup complete; stopped after smoke boot
- `pytest backend/tests/test_baseline_blend.py backend/tests/test_dashboard_cache.py temperance/tests/test_auth.py temperance/tests/test_dashboard_api.py -q` — 37 passed, 4 warnings
- `pytest temperance/tests/test_activity_merges.py backend/tests/test_mcp_server.py::MCPServerHelpersTest::test_tool_get_activity_detail_delegates_to_backend_handler -q` — 12 passed, 4 warnings
- `pytest temperance/tests/test_generated_activity.py temperance/tests/test_planning_parsing.py backend/tests/test_week_planner_baselines.py -q` — 11 passed, 4 warnings
- `pytest temperance/tests/test_garmin_oauth.py temperance/tests/test_garmin_auth_reset.py temperance/tests/test_garmin_auth_reset_endpoint.py temperance/tests/test_auto_sync_schedule.py -q` — 23 passed, 4 warnings

### P1 remaining work

First-pass route registration extraction is complete and was shipped in `4d0ff40`. Remaining work is follow-up service extraction only: promote dense compatibility functions/helpers from `main.py` into service modules per router group without changing endpoint behavior.

**Status 2026-04-19:** In progress. `backend/app/owner_paths.py` now owns owner slugging and owner-scoped DB path resolution; `main.py` keeps thin compatibility wrappers for existing tests/MCP patch points. The larger settings/dashboard/activity/planning/Garmin service extractions remain pending.

**Current backend shape:**

```
backend/app/
  models.py          # DONE
  cache.py           # DONE
  auth_service.py    # DONE
  routers/
    __init__.py      # DONE
    auth.py          # DONE
    settings.py      # DONE
    dashboard.py     # DONE
    garmin.py        # DONE
    activities.py    # DONE
    planning.py      # DONE
  main.py            # app init, middleware, startup/shutdown, include_router calls
```

**Next service-extraction order (low → high risk):**
1. `settings_service.py` — settings, VDOT, LT history, and timezone helpers. Keep `main.py` wrappers until backend tests stop patching them.
2. `dashboard_service.py` — dashboard payload assembly, athlete progression, wellness projections, weekly outlook. Highest invariant: MCP weekly baseline and dashboard baseline must stay aligned.
3. `activity_service.py` — detail card assembly, merge lookup/materialization, activity ID parsing helpers.
4. `planning_api_service.py` — planned/custom/generated activity persistence and parser adapter calls.
5. `garmin_service.py` — OAuth status, extraction orchestration, sync source resolution, runtime credential fallback.

**Key constraint:** Helper functions are densely interconnected. Do NOT try to reorganize them in the first pass. Route registration is now extracted into routers that import/delegate to compatibility functions in `main.py`; follow-up sessions should incrementally promote helpers into service modules.

**Verification:** `pytest temperance/tests -q` and the backend route/helper focused suites passed after the extraction. Future service-extraction slices should keep the shared-library suite green and add focused backend tests for the affected router/service boundary.

---

## P2 — In-process dashboard cache not multi-worker safe

**Location:** `backend/app/main.py` lines 144–145 (or `backend/app/cache.py` after P1 split).

```python
_dashboard_payload_cache: OrderedDict[str, dict] = OrderedDict()
_dashboard_payload_cache_lock = threading.Lock()
```

**Problem:** This is a per-process in-memory cache. Under `uvicorn --workers N` (or gunicorn), each worker has its own copy — cache misses are guaranteed on every cross-worker request, and cache invalidation is impossible. Fine for single-worker local use; breaks silently under multi-worker deploy.

**Fix (when multi-worker matters):** Replace with Redis or a file-based sidecar cache keyed by the same content hash. For now: add a comment documenting the single-worker constraint and add `assert` or startup check that `WEB_CONCURRENCY == 1` if the env flag is set.

**Status 2026-04-19:** Done. Single-worker constraint is documented in `backend/app/cache.py`. No startup assertion was added because local development currently uses the in-process cache intentionally.

---

## P2 — `AUTO_SYNC_TEMPORARILY_DISABLED = True` hardcoded

**Location:** `backend/app/main.py` line 242.

```python
AUTO_SYNC_TEMPORARILY_DISABLED = True
```

**Problem:** This disables background Garmin sync permanently until someone edits the source. Should be an env var: `TEMPERANCE_AUTO_SYNC_DISABLED=1`.

**Fix:** Replace with:
```python
AUTO_SYNC_TEMPORARILY_DISABLED = str(
    os.getenv("TEMPERANCE_AUTO_SYNC_DISABLED", "0")
).strip().lower() in {"1", "true", "yes", "on"}
```

XS change, zero risk.

**Status 2026-04-19:** Done. `AUTO_SYNC_TEMPORARILY_DISABLED` is now controlled by `TEMPERANCE_AUTO_SYNC_DISABLED`.

---

## P2 — Test-layer coupling: `temperance/tests/` imports `backend.app`

**Location:** `temperance/tests/test_auth.py`, `test_dashboard_api.py`, `test_activity_parsing.py`.

**Problem:** These tests import `backend.app.main` (FastAPI app) to call routes via `TestClient`. They live in `temperance/tests/` which is supposed to test the shared library, not the API layer. This creates a production circular risk and makes test organization misleading.

**Fix:** Move API-coupled tests to `backend/tests/`. The existing `backend/tests/test_activity_merges_api.py` is already there. Pure library tests (analytics, planning, auth helpers) stay in `temperance/tests/`.

**Note:** `backend/tests/` currently has a Starlette collection error — fix that first before moving tests.

**Status 2026-04-19:** Done for direct backend-coupled tests. Files that import `backend.app` now live under `backend/tests/`: auth, dashboard API helpers, date parsing, generated activity, auto sync schedule, Garmin OAuth/reset endpoints, MCP server contract tests, and the backend parser adapter assertion split out of `temperance/tests/test_activity_parsing.py`. `backend/tests/test_activity_merges_api.py` now skips when `httpx` is unavailable because FastAPI/Starlette `TestClient` cannot run without it; the full API integration test path still needs the backend test environment to install `httpx` when that coverage is required.

---

## P2 — Dual Garmin auth paths undocumented

**Locations:**
- `backend/app/garmin_oauth.py` — OAuth2 PKCE flow (token-based, per-user)
- `temperance/garmin_client.py` — legacy credential-based sync (email/password)

**Problem:** Two completely different auth mechanisms for Garmin with no documentation of which one is preferred, which one is deprecated, and under what conditions each is used.

**Fix:** Add a comment block at the top of each file explaining the relationship. Long-term: deprecate the credential path once OAuth is stable.

**Status 2026-04-19:** Done. Both Garmin auth modules now document OAuth as the preferred per-user path and legacy credentials as the admin/local/fallback path.

---

## P3 — Dual schema source of truth in `db.py`

**Location:** `temperance/db.py` — `SCHEMA_SQL` block at top + inline `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` inside `run_migrations()`.

**Problem:** New columns are sometimes added via `SCHEMA_SQL`, sometimes via migration statements. A fresh install and an upgraded install end up in the same state, but it's hard to reason about which columns exist where.

**Fix:** Make `run_migrations()` the single source of truth. `SCHEMA_SQL` should only be used for truly immutable base tables. Or: adopt a numbered migration scheme (001_initial.sql, 002_add_col.sql).

**Execution notes:** Fresh initialization runs `SCHEMA_SQL` first in `init_db()`, then `run_migrations()` creates or alters migration-managed structures including `schema_migrations`, `activity_splits`, `planned_activities`, `custom_activities`, `activities.is_invalid`, `planning_decisions`, `activity_merges`, and `activity_merge_members`. The immediate cleanup should document this order in code and add a schema snapshot/assertion test before changing behavior. Do not introduce a new migration framework until the existing bootstrap path is covered by tests.

**Status 2026-04-19:** Guarded. `temperance/tests/test_db_schema.py` now asserts that fresh `init_db()` applies the schema and migration-managed tables/columns. `run_migrations()` documents that this bootstrap order must stay covered before moving columns between `SCHEMA_SQL` and migration-managed DDL. Full migration consolidation remains pending.

---

## P3 — Planning parser partially extracted

**Location:** `backend/app/planning_parsing.py` exists but `backend/app/main.py` still contains parsing logic alongside route handlers.

**Problem:** The extraction was started but not completed. This creates two sources of planning parse logic.

**Fix:** Audit what's in `planning_parsing.py` vs what's still in `main.py`; either finish the extraction or revert and document why.

**Execution notes:** `main.py` imports shared parser entry points from `backend.app.planning_parsing`, but local token parsers and `_parse_dated_activity_entry` definitions still exist before being rebound to the shared implementation. This should be the next small cleanup: remove dead duplicate parser helpers only after focused parser tests prove the shared parser remains the only behavior used by API routes.

**Status 2026-04-19:** Guarded. `backend/tests/test_planning_parser_adapter.py` now asserts that `main.py` uses the shared parser entry points for normalization, dated-entry parsing, entry splitting, and row signatures. Dead duplicate helper removal remains pending.

---

## P3 — No per-owner DB fixture in test suite

**Location:** `temperance/tests/` — tests use a shared single DB path.

**Problem:** The production system uses per-owner DBs (`users/<slug>.db`). Tests don't exercise this path, so multi-user isolation bugs won't be caught.

**Fix:** Add a pytest fixture that creates a temp directory with a `users/` subdirectory and injects `TEMPERANCE_DB_PATH` env var before each test that exercises owner-scoped endpoints.

**Execution notes:** Backend tests patch `_db_path_for_owner` in several places, which verifies endpoint behavior but does not exercise the real `DB_PATH.parent / "users" / "<owner>.db"` path. Add a backend fixture first, not a shared-library fixture: it should set `TEMPERANCE_DB_PATH` before importing `backend.app.main` or isolate the resolver behind a testable helper that accepts a base path.

**Status 2026-04-19:** Done. `backend/app/owner_paths.py` isolates owner path resolution behind an injectable base DB path, and `backend/tests/test_owner_db_paths.py` covers real named-owner scoped DB creation plus the default-owner legacy base DB path.

---

## P3 — `merge_asof` per-activity on bulk import

**Location:** `temperance/analytics.py` — `compute_metrics()` uses `pd.merge_asof` to interpolate the LT curve for each activity.

**Problem:** On a bulk import of 500+ activities, this runs 500+ separate merge operations. The LT curve is read from settings and doesn't change between activities in the same import batch.

**Fix:** Cache the LT curve for the duration of the import batch. Pass it as a parameter into `compute_metrics()` rather than re-reading from DB on each call.

**Execution notes:** This is a performance refactor, not a correctness fix. First add a narrow test that `compute_metrics()` produces identical outputs with an injected precomputed LT frame and with the current point-list lookup. Then thread that optional precomputed curve through backend metrics callers and the Garmin import/bulk metrics path where applicable.

**Status 2026-04-19:** Guarded. `compute_metrics()` accepts prepared LT pace/LTHR curve frames, preserves point-list behavior, and the current backend `compute_metrics()` callers pass prepared frames after loading curves once. `temperance/tests/test_analytics_series.py` verifies frame-backed and point-backed outputs match. A Garmin import-specific threading audit remains pending if a future import path computes metrics per activity.

---

## P3 — Dashboard cache key completeness unverified

**Location:** `backend/app/cache.py` (or `main.py`) — `dashboard_cache_key()` uses six DB-derived components.

**Problem:** It's unclear whether all tables that affect the dashboard payload are covered by the cache key. A missing component means stale data is served without invalidation.

**Fix:** Audit `_build_activity_dashboard_payload()` and list every table it reads. Cross-check against the six cache components in `get_dashboard_cache_components()`. Add a test that mutates each table and asserts the cache key changes.

**Status 2026-04-19:** Done. `_dashboard_cache_key()` now uses the consolidated `get_dashboard_cache_components()` component set, and `backend/tests/test_dashboard_cache.py` mutates each dashboard-relevant component family (`activities`, `planned_activities`, `custom_activities`, `settings`, `wellness_daily`, and activity merges) and asserts the dashboard key changes. The payload builder was audited against those table families; it does not read activity splits for the dashboard card list.

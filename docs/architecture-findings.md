# Architecture Findings

Audit date: 2026-04-19. Covers backend, frontend, shared lib, tests.

## Priority stack

| # | Finding | Priority | Size |
|---|---------|----------|------|
| 1 | God file: `backend/app/main.py` | P1 | XL |
| 2 | In-process dashboard cache not multi-worker safe | P2 | S |
| 3 | `AUTO_SYNC_TEMPORARILY_DISABLED = True` hardcoded | P2 | XS |
| 4 | Test-layer coupling: `temperance/tests/` imports `backend.app` | P2 | S |
| 5 | Dual Garmin auth paths undocumented | P2 | XS |
| 6 | Dual schema source of truth in `db.py` | P3 | M |
| 7 | Planning parser partially extracted | P3 | S |
| 8 | No per-owner DB fixture in test suite | P3 | M |
| 9 | `merge_asof` per-activity on bulk import | P3 | M |
| 10 | Dashboard cache key completeness unverified | P3 | S |

---

## P1 — God file: `backend/app/main.py`

**Location:** `backend/app/main.py` — 12,752 lines, 289 functions/classes, 35+ route handlers.

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

### Next steps to continue P1

1. Commit the completed route registration split: `refactor(p1): extract backend route registration`
2. Follow-up sessions can promote dense compatibility functions/helpers from `main.py` into service modules per router group.

**Proposed split (remaining):**

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

**Extraction order (low → high risk):**
1. `models.py` — pure move, zero behavioral risk
2. `cache.py` — module-level vars + one function
3. `auth_service.py` — auth constants + helpers; routers import from here, avoiding circular deps
4. `routers/auth.py` — 4 routes: login, logout, me, owners
5. `routers/settings.py` — settings and VDOT routes
6. `routers/dashboard.py` — dashboard read endpoints
7. `routers/activities.py` — activity merge/detail registration
8. `routers/planning.py` — planned/custom/generated activity registration
9. `routers/garmin.py` — Garmin OAuth and data-extract registration

**Key constraint:** Helper functions are densely interconnected. Do NOT try to reorganize them in the first pass. Route registration is now extracted into routers that import/delegate to compatibility functions in `main.py`; follow-up sessions should incrementally promote helpers into service modules.

**Verification:** `python3 -m pytest temperance/tests -q` — baseline is 146 passed. Must hold after each extraction step.

---

## P2 — In-process dashboard cache not multi-worker safe

**Location:** `backend/app/main.py` lines 144–145 (or `backend/app/cache.py` after P1 split).

```python
_dashboard_payload_cache: OrderedDict[str, dict] = OrderedDict()
_dashboard_payload_cache_lock = threading.Lock()
```

**Problem:** This is a per-process in-memory cache. Under `uvicorn --workers N` (or gunicorn), each worker has its own copy — cache misses are guaranteed on every cross-worker request, and cache invalidation is impossible. Fine for single-worker local use; breaks silently under multi-worker deploy.

**Fix (when multi-worker matters):** Replace with Redis or a file-based sidecar cache keyed by the same content hash. For now: add a comment documenting the single-worker constraint and add `assert` or startup check that `WEB_CONCURRENCY == 1` if the env flag is set.

**Status 2026-04-19:** Single-worker constraint is documented in `backend/app/cache.py`. No startup assertion was added because local development currently uses the in-process cache intentionally.

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

**Status 2026-04-19:** Fixed. `AUTO_SYNC_TEMPORARILY_DISABLED` is now controlled by `TEMPERANCE_AUTO_SYNC_DISABLED`.

---

## P2 — Test-layer coupling: `temperance/tests/` imports `backend.app`

**Location:** `temperance/tests/test_auth.py`, `test_dashboard_api.py`, `test_activity_parsing.py`.

**Problem:** These tests import `backend.app.main` (FastAPI app) to call routes via `TestClient`. They live in `temperance/tests/` which is supposed to test the shared library, not the API layer. This creates a production circular risk and makes test organization misleading.

**Fix:** Move API-coupled tests to `backend/tests/`. The existing `backend/tests/test_activity_merges_api.py` is already there. Pure library tests (analytics, planning, auth helpers) stay in `temperance/tests/`.

**Note:** `backend/tests/` currently has a Starlette collection error — fix that first before moving tests.

**Status 2026-04-19:** Fixed for direct backend-coupled tests. Files that import `backend.app` now live under `backend/tests/`: auth, dashboard API helpers, date parsing, generated activity, auto sync schedule, Garmin OAuth/reset endpoints, MCP server contract tests, and the backend parser adapter assertion split out of `temperance/tests/test_activity_parsing.py`. `backend/tests/test_activity_merges_api.py` now skips when `httpx` is unavailable because FastAPI/Starlette `TestClient` cannot run without it; the full API integration test path still needs the backend test environment to install `httpx` when that coverage is required.

---

## P2 — Dual Garmin auth paths undocumented

**Locations:**
- `backend/app/garmin_oauth.py` — OAuth2 PKCE flow (token-based, per-user)
- `temperance/garmin_client.py` — legacy credential-based sync (email/password)

**Problem:** Two completely different auth mechanisms for Garmin with no documentation of which one is preferred, which one is deprecated, and under what conditions each is used.

**Fix:** Add a comment block at the top of each file explaining the relationship. Long-term: deprecate the credential path once OAuth is stable.

**Status 2026-04-19:** Fixed. Both Garmin auth modules now document OAuth as the preferred per-user path and legacy credentials as the admin/local/fallback path.

---

## P3 — Dual schema source of truth in `db.py`

**Location:** `temperance/db.py` — `SCHEMA_SQL` block at top + inline `ALTER TABLE`/`CREATE TABLE IF NOT EXISTS` inside `run_migrations()`.

**Problem:** New columns are sometimes added via `SCHEMA_SQL`, sometimes via migration statements. A fresh install and an upgraded install end up in the same state, but it's hard to reason about which columns exist where.

**Fix:** Make `run_migrations()` the single source of truth. `SCHEMA_SQL` should only be used for truly immutable base tables. Or: adopt a numbered migration scheme (001_initial.sql, 002_add_col.sql).

---

## P3 — Planning parser partially extracted

**Location:** `backend/app/planning_parsing.py` exists but `backend/app/main.py` still contains parsing logic alongside route handlers.

**Problem:** The extraction was started but not completed. This creates two sources of planning parse logic.

**Fix:** Audit what's in `planning_parsing.py` vs what's still in `main.py`; either finish the extraction or revert and document why.

---

## P3 — No per-owner DB fixture in test suite

**Location:** `temperance/tests/` — tests use a shared single DB path.

**Problem:** The production system uses per-owner DBs (`users/<slug>.db`). Tests don't exercise this path, so multi-user isolation bugs won't be caught.

**Fix:** Add a pytest fixture that creates a temp directory with a `users/` subdirectory and injects `TEMPERANCE_DB_PATH` env var before each test that exercises owner-scoped endpoints.

---

## P3 — `merge_asof` per-activity on bulk import

**Location:** `temperance/analytics.py` — `compute_metrics()` uses `pd.merge_asof` to interpolate the LT curve for each activity.

**Problem:** On a bulk import of 500+ activities, this runs 500+ separate merge operations. The LT curve is read from settings and doesn't change between activities in the same import batch.

**Fix:** Cache the LT curve for the duration of the import batch. Pass it as a parameter into `compute_metrics()` rather than re-reading from DB on each call.

---

## P3 — Dashboard cache key completeness unverified

**Location:** `backend/app/cache.py` (or `main.py`) — `dashboard_cache_key()` uses six DB-derived components.

**Problem:** It's unclear whether all tables that affect the dashboard payload are covered by the cache key. A missing component means stale data is served without invalidation.

**Fix:** Audit `_build_activity_dashboard_payload()` and list every table it reads. Cross-check against the six cache components in `get_dashboard_cache_components()`. Add a test that mutates each table and asserts the cache key changes.

**Status 2026-04-19:** Fixed. `_dashboard_cache_key()` now uses the consolidated `get_dashboard_cache_components()` component set, and `backend/tests/test_dashboard_cache.py` mutates each dashboard-relevant component family (`activities`, `planned_activities`, `custom_activities`, `settings`, `wellness_daily`, and activity merges) and asserts the dashboard key changes. The payload builder was audited against those table families; it does not read activity splits for the dashboard card list.

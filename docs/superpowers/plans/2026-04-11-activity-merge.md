# Activity Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users merge two Garmin activities into a single virtual activity that sums their metrics and concatenates their splits, without mutating the original activity records.

**Architecture:** A new `activity_merges` table stores pairs of original activity IDs. The dashboard payload collapses merged pairs into one virtual card with summed/weighted metrics. The existing activity detail endpoint is extended to handle `merged-{id}` virtual IDs by fetching and concatenating both activities' splits. The analytics pipeline (CTL/ATL/TSB) is unchanged — both underlying activities continue to contribute independently to load calculations.

**Tech Stack:** SQLite (new migration in `run_migrations`), FastAPI (new endpoints + dashboard payload update), React + TypeScript (merge affordance on dashboard cards), `@tanstack/react-query` for cache invalidation.

---

## Assumptions / Constraints (read before coding)

- **Owner-scoped DB:** `activity_merges` lives in the per-owner DB file. No `owner_id` column needed.
- **Same-day only:** Both activities must start on the same local calendar day. Enforced in the POST handler.
- **One merge per activity:** Each activity participates in at most one merge. Enforced by UNIQUE constraints.
- **Garmin activities only:** Custom activities (`source = 'custom'`) cannot be merged — they lack splits/records and have synthetic IDs.
- **Compatibility groups (actual `sport_type` values):**
  ```python
  MERGE_COMPAT_GROUPS: list[frozenset[str]] = [
      frozenset({"running", "track_running", "virtual_run", "treadmill_running"}),
      frozenset({"cycling", "indoor_cycling"}),
  ]
  ```
  Two activities can be merged iff both sport types fall in the same group. All other sport types (elliptical, walking, strength_training, breathwork, mountaineering, etc.) **cannot be merged**. The run+treadmill exception is covered naturally — both are in the running group.
- **Unmerge is a DELETE.** There is no "edit merge"; you delete and re-create.
- **Virtual ID format:** `merged-{merge_id}` (e.g., `merged-3`). Used only in the API response; never stored.

---

## File Structure

| File | Change | What it does |
|------|--------|--------------|
| `temperance/db.py` | Modify | Add `activity_merges` DDL, migration block, and 4 CRUD functions |
| `temperance/tests/test_activity_merges.py` | Create | Unit tests for all db.py merge functions |
| `backend/app/main.py` | Modify | Add `MERGE_COMPAT_GROUPS`, POST/DELETE endpoints, `_build_merged_activity_card`, `_collapse_merged_cards`, dashboard payload update, detail endpoint extension |
| `backend/tests/test_activity_merges_api.py` | Create | API-level tests for POST/DELETE and merged dashboard card |
| `frontend/src/features/dashboard/types/dashboard.ts` | Modify | Add `merge_id?`, `merged_activity_ids?` to `DashboardActivityCard` |
| `frontend/src/features/dashboard/services/activity-merge-api.ts` | Create | `createActivityMerge`, `deleteActivityMerge` API calls |
| `frontend/src/features/dashboard/components/dashboard-day-column.tsx` | Modify | Merge icon on activity cards, merged card badge + unmerge button |
| `frontend/src/features/dashboard/pages/dashboard-page.tsx` | Modify | `mergePendingId` state, wire merge/unmerge mutations |

---

## Task 1: DB schema + migration + CRUD

**Files:**
- Modify: `temperance/db.py`
- Create: `temperance/tests/test_activity_merges.py`

### Step 1.1: Write failing tests for the four CRUD functions

Create `temperance/tests/test_activity_merges.py`:

```python
import pytest
import tempfile
from pathlib import Path
from temperance.db import (
    init_db,
    create_activity_merge,
    delete_activity_merge,
    get_activity_merge_by_id,
    get_active_merges,
    upsert_activities,
)

UTC_NOW_STR = "2026-04-10T07:00:00"

def _make_activity(activity_id: str, sport_type: str = "running") -> dict:
    return {
        "activity_id": activity_id,
        "start_time_utc": UTC_NOW_STR,
        "sport_type": sport_type,
        "source": "garmin_api",
        "raw": {},
    }

@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test.db"
    init_db(path)
    upsert_activities(path, [
        _make_activity("act-1", "running"),
        _make_activity("act-2", "running"),
        _make_activity("act-3", "treadmill_running"),
        _make_activity("act-4", "cycling"),
    ])
    return path


def test_create_merge_returns_id(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    assert isinstance(merge_id, int)
    assert merge_id > 0


def test_get_merge_by_id(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    row = get_activity_merge_by_id(db_path, merge_id)
    assert row is not None
    assert row["activity_id_1"] == "act-1"
    assert row["activity_id_2"] == "act-2"


def test_delete_merge(db_path: Path) -> None:
    merge_id = create_activity_merge(db_path, "act-1", "act-2")
    assert delete_activity_merge(db_path, merge_id) is True
    assert get_activity_merge_by_id(db_path, merge_id) is None


def test_delete_nonexistent_merge_returns_false(db_path: Path) -> None:
    assert delete_activity_merge(db_path, 9999) is False


def test_get_active_merges(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    merges = get_active_merges(db_path)
    assert len(merges) == 1
    assert merges[0]["activity_id_1"] == "act-1"


def test_duplicate_activity_in_merge_raises(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    with pytest.raises(Exception):  # UNIQUE constraint
        create_activity_merge(db_path, "act-1", "act-3")


def test_activity_cant_appear_on_both_sides(db_path: Path) -> None:
    create_activity_merge(db_path, "act-1", "act-2")
    with pytest.raises(Exception):
        create_activity_merge(db_path, "act-3", "act-2")
```

- [ ] **Step 1.2: Run test to verify it fails**

```bash
cd /path/to/repo
pytest temperance/tests/test_activity_merges.py -v
```
Expected: `ImportError` — `create_activity_merge` not defined yet.

- [ ] **Step 1.3: Add `activity_merges` DDL to `SCHEMA_SQL` in `temperance/db.py`**

Append to `SCHEMA_SQL` (around line 217, after `schema_migrations`):

```python
CREATE TABLE IF NOT EXISTS activity_merges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity_id_1 TEXT NOT NULL UNIQUE,
    activity_id_2 TEXT NOT NULL UNIQUE,
    merged_at TEXT NOT NULL,
    FOREIGN KEY(activity_id_1) REFERENCES activities(activity_id),
    FOREIGN KEY(activity_id_2) REFERENCES activities(activity_id)
);
```

- [ ] **Step 1.4: Add migration block to `run_migrations` in `temperance/db.py`**

At the end of `run_migrations`, before `conn.commit()`:

```python
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activity_merges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id_1 TEXT NOT NULL UNIQUE,
                activity_id_2 TEXT NOT NULL UNIQUE,
                merged_at TEXT NOT NULL,
                FOREIGN KEY(activity_id_1) REFERENCES activities(activity_id),
                FOREIGN KEY(activity_id_2) REFERENCES activities(activity_id)
            )
            """
        )
```

- [ ] **Step 1.5: Add four CRUD functions to `temperance/db.py`**

Add after `upsert_activity_trimp` (around line 853):

```python
def create_activity_merge(
    db_path: Path, activity_id_1: str, activity_id_2: str
) -> int:
    """Create a merge record. Raises sqlite3.IntegrityError if either activity
    already participates in a merge (UNIQUE constraints on both columns)."""
    now = UTC_NOW()
    with closing(get_conn(db_path)) as conn:
        cur = conn.execute(
            """
            INSERT INTO activity_merges (activity_id_1, activity_id_2, merged_at)
            VALUES (?, ?, ?)
            """,
            (activity_id_1, activity_id_2, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def delete_activity_merge(db_path: Path, merge_id: int) -> bool:
    """Delete a merge by id. Returns True if a row was deleted, False if not found."""
    with closing(get_conn(db_path)) as conn:
        cur = conn.execute(
            "DELETE FROM activity_merges WHERE id = ?", (merge_id,)
        )
        conn.commit()
        return cur.rowcount > 0


def get_activity_merge_by_id(
    db_path: Path, merge_id: int
) -> dict[str, Any] | None:
    with closing(get_conn(db_path)) as conn:
        row = conn.execute(
            "SELECT id, activity_id_1, activity_id_2, merged_at "
            "FROM activity_merges WHERE id = ?",
            (merge_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "activity_id_1": row["activity_id_1"],
            "activity_id_2": row["activity_id_2"],
            "merged_at": row["merged_at"],
        }


def get_active_merges(db_path: Path) -> list[dict[str, Any]]:
    """Return all merge records, ordered by id."""
    with closing(get_conn(db_path)) as conn:
        rows = conn.execute(
            "SELECT id, activity_id_1, activity_id_2, merged_at "
            "FROM activity_merges ORDER BY id"
        ).fetchall()
        return [
            {
                "id": r["id"],
                "activity_id_1": r["activity_id_1"],
                "activity_id_2": r["activity_id_2"],
                "merged_at": r["merged_at"],
            }
            for r in rows
        ]
```

- [ ] **Step 1.6: Run tests — expect pass**

```bash
pytest temperance/tests/test_activity_merges.py -v
```
Expected: all 8 tests PASS.

- [ ] **Step 1.7: Commit**

```bash
git add temperance/db.py temperance/tests/test_activity_merges.py
git commit -m "feat: add activity_merges table and CRUD functions"
```

---

## Task 2: Backend merge endpoints (POST + DELETE)

**Files:**
- Modify: `backend/app/main.py` (add `MERGE_COMPAT_GROUPS`, two request models, two endpoints)
- Create: `backend/tests/test_activity_merges_api.py`

- [ ] **Step 2.1: Write failing API tests**

Create `backend/tests/test_activity_merges_api.py`:

```python
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# We test endpoint handlers directly by importing main and using TestClient.
from fastapi.testclient import TestClient

# Patch DB path resolution so tests use a temp DB.
from backend.app.main import app
from temperance.db import init_db, upsert_activities

UTC_STR = "2026-04-10T07:00:00"

def _make_activity(activity_id: str, sport_type: str = "running") -> dict:
    return {
        "activity_id": activity_id,
        "start_time_utc": UTC_STR,
        "sport_type": sport_type,
        "source": "garmin_api",
        "raw": {},
    }


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    p = tmp_path / "test.db"
    init_db(p)
    upsert_activities(p, [
        _make_activity("act-1", "running"),
        _make_activity("act-2", "running"),
        _make_activity("act-3", "treadmill_running"),
        _make_activity("act-4", "cycling"),
    ])
    return p


def _client(tmp_db: Path) -> TestClient:
    # Patch _db_path_for_owner to always return our tmp_db.
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db):
        with patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)):
            with patch("backend.app.main._resolve_owner", return_value="test"):
                client = TestClient(app, raise_server_exceptions=True)
                yield client


def test_create_merge_compatible_activities(tmp_db: Path) -> None:
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db), \
         patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)), \
         patch("backend.app.main._resolve_owner", return_value="test"):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/activity-merges",
            json={"activity_id_1": "act-1", "activity_id_2": "act-2"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "merge_id" in body
        assert isinstance(body["merge_id"], int)


def test_create_merge_incompatible_types_returns_422(tmp_db: Path) -> None:
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db), \
         patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)), \
         patch("backend.app.main._resolve_owner", return_value="test"):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/activity-merges",
            json={"activity_id_1": "act-1", "activity_id_2": "act-4"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 422


def test_create_merge_run_plus_treadmill_allowed(tmp_db: Path) -> None:
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db), \
         patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)), \
         patch("backend.app.main._resolve_owner", return_value="test"):
        client = TestClient(app)
        resp = client.post(
            "/api/v1/activity-merges",
            json={"activity_id_1": "act-1", "activity_id_2": "act-3"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200


def test_delete_merge(tmp_db: Path) -> None:
    from temperance.db import create_activity_merge
    merge_id = create_activity_merge(tmp_db, "act-1", "act-2")
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db), \
         patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)), \
         patch("backend.app.main._resolve_owner", return_value="test"):
        client = TestClient(app)
        resp = client.delete(
            f"/api/v1/activity-merges/{merge_id}",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True


def test_delete_nonexistent_merge_returns_404(tmp_db: Path) -> None:
    with patch("backend.app.main._db_path_for_owner", return_value=tmp_db), \
         patch("backend.app.main._auth_context", return_value=MagicMock(owner="test", is_admin=True)), \
         patch("backend.app.main._resolve_owner", return_value="test"):
        client = TestClient(app)
        resp = client.delete(
            "/api/v1/activity-merges/9999",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 404
```

- [ ] **Step 2.2: Run test to verify it fails**

```bash
python -m unittest backend.tests.test_activity_merges_api 2>&1 | head -20
# or
pytest backend/tests/test_activity_merges_api.py -v 2>&1 | head -30
```
Expected: import error or 404 from TestClient (endpoints don't exist yet).

- [ ] **Step 2.3: Add to `backend/app/main.py`**

Near the other `db` imports (around line 70), add:
```python
from temperance.db import (
    ...
    create_activity_merge,
    delete_activity_merge,
    get_activity_merge_by_id,
    get_active_merges,
)
```

Add the compatibility constant near the top of `main.py` with other constants (after the `DEFAULT_OWNER` block):

```python
# Only running-like and cycling-like activities may be merged.
MERGE_COMPAT_GROUPS: list[frozenset[str]] = [
    frozenset({"running", "track_running", "virtual_run", "treadmill_running"}),
    frozenset({"cycling", "indoor_cycling"}),
]


def _merge_compatible(sport_a: str, sport_b: str) -> bool:
    """Return True iff the two sport_type values belong to the same merge group."""
    a = sport_a.strip().lower()
    b = sport_b.strip().lower()
    return any(a in g and b in g for g in MERGE_COMPAT_GROUPS)
```

Add Pydantic models near the other request models:

```python
class ActivityMergeRequest(BaseModel):
    activity_id_1: str
    activity_id_2: str
```

Add the two endpoints (append after the `DELETE /api/v1/custom-activities` endpoint, before `GET /api/v1/activities/{activity_id}`):

```python
@app.post("/api/v1/activity-merges")
def create_merge(
    payload: ActivityMergeRequest,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)

    id1 = _normalize_activity_id(payload.activity_id_1)
    id2 = _normalize_activity_id(payload.activity_id_2)

    if id1 == id2:
        raise HTTPException(status_code=422, detail="Cannot merge an activity with itself")

    # Validate both exist and are not custom.
    raw1 = get_activity_raw(db_path, id1)
    raw2 = get_activity_raw(db_path, id2)
    if raw1 is None or raw2 is None:
        raise HTTPException(status_code=404, detail="One or both activities not found")
    if str(raw1.get("source") or "").lower() == "custom" or str(raw2.get("source") or "").lower() == "custom":
        raise HTTPException(status_code=422, detail="Custom activities cannot be merged")

    # Compatibility check.
    sport1 = str(raw1.get("sport_type") or "").strip().lower()
    sport2 = str(raw2.get("sport_type") or "").strip().lower()
    if not _merge_compatible(sport1, sport2):
        raise HTTPException(
            status_code=422,
            detail=f"Incompatible sport types: {sport1!r} and {sport2!r}",
        )

    # Same-day check (local date, derived from start_time_utc stored in the activity row).
    # We use start_time_utc and convert to local using the stored start_local if available,
    # otherwise fall back to UTC date. The key invariant is that both activities
    # must appear on the same dashboard day column.
    local_map = get_activity_local_start_map(db_path=db_path, activity_ids=[id1, id2])
    ts1 = local_map.get(id1)
    ts2 = local_map.get(id2)
    if ts1 is not None and ts2 is not None:
        if pd.Timestamp(ts1).date() != pd.Timestamp(ts2).date():
            raise HTTPException(status_code=422, detail="Activities must be on the same day to be merged")

    try:
        merge_id = create_activity_merge(db_path, id1, id2)
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail="One or both activities are already part of a merge",
        ) from exc

    return {"merge_id": merge_id}


@app.delete("/api/v1/activity-merges/{merge_id}")
def delete_merge(
    merge_id: int,
    owner: str | None = Query(default=None),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict[str, Any]:
    ctx = _auth_context(authorization)
    resolved_owner = _resolve_owner(ctx, owner)
    db_path = _db_path_for_owner(resolved_owner)
    deleted = delete_activity_merge(db_path, merge_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Merge not found")
    return {"deleted": True}
```

- [ ] **Step 2.4: Run tests — expect pass**

```bash
python -m unittest backend.tests.test_activity_merges_api -v
```
Expected: all 5 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add backend/app/main.py backend/tests/test_activity_merges_api.py
git commit -m "feat: add POST/DELETE activity-merges endpoints with sport compatibility check"
```

---

## Task 3: Dashboard payload — collapse merged pairs into one card

**Files:**
- Modify: `backend/app/main.py` (add `_build_merged_activity_card`, `_collapse_merged_cards`, update `_build_activity_dashboard_payload`)

This task has no new test file — the existing dashboard endpoint test coverage in `backend/tests/test_mcp_server.py` covers the broader pipeline. Add targeted inline assertions in the test file created in Task 2 if you want (step 3.6).

- [ ] **Step 3.1: Add `_build_merged_activity_card` helper to `backend/app/main.py`**

Add this function near `_build_activity_dashboard_payload` (around line 7990):

```python
def _build_merged_activity_card(
    card1: dict[str, Any],
    card2: dict[str, Any],
    merge_id: int,
) -> dict[str, Any]:
    """Combine two DashboardActivityCard dicts into one merged card.

    card1 and card2 are the assembled dashboard cards (already contain
    duration_label, distance_label, hr_label, etc.).
    We recompute the summary fields from the underlying numeric values
    stored in the cards (tss, rtss, if_pct) using duration-weighted averages.
    """
    # Durations (seconds) for weighting — derive from duration_label is brittle;
    # we rely on tss/rtss being additive and if_pct being weighted.
    # Duration is not stored numerically on the card, so fall back to equal weight.
    tss1 = float(card1.get("tss") or 0.0)
    tss2 = float(card2.get("tss") or 0.0)

    # For IF (intensity factor %) use simple average — we don't have durations on the card.
    if_pct1 = float(card1.get("if_pct") or 0.0)
    if_pct2 = float(card2.get("if_pct") or 0.0)
    if_pct_merged = round((if_pct1 + if_pct2) / 2.0, 1)

    # Distance: parse labels like "42 km" or "42 km eqv.". Use first non-zero.
    def _km_from_label(label: str) -> float:
        import re
        m = re.search(r"([\d.]+)\s*km", str(label or ""))
        return float(m.group(1)) if m else 0.0

    dist1 = _km_from_label(card1.get("distance_label", ""))
    dist2 = _km_from_label(card2.get("distance_label", ""))
    dist_total = dist1 + dist2
    dist_label_suffix = " km eqv." if "eqv" in str(card1.get("distance_label", "")) or "eqv" in str(card2.get("distance_label", "")) else " km"
    distance_label = f"{dist_total:.0f}{dist_label_suffix}" if dist_total > 0 else "0 km"

    # HR: average of the two (simple, not weighted — we don't have duration on card).
    def _hr_from_label(label: str) -> float:
        import re
        m = re.search(r"([\d.]+)b", str(label or ""))
        return float(m.group(1)) if m else 0.0

    hr1 = _hr_from_label(card1.get("hr_label", ""))
    hr2 = _hr_from_label(card2.get("hr_label", ""))
    hr_avg = (hr1 + hr2) / 2.0 if hr1 > 0 and hr2 > 0 else max(hr1, hr2)
    hr_label = f"{hr_avg:.0f}b" if hr_avg > 0 else "-"

    # Intensity token: take the higher intensity of the two.
    intensity_rank = {"green": 0, "blue": 1, "orange": 2, "red": 3}
    def _rank(tok: str) -> int:
        return intensity_rank.get(str(tok or "").lower(), 1)
    intensity = card1["intensity"] if _rank(card1["intensity"]) >= _rank(card2["intensity"]) else card2["intensity"]

    # Duration: sum labels — we concatenate as "Xh Ym + Xh Ym" is ugly;
    # use the start_time of the earlier card and show total in the label field.
    # Since we don't have raw seconds, show the individual labels joined with "+".
    duration_label = f"{card1['duration_label']}+{card2['duration_label']}"

    # The merged card's sport is from the card that started earlier (card1 assumed earlier).
    sport = card1.get("sport") or card2.get("sport") or "Activity"
    start_time_hhmm = card1.get("start_time_hhmm") or card2.get("start_time_hhmm") or ""
    start_time_utc = card1.get("start_time_utc") or card2.get("start_time_utc") or ""

    return {
        "activity_id": f"merged-{merge_id}",
        "sport": sport,
        "is_custom": False,
        "is_invalid": False,
        "is_merged": True,
        "merge_id": merge_id,
        "merged_activity_ids": [
            str(card1["activity_id"]),
            str(card2["activity_id"]),
        ],
        "start_time_utc": start_time_utc,
        "start_time_hhmm": start_time_hhmm,
        "duration_label": duration_label,
        "distance_label": distance_label,
        "hr_label": hr_label,
        "pace_label": card1.get("pace_label") or card2.get("pace_label") or "-",
        "vdot": None,
        "if_pct": if_pct_merged,
        "tss": round(tss1 + tss2, 1),
        "rtss": round(
            float(card1.get("rtss") or 0.0) + float(card2.get("rtss") or 0.0), 1
        ),
        "intensity": intensity,
    }
```

- [ ] **Step 3.2: Add `_collapse_merged_cards` helper**

Add immediately after `_build_merged_activity_card`:

```python
def _collapse_merged_cards(
    actual_cards: list[dict[str, Any]],
    merges_by_id1: dict[str, dict[str, Any]],
    merges_by_id2: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Given a list of dashboard activity cards for one day, replace any
    merged pair with a single merged card. Cards not part of any merge pass through.

    merges_by_id1: {activity_id_1: merge_record}
    merges_by_id2: {activity_id_2: merge_record}
    """
    result: list[dict[str, Any]] = []
    consumed: set[str] = set()

    card_by_id: dict[str, dict[str, Any]] = {c["activity_id"]: c for c in actual_cards}

    for card in actual_cards:
        aid = str(card["activity_id"])
        if aid in consumed:
            continue

        merge = merges_by_id1.get(aid) or merges_by_id2.get(aid)
        if merge is None:
            result.append(card)
            continue

        # Identify the partner.
        partner_id = (
            merge["activity_id_2"] if merge["activity_id_1"] == aid
            else merge["activity_id_1"]
        )
        partner = card_by_id.get(partner_id)
        if partner is None:
            # Partner not in this day (shouldn't happen with same-day constraint, but be safe).
            result.append(card)
            continue

        # Build the merged card — put the earlier activity (lower start_time_utc) first.
        card1, card2 = (
            (card, partner)
            if str(card.get("start_time_utc") or "") <= str(partner.get("start_time_utc") or "")
            else (partner, card)
        )
        result.append(_build_merged_activity_card(card1, card2, int(merge["id"])))
        consumed.add(aid)
        consumed.add(partner_id)

    return result
```

- [ ] **Step 3.3: Load merges in `_build_activity_dashboard_payload` and apply collapsing**

In `_build_activity_dashboard_payload`, after the `wellness_lookup` block is populated (around line 8233), add:

```python
    # Build a lookup of active merges keyed by each activity_id.
    all_merges = get_active_merges(db_path)
    merges_by_id1: dict[str, dict[str, Any]] = {m["activity_id_1"]: m for m in all_merges}
    merges_by_id2: dict[str, dict[str, Any]] = {m["activity_id_2"]: m for m in all_merges}
```

Then, in the `day_cards` loop, after `actual_cards` is assembled (after the `for _, act in day_df.iterrows()` loop ends, before `planned_cards = planned_by_day.get(day, [])`):

```python
            actual_cards = _collapse_merged_cards(actual_cards, merges_by_id1, merges_by_id2)
```

- [ ] **Step 3.4: Run the dashboard endpoint manually to confirm it works**

```bash
cd /path/to/repo && source backend/.venv/bin/activate
python -c "
from pathlib import Path
from backend.app.main import _build_activity_dashboard_payload
payload = _build_activity_dashboard_payload(
    db_path=Path('temperance/data/private/users/admin.db'),
    visible_weeks=1,
    week_offset=0,
    sport=None,
)
print('weeks:', len(payload['weeks']))
if payload['weeks']:
    for day in payload['weeks'][0]['days']:
        for act in day['actual_activities']:
            if act.get('is_merged'):
                print('MERGED:', act)
                break
"
```
Expected: no crash; if a merge exists in the DB, a merged card appears.

- [ ] **Step 3.5: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: collapse merged activity pairs in dashboard payload"
```

---

## Task 4: Activity detail endpoint — handle `merged-{id}` virtual IDs

**Files:**
- Modify: `backend/app/main.py` (extend the `activity_detail` endpoint at line 11122)

- [ ] **Step 4.1: Add a `_parse_merged_activity_id` helper**

Add near `_parse_custom_activity_id`:

```python
def _parse_merged_activity_id(activity_id: str) -> int | None:
    """If activity_id has the form 'merged-{N}', return N. Else None."""
    import re
    m = re.fullmatch(r"merged-(\d+)", str(activity_id or "").strip().lower())
    return int(m.group(1)) if m else None
```

- [ ] **Step 4.2: Add merged-activity handling at the top of `activity_detail`**

In `activity_detail` (line 11122), after `activity_id_norm = _normalize_activity_id(activity_id)`, before `custom_key = _parse_custom_activity_id(...)`, add:

```python
    merge_id = _parse_merged_activity_id(activity_id_norm)
    if merge_id is not None:
        merge = get_activity_merge_by_id(db_path, merge_id)
        if merge is None:
            raise HTTPException(status_code=404, detail="Merged activity not found")

        # Fetch both underlying activity details.
        detail1 = _build_garmin_activity_detail(
            activity_id=merge["activity_id_1"],
            db_path=db_path,
            lthr_curve=lthr_curve,
            pace_curve=pace_curve,
        )
        detail2 = _build_garmin_activity_detail(
            activity_id=merge["activity_id_2"],
            db_path=db_path,
            lthr_curve=lthr_curve,
            pace_curve=pace_curve,
        )

        if detail1 is None or detail2 is None:
            raise HTTPException(
                status_code=404, detail="One or both source activities not found"
            )

        return _merge_activity_details(
            detail1=detail1,
            detail2=detail2,
            merge_id=merge_id,
            activity_id_1=merge["activity_id_1"],
            activity_id_2=merge["activity_id_2"],
        )
```

- [ ] **Step 4.3: Extract `_build_garmin_activity_detail` helper**

The existing `activity_detail` endpoint already has the logic to build a detail response for a Garmin activity (the `custom_key is None` branch, roughly lines 11400–11700). Extract it into a helper function:

```python
def _build_garmin_activity_detail(
    activity_id: str,
    db_path: Path,
    lthr_curve: list,
    pace_curve: list,
) -> dict[str, Any] | None:
    """Build the full detail response dict for a single Garmin activity.
    Returns None if the activity is not found."""
    raw = get_activity_raw(db_path, activity_id)
    if raw is None:
        return None

    splits_raw = get_activity_splits_raw(db_path, activity_id)
    records_df = get_activity_records_df(db_path, activity_id)

    # ... (move the existing Garmin-activity detail-building logic here,
    # replacing `activity_id_norm` references with `activity_id` and
    # returning `response_payload` at the end instead of `return response_payload`)
    # This is a refactor of existing code, not new logic.
    ...
    return response_payload
```

**Implementation note:** The existing `activity_detail` handler has a long Garmin-activity branch starting around line 11400. Move that entire block into `_build_garmin_activity_detail`, change the final `return` to `return response_payload`, and call it from the handler. The handler then becomes:

```python
    # ... (custom_key handling stays as-is) ...
    # (merged-id handling above) ...

    # Garmin activity (original path).
    result = _build_garmin_activity_detail(activity_id_norm, db_path, lthr_curve, pace_curve)
    if result is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    return result
```

- [ ] **Step 4.4: Add `_merge_activity_details`**

```python
def _merge_activity_details(
    detail1: dict[str, Any],
    detail2: dict[str, Any],
    merge_id: int,
    activity_id_1: str,
    activity_id_2: str,
) -> dict[str, Any]:
    """Combine two activity detail dicts into one merged detail response.

    - Scalar metrics (distance, duration, tss, rtss) are summed.
    - HR and pace are duration-weighted averages.
    - split_rows are concatenated with lap indices renumbered.
    - zone_summary seconds are summed.
    """
    a1 = detail1.get("activity", {})
    a2 = detail2.get("activity", {})

    dur1 = float(a1.get("duration_min") or 0.0) * 60.0
    dur2 = float(a2.get("duration_min") or 0.0) * 60.0
    total_dur = dur1 + dur2
    total_dur_min = total_dur / 60.0

    dist1 = float(a1.get("distance_km") or 0.0)
    dist2 = float(a2.get("distance_km") or 0.0)
    total_dist = dist1 + dist2

    # Weighted average HR and pace.
    def _wav(v1: float, w1: float, v2: float, w2: float) -> float:
        if w1 + w2 == 0:
            return 0.0
        return (v1 * w1 + v2 * w2) / (w1 + w2)

    avg_hr = _wav(float(a1.get("avg_hr") or 0), dur1, float(a2.get("avg_hr") or 0), dur2)
    max_hr = max(float(a1.get("max_hr") or 0), float(a2.get("max_hr") or 0))

    # avg_pace: use total_dist / total_dur (s per km).
    if total_dist > 0 and total_dur > 0:
        avg_pace_s_per_km = total_dur / total_dist
        avg_pace_display = _format_pace_short(avg_pace_s_per_km)
    else:
        avg_pace_display = "-"

    tss_total = float(a1.get("tss") or 0) + float(a2.get("tss") or 0)
    rtss_total = float(a1.get("rtss") or 0) + float(a2.get("rtss") or 0)

    # Concatenate split_rows with renumbered laps.
    splits1 = list(detail1.get("split_rows") or [])
    splits2 = list(detail2.get("split_rows") or [])
    combined_splits: list[dict[str, Any]] = []
    for s in splits1:
        combined_splits.append(dict(s))
    offset = len(splits1)
    for i, s in enumerate(splits2):
        row = dict(s)
        row["lap"] = offset + i + 1
        combined_splits.append(row)

    # Sum zone seconds.
    zones_map: dict[str, float] = {}
    for zrow in (detail1.get("zone_summary") or []) + (detail2.get("zone_summary") or []):
        z = str(zrow.get("zone") or "")
        zones_map[z] = zones_map.get(z, 0.0) + float(zrow.get("seconds") or 0.0)
    zone_total = max(sum(zones_map.values()), 1.0)
    zone_summary = [
        {"zone": z, "seconds": round(s, 1), "pct": round(s / zone_total * 100.0, 1)}
        for z, s in sorted(zones_map.items())
    ]

    # Use the earlier activity's date/time.
    start1 = str(a1.get("start_time_utc") or "")
    start2 = str(a2.get("start_time_utc") or "")
    start_time_utc = start1 if start1 <= start2 else start2
    date = (detail1 if start1 <= start2 else detail2).get("activity", {}).get("date", "")

    return {
        "owner": detail1.get("owner", ""),
        "is_merged": True,
        "merge_id": merge_id,
        "merged_activity_ids": [activity_id_1, activity_id_2],
        "activity": {
            "activity_id": f"merged-{merge_id}",
            "date": date,
            "start_time_utc": start_time_utc,
            "sport_type": a1.get("sport_type") or a2.get("sport_type") or "unknown",
            "distance_km": round(total_dist, 2),
            "duration_min": round(total_dur_min, 2),
            "avg_pace_display": avg_pace_display,
            "avg_hr": round(avg_hr, 1),
            "max_hr": round(max_hr, 1),
            "tss": round(tss_total, 1),
            "rtss": round(rtss_total, 1),
            "training_load_garmin": round(
                float(a1.get("training_load_garmin") or 0)
                + float(a2.get("training_load_garmin") or 0),
                1,
            ),
        },
        "details": {"source": "merged"},
        "split_rows": combined_splits,
        "zone_summary": zone_summary,
    }
```

- [ ] **Step 4.5: Verify manually**

After creating a merge via the API (or by direct DB insert), call the detail endpoint:

```bash
curl -s "http://127.0.0.1:8000/api/v1/activities/merged-1" \
  -H "Authorization: Bearer <token>" | python3 -m json.tool | head -40
```
Expected: `activity_id` is `"merged-1"`, `is_merged` is `true`, `split_rows` is concatenation.

- [ ] **Step 4.6: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: activity detail endpoint handles merged-{id} virtual IDs"
```

---

## Task 5: Frontend types + API service

**Files:**
- Modify: `frontend/src/features/dashboard/types/dashboard.ts`
- Create: `frontend/src/features/dashboard/services/activity-merge-api.ts`

- [ ] **Step 5.1: Extend `DashboardActivityCard` with merge fields**

In `frontend/src/features/dashboard/types/dashboard.ts`, change:

```typescript
export interface DashboardActivityCard {
  activity_id: string;
  sport: string;
  is_custom?: boolean;
  is_invalid?: boolean;
  day_utc?: string;
  line_no?: number;
  activity_text?: string;
  start_time_hhmm?: string;
  start_time_utc?: string;
  duration_label: string;
  distance_label: string;
  hr_label: string;
  pace_label: string;
  vdot?: number | null;
  if_pct: number;
  tss: number;
  rtss: number;
  intensity: 'green' | 'blue' | 'orange' | 'red' | string;
}
```

to:

```typescript
export interface DashboardActivityCard {
  activity_id: string;
  sport: string;
  is_custom?: boolean;
  is_invalid?: boolean;
  is_merged?: boolean;
  merge_id?: number;
  merged_activity_ids?: string[];
  day_utc?: string;
  line_no?: number;
  activity_text?: string;
  start_time_hhmm?: string;
  start_time_utc?: string;
  duration_label: string;
  distance_label: string;
  hr_label: string;
  pace_label: string;
  vdot?: number | null;
  if_pct: number;
  tss: number;
  rtss: number;
  intensity: 'green' | 'blue' | 'orange' | 'red' | string;
}
```

- [ ] **Step 5.2: Create `activity-merge-api.ts`**

Create `frontend/src/features/dashboard/services/activity-merge-api.ts`:

```typescript
import { apiBase, authHeaders } from '@/api/config';

export async function createActivityMerge(
  activityId1: string,
  activityId2: string,
): Promise<{ merge_id: number }> {
  const resp = await fetch(`${apiBase}/api/v1/activity-merges`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ activity_id_1: activityId1, activity_id_2: activityId2 }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<{ merge_id: number }>;
}

export async function deleteActivityMerge(mergeId: number): Promise<void> {
  const resp = await fetch(`${apiBase}/api/v1/activity-merges/${mergeId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `HTTP ${resp.status}`);
  }
}
```

- [ ] **Step 5.3: Confirm TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: build succeeds (zero TS errors).

- [ ] **Step 5.4: Commit**

```bash
git add frontend/src/features/dashboard/types/dashboard.ts \
        frontend/src/features/dashboard/services/activity-merge-api.ts
git commit -m "feat: add merge fields to DashboardActivityCard + activity-merge-api service"
```

---

## Task 6: Frontend — merge affordance on dashboard cards

**Files:**
- Modify: `frontend/src/features/dashboard/components/dashboard-day-column.tsx`
- Modify: `frontend/src/features/dashboard/pages/dashboard-page.tsx`

### UX flow:
1. Each actual activity card shows a small "link" icon (Lucide `Link2`) button.
2. Clicking it sets `mergePendingId` in dashboard page state.
3. While `mergePendingId` is set: the pending card shows a highlighted ring + a cancel (`X`) button. Compatible activity cards on any day show a "merge here" (`Link`) button.
4. Clicking the "merge here" button calls `createActivityMerge`, then invalidates the dashboard query. `mergePendingId` is cleared.
5. A **merged card** shows: a `Link2` badge on its sport icon, `duration_label` like "45m+30m", and an `Unlink` icon button that calls `deleteActivityMerge`.
6. Clicking a merged card's activity area still opens the splits drawer (with concatenated splits from `merged-{id}`).

- [ ] **Step 6.1: Add `mergePendingId` state and mutations to `dashboard-page.tsx`**

In `dashboard-page.tsx`, after the existing `useState` declarations, add:

```tsx
const [mergePendingId, setMergePendingId] = useState<string | null>(null);

const mergeMutation = useMutation({
  mutationFn: ({ id1, id2 }: { id1: string; id2: string }) =>
    createActivityMerge(id1, id2),
  onSuccess: () => {
    setMergePendingId(null);
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  },
});

const unmergeMutation = useMutation({
  mutationFn: (mergeId: number) => deleteActivityMerge(mergeId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
  },
});
```

Import at top of file:
```tsx
import { createActivityMerge, deleteActivityMerge } from '@/features/dashboard/services/activity-merge-api';
```

Pass to each `DashboardWeekCard`:
```tsx
mergePendingId={mergePendingId}
onStartMerge={(activityId) => setMergePendingId(activityId)}
onCancelMerge={() => setMergePendingId(null)}
onConfirmMerge={(activityId) => {
  if (mergePendingId) {
    mergeMutation.mutate({ id1: mergePendingId, id2: activityId });
  }
}}
onUnmerge={(mergeId) => unmergeMutation.mutate(mergeId)}
isMerging={mergeMutation.isPending}
isUnmerging={unmergeMutation.isPending}
```

- [ ] **Step 6.2: Thread props through `DashboardWeekCard` to `DashboardDayColumn`**

In `frontend/src/features/dashboard/components/dashboard-week-card.tsx`, add the new props to the component's interface and forward them to each `<DashboardDayColumn>` render. The exact forwarding mirrors the existing `onSelectActivity` pattern already in the file. No logic changes in `dashboard-week-card.tsx` — pure prop forwarding.

- [ ] **Step 6.3: Update `DashboardDayColumn` interface and card rendering**

In `dashboard-day-column.tsx`, extend the interface:

```tsx
interface DashboardDayColumnProps {
  // ... existing props ...
  mergePendingId?: string | null;
  onStartMerge?: (activityId: string) => void;
  onCancelMerge?: () => void;
  onConfirmMerge?: (activityId: string) => void;
  onUnmerge?: (mergeId: number) => void;
  isMerging?: boolean;
  isUnmerging?: boolean;
}
```

In the actual activity card rendering block (the `day.actual_activities.map(...)` render), add the following logic:

**For a normal (unmerged) card:**
```tsx
{/* Merge trigger button */}
{!activity.is_merged && onStartMerge && (
  <button
    type="button"
    onClick={(e) => {
      e.stopPropagation();
      if (mergePendingId === activity.activity_id) {
        onCancelMerge?.();
      } else if (mergePendingId) {
        onConfirmMerge?.(activity.activity_id);
      } else {
        onStartMerge(activity.activity_id);
      }
    }}
    className={cn(
      'absolute top-1 right-1 p-0.5 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity',
      mergePendingId === activity.activity_id && 'opacity-100 text-blue-400',
      mergePendingId && mergePendingId !== activity.activity_id && 'opacity-60 text-emerald-400',
    )}
    title={
      mergePendingId === activity.activity_id
        ? 'Cancel merge'
        : mergePendingId
          ? 'Merge with this activity'
          : 'Start merge'
    }
  >
    {mergePendingId === activity.activity_id ? <X size={12} /> : <Link2 size={12} />}
  </button>
)}
```

**For a merged card** (add a badge and unmerge button):
```tsx
{activity.is_merged && (
  <>
    {/* Merged badge on sport icon */}
    <Link2 size={10} className="inline ml-1 text-sky-400 opacity-70" />
    {/* Unmerge button */}
    {onUnmerge && activity.merge_id != null && (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onUnmerge(activity.merge_id!);
        }}
        className="absolute top-1 right-1 p-0.5 rounded opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity text-rose-400"
        title="Unmerge activities"
        disabled={isUnmerging}
      >
        <Unlink size={12} />
      </button>
    )}
  </>
)}
```

Add `Link2`, `Unlink` to the Lucide import line at the top of `dashboard-day-column.tsx`.

- [ ] **Step 6.4: Start dev server and test the merge flow manually**

```bash
cd frontend && npm run dev
```

1. Open the dashboard in a browser.
2. Find a day with two running activities.
3. Hover over the first activity card — the `Link2` icon appears.
4. Click it — the card gets a blue ring and the `Link2` icon on the other cards turns green.
5. Click the green icon on the second activity — the two cards collapse into one merged card showing the summed stats and a `Link2` badge.
6. Hover the merged card — the `Unlink` icon appears in the top-right.
7. Click `Unlink` — the merged card splits back into two.
8. Click the merged card's body — the splits drawer opens showing concatenated splits.

- [ ] **Step 6.5: TypeScript build check**

```bash
cd frontend && npm run build 2>&1 | tail -10
```
Expected: zero errors.

- [ ] **Step 6.6: Commit**

```bash
git add frontend/src/features/dashboard/components/dashboard-day-column.tsx \
        frontend/src/features/dashboard/components/dashboard-week-card.tsx \
        frontend/src/features/dashboard/pages/dashboard-page.tsx
git commit -m "feat: add merge/unmerge affordance to dashboard activity cards"
```

---

## Self-Review Against Spec

| Requirement | Covered by |
|-------------|-----------|
| Separate table pointing to original activities | Task 1 (`activity_merges` table) |
| Frontend renders merged activities together | Task 3 (payload collapsing) + Task 6 (merged card) |
| Sum up metrics | Task 3 (`_build_merged_activity_card`), Task 4 (`_merge_activity_details`) |
| Treat as concatenated splits | Task 4 (`_merge_activity_details` split_rows concat) |
| Same-type restriction | Task 2 (`_merge_compatible` check) |
| run+treadmill exception | Task 2 (`MERGE_COMPAT_GROUPS` puts all run-likes in one group) |
| Unmerge | Task 2 (DELETE endpoint) + Task 6 (Unlink button) |
| Custom activities excluded | Task 2 (source check in POST handler) |
| Same-day constraint | Task 2 (local date check in POST handler) |
| One-merge-per-activity | Task 1 (UNIQUE constraints on both columns) |

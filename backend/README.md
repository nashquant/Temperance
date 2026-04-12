# Temperance Backend

The backend is the local server that powers the app. It handles auth, Garmin sync, training analytics, planning, and the MCP coaching interface. Everything runs on your machine — no cloud dependency for core function.

## Start the server

```bash
cd backend
source .venv/bin/activate
./run.sh
```

API available at `http://127.0.0.1:8000`. The frontend proxies to this during local development.

First-time setup:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## MCP coaching tools

The MCP server gives a Claude-based client doctrine-aware coaching context: what the current build is doing, how recent training looks against it, and what makes sense tomorrow.

```bash
# from repo root
python3 -m backend.app.mcp_server --stdio
```

Claude Desktop / Claude Code config:

```json
{
  "mcpServers": {
    "temperance": {
      "command": "python3",
      "args": ["-m", "backend.app.mcp_server"],
      "cwd": "/absolute/path/to/Temperance"
    }
  }
}
```

Useful starting prompts once connected:

- `Read the active build and tell me which doctrine files matter most before planning tomorrow.`
- `Why is tomorrow hard?`
- `Judge the last 6 weeks of actual training against the active build and point out the main gaps.`
- `If I swap this run for elliptical, how does the next 3-day cycle change?`
- `For week 2026-03-30, confirm that MCP weekly baseline matches Athlete Progression Base.`

## Tools and resources

**Planning**
- `plan_next_day`, `preview_cycle`, `explain_planning_decision`

**Analytics and status**
- `get_today_status`, `get_coaching_brief`, `get_fitness_form`, `get_week_outlook`
- `get_recent_activities`, `get_planned_activities`, `get_load_trend`, `get_recovery_trend`, `get_activity_detail`

**History**
- `judge_training_history`, `explain_history_judgment`

**Load analysis**
- `estimate_workout_tss`, `simulate_plan_week`, `critique_day_plan`, `estimate_xtrain_tss`, `search_workouts`

**Writes and admin**
- `save_planned_activities`, `update_planned_activity`, `delete_planned_activities`, `mark_planned_done`
- `save_custom_activities`, `delete_custom_activities`
- `trigger_sync`, `get_sync_status`, `get_settings`, `update_settings`

**Resources**
- `temperance://guidelines/read-order` — doctrine read order
- `temperance://guidelines/core-bundle` — core guideline set
- `temperance://guidelines/active-build` — current build context
- `temperance://workouts/overview` and `temperance://workouts/catalog`
- `temperance://planning/context/{owner}/{target_day_utc}`
- `temperance://history/snapshot/{owner}/{window_days}`

## Weekly baseline contract

`get_fitness_form.weekly_baseline` must match the Athlete Progression `Base` line in the frontend. The path:

1. Start from LT-derived weekly capacity.
2. Blend with trailing 21/63/365-day TSS load history.
3. Expose Monday-labeled weekly points — no extra EMA layer on top.

If they diverge materially, it is a bug. Backend and MCP use the same helper so the numbers should agree to within rounding.

## After code changes

```bash
./temperance/scripts/install_keepalive.sh restart
```

Required whenever a backend process restart is needed (e.g. adding endpoints, changing imports).

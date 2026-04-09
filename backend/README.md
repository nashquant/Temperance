# Temperance Backend

## MCP Server

Temperance exposes one canonical stdio MCP server at `backend/app/mcp_server.py`.

This server gives an MCP client access to:
- planning tools
- analytics and status tools
- doctrine resources and workout-library context
- write tools for planned/custom activities and admin actions

The MCP server is not a separate analytics engine. It is a thin interface over the backend logic in [`backend/app/main.py`](/Users/matheus/Temperance/backend/app/main.py).

## Quick start

Run it from the repo root:

```bash
python3 -m backend.app.mcp_server --stdio
```

Example MCP client config:

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

The server exposes standard MCP `tools` and `resources`.

## Baseline rules

The weekly baseline shown by MCP is the same baseline used by Athlete Progression. This is the current contract:

1. Start from LT-derived weekly capacity.
2. Blend that capacity with trailing load history using the prior 21, 63, and 365 days of TSS.
3. Use that blended model directly as the canonical baseline; there is no extra post-blend EMA layer.
4. Expose Monday-labeled weekly baseline points using the latest modeled baseline observed within each week.
5. Expose those weekly points through `get_fitness_form.weekly_baseline`.

Practical interpretation:
- MCP does not own an alternate baseline formula.
- If the dashboard shows `Base = X` for a given Monday week, MCP should return approximately the same `baseline_tss` for that same `week_start`.
- If they diverge materially, treat it as a bug, version mismatch, or data mismatch.
- Backend and MCP now use the same formatter/helper for weekly baseline rows, including deviation explanation fields.
- If a Monday-labeled week has no modeled point yet, the dashboard leaves `baseline_tss` blank rather than fabricating a carry-forward weekly value.

## Main tools

Available tools:
- planning:
  - `plan_next_day`
  - `preview_cycle`
  - `explain_planning_decision`
- analytics / data:
  - `get_today_status`
  - `get_recent_activities`
  - `get_planned_activities`
  - `get_week_outlook`
  - `get_load_trend`
  - `get_recovery_trend`
  - `get_activity_detail`
- history:
  - `judge_training_history`
  - `explain_history_judgment`

Also available:
- load analysis:
  - `estimate_workout_tss`
  - `simulate_plan_week`
  - `critique_day_plan`
  - `estimate_xtrain_tss`
  - `search_workouts`
- writes/admin:
  - `save_planned_activities`
  - `update_planned_activity`
  - `delete_planned_activities`
  - `mark_planned_done`
  - `save_custom_activities`
  - `delete_custom_activities`
  - `trigger_sync`
  - `get_sync_status`
  - `mark_activity_invalid`
  - `get_settings`
  - `update_settings`

## Resources

Static resources:
- `temperance://guidelines/read-order`
- `temperance://guidelines/core-bundle`
- `temperance://guidelines/active-build`
- `temperance://workouts/overview`
- `temperance://workouts/catalog`

Resource templates:
- `temperance://guidelines/doc/{doc_id}`
- `temperance://workouts/family/{session_family}`
- `temperance://workouts/template/{template_id}`
- `temperance://planning/context/{owner}/{target_day_utc}`
- `temperance://history/snapshot/{owner}/{window_days}`

## Example requests

Example `resources/read` request:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "resources/read",
  "params": {
    "uri": "temperance://planning/context/admin/2026-04-05"
  }
}
```

Example `judge_training_history` arguments:

```json
{
  "owner": "admin",
  "window_days": 42,
  "include_planned_comparison": true
}
```

Useful prompts once the MCP tool is connected:

- `Read the active build and tell me which doctrine files matter most before planning tomorrow.`
- `Why is tomorrow hard?`
- `Why not put the long run on Friday?`
- `If I swap this run for elliptical, how does the next 3-day cycle change?`
- `Show me how the long run is progressing from the last 4 long runs.`
- `Judge the last 6 weeks of actual training against the active build and point out the main gaps.`
- `For week 2026-03-30, confirm that MCP weekly baseline matches Athlete Progression Base and explain any residual difference.`

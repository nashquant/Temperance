# Temperance Backend

## MCP Server

Temperance now exposes one canonical stdio MCP server that combines doctrine resources, workout-library context, planning tools, analytics tools, and history judgment on one JSON-RPC surface.

Run it from the repo root:

```bash
python3 -m backend.app.mcp_server
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

The server advertises:
- `tools: {}`
- `resources: {}`

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
- deprecated heuristic tools:
  - `recommend_training`
  - `explain_recommendation`
- history:
  - `judge_training_history`
  - `explain_history_judgment`

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

Useful chat questions once the MCP tool is connected:

- `Read the active build and tell me which doctrine files matter most before planning tomorrow.`
- `Why is tomorrow hard?`
- `Why not put the long run on Friday?`
- `If I swap this run for elliptical, how does the next 3-day cycle change?`
- `Show me how the long run is progressing from the last 4 long runs.`
- `Judge the last 6 weeks of actual training against the active build and point out the main gaps.`

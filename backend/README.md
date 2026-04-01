# Temperance Backend

## MCP Server

Temperance now exposes a small stdio MCP server that calls the same planning engine used by `/api/v1/generated-activity`.

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

Available tools:

- `plan_next_day`
  - Inputs: `owner`, `target_day_utc`, `mode`, `activity_type_preference`, `previous_activity_text`, `methodology_id`, `seed`, `schedule_constraints`
  - Returns: workout string plus full planning metadata
- `preview_cycle`
  - Inputs: `owner`, `target_day_utc`, `methodology_id`, `seed`, `horizon_days`, `schedule_constraints`
  - Returns: the upcoming rolling horizon, recent long-run history, and preview metadata
- `explain_planning_decision`
  - Inputs: same planning inputs plus optional `question`
  - Returns: the structured planning payload plus a concise text explanation

Example `plan_next_day` arguments:

```json
{
  "owner": "default",
  "target_day_utc": "2026-04-05",
  "activity_type_preference": "running",
  "methodology_id": "rolling_3_day_v1",
  "seed": 17
}
```

Example `preview_cycle` arguments:

```json
{
  "owner": "default",
  "target_day_utc": "2026-04-05",
  "methodology_id": "rolling_3_day_v1",
  "horizon_days": 9
}
```

Useful chat questions once the MCP tool is connected:

- `Why is tomorrow hard?`
- `Why not put the long run on Friday?`
- `If I swap this run for elliptical, how does the next 3-day cycle change?`
- `Show me how the long run is progressing from the last 4 long runs.`

from __future__ import annotations

import json
import sys
from typing import Any

from backend.app import main as backend_main
from temperance.planning import get_methodology, preview_horizon


def _tool_schema_plan_next_day() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "target_day_utc": {"type": "string"},
            "mode": {"type": "string", "enum": ["planned", "custom"], "default": "planned"},
            "activity_type_preference": {"type": "string", "enum": ["running", "elliptical", "bike"]},
            "previous_activity_text": {"type": "string"},
            "methodology_id": {"type": "string"},
            "seed": {"type": "integer"},
            "schedule_constraints": {"type": "array"},
        },
        "required": ["target_day_utc"],
    }


def _tool_schema_preview_cycle() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "target_day_utc": {"type": "string"},
            "methodology_id": {"type": "string"},
            "seed": {"type": "integer"},
            "horizon_days": {"type": "integer"},
            "schedule_constraints": {"type": "array"},
        },
        "required": ["target_day_utc"],
    }


def _tool_schema_explain() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "target_day_utc": {"type": "string"},
            "mode": {"type": "string", "enum": ["planned", "custom"], "default": "planned"},
            "activity_type_preference": {"type": "string", "enum": ["running", "elliptical", "bike"]},
            "previous_activity_text": {"type": "string"},
            "methodology_id": {"type": "string"},
            "seed": {"type": "integer"},
            "question": {"type": "string"},
            "schedule_constraints": {"type": "array"},
        },
        "required": ["target_day_utc"],
    }


def _tool_list() -> list[dict[str, Any]]:
    return [
        {
            "name": "plan_next_day",
            "description": "Generate the next workout suggestion plus the full planning decision metadata.",
            "inputSchema": _tool_schema_plan_next_day(),
        },
        {
            "name": "preview_cycle",
            "description": "Preview the next cycle horizon using the selected methodology and current athlete state.",
            "inputSchema": _tool_schema_preview_cycle(),
        },
        {
            "name": "explain_planning_decision",
            "description": "Explain why the planner chose the current intent, including long-run and weekend constraints.",
            "inputSchema": _tool_schema_explain(),
        },
    ]


def _coerce_constraints(args: dict[str, Any]) -> list[dict[str, Any]]:
    constraints = args.get("schedule_constraints")
    if not isinstance(constraints, list):
        return []
    out: list[dict[str, Any]] = []
    for item in constraints:
        if not isinstance(item, dict):
            continue
        day_utc = str(item.get("day_utc") or "").strip()
        if not day_utc:
            continue
        out.append(
            {
                "day_utc": day_utc,
                "allow_long_run": item.get("allow_long_run"),
                "preferred_modality": str(item.get("preferred_modality") or "").strip().lower() or None,
                "blocked": bool(item.get("blocked")),
            }
        )
    return out


def _build_preview_payload(args: dict[str, Any]) -> dict[str, Any]:
    owner = str(args.get("owner") or "default").strip() or "default"
    day_utc = str(args.get("target_day_utc") or "").strip()
    methodology_id = str(args.get("methodology_id") or "").strip() or None
    seed = int(args["seed"]) if args.get("seed") is not None else None
    horizon_days = int(args["horizon_days"]) if args.get("horizon_days") is not None else None
    db_path = backend_main._db_path_for_owner(owner)
    pace_curve = backend_main._load_curve_points(
        db_path=db_path,
        key=backend_main.SETTINGS_KEY_LT_PACE_CURVE,
        value_key="lt_pace_sec",
        fallback_value=backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM,
    )
    pace_default = float(pace_curve[-1][1]) if pace_curve else backend_main.DEFAULT_THRESHOLD_PACE_SEC_PER_KM
    day_ts = backend_main.pd.to_datetime(day_utc, utc=True, errors="coerce")
    pace_for_day = float(backend_main._curve_value_at(pace_curve, pace_default, day_ts))
    planning_state = backend_main._generated_activity_planning_state(
        db_path=db_path,
        day_utc=day_utc,
        threshold_pace_sec_per_km=pace_for_day,
        methodology_id=methodology_id,
        schedule_constraints=_coerce_constraints(args),
    )
    if planning_state is None:
        raise ValueError("Invalid target_day_utc")
    methodology = get_methodology(methodology_id)
    horizon, preview_meta = preview_horizon(
        state=planning_state,
        methodology_id=methodology.methodology_id,
        seed=seed,
        horizon_days=horizon_days,
    )
    return {
        "owner": owner,
        "methodology_id": methodology.methodology_id,
        "target_day_utc": day_utc,
        "preview": [
            {
                "day_utc": intent.day_utc,
                "cycle_step_id": intent.cycle_step_id,
                "day_type": intent.day_type.value,
                "hard_subtype": intent.hard_subtype.value if intent.hard_subtype is not None else None,
                "target_tss": intent.target_tss,
                "sampled_tss_share": intent.sampled_tss_share,
                "target_duration_min": intent.target_duration_min,
                "modality_bias": intent.modality_bias,
                "planned_rest": intent.planned_rest,
            }
            for intent in horizon
        ],
        "recent_long_runs": [
            {
                "day_utc": item.day_utc,
                "duration_min": item.duration_min,
                "avg_if": item.avg_if,
                "tss": item.tss,
                "source": item.source,
            }
            for item in planning_state.recent_long_runs
        ],
        "preview_meta": preview_meta,
    }


def _explain_response(plan_payload: dict[str, Any], question: str | None = None) -> str:
    planning = dict(plan_payload.get("planning") or {})
    selected = dict(planning.get("selected_intent") or {})
    explanation = dict(planning.get("explanation") or {})
    lines = [
        f"Methodology: {planning.get('methodology_id') or explanation.get('methodology_id') or 'unknown'}",
        f"Cycle step: {selected.get('cycle_step_id') or explanation.get('cycle_step_id') or 'unknown'}",
        f"Selected day type: {selected.get('day_type') or explanation.get('next_day_type') or 'unknown'}",
        f"Sampled target: {round(float(selected.get('target_tss') or 0.0), 1)} TSS from share {round(float(selected.get('sampled_tss_share') or 0.0) * 100.0, 1)}%",
    ]
    if selected.get("hard_subtype"):
        lines.append(f"Hard subtype: {selected['hard_subtype']}")
    if explanation.get("weekend_adjustment"):
        lines.append(f"Weekend adjustment: {explanation['weekend_adjustment']}")
    if explanation.get("long_run_progression_reason"):
        lines.append(f"Long-run progression: {explanation['long_run_progression_reason']}")
    if explanation.get("candidate_rejections"):
        lines.append(f"Candidate rejections: {', '.join(explanation['candidate_rejections'])}")
    if question:
        lines.append(f"Question: {question}")
    return "\n".join(lines)


def call_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    tool_name = str(name or "").strip()
    if tool_name == "plan_next_day":
        owner = str(args.get("owner") or "default").strip() or "default"
        payload, _ = backend_main._planning_decision_for_owner(
            owner=owner,
            day_utc=str(args.get("target_day_utc") or "").strip(),
            mode=str(args.get("mode") or "planned").strip().lower() or "planned",
            activity_type=str(args.get("activity_type_preference") or "").strip().lower() or None,
            previous_activity_text=str(args.get("previous_activity_text") or "").strip() or None,
            seed=int(args["seed"]) if args.get("seed") is not None else None,
            methodology_id=str(args.get("methodology_id") or "").strip() or None,
            schedule_constraints=_coerce_constraints(args),
        )
        return payload
    if tool_name == "preview_cycle":
        return _build_preview_payload(args)
    if tool_name == "explain_planning_decision":
        owner = str(args.get("owner") or "default").strip() or "default"
        payload, _ = backend_main._planning_decision_for_owner(
            owner=owner,
            day_utc=str(args.get("target_day_utc") or "").strip(),
            mode=str(args.get("mode") or "planned").strip().lower() or "planned",
            activity_type=str(args.get("activity_type_preference") or "").strip().lower() or None,
            previous_activity_text=str(args.get("previous_activity_text") or "").strip() or None,
            seed=int(args["seed"]) if args.get("seed") is not None else None,
            methodology_id=str(args.get("methodology_id") or "").strip() or None,
            schedule_constraints=_coerce_constraints(args),
        )
        return {
            "planning": payload.get("planning"),
            "answer": _explain_response(payload, str(args.get("question") or "").strip() or None),
        }
    raise ValueError(f"Unknown tool: {tool_name}")


class TemperanceMCPServer:
    server_name = "temperance-planner"
    protocol_version = "2024-11-05"

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        method = str(request.get("method") or "")
        request_id = request.get("id")
        params = request.get("params") or {}
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "serverInfo": {"name": self.server_name, "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                },
            }
        if method == "initialized":
            return None
        if method == "ping":
            return {"jsonrpc": "2.0", "id": request_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _tool_list()}}
        if method == "tools/call":
            tool_name = str(params.get("name") or "").strip()
            args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            try:
                result = call_tool(tool_name, args)
            except Exception as exc:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2, sort_keys=True)}],
                    "structuredContent": result,
                },
            }
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }


def _read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        name, value = line.decode("utf-8").split(":", 1)
        headers[name.strip().lower()] = value.strip()
    content_length = int(headers.get("content-length") or "0")
    if content_length <= 0:
        return None
    raw = sys.stdin.buffer.read(content_length)
    return json.loads(raw.decode("utf-8"))


def _write_message(message: dict[str, Any]) -> None:
    encoded = json.dumps(message, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    server = TemperanceMCPServer()
    while True:
        request = _read_message()
        if request is None:
            return 0
        response = server.handle_request(request)
        if response is not None:
            _write_message(response)


if __name__ == "__main__":
    raise SystemExit(main())

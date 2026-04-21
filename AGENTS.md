# AGENTS.md

Follow `CORE.md` first; this file only adds Codex-specific operational notes.
System and Codex runtime instructions still take precedence over repository
docs.

## Codex Notes

- Shared project commands, migrations, invariants, and validation expectations
  live in `CORE.md`.
- Keep edits scoped to the requested files or the smallest needed module set.
- Preserve unrelated uncommitted work in this repository.
- When prior decisions, fixes, or session history are relevant, use claude-mem
  in this order: `search`, then `timeline`, then `get_observations` for only the
  filtered IDs needed.

## Project Pointers

- Workout strings and `weekly_baseline` are hard project invariants owned by
  `CORE.md`.
- Dynamic memory summaries belong in generated context, not in committed
  instruction files.

# AGENTS.md

Follow `CORE.md` first; this file adds operational notes shared across agent
runtimes. System and runtime instructions still take precedence over repository
docs.

## Notes

- Shared project commands, migrations, invariants, and validation expectations
  live in `CORE.md`.
- Keep edits scoped to the requested files or the smallest needed module set.
- Preserve unrelated uncommitted work in this repository.

## Project Pointers

- Workout strings and `weekly_baseline` are hard project invariants owned by
  `CORE.md`.
- Dynamic memory summaries belong in generated context, not in committed
  instruction files.
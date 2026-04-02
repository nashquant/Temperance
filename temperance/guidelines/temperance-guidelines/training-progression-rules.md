# Training Progression Rules

Status: practical cheat sheet.

The authoritative planning stack now lives in:
- `training-control-system-doctrine.md`
- `training-phase-doctrine.md`
- `training-recent-cache.local.md` when present, otherwise `training-recent-cache.md`
- the active overlay set named in the active build declaration

Use this file as a compact operational summary only. If any detail here conflicts with the invariant core or active build declaration, the core and active build win.

## Core workflow

- Start with the active build declaration, not with isolated session intuition.
- Map the core terms to the actual metrics used in the current build.
- For dense phase intent, read `training-phase-doctrine.md`.
- Apply precedence in this order: core, current-state constraints / athlete-state overlay, event overlay, philosophy overlay.
- Anchor recommendations to projected **weekly total_load** and **weekly primary_specific_load**.
- If the build has a **key_duration_anchor**, track it explicitly rather than burying it inside total load.
- Treat load class and hard-session subtype as separate decisions.
- Preserve the declared local spacing and rolling density windows.
- Choose hard-session type intentionally rather than merely counting hard days.
- Progress primary_specific_load relative to baseline, with an absolute sanity check.
- Progress specificity only when the current structure is being absorbed coherently.
- Progress the key duration anchor only after the prior exposure was absorbed acceptably.
- Let the athlete-state overlay tighten the plan when the body demands it.
- Let the event overlay define specificity and what a good week means.
- Let the philosophy overlay choose stimulus mix and quality hierarchy inside those constraints.
- Let alerts hold, redirect, or reduce before forcing more progression.

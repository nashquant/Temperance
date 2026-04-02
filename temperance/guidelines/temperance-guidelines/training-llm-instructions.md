# Training LLM Instructions

Status: invariant core companion.

## Purpose

This file tells an LLM how to read and use the training doctrine stack when the documents are supplied through Temperance MCP or another machine context layer.

## Read order

Read the stack in this order:

1. `training-doctrine-governance.md`
2. `training-control-system-doctrine.md`
3. `training-phase-doctrine.md`
4. `training-overlay-contract.md`
5. `training-recent-cache.local.md` if present, otherwise `training-recent-cache.md`
6. the athlete-state, event, and philosophy profiles named in the active build declaration
7. `training-history-memo.local.md` if present, otherwise `training-history-memo.md`, only when deeper evidence is needed
8. `training-phase-transition-checklists.md` when the question is about phase changes
9. `training-progression-rules.md` when a compact operational summary is useful

If the task is to choose or suggest a concrete workout template, also read:

10. `temperance/guidelines/temperance-workouts/README.md`
11. `temperance/guidelines/temperance-workouts/template-contract.md`
12. `temperance/guidelines/temperance-workouts/quick-reference.md` when a distilled view is enough
13. `temperance/guidelines/temperance-workouts/catalog.md` when you need the full list
14. `temperance/guidelines/temperance-workouts/taxonomy.md`
15. the relevant workout-template file for the chosen family

## Local/private resolution

- Prefer `*.local.md` over the tracked file with the same base name whenever both exist.
- Treat `*.local.md` files as the private current source for personal history, current build state, or local experiments.
- Treat tracked non-local files as repo-safe doctrine, templates, or reusable defaults.

## Precedence

Apply doctrine layers in this order:

1. invariant core
2. active current-state constraints and athlete-state overlay
3. event overlay
4. philosophy overlay

Never let a lower-precedence layer silently override a higher-precedence constraint.

## Interpretation rules

- Do not infer the current build from the history memo if the active build declaration already exists.
- Use the history memo as evidence, not as the active state.
- Use the active anchor mapping before reasoning about metrics.
- Distinguish clearly between invariant doctrine, active build facts, evidence from history, and your own inference.
- If an event overlay and philosophy overlay pull in different directions, keep the event demands but bias execution using the philosophy overlay.
- If a current-state constraint conflicts with the preferred philosophy, current-state safety wins.

## Recommendation behavior

When using this doctrine to plan or interpret training:

- Anchor recommendations to the current weekly load budget.
- Name which phase the build is in and which overlay set is active.
- Explain recommendations through hard-session type, spacing, density, and progression control rather than only intensity labels.
- Preserve some background contact with non-dominant qualities unless the active build explicitly says not to.
- During Base / Capacity Build, do not collapse the block into one monotone middle intensity lane.

## Workout-template behavior

When selecting from the workout-template repository:

- choose `load_role` and doctrine-facing `category` before choosing the specific template
- choose `session_family` before narrowing to the exact structure
- use `structural_subtype` and `modality_pattern` to narrow the family
- read repository-level contract rules before treating template prose as authoritative
- prefer the nearest stored variant inside the template's scaling band before inventing a new rewrite
- preserve the session's identity when scaling; prefer rep-count or small support-volume changes over changing the category
- treat the stored template TSS as the library reference estimate, not as athlete-specific truth
- keep the stored recovery structure unless there is a clear reason to override it
- if interval delineation is not specified, treat the in-between handling as user discretion rather than inventing a recovery prescription
- treat LT1 and LT2 as distinct threshold bands rather than interchangeable labels: LT1 usually sits around `88-92%` depending on rep length, while LT2 usually sits around `98-102%` and should stay in short `2-4min` reps
- if a threshold session is materially longer and sits closer to `90-92%`, do not silently label it LT2
- for `vo2-max` templates, prefer a longer setup, usually around `20min`, plus short `2-3min` reps and enough recovery to preserve pace quality rather than forcing threshold-like continuity
- when reasoning about running pace, treat `vo2-max` templates as controlled 5k-10k-feel work rather than sprint work; this is an inference layer, not a universal metric mapping
- treat `physiology_label` as a descriptive hint inside the chosen category, not as a replacement for category
- treat `session_family`, `load_role`, and `structural_subtype` as first-class taxonomy fields, not as prose-only hints
- only use split-day templates when the planning task explicitly wants split quality or split support
- for double-threshold templates, prefer LT1-oriented work in the morning and LT2-oriented work in the evening unless the template explicitly says otherwise
- keep mixed-modality templates explicit; do not silently convert them into modality-light generic sessions
- keep generic templates modality-light unless modality is part of the session identity

## Update behavior

- Do not write private athlete information back into tracked repo-safe template files unless explicitly asked.
- Update `*.local.md` files for current personal state when privacy matters.
- Revise overlays when philosophy, athlete-state interpretation, or event model changes.
- Revise the core only when semantics or non-negotiable control logic changes.

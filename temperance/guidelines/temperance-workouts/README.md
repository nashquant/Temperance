# Temperance Workout Templates

## Purpose

This directory is the reusable workout library written in Temperance `activity_text` lingo.

The design goal is:
- doctrine-facing category first
- richer taxonomy for browsing and machine selection
- modality-light defaults unless the session identity requires explicit modality
- saved reference TSS for each stable session idea
- narrow, explicit scaling around the baseline rather than ad hoc rewriting

Common rules live in [template-contract.md](./template-contract.md). The family map lives in [taxonomy.md](./taxonomy.md). The full list lives in [catalog.md](./catalog.md). The shortest summary lives in [quick-reference.md](./quick-reference.md). Template files should stay thin and only carry workout-specific notes.

## Repository structure

- `template-contract.md`: shared template fields, normalization rules, scaling rules, and machine expectations
- `taxonomy.md`: mapping between doctrine-facing categories and richer session families
- `catalog.md`: one-file list of the whole template library
- `quick-reference.md`: distilled short access note
- family directories: concrete workout templates usually grouped by canonical `session_family`, with legacy alias paths allowed when taxonomy changes would otherwise create unnecessary churn
- template files: one stable session idea plus saved TSS variants

## Library model

The library uses two layers:

1. doctrine-facing `category`
2. richer taxonomy fields such as `session_family`, `structural_subtype`, `load_role`, and `planning_intent`

`category` remains the top-level selector:
- `easy-support`
- `moderate-support`
- `threshold-hard`
- `long-duration-hard`
- `specific-hard`
- `sharp-hard`

The richer taxonomy describes what kind of session sits inside that category.

## Selection order

1. choose `load_role` and doctrine-facing `category`
2. choose `session_family`
3. choose `structural_subtype`
4. apply `modality_pattern`
5. choose the nearest baseline session whose stored window contains the target TSS
6. choose the nearest stored variant before inventing a new rewrite

Special cases:
- split-day templates are only eligible when the planner explicitly wants split quality or split support
- mixed-modality templates must keep explicit modality in the stored concrete strings
- generic templates stay modality-light unless modality is part of the session identity

## Normalization rule

Imported source material should be normalized into the current library language before it is stored here.

That means:
- no legacy doctrine metric aliases
- no implicit rule that omitted modality means run
- long durations stored in `min`
- recoveries stored in the current library style when they are explicit
- `session_parts` used for split-day templates instead of relying on one raw summary string

## TSS rule

The stored TSS in a template is the library reference estimate for that structure.

For simple `%`-based templates, use this approximation unless a better model is stored in the file:
- segment TSS = `duration_h * IF^2 * 100`
- session TSS = sum of segment TSS

That keeps the repository modality-agnostic while still preserving a usable load anchor.

## Covered families

The library now covers:
- `recovery`
- `easy`
- `support`
- `steady-aerobic`
- `lt1-threshold`
- `lt2-threshold`
- `specific-endurance`
- `vo2-max`
- `hills-strength-endurance`
- `progressive`
- `medium-long`
- `long-run`
- `fartlek-alternations`
- `strides-neuromuscular`
- `x-train-specific`
- `mixed-combo`
- `split-quality`

Use [taxonomy.md](./taxonomy.md) to map these families back to doctrine-facing categories and typical planning roles.

`cruise intervals` are treated as an LT1-threshold variant rather than a standalone family.

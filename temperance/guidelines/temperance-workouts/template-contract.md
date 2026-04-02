# Workout Template Contract

Status: invariant workout companion.

## Purpose

This file defines the shared contract for the workout-template repository.

If a rule would be true for many templates, keep it here instead of repeating it in each template file.

## Required front matter

Each template should expose machine-readable front matter with at least:
- `template_id`
- `category`
- `session_family`
- `structural_subtype`
- `load_role`
- `planning_intent`
- `bucket`
- `stress_class`
- `hard_subtype`
- `physiology_label`
- `modality_pattern`
- `modality_scope`
- `phase_fit`
- `specificity_target`
- `durability_cost`
- `activity_text_template`
- `baseline_activity_text`
- `baseline_estimated_tss`
- `baseline_total_minutes`
- `baseline_avg_if`
- `baseline_max_if`
- `scaling_axis`
- `scaling_band_pct`
- `selection_window_tss`
- `tss_model`
- `variants`

`machine_notes` is optional.

Use `hard_subtype: null` for support sessions that are not hard days.

## Composite-session support

Split-day templates may also include:
- `composite_kind`
- `session_parts`
- `baseline_estimated_tss_total`

For split-day templates:
- keep `baseline_estimated_tss` equal to the total session estimate for backward compatibility
- store each part as a full concrete `activity_text` inside `session_parts`
- if variants are split-day variants, each variant may also include its own `session_parts`

## Taxonomy rule

Use the metadata fields as follows:
- `category`: doctrine-facing top-level selector
- `session_family`: library browsing family
- `structural_subtype`: shape of the session
- `load_role`: what job the session plays in the week
- `planning_intent`: main reason to choose the session
- `modality_pattern`: whether the session is generic, run-only, xtrain-only, mixed-modality, or split-day
- `phase_fit`: phases where the template is usually appropriate
- `specificity_target`: what kind of specificity the session primarily serves
- `durability_cost`: rough structural or absorption cost

## Lingo rule

Prefer parse-friendly Temperance strings such as:
- `45min @ 72%`
- `3x10' @ 90% (2' @ 72%)`
- `60min @ 72% + 20min @ 80%`
- `20min @ 72% + 8x2' @ 102% (150s @ 72%)`
- `AM: 20min @ 72% + 4x8' @ 90% (90s @ 75%) | PM: 15min @ 72% + 6x3' @ 100% (60s @ 75%)`

Keep templates modality-light when the same structure works across running, bike, and elliptical.

## Normalization rule

When source material is imported into this library:
- remove legacy doctrine metric aliases
- do not assume omitted modality means run
- store long durations in `min`
- keep `'` for repeated minute reps and `s` for second-based reps
- store explicit recoveries in the current library style, usually parenthesized
- use `session_parts` for split-day templates rather than relying only on one summary string

## Recovery rule

- Repeat-based templates must include the between-rep recovery inside `baseline_activity_text` and each repeat-based variant.
- If recoveries are meant to stay moving and aerobic, say so in the template's `Recovery` section.
- If interval delineation is not specified, leave the in-between handling to user discretion rather than inventing a default recovery.
- If a session is continuous, do not invent recoveries just to make the file look uniform.

## Scaling rule

Scaling should preserve the session's identity.

That means:
- keep the same core stimulus
- keep the same category
- prefer rep-count changes or small support-volume changes
- avoid rewriting the session into a different physiology just to hit a target TSS

Saved variants should usually stay around `+/- 20-25%` from baseline. If a template needs a wider or tighter band, say why in the template-specific scaling note.

## Template body rule

Each template file should stay specific to that workout.

Use short sections such as:
- `Session note`
- `Best use`
- `Recovery`
- `Scaling note`

Do not repeat repository-wide statements about category-first selection, modality-agnostic use, or generic TSS logic in every file.

## Optional template syntax

`activity_text_template` may use placeholder or optional-block notation when scaling changes one small part of the session, for example:
- `15min @ 72% + {threshold_reps}x10' @ 90% (2' @ 72%)`
- `15min @ 72% + 3x12' @ 88% (2' @ 72%) [+ {support_minutes}min @ 72%]`
- `AM: {am_activity} | PM: {pm_activity}`

The baseline and stored variants should always use complete concrete strings.

## Interpretation rule

- Treat `category` as the doctrine-facing selector and `session_family` as the richer library taxonomy.
- Treat `physiology_label` as a descriptive hint, not as a replacement for category.
- Treat stored TSS as a library anchor, not as athlete-specific truth.
- When a session sits near a boundary, let category express planning role and let `physiology_label` express the flavor.

## Family guardrails

- LT1 threshold usually lives around `88-92%`, with longer reps tending lower and medium-length reps able to sit higher.
- LT2 threshold usually lives around `98-102%` and should stay in short `2-4min` reps.
- VO2 max should usually stay on the shorter side than LT2, most often in `2-3min` reps with a longer setup and enough recovery to preserve pace quality.
- If a session is materially longer and lives closer to `90-92%`, do not label it LT2 or VO2.

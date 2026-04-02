# Workout Template Contract

Status: invariant workout companion.

## Purpose

This file defines the shared contract for the workout-template repository.

If a rule would be true for many templates, keep it here instead of repeating it in each template file.

## Required front matter

Each template should expose machine-readable front matter with at least:
- `template_id`
- `category`
- `bucket`
- `stress_class`
- `hard_subtype`
- `physiology_label`
- `modality_scope`
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

## Lingo rule

Prefer parse-friendly Temperance strings such as:
- `45min @ 72%`
- `3x10' @ 90% (2' @ 72%)`
- `60min @ 72% + 20min @ 80%`
- `15min @ 72% + 8x2' @ 100% (2' @ 72%)`

Keep templates modality-light when the same structure works across running, bike, and elliptical.

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

The baseline and stored variants should always use complete concrete strings.

## Interpretation rule

- Treat `physiology_label` as a descriptive hint, not as a replacement for category.
- Treat stored TSS as a library anchor, not as athlete-specific truth.
- When a session sits near a boundary, let category express planning role and let `physiology_label` express the flavor.

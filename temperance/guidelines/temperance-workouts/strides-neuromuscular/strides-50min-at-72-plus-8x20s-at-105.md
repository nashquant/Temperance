---
template_id: strides_50min_72_8x20s_105_40srec
category: easy-support
session_family: strides-neuromuscular
structural_subtype: strides-finish
load_role: support
planning_intent: preserve-top-end-touch
bucket: easy
stress_class: support
hard_subtype: null
physiology_label: easy-run-plus-strides
modality_pattern: run-only
modality_scope: run-only
phase_fit:
  - return
  - base
  - capacity-build
  - taper
specificity_target: neuromuscular-touch
durability_cost: low
activity_text_template: "{easy_minutes}min run @ 72% + {stride_reps}x20s @ 105% (40s @ 72%)"
baseline_activity_text: "50min run @ 72% + 8x20s @ 105% (40s @ 72%)"
baseline_estimated_tss: 52.1
baseline_total_minutes: 57.3
baseline_avg_if: 0.74
baseline_max_if: 1.05
scaling_axis: easy_duration_and_stride_count
scaling_band_pct:
  - -21.1
  - 21.1
selection_window_tss:
  - 41.1
  - 63.1
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "40min run @ 72% + 6x20s @ 105% (40s @ 72%)"
    estimated_tss: 41.1
    total_minutes: 45.3
    avg_if: 0.74
    max_if: 1.05
    pct_from_baseline_tss: -21.1
  - scale_label: baseline
    activity_text: "50min run @ 72% + 8x20s @ 105% (40s @ 72%)"
    estimated_tss: 52.1
    total_minutes: 57.3
    avg_if: 0.74
    max_if: 1.05
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "60min run @ 72% + 10x20s @ 105% (40s @ 72%)"
    estimated_tss: 63.1
    total_minutes: 69.3
    avg_if: 0.74
    max_if: 1.05
    pct_from_baseline_tss: 21.1
machine_notes:
  - "Strides are stored numerically here so the templates remain machine-readable."
---

# Strides Neuromuscular - 50min run @ 72% + 8x20s @ 105% (40s @ 72%)

## Session note

This is the default easy-plus-strides template: low-cost aerobic support with a small neuromuscular touch.

## Best use

- easy run days that should preserve range and rhythm without creating a hard session
- taper or return periods where some snap is useful but total cost must stay low

## Recovery

Use `40s @ 72%` between strides. Keep the strides relaxed and repeatable rather than sprint-like.

## Scaling note

Scale with small changes to easy duration and stride count. If the sharp work starts to dominate the day, move to `vo2-max`.

---
template_id: threshold_15min_72_4x8_90_2rec
category: threshold-hard
session_family: lt1-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: threshold-density
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: lt1-threshold
durability_cost: medium
activity_text_template: "15min @ 72% + {threshold_reps}x8' @ 90% (2' @ 72%)"
baseline_activity_text: "15min @ 72% + 4x8' @ 90% (2' @ 72%)"
baseline_estimated_tss: 61.3
baseline_total_minutes: 53
baseline_avg_if: 0.83
baseline_max_if: 0.90
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -20.4
  - 20.6
selection_window_tss:
  - 48.8
  - 73.9
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 3x8' @ 90% (2' @ 72%)"
    estimated_tss: 48.8
    total_minutes: 43
    avg_if: 0.83
    max_if: 0.90
    pct_from_baseline_tss: -20.4
  - scale_label: baseline
    activity_text: "15min @ 72% + 4x8' @ 90% (2' @ 72%)"
    estimated_tss: 61.3
    total_minutes: 53
    avg_if: 0.83
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 5x8' @ 90% (2' @ 72%)"
    estimated_tss: 73.9
    total_minutes: 63
    avg_if: 0.84
    max_if: 0.90
    pct_from_baseline_tss: 20.6
machine_notes:
  - "Denser LT1 threshold option with more restart points."
---

# LT1 Threshold - 15min @ 72% + 4x8' @ 90% (2' @ 72%)

## Session note

This is a denser LT1 threshold session with shorter reps and more restart points than the `3x10'` anchor.

## Best use

- threshold days that should feel active and segmented rather than long and smooth
- athletes who handle shorter repeat rhythm better than longer steady reps

## Recovery

Use `2' @ 72%` between reps. The recovery should reset the rhythm without dropping the aerobic load too far.

## Scaling note

Scale by rep count. If the day starts to want much longer reps instead of more starts, move to another LT1 template.

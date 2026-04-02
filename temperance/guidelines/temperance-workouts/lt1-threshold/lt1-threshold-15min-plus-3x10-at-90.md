---
template_id: threshold_15min_72_3x10_90_2rec
category: threshold-hard
session_family: lt1-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: lt1-biased-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: lt1-threshold
durability_cost: medium
activity_text_template: "15min @ 72% + {threshold_reps}x10' @ 90% (2' @ 72%)"
baseline_activity_text: "15min @ 72% + 3x10' @ 90% (2' @ 72%)"
baseline_estimated_tss: 56.9
baseline_total_minutes: 49
baseline_avg_if: 0.83
baseline_max_if: 0.90
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -26.7
  - 26.7
selection_window_tss:
  - 41.7
  - 72.1
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 2x10' @ 90% (2' @ 72%)"
    estimated_tss: 41.7
    total_minutes: 37
    avg_if: 0.82
    max_if: 0.90
    pct_from_baseline_tss: -26.7
  - scale_label: baseline
    activity_text: "15min @ 72% + 3x10' @ 90% (2' @ 72%)"
    estimated_tss: 56.9
    total_minutes: 49
    avg_if: 0.83
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 4x10' @ 90% (2' @ 72%)"
    estimated_tss: 72.1
    total_minutes: 61
    avg_if: 0.84
    max_if: 0.90
    pct_from_baseline_tss: 26.7
machine_notes:
  - "Low-threshold anchor inside the lt1-threshold family."
  - "Recovery stays aerobic so the session keeps continuous pressure."
---

# LT1 Threshold - 15min @ 72% + 3x10' @ 90% (2' @ 72%)

## Session note

This is the compact LT1 threshold anchor. It sits closer to the LT1-to-threshold bridge than to sharp threshold work.

## Best use

- controlled H1 threshold days that should stay smooth
- base or capacity phases that want true threshold contact without turning sharp

## Recovery

Use `2' @ 72%` between reps. Keep the recoveries moving and aerobic.

## Scaling note

Change rep count before intensity. If the day needs much more than `72.1 TSS`, move to a larger LT1 or cruise template instead of stretching this one.

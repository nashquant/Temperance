---
template_id: threshold_15min_72_3x12_88_2rec
category: threshold-hard
session_family: lt1-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: upper-aerobic-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: lt1-threshold
durability_cost: medium
activity_text_template: "15min @ 72% + 3x12' @ 88% (2' @ 72%) [+ {support_minutes}min @ 72%]"
baseline_activity_text: "15min @ 72% + 3x12' @ 88% (2' @ 72%)"
baseline_estimated_tss: 62.9
baseline_total_minutes: 55
baseline_avg_if: 0.83
baseline_max_if: 0.88
scaling_axis: support_volume_around_fixed_rep_set
scaling_band_pct:
  - -20.5
  - 20.5
selection_window_tss:
  - 50.0
  - 75.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 2x12' @ 88% (2' @ 72%) + 5min @ 72%"
    estimated_tss: 50.0
    total_minutes: 46
    avg_if: 0.81
    max_if: 0.88
    pct_from_baseline_tss: -20.5
  - scale_label: baseline
    activity_text: "15min @ 72% + 3x12' @ 88% (2' @ 72%)"
    estimated_tss: 62.9
    total_minutes: 55
    avg_if: 0.83
    max_if: 0.88
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 3x12' @ 88% (2' @ 72%) + 15min @ 72%"
    estimated_tss: 75.8
    total_minutes: 70
    avg_if: 0.81
    max_if: 0.88
    pct_from_baseline_tss: 20.5
machine_notes:
  - "Smoothest LT1 threshold option in the library."
  - "Scaling changes support volume instead of making the reps sharper."
---

# LT1 Threshold - 15min @ 72% + 3x12' @ 88% (2' @ 72%)

## Session note

This is the smoothest LT1 threshold template in the library. It leans upper aerobic and low threshold rather than pushing the top end of threshold.

## Best use

- base and capacity phases that want long controlled work
- durability-first periods where threshold should be present but not aggressive

## Recovery

Use `2' @ 72%` between reps. The recoveries should feel like continuation, not reset.

## Scaling note

Keep the `3x12' @ 88%` identity fixed. Scale with small support-volume changes instead of making the reps harder.

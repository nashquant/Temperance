---
template_id: lt2_15min_72_8x3_100_75float
category: threshold-hard
session_family: lt2-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt2-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: short-rep-upper-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
  - peak
specificity_target: lt2-threshold
durability_cost: medium
activity_text_template: "15min @ 72% + {threshold_reps}x3' @ 100% (75s @ 76%)"
baseline_activity_text: "15min @ 72% + 8x3' @ 100% (75s @ 76%)"
baseline_estimated_tss: 62.6
baseline_total_minutes: 49
baseline_avg_if: 0.88
baseline_max_if: 1.00
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -19.8
  - 19.8
selection_window_tss:
  - 50.2
  - 75.0
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 6x3' @ 100% (75s @ 76%)"
    estimated_tss: 50.2
    total_minutes: 40.5
    avg_if: 0.86
    max_if: 1.00
    pct_from_baseline_tss: -19.8
  - scale_label: baseline
    activity_text: "15min @ 72% + 8x3' @ 100% (75s @ 76%)"
    estimated_tss: 62.6
    total_minutes: 49
    avg_if: 0.88
    max_if: 1.00
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 10x3' @ 100% (75s @ 76%)"
    estimated_tss: 75.0
    total_minutes: 57.5
    avg_if: 0.88
    max_if: 1.00
    pct_from_baseline_tss: 19.8
machine_notes:
  - "This is the middle LT2 anchor: shorter than the 4-minute template, denser than the 2-minute one."
  - "Keep the work near 100% and let rep count do the scaling."
---

# LT2 Threshold - 15min @ 72% + 8x3' @ 100% (75s @ 76%)

## Session note

This is the central short-rep LT2 template: clearly above LT1, but still controlled enough to stay threshold-hard rather than turning into full VO2 work.

## Best use

- weeks that want real LT2 exposure without using the longest `4'` reps
- blocks that want denser threshold with a sharper feel but not a full H2 session

## Recovery

Use `75s @ 76%` between reps. The float stays short enough to preserve the upper-threshold feel.

## Scaling note

Scale by rep count. If the day wants materially more recovery or a longer warm-up, move to `vo2-max` instead of stretching this template across families.

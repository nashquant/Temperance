---
template_id: lt2_15min_72_10x2_102_60float
category: threshold-hard
session_family: lt2-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt2-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: shortest-lt2-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
  - peak
specificity_target: lt2-threshold
durability_cost: medium
activity_text_template: "15min @ 72% + {threshold_reps}x2' @ 102% (60s @ 76%)"
baseline_activity_text: "15min @ 72% + 10x2' @ 102% (60s @ 76%)"
baseline_estimated_tss: 57.3
baseline_total_minutes: 45
baseline_avg_if: 0.87
baseline_max_if: 1.02
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -15.5
  - 15.4
selection_window_tss:
  - 48.4
  - 66.1
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 8x2' @ 102% (60s @ 76%)"
    estimated_tss: 48.4
    total_minutes: 39
    avg_if: 0.86
    max_if: 1.02
    pct_from_baseline_tss: -15.5
  - scale_label: baseline
    activity_text: "15min @ 72% + 10x2' @ 102% (60s @ 76%)"
    estimated_tss: 57.3
    total_minutes: 45
    avg_if: 0.87
    max_if: 1.02
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 12x2' @ 102% (60s @ 76%)"
    estimated_tss: 66.1
    total_minutes: 51
    avg_if: 0.88
    max_if: 1.02
    pct_from_baseline_tss: 15.4
machine_notes:
  - "This is the shortest LT2 template in the library."
  - "Use it when the threshold day wants the top end of LT2, but still should not become a VO2 session."
---

# LT2 Threshold - 15min @ 72% + 10x2' @ 102% (60s @ 76%)

## Session note

This is the shortest LT2 template in the library. It uses very short reps at the top of the LT2 band while keeping the day inside threshold-hard.

## Best use

- blocks that want the sharpest threshold option without moving fully into `vo2-max`
- athletes who handle short upper-threshold repetitions better than longer dense reps

## Recovery

Use `60s @ 76%` between reps. The float should stay active and short so the session still behaves like LT2 rather than like separate standalone efforts.

## Scaling note

Keep this one on a tight structural leash. If the day needs much more rest, longer setup, or clearly higher pace quality, move to `vo2-max`.

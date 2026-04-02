---
template_id: sharp_15min_72_8x2_100_2rec
category: sharp-hard
session_family: vo2-max
structural_subtype: intervals
load_role: sharpening
planning_intent: preserve-top-end-touch
bucket: intervals
stress_class: hard
hard_subtype: h2
physiology_label: short-repeat-vo2
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - peak
specificity_target: vo2-touch
durability_cost: medium
activity_text_template: "15min @ 72% + {vo2_reps}x2' @ 100% (2' @ 72%)"
baseline_activity_text: "15min @ 72% + 8x2' @ 100% (2' @ 72%)"
baseline_estimated_tss: 51.7
baseline_total_minutes: 45
baseline_avg_if: 0.83
baseline_max_if: 1.00
scaling_axis: vo2_rep_count
scaling_band_pct:
  - -19.5
  - 19.5
selection_window_tss:
  - 41.6
  - 61.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 6x2' @ 100% (2' @ 72%)"
    estimated_tss: 41.6
    total_minutes: 37
    avg_if: 0.82
    max_if: 1.00
    pct_from_baseline_tss: -19.5
  - scale_label: baseline
    activity_text: "15min @ 72% + 8x2' @ 100% (2' @ 72%)"
    estimated_tss: 51.7
    total_minutes: 45
    avg_if: 0.83
    max_if: 1.00
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 10x2' @ 100% (2' @ 72%)"
    estimated_tss: 61.8
    total_minutes: 53
    avg_if: 0.84
    max_if: 1.00
    pct_from_baseline_tss: 19.5
machine_notes:
  - "Short-repeat VO2 anchor."
  - "Recovery is aerobic but brief enough to preserve sharpness."
---

# VO2 Max - 15min @ 72% + 8x2' @ 100% (2' @ 72%)

## Session note

This is the short-repeat VO2 anchor: frequent starts, controlled exposure at maximal aerobic intensity, and enough recovery to repeat quality.

## Best use

- H2 days where sharper intensity is the point
- periods that need ceiling touch without building a huge threshold session

## Recovery

Use `2' @ 72%` between reps. The recovery is short and active; it should preserve repeat quality, not fully reset the system.

## Scaling note

Scale with rep count. If the day should drift toward sustained threshold or specific endurance, change family instead of flattening this session.

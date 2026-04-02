---
template_id: sharp_20min_72_6x3_100_3rec
category: sharp-hard
session_family: vo2-max
structural_subtype: intervals
load_role: sharpening
planning_intent: preserve-top-end-touch
bucket: intervals
stress_class: hard
hard_subtype: h2
physiology_label: longer-repeat-vo2
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - peak
specificity_target: vo2-touch
durability_cost: medium
activity_text_template: "20min @ 72% + {vo2_reps}x3' @ 100% (3' @ 72%)"
baseline_activity_text: "20min @ 72% + 6x3' @ 100% (3' @ 72%)"
baseline_estimated_tss: 62.8
baseline_total_minutes: 56
baseline_avg_if: 0.82
baseline_max_if: 1.00
scaling_axis: vo2_rep_count
scaling_band_pct:
  - -12.1
  - 12.1
selection_window_tss:
  - 55.2
  - 70.4
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 5x3' @ 100% (3' @ 72%)"
    estimated_tss: 55.2
    total_minutes: 50
    avg_if: 0.81
    max_if: 1.00
    pct_from_baseline_tss: -12.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 6x3' @ 100% (3' @ 72%)"
    estimated_tss: 62.8
    total_minutes: 56
    avg_if: 0.82
    max_if: 1.00
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 7x3' @ 100% (3' @ 72%)"
    estimated_tss: 70.4
    total_minutes: 62
    avg_if: 0.83
    max_if: 1.00
    pct_from_baseline_tss: 12.1
machine_notes:
  - "Longer-repeat VO2 template with a longer setup and recovery than the threshold families."
  - "Keep this as a quality-preserving aerobic-power session, not as a disguised threshold workout."
---

# VO2 Max - 20min @ 72% + 6x3' @ 100% (3' @ 72%)

## Session note

This is the longer-repeat VO2 option. It is still sharp, but the `3'` reps make it feel slightly more rhythm-based than the `2'` template while staying clearly above LT2.

## Best use

- H2 days that should stay aerobic-power focused without becoming ragged
- athletes who respond better to a little more continuity than the shortest VO2 starts

## Recovery

Use `3' @ 72%` between reps. The recovery should be long enough to preserve pace quality across all reps rather than turning the workout into threshold drag.

## Scaling note

Keep this on a tight band. If the session starts wanting much longer reps, move to `lt2-threshold` instead of stretching VO2 into upper-threshold density.

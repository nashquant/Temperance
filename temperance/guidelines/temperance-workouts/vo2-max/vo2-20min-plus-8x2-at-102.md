---
template_id: sharp_20min_72_8x2_102_150float
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
activity_text_template: "20min @ 72% + {vo2_reps}x2' @ 102% (150s @ 72%)"
baseline_activity_text: "20min @ 72% + 8x2' @ 102% (150s @ 72%)"
baseline_estimated_tss: 62.3
baseline_total_minutes: 56
baseline_avg_if: 0.82
baseline_max_if: 1.02
scaling_axis: vo2_rep_count
scaling_band_pct:
  - -18.1
  - 18.1
selection_window_tss:
  - 51.0
  - 73.6
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 6x2' @ 102% (150s @ 72%)"
    estimated_tss: 51.0
    total_minutes: 47
    avg_if: 0.81
    max_if: 1.02
    pct_from_baseline_tss: -18.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 8x2' @ 102% (150s @ 72%)"
    estimated_tss: 62.3
    total_minutes: 56
    avg_if: 0.82
    max_if: 1.02
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 10x2' @ 102% (150s @ 72%)"
    estimated_tss: 73.6
    total_minutes: 65
    avg_if: 0.82
    max_if: 1.02
    pct_from_baseline_tss: 18.1
machine_notes:
  - "Short-repeat VO2 anchor with a longer setup and more generous between-rep recovery."
  - "Use this family for pace-quality work that feels closer to controlled 5k-10k rhythm than to sprinting."
---

# VO2 Max - 20min @ 72% + 8x2' @ 102% (150s @ 72%)

## Session note

This is the short-repeat VO2 anchor: longer setup, short reps, and enough recovery to preserve pace quality across the whole session.

## Best use

- H2 days where the point is a true aerobic-power touch rather than threshold density
- periods that want controlled 5k-10k-feel rhythm without drifting into all-out work

## Recovery

Use `150s @ 72%` between reps. The recovery should be generous enough to keep the pace honest and the mechanics clean.

## Scaling note

Scale with rep count. If the day wants shorter recovery or a more continuous threshold feel, move back to `lt2-threshold` instead of flattening VO2 into threshold work.

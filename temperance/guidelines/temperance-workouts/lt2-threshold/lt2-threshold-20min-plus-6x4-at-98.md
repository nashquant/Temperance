---
template_id: lt2_20min_72_6x4_98_75float
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
activity_text_template: "20min @ 72% + {threshold_reps}x4' @ 98% (75s @ 76%)"
baseline_activity_text: "20min @ 72% + 6x4' @ 98% (75s @ 76%)"
baseline_estimated_tss: 62.9
baseline_total_minutes: 51.5
baseline_avg_if: 0.86
baseline_max_if: 0.98
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -12.1
  - 12.1
selection_window_tss:
  - 55.3
  - 70.5
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 5x4' @ 98% (75s @ 76%)"
    estimated_tss: 55.3
    total_minutes: 46.2
    avg_if: 0.85
    max_if: 0.98
    pct_from_baseline_tss: -12.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 6x4' @ 98% (75s @ 76%)"
    estimated_tss: 62.9
    total_minutes: 51.5
    avg_if: 0.86
    max_if: 0.98
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 7x4' @ 98% (75s @ 76%)"
    estimated_tss: 70.5
    total_minutes: 56.8
    avg_if: 0.86
    max_if: 0.98
    pct_from_baseline_tss: 12.1
machine_notes:
  - "LT2 templates stay inside threshold-hard, but the rep prescription should remain short enough to avoid drifting into VO2 or long threshold-density work."
  - "Use roughly 98-102% for the work reps, with 2-4 minute repetitions."
---

# LT2 Threshold - 20min @ 72% + 6x4' @ 98% (75s @ 76%)

## Session note

This is the canonical LT2 threshold template: short reps near upper threshold, short floats, and enough density to stay threshold-hard without becoming a VO2 session.

## Best use

- phases that need true LT2 exposure without turning the day into a sharp H2 session
- weeks where the primary hard session should stay threshold-first but clearly above LT1 work

## Recovery

Use `75s @ 76%` between reps. The recoveries should stay short and purposeful enough to preserve the LT2 character.

## Scaling note

Scale by rep count. If the day starts wanting longer reps at sub-98% intensity, move to `lt1-threshold` instead.

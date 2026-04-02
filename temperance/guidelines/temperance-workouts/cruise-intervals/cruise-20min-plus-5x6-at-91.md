---
template_id: cruise_20min_72_5x6_91_90srec
category: threshold-hard
session_family: cruise-intervals
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: dense-threshold-support
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
specificity_target: cruise-threshold
durability_cost: medium
activity_text_template: "20min @ 72% + {cruise_reps}x6' @ 91% (90s @ 75%)"
baseline_activity_text: "20min @ 72% + 5x6' @ 91% (90s @ 75%)"
baseline_estimated_tss: 64.3
baseline_total_minutes: 56
baseline_avg_if: 0.83
baseline_max_if: 0.91
scaling_axis: rep_count
scaling_band_pct:
  - -15.1
  - 15.1
selection_window_tss:
  - 54.6
  - 74.0
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 4x6' @ 91% (90s @ 75%)"
    estimated_tss: 54.6
    total_minutes: 48.5
    avg_if: 0.82
    max_if: 0.91
    pct_from_baseline_tss: -15.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 5x6' @ 91% (90s @ 75%)"
    estimated_tss: 64.3
    total_minutes: 56
    avg_if: 0.83
    max_if: 0.91
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 6x6' @ 91% (90s @ 75%)"
    estimated_tss: 74.0
    total_minutes: 63.5
    avg_if: 0.84
    max_if: 0.91
    pct_from_baseline_tss: 15.1
machine_notes:
  - "Cruise intervals are threshold-supportive and dense without being treated as event-specific by default."
---

# Cruise Intervals - 20min @ 72% + 5x6' @ 91% (90s @ 75%)

## Session note

This is the canonical cruise interval template: moderate-density threshold work that is useful as core support quality.

## Best use

- threshold-forward blocks that want more rhythm and density than classic LT1 work
- marathon-supportive or HM-supportive periods where the session should stay generic rather than event-locked

## Recovery

Use `90s @ 75%` between reps. Recoveries should be quick and controlled.

## Scaling note

Scale with rep count. If the day wants much longer reps or stronger event relevance, move to `specific-endurance`.

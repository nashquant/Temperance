---
template_id: long_120min_76
category: long-duration-hard
session_family: long-run
structural_subtype: continuous
load_role: long-durability
planning_intent: build-long-durability
bucket: long
stress_class: hard
hard_subtype: h1
physiology_label: steady-durability-long
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
specificity_target: long-durability
durability_cost: high
activity_text_template: "{long_minutes}min @ 76%"
baseline_activity_text: "120min @ 76%"
baseline_estimated_tss: 115.5
baseline_total_minutes: 120
baseline_avg_if: 0.76
baseline_max_if: 0.76
scaling_axis: total_duration
scaling_band_pct:
  - -20.8
  - 20.9
selection_window_tss:
  - 91.5
  - 139.6
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "95min @ 76%"
    estimated_tss: 91.5
    total_minutes: 95
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: -20.8
  - scale_label: baseline
    activity_text: "120min @ 76%"
    estimated_tss: 115.5
    total_minutes: 120
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "145min @ 76%"
    estimated_tss: 139.6
    total_minutes: 145
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: 20.9
machine_notes:
  - "Straight long-run template where duration is the main cost driver."
---

# Long Run - 120min @ 76%

## Session note

This is the simplest hard long-session anchor in the library: steady, duration-driven, and intentionally free of extra shape.

## Best use

- long sessions where straight durability is the main point
- blocks that need long-session robustness more than finish work

## Scaling note

Scale only with duration. If the session needs a meaningful late block, choose a shaped long-run or specific-endurance template instead.

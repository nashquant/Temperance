---
template_id: moderate_75min_72
category: moderate-support
session_family: medium-long
structural_subtype: continuous
load_role: long-durability
planning_intent: build-long-durability
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: medium-long-aerobic
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: long-durability
durability_cost: medium
activity_text_template: "{steady_minutes}min @ 72%"
baseline_activity_text: "75min @ 72%"
baseline_estimated_tss: 64.8
baseline_total_minutes: 75
baseline_avg_if: 0.72
baseline_max_if: 0.72
scaling_axis: total_duration
scaling_band_pct:
  - -20.1
  - 20.1
selection_window_tss:
  - 51.8
  - 77.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "60min @ 72%"
    estimated_tss: 51.8
    total_minutes: 60
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: -20.1
  - scale_label: baseline
    activity_text: "75min @ 72%"
    estimated_tss: 64.8
    total_minutes: 75
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "90min @ 72%"
    estimated_tss: 77.8
    total_minutes: 90
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: 20.1
machine_notes:
  - "Medium-long templates sit between support and true long-run cost."
---

# Medium Long - 75min @ 72%

## Session note

This is the clean medium-long aerobic anchor: simple, durable, and easy to place around harder days.

## Best use

- medium-long support in weeks where the hard load already exists elsewhere
- blocks that want durable volume without the full cost of the longest session

## Scaling note

Scale only with duration. If the day starts to want a meaningful moderate finish, move to another medium-long or progressive template instead.

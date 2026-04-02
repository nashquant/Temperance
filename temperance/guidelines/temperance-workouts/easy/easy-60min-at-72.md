---
template_id: easy_60min_72
category: easy-support
session_family: easy
structural_subtype: continuous
load_role: support
planning_intent: preserve-rhythm
bucket: easy
stress_class: support
hard_subtype: null
physiology_label: easy-aerobic-support
modality_pattern: generic
modality_scope: any
phase_fit:
  - return
  - base
  - capacity-build
  - specificity
  - taper
specificity_target: general-aerobic
durability_cost: low
activity_text_template: "{duration_minutes}min @ 72%"
baseline_activity_text: "60min @ 72%"
baseline_estimated_tss: 51.8
baseline_total_minutes: 60
baseline_avg_if: 0.72
baseline_max_if: 0.72
scaling_axis: total_duration
scaling_band_pct:
  - -24.9
  - 25.1
selection_window_tss:
  - 38.9
  - 64.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "45min @ 72%"
    estimated_tss: 38.9
    total_minutes: 45
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: -24.9
  - scale_label: baseline
    activity_text: "60min @ 72%"
    estimated_tss: 51.8
    total_minutes: 60
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "75min @ 72%"
    estimated_tss: 64.8
    total_minutes: 75
    avg_if: 0.72
    max_if: 0.72
    pct_from_baseline_tss: 25.1
machine_notes:
  - "Default modality-light easy aerobic template."
---

# Easy - 60min @ 72%

## Session note

This is the clean easy aerobic anchor: simple enough to travel across modalities, long enough to matter, and still clearly support rather than quality.

## Best use

- default easy days that should add rhythm and aerobic load without carrying planning complexity
- weeks where the real stress already sits elsewhere

## Scaling note

Scale only with duration. If the day needs a meaningful moderate finish, move to a `support`, `progressive`, or `medium-long` template instead.

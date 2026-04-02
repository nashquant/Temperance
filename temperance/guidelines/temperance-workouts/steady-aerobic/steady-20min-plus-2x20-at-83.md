---
template_id: steady_20min_72_2x20_83_3rec
category: moderate-support
session_family: steady-aerobic
structural_subtype: broken-continuous
load_role: moderate-support
planning_intent: build-steady-aerobic
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: strong-aerobic-broken
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
specificity_target: steady-aerobic
durability_cost: medium
activity_text_template: "20min @ 72% + 2x{steady_rep_minutes}' @ 83% (3' @ 72%)"
baseline_activity_text: "20min @ 72% + 2x20' @ 83% (3' @ 72%)"
baseline_estimated_tss: 65.8
baseline_total_minutes: 63
baseline_avg_if: 0.79
baseline_max_if: 0.83
scaling_axis: rep_duration
scaling_band_pct:
  - -17.5
  - 17.5
selection_window_tss:
  - 54.3
  - 77.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 2x15' @ 83% (3' @ 72%)"
    estimated_tss: 54.3
    total_minutes: 53
    avg_if: 0.78
    max_if: 0.83
    pct_from_baseline_tss: -17.5
  - scale_label: baseline
    activity_text: "20min @ 72% + 2x20' @ 83% (3' @ 72%)"
    estimated_tss: 65.8
    total_minutes: 63
    avg_if: 0.79
    max_if: 0.83
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 2x25' @ 83% (3' @ 72%)"
    estimated_tss: 77.3
    total_minutes: 73
    avg_if: 0.80
    max_if: 0.83
    pct_from_baseline_tss: 17.5
machine_notes:
  - "Steady aerobic family sits below threshold-hard even when it becomes substantial."
---

# Steady Aerobic - 20min @ 72% + 2x20' @ 83% (3' @ 72%)

## Session note

This is the default strong-aerobic broken-continuous template. It builds steady strength without turning into hidden threshold.

## Best use

- base and capacity phases that want stronger aerobic work without promoting the day to hard
- sessions where one long steady block would be harder to place or absorb

## Recovery

Use `3' @ 72%` between blocks. The recovery should reset posture and rhythm without dropping the aerobic thread.

## Scaling note

Scale by rep duration. If the session starts wanting threshold-level pressure, move to `lt1-threshold` instead of stretching this template upward.

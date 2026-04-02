---
template_id: mixed_20min_72_3x10_90_10min_84
category: threshold-hard
session_family: mixed-combo
structural_subtype: fast-finish
load_role: secondary-hard
planning_intent: blend-threshold-and-finish
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: threshold-plus-fast-finish
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
specificity_target: mixed-specificity
durability_cost: medium
activity_text_template: "20min @ 72% + {threshold_reps}x10' @ 90% (2' @ 75%) + {finish_minutes}min @ 84%"
baseline_activity_text: "20min @ 72% + 3x10' @ 90% (2' @ 75%) + 10min @ 84%"
baseline_estimated_tss: 73.3
baseline_total_minutes: 64
baseline_avg_if: 0.83
baseline_max_if: 0.90
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -24.1
  - 21.0
selection_window_tss:
  - 55.6
  - 88.7
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 2x10' @ 90% (2' @ 75%) + 8min @ 84%"
    estimated_tss: 55.6
    total_minutes: 50
    avg_if: 0.82
    max_if: 0.90
    pct_from_baseline_tss: -24.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 3x10' @ 90% (2' @ 75%) + 10min @ 84%"
    estimated_tss: 73.3
    total_minutes: 64
    avg_if: 0.83
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 4x10' @ 90% (2' @ 75%) + 10min @ 84%"
    estimated_tss: 88.7
    total_minutes: 76
    avg_if: 0.84
    max_if: 0.90
    pct_from_baseline_tss: 21.0
machine_notes:
  - "Mixed-combo templates blend two useful session shapes without splitting the day."
---

# Mixed Combo - 20min @ 72% + 3x10' @ 90% (2' @ 75%) + 10min @ 84%

## Session note

This is the default threshold-plus-finish combo: threshold first, then a smaller strong finish block rather than two unrelated sessions.

## Best use

- blocks that want one meaningful session to cover two adjacent qualities
- days that should sit between plain threshold and event-specific endurance

## Recovery

Use `2' @ 75%` between threshold reps. The finish block should start directly after the rep set rather than after a long reset.

## Scaling note

Scale the threshold set before touching the finish block. If the session becomes truly specific, move it into `specific-endurance`.

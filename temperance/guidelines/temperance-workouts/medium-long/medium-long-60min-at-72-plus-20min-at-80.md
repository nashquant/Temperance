---
template_id: moderate_60min_72_20min_80
category: moderate-support
session_family: medium-long
structural_subtype: progression
load_role: long-durability
planning_intent: build-long-durability
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: medium-long-progression
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: long-durability
durability_cost: medium
activity_text_template: "{support_minutes}min @ 72% + {moderate_minutes}min @ 80%"
baseline_activity_text: "60min @ 72% + 20min @ 80%"
baseline_estimated_tss: 73.2
baseline_total_minutes: 80
baseline_avg_if: 0.74
baseline_max_if: 0.80
scaling_axis: total_duration_with_fixed_progression_shape
scaling_band_pct:
  - -19.1
  - 19.0
selection_window_tss:
  - 59.2
  - 87.1
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "50min @ 72% + 15min @ 80%"
    estimated_tss: 59.2
    total_minutes: 65
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: -19.1
  - scale_label: baseline
    activity_text: "60min @ 72% + 20min @ 80%"
    estimated_tss: 73.2
    total_minutes: 80
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "70min @ 72% + 25min @ 80%"
    estimated_tss: 87.1
    total_minutes: 95
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 19.0
machine_notes:
  - "Medium-long progression template with a moderate finish but not a hard-session role."
---

# Medium Long - 60min @ 72% + 20min @ 80%

## Session note

This is a medium-long progression support day. The moderate finish matters, but it is still meant to support the week rather than dominate it.

## Best use

- medium-long sessions that should prepare later long or specific work
- phases where some moderate contact is useful without committing to a hard day

## Scaling note

Preserve the progression shape. If the last block starts to become event-specific or hard enough to change the planning role, move to `specific-endurance`.

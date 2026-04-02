---
template_id: progressive_40min_72_20min_79_10min_83
category: moderate-support
session_family: progressive
structural_subtype: progression
load_role: moderate-support
planning_intent: build-progressive-strength
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: progression-to-steady
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: steady-aerobic
durability_cost: medium
activity_text_template: "{easy_minutes}min @ 72% + {steady_minutes}min @ 79% + {finish_minutes}min @ 83%"
baseline_activity_text: "40min @ 72% + 20min @ 79% + 10min @ 83%"
baseline_estimated_tss: 66.8
baseline_total_minutes: 70
baseline_avg_if: 0.76
baseline_max_if: 0.83
scaling_axis: preload_duration
scaling_band_pct:
  - -20.7
  - 13.0
selection_window_tss:
  - 53.0
  - 75.5
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "30min @ 72% + 15min @ 79% + 10min @ 83%"
    estimated_tss: 53.0
    total_minutes: 55
    avg_if: 0.76
    max_if: 0.83
    pct_from_baseline_tss: -20.7
  - scale_label: baseline
    activity_text: "40min @ 72% + 20min @ 79% + 10min @ 83%"
    estimated_tss: 66.8
    total_minutes: 70
    avg_if: 0.76
    max_if: 0.83
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "50min @ 72% + 20min @ 79% + 10min @ 83%"
    estimated_tss: 75.5
    total_minutes: 80
    avg_if: 0.75
    max_if: 0.83
    pct_from_baseline_tss: 13.0
machine_notes:
  - "Progressive templates are support by default unless the finish block becomes hard enough to change category."
---

# Progressive - 40min @ 72% + 20min @ 79% + 10min @ 83%

## Session note

This is the default progression template: controlled early, moderately strong late, and still below true hard-session cost.

## Best use

- support days that should finish stronger without becoming threshold work
- blocks that want some variety in aerobic pressure without adding another hard anchor

## Scaling note

Scale mostly through the easy preload. If the finish becomes threshold-like, move to `mixed-combo` or `lt1-threshold`.

---
template_id: support_50min_72_20min_80
category: moderate-support
session_family: support
structural_subtype: progression
load_role: moderate-support
planning_intent: raise-support-load
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: easy-to-moderate-support
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: general-aerobic
durability_cost: medium
activity_text_template: "{support_minutes}min @ 72% + {moderate_minutes}min @ 80%"
baseline_activity_text: "50min @ 72% + 20min @ 80%"
baseline_estimated_tss: 64.5
baseline_total_minutes: 70
baseline_avg_if: 0.74
baseline_max_if: 0.80
scaling_axis: total_duration_with_fixed_progression_shape
scaling_band_pct:
  - -21.6
  - 21.7
selection_window_tss:
  - 50.6
  - 78.5
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "40min @ 72% + 15min @ 80%"
    estimated_tss: 50.6
    total_minutes: 55
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: -21.6
  - scale_label: baseline
    activity_text: "50min @ 72% + 20min @ 80%"
    estimated_tss: 64.5
    total_minutes: 70
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "60min @ 72% + 25min @ 80%"
    estimated_tss: 78.5
    total_minutes: 85
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 21.7
machine_notes:
  - "Canonical support template for productive non-hard work."
---

# Support - 50min @ 72% + 20min @ 80%

## Session note

This is the default productive support template: more useful than plain easy work, but still not meant to displace the week's real anchors.

## Best use

- support days that should contribute load without becoming a hard session
- x-train or run days where easy-only would undershoot the weekly budget

## Scaling note

Keep the progression shape intact. If the final block starts to become event-specific or truly hard, move to `specific-endurance` or `mixed-combo`.

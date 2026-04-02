---
template_id: xtrain_60min_78_10min_82
category: moderate-support
session_family: x-train-specific
structural_subtype: progression
load_role: support
planning_intent: build-xtrain-support
bucket: steady
stress_class: support
hard_subtype: null
physiology_label: moderate-aerobic-xtrain
modality_pattern: xtrain-only
modality_scope: xtrain-only
phase_fit:
  - return
  - base
  - capacity-build
  - specificity
specificity_target: xtrain-support
durability_cost: low
activity_text_template: "{xtrain_minutes}min xtrain @ 78% + {finish_minutes}min @ 82%"
baseline_activity_text: "60min xtrain @ 78% + 10min @ 82%"
baseline_estimated_tss: 72.0
baseline_total_minutes: 70
baseline_avg_if: 0.79
baseline_max_if: 0.82
scaling_axis: total_duration_with_fixed_xtrain_finish
scaling_band_pct:
  - -21.1
  - 21.2
selection_window_tss:
  - 56.8
  - 87.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "45min xtrain @ 78% + 10min @ 82%"
    estimated_tss: 56.8
    total_minutes: 55
    avg_if: 0.79
    max_if: 0.82
    pct_from_baseline_tss: -21.1
  - scale_label: baseline
    activity_text: "60min xtrain @ 78% + 10min @ 82%"
    estimated_tss: 72.0
    total_minutes: 70
    avg_if: 0.79
    max_if: 0.82
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "75min xtrain @ 78% + 10min @ 82%"
    estimated_tss: 87.3
    total_minutes: 85
    avg_if: 0.79
    max_if: 0.82
    pct_from_baseline_tss: 21.2
machine_notes:
  - "X-train-specific templates let support work stay productive while running stays capped."
---

# X-Train Specific - 60min xtrain @ 78% + 10min @ 82%

## Session note

This is the canonical moderate-aerobic x-train template: productive enough to matter, but still clearly support work.

## Best use

- periods where total work should stay high while running stays modest
- support days where x-train is the right tool rather than a fallback

## Scaling note

Scale mainly with x-train duration. If the finish block starts to become hard enough to carry the day, move to a threshold or specific family instead.

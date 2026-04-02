---
template_id: recovery_run_35min_69
category: easy-support
session_family: recovery
structural_subtype: continuous
load_role: recovery
planning_intent: absorb-fatigue
bucket: recovery
stress_class: support
hard_subtype: null
physiology_label: low-cost-aerobic-rhythm
modality_pattern: run-only
modality_scope: run-only
phase_fit:
  - return
  - base
  - capacity-build
  - taper
specificity_target: general-aerobic
durability_cost: low
activity_text_template: "{duration_minutes}min run @ {if_percent}%"
baseline_activity_text: "35min run @ 69%"
baseline_estimated_tss: 27.8
baseline_total_minutes: 35
baseline_avg_if: 0.69
baseline_max_if: 0.69
scaling_axis: duration_with_small_intensity_adjustment
scaling_band_pct:
  - -14.4
  - 17.6
selection_window_tss:
  - 23.8
  - 32.7
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "30min run @ 69%"
    estimated_tss: 23.8
    total_minutes: 30
    avg_if: 0.69
    max_if: 0.69
    pct_from_baseline_tss: -14.4
  - scale_label: baseline
    activity_text: "35min run @ 69%"
    estimated_tss: 27.8
    total_minutes: 35
    avg_if: 0.69
    max_if: 0.69
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "40min run @ 70%"
    estimated_tss: 32.7
    total_minutes: 40
    avg_if: 0.70
    max_if: 0.70
    pct_from_baseline_tss: 17.6
machine_notes:
  - "Recovery templates stay explicitly low cost and run-specific when rhythm matters."
---

# Recovery - 35min run @ 69%

## Session note

This is the default run-based recovery template: low stress, light rhythm, and minimal structural cost.

## Best use

- recovery days where some running contact is still useful
- low-load bridge days before or after a true hard anchor

## Scaling note

Scale mostly with duration. If the day starts to behave like support rather than recovery, move to an `easy` or `support` family template instead.

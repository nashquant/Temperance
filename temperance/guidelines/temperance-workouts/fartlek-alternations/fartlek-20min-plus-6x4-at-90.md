---
template_id: fartlek_20min_72_6x4_90_2float78
category: threshold-hard
session_family: fartlek-alternations
structural_subtype: alternation
load_role: primary-hard
planning_intent: build-threshold-alternation
bucket: fartlek
stress_class: hard
hard_subtype: h1
physiology_label: larger-amplitude-fartlek
modality_pattern: generic
modality_scope: any
phase_fit:
  - capacity-build
  - specificity
specificity_target: mixed-specificity
durability_cost: medium
activity_text_template: "20min @ 72% + {fartlek_reps}x4' @ 90% (2' @ 78%)"
baseline_activity_text: "20min @ 72% + 6x4' @ 90% (2' @ 78%)"
baseline_estimated_tss: 61.8
baseline_total_minutes: 56
baseline_avg_if: 0.81
baseline_max_if: 0.90
scaling_axis: rep_count
scaling_band_pct:
  - -12.0
  - 12.1
selection_window_tss:
  - 54.4
  - 69.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 5x4' @ 90% (2' @ 78%)"
    estimated_tss: 54.4
    total_minutes: 50
    avg_if: 0.81
    max_if: 0.90
    pct_from_baseline_tss: -12.0
  - scale_label: baseline
    activity_text: "20min @ 72% + 6x4' @ 90% (2' @ 78%)"
    estimated_tss: 61.8
    total_minutes: 56
    avg_if: 0.81
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 7x4' @ 90% (2' @ 78%)"
    estimated_tss: 69.3
    total_minutes: 62
    avg_if: 0.82
    max_if: 0.90
    pct_from_baseline_tss: 12.1
machine_notes:
  - "This is the explicit sharper fartlek variant in the library."
  - "Use it when the alternation itself is part of the hard-session identity, not just a support rhythm device."
---

# Fartlek Alternations - 20min @ 72% + 6x4' @ 90% (2' @ 78%)

## Session note

This is the sharper fartlek variant: still alternation-based, but with enough amplitude to behave like a real threshold-hard session rather than support rhythm work.

## Best use

- blocks that want a hard session with alternation feel instead of cleaner threshold reps
- days where changing rhythm helps execution more than holding one static threshold shape

## Recovery

Use `2' @ 78%` between work reps. The float should stay meaningful enough to preserve alternation rather than turning the session into simple reps with full reset.

## Scaling note

Scale with rep count. If the day wants smaller amplitude and less structural cost, move to the default fartlek template instead.

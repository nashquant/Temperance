---
template_id: threshold_20min_72_3x8_90_2rec
category: threshold-hard
session_family: lt1-threshold
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: supported-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: lt1-threshold
durability_cost: medium
activity_text_template: "20min @ 72% + {threshold_reps}x8' @ 90% (2' @ 72%)"
baseline_activity_text: "20min @ 72% + 3x8' @ 90% (2' @ 72%)"
baseline_estimated_tss: 53.1
baseline_total_minutes: 48
baseline_avg_if: 0.81
baseline_max_if: 0.90
scaling_axis: threshold_rep_count
scaling_band_pct:
  - -23.5
  - 23.7
selection_window_tss:
  - 40.6
  - 65.7
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 2x8' @ 90% (2' @ 72%)"
    estimated_tss: 40.6
    total_minutes: 38
    avg_if: 0.80
    max_if: 0.90
    pct_from_baseline_tss: -23.5
  - scale_label: baseline
    activity_text: "20min @ 72% + 3x8' @ 90% (2' @ 72%)"
    estimated_tss: 53.1
    total_minutes: 48
    avg_if: 0.81
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 4x8' @ 90% (2' @ 72%)"
    estimated_tss: 65.7
    total_minutes: 58
    avg_if: 0.82
    max_if: 0.90
    pct_from_baseline_tss: 23.7
machine_notes:
  - "Longer easy setup makes this LT1 threshold session partly support-oriented."
---

# LT1 Threshold - 20min @ 72% + 3x8' @ 90% (2' @ 72%)

## Session note

This is a supported LT1 threshold session with a longer easy lead-in and a slightly softer overall feel than denser threshold templates.

## Best use

- threshold days early in the block or after recent hard density
- mixed-support days where threshold should appear without dominating the whole session

## Recovery

Use `2' @ 72%` between reps. Recoveries should stay composed and aerobic.

## Scaling note

Scale by rep count. If you want the same total TSS but less threshold presence, shift toward `steady-aerobic` or `support`.

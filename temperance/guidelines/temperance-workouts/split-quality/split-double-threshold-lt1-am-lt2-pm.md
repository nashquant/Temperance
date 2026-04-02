---
template_id: split_threshold_lt1_am_lt2_pm
category: threshold-hard
session_family: split-quality
structural_subtype: split-day
load_role: primary-hard
planning_intent: increase-quality-density
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: split-threshold-lt1-am-lt2-pm
modality_pattern: split-day
modality_scope: any
phase_fit:
  - specificity
  - peak
specificity_target: threshold-density
durability_cost: high
composite_kind: split-day
activity_text_template: "AM: {am_activity} | PM: {pm_activity}"
baseline_activity_text: "AM: 20min @ 72% + 4x8' @ 90% (90s @ 75%) | PM: 15min @ 72% + 6x3' @ 100% (60s @ 75%)"
baseline_estimated_tss: 114.7
baseline_estimated_tss_total: 114.7
baseline_total_minutes: 97
baseline_avg_if: 0.84
baseline_max_if: 1.00
session_parts:
  - part_label: am
    activity_text: "20min @ 72% + 4x8' @ 90% (90s @ 75%)"
    estimated_tss: 66.1
    total_minutes: 58
    avg_if: 0.83
    max_if: 0.90
  - part_label: pm
    activity_text: "15min @ 72% + 6x3' @ 100% (60s @ 75%)"
    estimated_tss: 48.6
    total_minutes: 39
    avg_if: 0.86
    max_if: 1.00
scaling_axis: am_pm_rep_count
scaling_band_pct:
  - -15.9
  - 15.8
selection_window_tss:
  - 96.5
  - 132.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "AM: 20min @ 72% + 3x8' @ 90% (90s @ 75%) | PM: 15min @ 72% + 5x3' @ 100% (60s @ 75%)"
    estimated_tss: 96.5
    total_minutes: 83.5
    avg_if: 0.82
    max_if: 1.00
    pct_from_baseline_tss: -15.9
    session_parts:
      - part_label: am
        activity_text: "20min @ 72% + 3x8' @ 90% (90s @ 75%)"
        estimated_tss: 53.9
        total_minutes: 48.5
        avg_if: 0.82
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 5x3' @ 100% (60s @ 75%)"
        estimated_tss: 42.6
        total_minutes: 35
        avg_if: 0.86
        max_if: 1.00
  - scale_label: baseline
    activity_text: "AM: 20min @ 72% + 4x8' @ 90% (90s @ 75%) | PM: 15min @ 72% + 6x3' @ 100% (60s @ 75%)"
    estimated_tss: 114.7
    total_minutes: 97
    avg_if: 0.84
    max_if: 1.00
    pct_from_baseline_tss: 0.0
    session_parts:
      - part_label: am
        activity_text: "20min @ 72% + 4x8' @ 90% (90s @ 75%)"
        estimated_tss: 66.1
        total_minutes: 58
        avg_if: 0.83
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 6x3' @ 100% (60s @ 75%)"
        estimated_tss: 48.6
        total_minutes: 39
        avg_if: 0.86
        max_if: 1.00
  - scale_label: up
    activity_text: "AM: 20min @ 72% + 5x8' @ 90% (90s @ 75%) | PM: 15min @ 72% + 7x3' @ 100% (60s @ 75%)"
    estimated_tss: 132.8
    total_minutes: 110.5
    avg_if: 0.85
    max_if: 1.00
    pct_from_baseline_tss: 15.8
    session_parts:
      - part_label: am
        activity_text: "20min @ 72% + 5x8' @ 90% (90s @ 75%)"
        estimated_tss: 78.3
        total_minutes: 67.5
        avg_if: 0.83
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 7x3' @ 100% (60s @ 75%)"
        estimated_tss: 54.5
        total_minutes: 43
        avg_if: 0.87
        max_if: 1.00
machine_notes:
  - "Morning stays LT1-oriented and evening stays LT2-oriented."
  - "Use roughly 88-92% for LT1 work and 98-102% for LT2 work, with the LT2 session kept in short 2-4 minute reps."
  - "Each session part is the machine-safe source of truth, not the combined summary string."
---

# Split Quality - LT1 AM and LT2 PM

## Session note

This is the default split-threshold density day for the library: easier LT1-style work in the morning, then true short-rep LT2 work in the evening.

## Best use

- explicit split-quality days only after the build has clearly earned the density
- blocks that want double threshold without flattening both sessions into the same threshold level

## Recovery

Use `90s @ 75%` in the morning and `60s @ 75%` in the evening. Keep the gap between AM and PM as normal day-level recovery rather than as part of one continuous session.

## Scaling note

Scale by rep count in both parts together. If only one part should exist, do not use this family; choose the corresponding single-session LT1 or LT2 template instead.

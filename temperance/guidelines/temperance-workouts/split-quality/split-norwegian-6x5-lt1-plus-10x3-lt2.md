---
template_id: split_norwegian_6x5_lt1_10x3_lt2
category: threshold-hard
session_family: split-quality
structural_subtype: split-day
load_role: primary-hard
planning_intent: increase-quality-density
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: classic-norwegian-double-threshold
modality_pattern: split-day
modality_scope: any
phase_fit:
  - specificity
  - peak
specificity_target: threshold-density
durability_cost: high
composite_kind: split-day
activity_text_template: "AM: {am_activity} | PM: {pm_activity}"
baseline_activity_text: "AM: 20min @ 72% + 6x5' @ 90% (75s @ 75%) | PM: 15min @ 72% + 10x3' @ 100% (60s @ 75%)"
baseline_estimated_tss: 137.1
baseline_estimated_tss_total: 137.1
baseline_total_minutes: 112.5
baseline_avg_if: 0.86
baseline_max_if: 1.00
session_parts:
  - part_label: am
    activity_text: "20min @ 72% + 6x5' @ 90% (75s @ 75%)"
    estimated_tss: 64.8
    total_minutes: 57.5
    avg_if: 0.82
    max_if: 0.90
  - part_label: pm
    activity_text: "15min @ 72% + 10x3' @ 100% (60s @ 75%)"
    estimated_tss: 72.3
    total_minutes: 55
    avg_if: 0.89
    max_if: 1.00
scaling_axis: am_pm_rep_count
scaling_band_pct:
  - -17.6
  - 14.4
selection_window_tss:
  - 113.0
  - 156.9
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "AM: 15min @ 72% + 5x5' @ 90% (75s @ 75%) | PM: 15min @ 72% + 8x3' @ 100% (60s @ 75%)"
    estimated_tss: 113.0
    total_minutes: 93.2
    avg_if: 0.85
    max_if: 1.00
    pct_from_baseline_tss: -17.6
    session_parts:
      - part_label: am
        activity_text: "15min @ 72% + 5x5' @ 90% (75s @ 75%)"
        estimated_tss: 52.6
        total_minutes: 46.2
        avg_if: 0.83
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 8x3' @ 100% (60s @ 75%)"
        estimated_tss: 60.5
        total_minutes: 47
        avg_if: 0.88
        max_if: 1.00
  - scale_label: baseline
    activity_text: "AM: 20min @ 72% + 6x5' @ 90% (75s @ 75%) | PM: 15min @ 72% + 10x3' @ 100% (60s @ 75%)"
    estimated_tss: 137.1
    total_minutes: 112.5
    avg_if: 0.86
    max_if: 1.00
    pct_from_baseline_tss: 0.0
    session_parts:
      - part_label: am
        activity_text: "20min @ 72% + 6x5' @ 90% (75s @ 75%)"
        estimated_tss: 64.8
        total_minutes: 57.5
        avg_if: 0.82
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 10x3' @ 100% (60s @ 75%)"
        estimated_tss: 72.3
        total_minutes: 55
        avg_if: 0.89
        max_if: 1.00
  - scale_label: up
    activity_text: "AM: 20min @ 72% + 7x5' @ 90% (75s @ 75%) | PM: 15min @ 72% + 12x3' @ 100% (60s @ 75%)"
    estimated_tss: 156.9
    total_minutes: 126.8
    avg_if: 0.86
    max_if: 1.00
    pct_from_baseline_tss: 14.4
    session_parts:
      - part_label: am
        activity_text: "20min @ 72% + 7x5' @ 90% (75s @ 75%)"
        estimated_tss: 72.7
        total_minutes: 63.8
        avg_if: 0.83
        max_if: 0.90
      - part_label: pm
        activity_text: "15min @ 72% + 12x3' @ 100% (60s @ 75%)"
        estimated_tss: 84.2
        total_minutes: 63
        avg_if: 0.90
        max_if: 1.00
machine_notes:
  - "Classic Norwegian double threshold pattern: LT1-oriented AM, LT2-oriented PM."
  - "LT1 work can live around 88-92% depending on rep length, while the LT2 evening part should stay around 98-102% in 2-4 minute reps."
  - "Evening session uses shorter reps and materially higher intensity."
---

# Split Quality - Norwegian 6x5 LT1 and 10x3 LT2

## Session note

This is the classic Norwegian-style double threshold template: LT1-oriented work in the morning, then a shorter-rep LT2 session in the evening.

## Best use

- explicit double-threshold days when the build clearly supports high quality density
- blocks that want the classic LT1 AM and LT2 PM split rather than two similar threshold sessions

## Recovery

Use `75s @ 75%` in the morning and `60s @ 75%` in the evening. The evening recoveries stay shorter to preserve the LT2 character.

## Scaling note

Scale the morning and evening rep counts together. If the day cannot support two meaningful sessions, do not partially use this template.

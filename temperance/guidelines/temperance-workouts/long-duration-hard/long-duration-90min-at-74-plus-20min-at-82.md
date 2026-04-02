---
template_id: long_90min_74_20min_82
category: long-duration-hard
bucket: long
stress_class: hard
hard_subtype: h1
physiology_label: compact-hard-long
modality_scope: any
activity_text_template: "{support_minutes}min @ 74% + {late_block_minutes}min @ 82%"
baseline_activity_text: "90min @ 74% + 20min @ 82%"
baseline_estimated_tss: 104.6
baseline_total_minutes: 110
baseline_avg_if: 0.76
baseline_max_if: 0.82
scaling_axis: total_duration_with_fixed_late_load_shape
scaling_band_pct:
  - -14.1
  - 14.1
selection_window_tss:
  - 89.8
  - 119.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "80min @ 74% + 15min @ 82%"
    estimated_tss: 89.8
    total_minutes: 95
    avg_if: 0.75
    max_if: 0.82
    pct_from_baseline_tss: -14.1
  - scale_label: baseline
    activity_text: "90min @ 74% + 20min @ 82%"
    estimated_tss: 104.6
    total_minutes: 110
    avg_if: 0.76
    max_if: 0.82
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "100min @ 74% + 25min @ 82%"
    estimated_tss: 119.3
    total_minutes: 125
    avg_if: 0.76
    max_if: 0.82
    pct_from_baseline_tss: 14.1
machine_notes:
  - "Compact long-duration hard session."
  - "Duration is the main stress driver, with a meaningful late moderate-to-strong block."
---

# Long Duration Hard - 90min @ 74% + 20min @ 82%

## Session note

This is a compact hard long-session template. The duration carries most of the cost, and the late block makes the day meaningfully hard without turning it sharp.

## Best use

- hard long runs or long x-train sessions that should still leave room for another hard anchor elsewhere in the week
- build phases where long-session durability and late composure both matter
- weeks that need a real long-session signal without pushing total duration too far

## Scaling note

Preserve the late-load shape. If the day should become mostly a pure duration play, move to a straighter long-duration template instead.

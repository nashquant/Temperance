---
template_id: long_120min_76
category: long-duration-hard
bucket: long
stress_class: hard
hard_subtype: h1
physiology_label: steady-durability-long
modality_scope: any
activity_text_template: "{long_minutes}min @ 76%"
baseline_activity_text: "120min @ 76%"
baseline_estimated_tss: 115.5
baseline_total_minutes: 120
baseline_avg_if: 0.76
baseline_max_if: 0.76
scaling_axis: total_duration
scaling_band_pct:
  - -20.8
  - 20.9
selection_window_tss:
  - 91.5
  - 139.6
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "95min @ 76%"
    estimated_tss: 91.5
    total_minutes: 95
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: -20.8
  - scale_label: baseline
    activity_text: "120min @ 76%"
    estimated_tss: 115.5
    total_minutes: 120
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "145min @ 76%"
    estimated_tss: 139.6
    total_minutes: 145
    avg_if: 0.76
    max_if: 0.76
    pct_from_baseline_tss: 20.9
machine_notes:
  - "Straight long-duration template."
  - "Use when steady durability load matters more than shape changes."
---

# Long Duration Hard - 120min @ 76%

## Session note

This is the simplest hard long-session anchor in the library: steady, duration-driven, and intentionally free of extra shape.

## Best use

- long runs or long aerobic sessions where straight durability is the main point
- phases that need long-session robustness more than moderate or specific finishing work
- weeks where adding structure would create more cost than value

## Scaling note

Scale only with duration. If the session needs a meaningful late block, choose a shaped long-duration or specific-endurance template instead.

---
template_id: specific_105min_72_30min_80
category: specific-hard
bucket: long
stress_class: hard
hard_subtype: h1
physiology_label: late-load-specific-endurance
modality_scope: any
activity_text_template: "{support_minutes}min @ 72% + {specific_block_minutes}min @ 80%"
baseline_activity_text: "105min @ 72% + 30min @ 80%"
baseline_estimated_tss: 122.7
baseline_total_minutes: 135
baseline_avg_if: 0.74
baseline_max_if: 0.80
scaling_axis: preload_and_late_block_minutes
scaling_band_pct:
  - -19.2
  - 19.2
selection_window_tss:
  - 99.1
  - 146.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "90min @ 72% + 20min @ 80%"
    estimated_tss: 99.1
    total_minutes: 110
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: -19.2
  - scale_label: baseline
    activity_text: "105min @ 72% + 30min @ 80%"
    estimated_tss: 122.7
    total_minutes: 135
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "120min @ 72% + 40min @ 80%"
    estimated_tss: 146.3
    total_minutes: 160
    avg_if: 0.74
    max_if: 0.80
    pct_from_baseline_tss: 19.2
machine_notes:
  - "The event overlay decides when this counts as truly specific."
  - "Without that context, it behaves like a late-load endurance session."
---

# Specific Hard - 105min @ 72% + 30min @ 80%

## Session note

This is the generic specific-endurance template in the library. Its planning value depends on the active event overlay more than the threshold or sharp templates do.

## Best use

- event overlays that value long pre-load followed by a sustained moderate finish
- build phases where late-load composure and fueled durability matter
- sessions that should bridge long-duration work and event-specific work without going sharp

## Scaling note

Keep the late-load structure intact. If the current event overlay does not treat this shape as specific, classify it as a long-duration hard variant instead of forcing the label.

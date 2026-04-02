---
template_id: specific_30min_72_3x12_82_4rec
category: specific-hard
session_family: specific-endurance
structural_subtype: broken-continuous
load_role: specific-endurance
planning_intent: build-specific-endurance
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: broken-specific-endurance
modality_pattern: generic
modality_scope: any
phase_fit:
  - specificity
  - peak
specificity_target: event-defined-specificity
durability_cost: medium
activity_text_template: "30min @ 72% + {specific_reps}x12' @ 82% (4' @ 72%)"
baseline_activity_text: "30min @ 72% + 3x12' @ 82% (4' @ 72%)"
baseline_estimated_tss: 73.2
baseline_total_minutes: 74
baseline_avg_if: 0.77
baseline_max_if: 0.82
scaling_axis: specific_rep_count
scaling_band_pct:
  - -23.1
  - 23.1
selection_window_tss:
  - 56.3
  - 90.1
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "30min @ 72% + 2x12' @ 82% (4' @ 72%)"
    estimated_tss: 56.3
    total_minutes: 58
    avg_if: 0.76
    max_if: 0.82
    pct_from_baseline_tss: -23.1
  - scale_label: baseline
    activity_text: "30min @ 72% + 3x12' @ 82% (4' @ 72%)"
    estimated_tss: 73.2
    total_minutes: 74
    avg_if: 0.77
    max_if: 0.82
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "30min @ 72% + 4x12' @ 82% (4' @ 72%)"
    estimated_tss: 90.1
    total_minutes: 90
    avg_if: 0.77
    max_if: 0.82
    pct_from_baseline_tss: 23.1
machine_notes:
  - "This is the less marathon-shaped specific-endurance anchor."
  - "The active event overlay still decides whether this is truly specific or just strong endurance work."
---

# Specific Endurance - 30min @ 72% + 3x12' @ 82% (4' @ 72%)

## Session note

This is the broken specific-endurance anchor: a moderate preload followed by multiple sustained specific blocks instead of one very long late-load finish.

## Best use

- event overlays that value repeated specific exposure more than one continuous long finish
- builds that need a more transferable specific-endurance shape than the long-preload template

## Recovery

Use `4' @ 72%` between blocks. The recoveries should reset the structure slightly without turning the session into short intervals.

## Scaling note

Scale by block count. If the active overlay wants one long continuous finish instead, move to the long-preload specific-endurance template rather than stretching this one.

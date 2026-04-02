---
template_id: hills_20min_run_4x6_90_2rec
category: threshold-hard
session_family: hills-strength-endurance
structural_subtype: intervals
load_role: primary-hard
planning_intent: build-hill-strength
bucket: intervals
stress_class: hard
hard_subtype: h1
physiology_label: hill-strength-endurance
modality_pattern: run-only
modality_scope: run-only
phase_fit:
  - base
  - capacity-build
specificity_target: hill-strength
durability_cost: medium
activity_text_template: "20min run @ 72% + {hill_reps}x6' uphill @ 90% (2' @ 70%)"
baseline_activity_text: "20min run @ 72% + 4x6' uphill @ 90% (2' @ 70%)"
baseline_estimated_tss: 54.6
baseline_total_minutes: 50
baseline_avg_if: 0.81
baseline_max_if: 0.90
scaling_axis: hill_rep_count
scaling_band_pct:
  - -17.9
  - 17.8
selection_window_tss:
  - 44.8
  - 64.3
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min run @ 72% + 3x6' uphill @ 90% (2' @ 70%)"
    estimated_tss: 44.8
    total_minutes: 42
    avg_if: 0.80
    max_if: 0.90
    pct_from_baseline_tss: -17.9
  - scale_label: baseline
    activity_text: "20min run @ 72% + 4x6' uphill @ 90% (2' @ 70%)"
    estimated_tss: 54.6
    total_minutes: 50
    avg_if: 0.81
    max_if: 0.90
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min run @ 72% + 5x6' uphill @ 90% (2' @ 70%)"
    estimated_tss: 64.3
    total_minutes: 58
    avg_if: 0.82
    max_if: 0.90
    pct_from_baseline_tss: 17.8
machine_notes:
  - "Hill templates are explicitly run-only because the terrain is part of the session identity."
---

# Hills Strength Endurance - 20min run @ 72% + 4x6' uphill @ 90% (2' @ 70%)

## Session note

This is the canonical hill-strength template: long enough to matter aerobically, short enough to keep the work clearly hill-specific.

## Best use

- base and capacity phases that want run-specific strength without turning the day fully sharp
- periods where flat threshold work is not the only useful H1 option

## Recovery

Use `2' @ 70%` between reps. Let the recovery restore posture before the next uphill block.

## Scaling note

Scale with rep count. If the day wants shorter and sharper uphill work, move to a different hill subtype rather than forcing this one.

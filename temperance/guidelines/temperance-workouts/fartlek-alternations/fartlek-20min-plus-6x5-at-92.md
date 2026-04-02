---
template_id: fartlek_20min_72_6x5_92_2rec
category: threshold-hard
session_family: fartlek-alternations
structural_subtype: alternation
load_role: primary-hard
planning_intent: build-threshold-density
bucket: fartlek
stress_class: hard
hard_subtype: h1
physiology_label: threshold-fartlek
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: mixed-specificity
durability_cost: medium
activity_text_template: "20min @ 72% + {fartlek_reps}x5' @ 92% (2' @ 78%)"
baseline_activity_text: "20min @ 72% + 6x5' @ 92% (2' @ 78%)"
baseline_estimated_tss: 69.7
baseline_total_minutes: 60
baseline_avg_if: 0.84
baseline_max_if: 0.92
scaling_axis: rep_count
scaling_band_pct:
  - -12.9
  - 13.1
selection_window_tss:
  - 60.7
  - 78.8
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 5x5' @ 92% (2' @ 78%)"
    estimated_tss: 60.7
    total_minutes: 53
    avg_if: 0.83
    max_if: 0.92
    pct_from_baseline_tss: -12.9
  - scale_label: baseline
    activity_text: "20min @ 72% + 6x5' @ 92% (2' @ 78%)"
    estimated_tss: 69.7
    total_minutes: 60
    avg_if: 0.84
    max_if: 0.92
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 7x5' @ 92% (2' @ 78%)"
    estimated_tss: 78.8
    total_minutes: 67
    avg_if: 0.84
    max_if: 0.92
    pct_from_baseline_tss: 13.1
machine_notes:
  - "Fartlek templates preserve variation, but the alternation still needs a planning role."
---

# Fartlek Alternations - 20min @ 72% + 6x5' @ 92% (2' @ 78%)

## Session note

This is the canonical threshold-fartlek template: variable enough to feel alive, but still organized enough to count as real work rather than random intensity.

## Best use

- threshold blocks that want more variation without going fully VO2-oriented
- days where alternation is mechanically or mentally easier than long steady reps

## Recovery

Use `2' @ 78%` between work reps. The float should stay strong enough to keep the session continuous.

## Scaling note

Scale with rep count. If the day wants a cleaner rhythm, choose `lt1-threshold`, `lt2-threshold`, or `cruise-intervals` based on the intended intensity band.

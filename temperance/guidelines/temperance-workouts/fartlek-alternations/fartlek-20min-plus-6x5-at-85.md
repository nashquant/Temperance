---
template_id: fartlek_20min_72_6x5_85_2float80
category: moderate-support
session_family: fartlek-alternations
structural_subtype: alternation
load_role: moderate-support
planning_intent: build-aerobic-rhythm
bucket: fartlek
stress_class: support
hard_subtype: null
physiology_label: small-amplitude-fartlek
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: steady-aerobic
durability_cost: medium
activity_text_template: "20min @ 72% + {fartlek_reps}x5' @ 85% (2' @ 80%)"
baseline_activity_text: "20min @ 72% + 6x5' @ 85% (2' @ 80%)"
baseline_estimated_tss: 66.2
baseline_total_minutes: 62
baseline_avg_if: 0.80
baseline_max_if: 0.85
scaling_axis: rep_count
scaling_band_pct:
  - -12.2
  - 12.4
selection_window_tss:
  - 58.1
  - 74.4
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 5x5' @ 85% (2' @ 80%)"
    estimated_tss: 58.1
    total_minutes: 55
    avg_if: 0.80
    max_if: 0.85
    pct_from_baseline_tss: -12.2
  - scale_label: baseline
    activity_text: "20min @ 72% + 6x5' @ 85% (2' @ 80%)"
    estimated_tss: 66.2
    total_minutes: 62
    avg_if: 0.80
    max_if: 0.85
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 7x5' @ 85% (2' @ 80%)"
    estimated_tss: 74.4
    total_minutes: 69
    avg_if: 0.80
    max_if: 0.85
    pct_from_baseline_tss: 12.4
machine_notes:
  - "Fartlek templates should usually use a smaller amplitude than threshold intervals unless a sharper variant is authored explicitly."
---

# Fartlek Alternations - 20min @ 72% + 6x5' @ 85% (2' @ 80%)

## Session note

This is the canonical small-amplitude fartlek template: the faster side sits closer to marathon-like rhythm, while the float stays in high Z2 to low Z3 territory rather than dropping back toward easy running.

## Best use

- support or bridge days that want controlled variation without becoming a true hard anchor
- blocks that want some marathon-supportive rhythm change without the amplitude of threshold intervals

## Recovery

Use `2' @ 80%` between work reps. The float should stay only slightly below the work segment so the session reads as rhythm change rather than hard/easy contrast.

## Scaling note

Scale with rep count. If the day wants larger amplitude or true threshold pressure, move to `lt1-threshold` or `lt2-threshold` instead.

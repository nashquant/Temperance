---
template_id: cruise_20min_72_5x6_91_90srec
category: threshold-hard
session_family: lt1-threshold
structural_subtype: float-intervals
load_role: primary-hard
planning_intent: build-lt1-threshold
bucket: tempo
stress_class: hard
hard_subtype: h1
physiology_label: dense-lt1-threshold
modality_pattern: generic
modality_scope: any
phase_fit:
  - base
  - capacity-build
  - specificity
specificity_target: lt1-threshold
durability_cost: medium
activity_text_template: "20min @ 72% + {cruise_reps}x6' @ 91% (90s @ 75%)"
baseline_activity_text: "20min @ 72% + 5x6' @ 91% (90s @ 75%)"
baseline_estimated_tss: 64.3
baseline_total_minutes: 56
baseline_avg_if: 0.83
baseline_max_if: 0.91
scaling_axis: rep_count
scaling_band_pct:
  - -15.1
  - 15.1
selection_window_tss:
  - 54.6
  - 74.0
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "20min @ 72% + 4x6' @ 91% (90s @ 75%)"
    estimated_tss: 54.6
    total_minutes: 48.5
    avg_if: 0.82
    max_if: 0.91
    pct_from_baseline_tss: -15.1
  - scale_label: baseline
    activity_text: "20min @ 72% + 5x6' @ 91% (90s @ 75%)"
    estimated_tss: 64.3
    total_minutes: 56
    avg_if: 0.83
    max_if: 0.91
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "20min @ 72% + 6x6' @ 91% (90s @ 75%)"
    estimated_tss: 74.0
    total_minutes: 63.5
    avg_if: 0.84
    max_if: 0.91
    pct_from_baseline_tss: 15.1
machine_notes:
  - "Cruise intervals are a structural presentation of LT1-threshold work, not a separate physiology family."
  - "This template stays in the legacy cruise-intervals path for compatibility, but its canonical session_family is lt1-threshold."
---

# LT1 Threshold (Cruise Style) - 20min @ 72% + 5x6' @ 91% (90s @ 75%)

## Session note

This is the canonical cruise-style LT1 threshold template: broken threshold work with short aerobic floats so the session keeps threshold pressure without becoming a separate category.

## Best use

- threshold days that want denser restart points and slightly more rhythm than the smoother LT1 templates
- blocks that want classic cruise-interval structure while still staying inside the existing LT1 band

## Recovery

Use `90s @ 75%` between reps. The recoveries should stay short and meaningfully aerobic so the workout reads as floated LT1 work instead of hard/easy contrast.

## Scaling note

Scale with rep count. If the day wants less density, move to another `lt1-threshold` template. If it wants stronger event relevance, move to `specific-endurance`.

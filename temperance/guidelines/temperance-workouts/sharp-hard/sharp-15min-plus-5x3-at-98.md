---
template_id: sharp_15min_72_5x3_98_2rec
category: sharp-hard
bucket: intervals
stress_class: hard
hard_subtype: h2
physiology_label: vo2-long-repeats
modality_scope: any
activity_text_template: "15min @ 72% + {vo2_reps}x3' @ 98% (2' @ 72%)"
baseline_activity_text: "15min @ 72% + 5x3' @ 98% (2' @ 72%)"
baseline_estimated_tss: 43.9
baseline_total_minutes: 38
baseline_avg_if: 0.83
baseline_max_if: 0.98
scaling_axis: vo2_rep_count
scaling_band_pct:
  - -14.8
  - 14.8
selection_window_tss:
  - 37.4
  - 50.4
tss_model: "segment_sum(duration_h * IF^2 * 100)"
variants:
  - scale_label: down
    activity_text: "15min @ 72% + 4x3' @ 98% (2' @ 72%)"
    estimated_tss: 37.4
    total_minutes: 33
    avg_if: 0.82
    max_if: 0.98
    pct_from_baseline_tss: -14.8
  - scale_label: baseline
    activity_text: "15min @ 72% + 5x3' @ 98% (2' @ 72%)"
    estimated_tss: 43.9
    total_minutes: 38
    avg_if: 0.83
    max_if: 0.98
    pct_from_baseline_tss: 0.0
  - scale_label: up
    activity_text: "15min @ 72% + 6x3' @ 98% (2' @ 72%)"
    estimated_tss: 50.4
    total_minutes: 43
    avg_if: 0.84
    max_if: 0.98
    pct_from_baseline_tss: 14.8
machine_notes:
  - "Longer-repeat VO2 template."
  - "A tighter scaling band keeps the session from drifting into threshold territory."
---

# Sharp Hard - 15min @ 72% + 5x3' @ 98% (2' @ 72%)

## Session note

This is the longer-repeat VO2 option. It is still sharp, but the longer reps make it feel more rhythm-based than the 2-minute template.

## Best use

- H2 days that should stay aerobic-power focused without becoming all-out
- athletes who respond better to fewer, longer hard reps than to many short starts
- blocks that want some ceiling touch but not an extreme neuromuscular session

## Recovery

Use `2' @ 72%` between reps. The recovery should be active and just long enough to keep the next rep honest.

## Scaling note

Keep this on a tight band. If scaling needs become much larger, move to another sharp template instead of stretching this one into a different session type.

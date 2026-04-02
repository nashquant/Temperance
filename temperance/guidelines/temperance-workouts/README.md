# Temperance Workout Templates

## Purpose

This directory is the reusable workout library written in Temperance `activity_text` lingo.

The design goal is:
- category first
- modality second
- saved reference TSS for each stable session idea
- narrow, explicit scaling around the baseline rather than ad hoc rewriting

Common rules live in [template-contract.md](./template-contract.md). Template files should stay thin and only carry workout-specific notes.

## Repository structure

- `template-contract.md`: shared template fields, recovery rules, scaling rules, and machine expectations
- category directories: concrete workout templates grouped by planning role
- template files: one stable session idea plus saved TSS variants

## Category model

Use planning role, not modality, as the main category.

- `easy-support`: low-cost aerobic load or recovery support
- `moderate-support`: medium-long or steady aerobic support that is not meant to be the week's main hard stress
- `threshold-hard`: controlled H1 threshold work, often low-threshold or upper-aerobic biased
- `long-duration-hard`: hard days where duration is the main cost driver
- `specific-hard`: event-specific or phase-specific endurance structure whose value depends on the active event overlay
- `sharp-hard`: H2 or VO2-oriented work where the sharper intensity is the main point

These should align to planning fields when possible:
- `bucket`
- `stress_class`
- `hard_subtype`

## Selection order

1. choose the category by planning role
2. choose the nearest baseline session whose stored window contains the target TSS
3. choose the nearest stored variant before inventing a new rewrite
4. if multiple templates are close, prefer the one whose physiology label and recovery pattern best fit the day

## TSS rule

The stored TSS in a template is the library reference estimate for that structure.

For simple `%`-based templates, use this approximation unless a better model is stored in the file:
- segment TSS = `duration_h * IF^2 * 100`
- session TSS = sum of segment TSS

That keeps the repository modality-agnostic while still preserving a usable load anchor.

## Current templates

### Threshold-hard

- [threshold-15min-plus-3x10-at-90.md](./threshold/threshold-15min-plus-3x10-at-90.md)
- [threshold-15min-plus-4x8-at-90.md](./threshold/threshold-15min-plus-4x8-at-90.md)
- [threshold-20min-plus-3x8-at-90.md](./threshold/threshold-20min-plus-3x8-at-90.md)
- [threshold-15min-plus-3x12-at-88.md](./threshold/threshold-15min-plus-3x12-at-88.md)

### Moderate-support

- [medium-long-75min-at-72.md](./moderate-support/medium-long-75min-at-72.md)
- [medium-long-60min-at-72-plus-20min-at-80.md](./moderate-support/medium-long-60min-at-72-plus-20min-at-80.md)

### Long-duration-hard

- [long-duration-90min-at-74-plus-20min-at-82.md](./long-duration-hard/long-duration-90min-at-74-plus-20min-at-82.md)
- [long-duration-120min-at-76.md](./long-duration-hard/long-duration-120min-at-76.md)

### Specific-hard

- [specific-105min-at-72-plus-30min-at-80.md](./specific-hard/specific-105min-at-72-plus-30min-at-80.md)

### Sharp-hard

- [sharp-15min-plus-8x2-at-100.md](./sharp-hard/sharp-15min-plus-8x2-at-100.md)
- [sharp-15min-plus-5x3-at-98.md](./sharp-hard/sharp-15min-plus-5x3-at-98.md)

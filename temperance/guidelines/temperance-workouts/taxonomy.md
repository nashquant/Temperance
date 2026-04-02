# Workout Taxonomy

Status: invariant workout companion.

## Purpose

This file maps the richer workout-library taxonomy back to the smaller doctrine-facing category model.

Use it when the library needs to stay broad without turning `category` into a catch-all.

## Core rule

- `category` is the doctrine-facing selector used to align a session to the current planning system.
- `session_family` is the library browsing family.
- `load_role` and `structural_subtype` narrow the family into a usable session shape.

## Family Map

| `session_family` | Typical `category` | Typical `load_role` | Common `structural_subtype` | Typical doctrine fit |
| --- | --- | --- | --- | --- |
| `recovery` | `easy-support` | `recovery` | `continuous` | absorption, rhythm, taper support |
| `easy` | `easy-support` | `support` | `continuous` | low-cost aerobic support |
| `support` | `moderate-support` | `moderate-support` | `continuous`, `progression`, `mixed-modality` | productive support without creating the week's main hard stress |
| `steady-aerobic` | `moderate-support` | `moderate-support` | `continuous`, `broken-continuous` | strong aerobic support below true hard-session cost |
| `lt1-threshold` | `threshold-hard` | `primary-hard` | `intervals`, `float-intervals`, `broken-continuous` | controlled H1 threshold in base through specificity, usually around `88-92%` depending on rep length |
| `lt2-threshold` | `threshold-hard` | `primary-hard` | `intervals`, `float-intervals` | short-rep upper-threshold work, usually around `98-102%` in `2-4min` reps while still staying H1 |
| `cruise-intervals` | `threshold-hard` | `primary-hard` | `intervals`, `alternation` | dense threshold support, often marathon-supportive without being event-defined |
| `specific-endurance` | `specific-hard` | `specific-endurance` | `continuous`, `fast-finish`, `alternation` | event-overlay-defined specificity |
| `vo2-max` | `sharp-hard` | `sharpening` | `intervals`, `alternation` | occasional H2 or ceiling-touch work, usually with short `2-3min` reps, a longer setup, and recovery generous enough to preserve pace quality |
| `hills-strength-endurance` | `threshold-hard`, `sharp-hard` | `primary-hard`, `sharpening` | `intervals` | run-specific strength or hill power depending the template |
| `progressive` | `moderate-support`, `specific-hard` | `moderate-support`, `secondary-hard` | `progression`, `fast-finish` | support or bridge work depending the finish block |
| `medium-long` | `moderate-support`, `specific-hard` | `moderate-support`, `long-durability` | `continuous`, `progression`, `fast-finish` | durable volume between support and long-session work |
| `long-run` | `long-duration-hard` | `long-durability` | `continuous`, `fast-finish`, `alternation` | duration-led long-session stress |
| `fartlek-alternations` | `threshold-hard`, `sharp-hard` | `primary-hard`, `sharpening` | `alternation` | controlled variability without random intensity |
| `strides-neuromuscular` | `easy-support` | `support`, `sharpening` | `strides-finish` | low-cost range and neuromuscular touch |
| `x-train-specific` | `moderate-support`, `threshold-hard` | `support`, `moderate-support` | `continuous`, `progression`, `intervals` | productive non-run work when x-train is the right tool |
| `mixed-combo` | `threshold-hard`, `specific-hard` | `secondary-hard`, `specific-endurance` | `mixed-modality`, `fast-finish`, `broken-continuous` | sessions that blend two useful shapes without splitting the day |
| `split-quality` | `threshold-hard`, `specific-hard` | `primary-hard` | `split-day` | explicit high-density days only when the planner wants split quality |

## Structural Subtypes

- `continuous`: one sustained block after any easy setup
- `intervals`: repeated work with recoveries
- `float-intervals`: repeated work with recoveries that stay meaningfully aerobic
- `broken-continuous`: a long block split into a small number of large pieces
- `progression`: steady rise across the session
- `fast-finish`: mostly controlled load with a clearly stronger finish
- `alternation`: repeating alternation between two intensity levels
- `mixed-modality`: two modalities inside one session
- `split-day`: distinct AM and PM parts
- `strides-finish`: low-cost neuromuscular work appended to an otherwise easy or steady session

## Load Roles

- `recovery`: absorb fatigue with minimal structural cost
- `support`: low or moderate load that mainly supports weekly structure
- `moderate-support`: productive support that still should not crowd out the week's anchors
- `primary-hard`: one of the block's main hard sessions
- `secondary-hard`: a meaningful session that still sits behind the primary anchors
- `long-durability`: duration-led durability stress
- `specific-endurance`: event-overlay-defined specific work
- `sharpening`: range, VO2, or neuromuscular touch rather than core durability work

## Modality Patterns

- `generic`: same structural idea can be used across run, bike, or elliptical
- `run-only`: the session identity depends on running
- `xtrain-only`: the session identity depends on non-run execution
- `mixed-modality`: the stored concrete string intentionally mixes modalities
- `split-day`: stored as separate AM and PM parts

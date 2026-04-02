# Training Overlay Contract

Status: invariant core companion.

## Purpose

Every reusable overlay should follow the same compact structure so the doctrine stays easy to read, compare, and version.

## Required fields

Each overlay should declare:

- `Status`
- `Profile type`
- `Profile id`
- `Objective and main limiter`
- `Primary specificity axis`
- `Hard-session priority order`
- `Spacing / density preferences`
- `Progression priorities`
- `Alert sensitivity / default responses`
- `Explicit non-goals`

## Optional fields

Use optional sections only when they materially improve planning clarity:

- `Good week notes`
- `Phase emphasis`
- `Metric mapping notes`
- `Evidence basis`
- `Open questions`

## Profile-type meaning

### Athlete-state overlay

Defines:
- what the body currently seems able to absorb
- the main limiter
- what should tighten progression or alert sensitivity

It should describe the body-state, not the event philosophy.

### Event overlay

Defines:
- what counts as specificity
- what the event is really asking for
- how to interpret a good week for that event
- which anchors deserve special protection

### Philosophy overlay

Defines:
- preferred stimulus mix
- preferred quality hierarchy
- preferred support-modality behavior
- what the planner is trying to emphasize or de-emphasize inside the event demands

## Usage rules

- Overlays are reusable profiles, not short-term notes.
- Overlays may tighten the core. They should not contradict the core.
- The active build declaration selects one athlete-state overlay, one event overlay, and one philosophy overlay.
- The active build declaration also maps core concepts to the actual metrics used in the current build.
- A local/private overlay variant may be used when the active build declaration points to a `*.local.md` profile.

## Minimal skeleton

```md
# Overlay Name

Status: reusable overlay / default.
Profile type: philosophy.
Profile id: example-profile-id.

## Objective and main limiter

## Primary specificity axis

## Hard-session priority order

## Spacing / density preferences

## Progression priorities

## Alert sensitivity / default responses

## Explicit non-goals
```

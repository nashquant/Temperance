# Training Doctrine Governance

Status: invariant core companion.

## Purpose

This file defines the document layers, status tags, and change rules for the training doctrine set.

The main goal is to keep:
- invariant control logic in one place
- variable athlete / event / philosophy assumptions in overlays
- temporary build-state decisions in the active build declaration

## Doctrine layers

- `training-control-system-doctrine.md` = invariant core semantics and control logic
- `training-overlay-contract.md` = required shape for reusable overlays
- `training-athlete-state-*.md` = reusable athlete-state overlays
- `training-event-*.md` = reusable event overlays
- `training-philosophy-*.md` = reusable philosophy overlays
- `training-recent-cache.md` = active build declaration and near-term cache
- `training-history-memo.md` = evidence memo supporting athlete-state interpretation
- `training-phase-transition-checklists.md` = generic phase-transition companion
- `training-progression-rules.md` = compact operational cheat sheet

## Status tags

Use one of these status labels near the top of each file:

- `invariant core`
- `invariant core companion`
- `reusable overlay / default`
- `reusable overlay / draft`
- `reusable overlay / deprecated`
- `ephemeral active build`
- `evidence memo`
- `secondary / transitional`

## Governance rules

### 1) What belongs in the core

Only put these in the invariant core:
- shared semantics
- control logic
- precedence rules
- generic anchor logic
- generic alert logic
- generic spacing / density logic
- generic phase framework

Do **not** put current-athlete assumptions, event-specific specificity rules, or philosophy preferences there.

### 2) What belongs in overlays

Use overlays for anything that can change without changing the planning system itself:
- athlete-state assumptions
- event-specific specificity definitions
- hard-session priority order
- philosophy-specific stimulus preferences
- support-modality preferences
- event-specific definitions of a good week

### 3) What belongs in the active build declaration

Use `training-recent-cache.md` for:
- which overlays are active right now
- metric / anchor mapping for the current build
- current weekly anchors
- temporary exceptions
- near-term watchouts
- short-lived interpretations that should influence the next few weeks

### 4) What belongs in the evidence memo

Use `training-history-memo.md` for:
- prior builds
- injury history
- data-backed lessons
- retrospective context

That memo may justify an athlete-state overlay, but it should not silently define universal doctrine.

## Change rules

- Change the core only when semantics or non-negotiable control logic truly need to change.
- Change an athlete-state overlay when the body-state interpretation changes.
- Change an event overlay when the target event type changes or the event-specific model evolves.
- Change a philosophy overlay when your preferred coaching lens changes.
- Change the active build declaration when the current block, anchors, or temporary constraints change.
- If a philosophy changes, create or revise an overlay instead of rewriting the core.

## Precedence reminder

When layers disagree, use this order:

1. invariant core
2. active current-state constraints and athlete-state overlay
3. event overlay
4. philosophy overlay

Lower layers may tighten the plan. They should not loosen a higher-layer constraint unless the higher layer is itself revised.

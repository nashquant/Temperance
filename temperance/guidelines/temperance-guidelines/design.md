# Training Doctrine Design

Status: invariant core companion.

## Purpose

This document is a machine-facing operational design spec for the Temperance training doctrine. Its primary purpose is to prevent unclear recommendations despite the presence of doctrine files.

The doctrine set already contains invariant control logic, runtime summaries, active overlays, local current-state declarations, and LLM loading rules. This design explains how an agent should load, interpret, critique, update, and apply that stack so its recommendations remain clear, grounded, and auditable.

It is not a generic cleanup wishlist. Document structure matters only when it affects recommendation clarity.

## Operating Goal

A recommendation is clear only when it exposes the decision frame, not just the workout text. For every substantive training recommendation, name:

- active phase
- weekly anchors
- limiting constraint
- hard-session type or load role
- spacing/density rationale
- what the recommendation is explicitly rejecting or not choosing

If any of those fields are unknown, the recommendation should say so and either load the missing doctrine layer or lower confidence.

## Doctrine Model

Use this model when applying the doctrine:

- `training-control-system-doctrine.md` is the full invariant source of truth for control semantics.
- `training-runtime-core.md` is the compact invariant runtime surface for default planning.
- `training-runtime-active.md` is the compact active runtime surface for current overlay selection, metric mapping, anchors, phase, constraints, and watchouts.
- `training-llm-instructions.md` defines the default load path, on-demand retrieval, local/private resolution, precedence, and update behavior.
- `training-doctrine-governance.md` defines document roles, status tags, local/private convention, and change boundaries.
- `training-overlay-contract.md` defines the reusable overlay shape.
- `training-recent-cache.local.md`, when present, is private local active-build evidence and a fuller current declaration. The tracked `training-recent-cache.md` remains a repo-safe template.
- `training-history-*.local.md`, when present, is private local evidence. It can justify interpretation but should not silently become invariant doctrine.

Default planning should load the runtime stack first, then load fuller doctrine only when the decision needs it.

## Main Doctrine Points

These points must survive into operational recommendation behavior:

- Weekly anchor first: establish projected weekly `total_load`, `primary_specific_load`, and any `key_duration_anchor` before judging a single day.
- Precedence by layer: invariant core comes first, then active current-state constraints and athlete-state overlay, then event overlay, then philosophy overlay.
- Durability and current-state constraints outrank philosophy preferences.
- Total load can hide insufficient specific readiness, especially when support modalities preserve aerobic load without equal specific mechanical cost.
- Load class and session subtype are distinct. A moderate day can behave like a hard day if it drifts above its structural ceiling.
- Spacing and density govern local viability. Meeting load targets does not excuse clustering that compromises the next key session or week.
- Support modalities can preserve productive load without identical specific cost, but they can also become hidden stress if density is ignored.
- Alert behavior must distinguish soft review from hard constraint. A soft alert should prompt review or adjustment; a hard alert should redirect or reduce.
- Event specificity defines what the event needs. Philosophy biases the stimulus mix inside event and current-state constraints.
- Evidence and inference are different. History and local active-state files inform the decision; they do not become universal rules unless the doctrine is explicitly updated.

## Operational Loading Flow

Use this flow for planning, critique, and MCP-facing recommendation generation:

1. Load `training-runtime-core.md`.
2. Load `training-runtime-active.md`.
3. Load the athlete-state, event, and philosophy overlays named in `training-runtime-active.md`, preferring `.local.md` variants when the active runtime points to them.
4. Resolve metric mapping before reasoning about numbers. In the current runtime, core concepts map to weekly `total_TSS`, weekly `rTSS`, long-run duration/load, support modalities, and declared spacing/density windows.
5. Establish the active phase, weekly anchors, limiting constraint, and overlay set.
6. If the task depends on history, failure modes, roadmap details, or private current build state, load the appropriate local evidence file on demand. Prefer `training-recent-cache.local.md` over `training-recent-cache.md` and `training-history-*.local.md` over tracked evidence templates.
7. If runtime-core lacks enough detail for semantics, readiness nuance, alerts, progression control, or source-of-truth questions, load `training-control-system-doctrine.md`.
8. If the task is about changing doctrine files, load `training-doctrine-governance.md` and the relevant overlay contract before editing.
9. If the task is about workout templates, load the workout-template contract and taxonomy before choosing a specific session.

Do not infer the current build from history when `training-runtime-active.md` already declares it. Use history as evidence, not as the active state.

## Recommendation Clarity Contract

Every substantive recommendation should be answerable in this shape:

```text
Phase: <active phase>
Weekly anchors: <total-load anchor, primary-specific-load anchor, key duration anchor if relevant>
Limiting constraint: <durability, recovery, event timing, density, life constraint, or unknown>
Session role: <hard-session type or load role>
Spacing/density rationale: <why this fits the local and rolling windows>
Rejected / not chosen: <the tempting alternative and why it loses>
Confidence: <evidence-backed confidence and missing inputs>
```

For a workout recommendation, choose the load role and hard-session type before choosing a specific workout text. For a critique, identify whether the issue is weekly anchor mismatch, subtype choice, spacing, density, progression control, or alert handling.

The contract is not user-interface boilerplate. Agents may compress wording, but the reasoning must be present enough that a reviewer can tell why the recommendation was chosen.

## Weak Assumptions And Gaps

### Runtime Core vs Control-System Doctrine

`training-runtime-core.md` repeats and distills claims from `training-control-system-doctrine.md`. This is useful for default loading but creates source-of-truth tension if the two drift.

Operational rule: treat `training-control-system-doctrine.md` as the full invariant source for semantics and `training-runtime-core.md` as the compact runtime projection. If invariant semantics change, update both together or explicitly mark the runtime-core mismatch as pending.

### Runtime Active vs Local Active Declaration

`training-runtime-active.md` is the compact active runtime surface. `training-recent-cache.local.md` is the fuller private active-build declaration when present.

Operational rule: use `training-runtime-active.md` for the default current planning frame. Load `training-recent-cache.local.md` when the task needs detailed roadmap, update notes, current recommendation style preferences, or fuller near-term declarations. Do not quote unnecessary private athlete details into tracked artifacts.

### Generic Doctrine vs Current Build vs Private Evidence

The doctrine stack mixes reusable doctrine, current active-build declarations, and private local evidence. Recommendations become unclear when an agent presents one layer as another.

Operational rule: label the basis of claims as invariant doctrine, active build fact, private/local evidence, or inference. Do not promote private local evidence into generic doctrine without an explicit doctrine update.

### Workout Text Without Decision Exposure

A recommendation can name an intensity, duration, or workout string while hiding the governing constraint or rejected alternative. That is the main clarity failure this design is meant to prevent.

Operational rule: every substantive recommendation should expose the governing constraint and the rejected alternative or not-chosen path. Examples include rejecting extra marathon-specific density because durability is still the limiter, rejecting sharp work because it is supporting rather than central, or rejecting more running load because weekly `rTSS` progression is already the constrained variable.

## Critique Flow

When critiquing a plan or recommendation:

1. Identify the active phase and overlay set.
2. Map proposed work to weekly anchors and actual metrics.
3. Separate load class from session subtype.
4. Check local spacing first, then rolling density.
5. Check whether the proposed progression raises multiple major constraints at once.
6. Classify alerts as soft review or hard constraint.
7. State the rejected alternative.
8. State what evidence would change the decision.

If the critique cannot complete because a layer was not loaded, say which file is missing rather than filling the gap with inference.

## Update Rules

Use these edit boundaries:

- Update `training-control-system-doctrine.md` when invariant semantics, precedence, alert logic, spacing/density logic, or progression control changes.
- Update `training-runtime-core.md` as the compact runtime projection when runtime-facing invariant semantics change.
- Update `training-runtime-active.md` when the compact current planning frame changes: active overlays, metric mapping, weekly anchors, phase/objective, constraints, or watchouts.
- Update `training-recent-cache.local.md` for private current-build roadmap details, near-term declarations, and update notes that should stay local.
- Update tracked active-build templates only with repo-safe placeholders or reusable defaults.
- Update athlete-state overlays when the body-state interpretation changes.
- Update event overlays when the target event model or specificity definition changes.
- Update philosophy overlays when the coaching lens or stimulus hierarchy changes.
- Update `training-llm-instructions.md` when loading, precedence, local resolution, MCP interpretation, or workout-template behavior changes.
- Update MCP/code behavior when recommendations or analytics outputs no longer expose enough information to satisfy the clarity contract, or when MCP and dashboard analytics disagree on a named invariant such as weekly baseline.

When changing a private or local file, keep the change local unless the user explicitly asks to publish or generalize it.

## Evidence Vs Inference

Evidence from the current corpus:

- The invariant core and runtime core both define precedence, weekly anchors, load/subtype distinction, spacing/density, progression control, alerts, readiness signals, and phase behavior.
- The LLM instructions already define default load, on-demand retrieval, local/private precedence, interpretation rules, recommendation behavior, workout-template behavior, and update behavior.
- Governance already defines document layers, status tags, local/private convention, and change rules.
- The active runtime declares compact current anchors, overlays, metric mapping, phase/objective, constraints, and watchouts.
- The local active declaration exists and is fuller/private. It should be used carefully and not copied into tracked artifacts without intent.

Inferences from the corpus:

- Runtime-core duplication is acceptable only if it remains a projection of the full invariant doctrine.
- Active-state overlap is acceptable when `training-runtime-active.md` stays compact and `training-recent-cache.local.md` stays the fuller private declaration.
- The highest-value improvement is a recommendation-output contract, not a wholesale file merge.
- Code and MCP changes are future work unless they are needed to expose the clarity fields above.

## Completion Standard

An agent has applied this design successfully when a recommendation can be audited back to:

- the active doctrine layer that controlled the decision
- the weekly anchor and limiting constraint
- the session role or hard-session subtype
- the spacing and density rationale
- the rejected alternative
- the evidence/inference boundary

If that audit trail is missing, the recommendation is not clear enough even if the proposed workout is plausible.

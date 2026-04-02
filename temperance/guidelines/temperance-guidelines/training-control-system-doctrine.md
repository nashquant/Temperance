# Training Control System Doctrine

Status: invariant core.

## Purpose

This document is the main source of truth for **invariant training-planning semantics and control logic**.

It is not a rigid rules engine. It is meant to support:

1. **Ex-ante planning guidance**
   - to shape future sessions, weeks, and blocks
2. **Post-processing interpretation**
   - to judge whether actual training structure and progression are coherent
3. **Control logic**
   - to decide when to progress, hold, redirect load, or alert

The goal is not to remove judgment. The goal is to make judgment more consistent.

This document does **not** define:
- the current athlete-state interpretation
- the current event model
- the current training philosophy

Those belong in overlays and the active build declaration.

## Doctrine stack

Use the doctrine set this way:

- `training-control-system-doctrine.md` = invariant semantics and control logic
- `training-doctrine-governance.md` = document roles and change rules
- `training-phase-doctrine.md` = dense generic phase descriptions and periodization intent
- `training-overlay-contract.md` = required shape for reusable overlays
- `training-recent-cache.local.md` when present, otherwise `training-recent-cache.md` = active build declaration
- `training-history-memo.local.md` when present, otherwise `training-history-memo.md` = evidence memo

## Precedence model

When layers disagree, use this order:

1. invariant core
2. active current-state constraints and athlete-state overlay
3. event overlay
4. philosophy overlay

Interpretation:
- the core defines non-negotiable semantics and control behavior
- current-state constraints may tighten the plan
- the event overlay defines what counts as specificity and what a good week means for that event
- the philosophy overlay chooses stimulus mix and hard-session hierarchy within those constraints

Lower layers may tighten the plan. They should not loosen a higher-layer constraint unless that higher layer is itself revised.

## Core definitions

- **total_load** = total planned load across the modalities the current build is actually using
- **primary_specific_load** = the load variable most central to event readiness or current progression risk
- **specificity_ratio** = primary_specific_load / total_load, when a ratio is useful
- **support_modality** = a modality used to support load, spacing, or fitness without carrying the same specific cost as the primary specific load
- **key_duration_anchor** = the main duration-based specific anchor that deserves staged progression in the current build
- **local_spacing_window** = the local lens used to protect spacing between meaningful stressors
- **rolling_density_window** = the rolling lens used to review subtype clustering, cumulative stress, and structural drift

Important clarification:
- the active build declaration maps these core concepts to the actual metrics used in the current build
- some builds may also need secondary anchors when one primary metric is not enough to describe the event

## Active build declaration

Every active build should explicitly declare:

- athlete-state profile
- event profile
- philosophy profile
- active anchor mapping
- temporary exceptions / current constraints

The active build declaration is where the planner says, in concrete terms, what the current build is actually using.

## Weekly anchor principle

Before making day-level recommendations, establish or verify:

- projected **weekly total_load**
- projected **weekly primary_specific_load**
- projected **key_duration_anchor** when one matters
- any secondary anchors the event requires

Those anchors should be inferred from:
- athlete level / current capacity
- current phase
- recent 2-4 week load
- injury / durability status
- recovery status
- event timing and event demands
- life constraints
- active overlay set

Planning implication:
- day-level suggestions should be judged relative to weekly anchors, not in isolation
- local intuition should not override unclear global context

## Hierarchy of priorities

When tradeoffs appear, use this order:

1. protect the current limiting tissue / durability constraint
2. preserve structural coherence
3. progress primary_specific_load sensibly
4. progress the event's key duration or specificity anchor appropriately
5. preserve productive total_load through support modalities when needed
6. add density or complexity only when the system is stable

If there is a conflict, the higher item wins.

## Load-class doctrine

Daily load should be treated as sampled, not fixed.

Useful load classes:
- **Easy**
- **Moderate**
- **Hard**

These are relative load classes, not deterministic quotas.

Important principles:
- sampled load is only a **proposal**
- constraints are **authoritative**
- load class and session subtype are different concepts

Working implication:
- a day may be moderate by load but still structurally expensive if it drifts above its intended ceiling
- if a moderate day behaves like extra hard work, the system should treat it as hard

## Spacing and density doctrine

The system must use:
- an explicit **local_spacing_window**
- an explicit **rolling_density_window**

Those windows may differ by overlay set, but they must be declared.

Core rules:
- local structure is a spacing principle, not a fixed repeating script
- meaningful stress should not be clustered so tightly that the next key session or next week becomes non-viable
- density review should examine subtype concentration, cumulative mechanical cost, and whether support work is quietly behaving like extra stress

Interpretation:
- meeting load targets does not excuse structural incoherence
- if density repeatedly compromises absorption, it is too high even if the numbers look impressive

## Hard-session taxonomy doctrine

Hard sessions should be classified in two nested ways.

### High-level stress class

- **H1 = metabolic hard**
- **H2 = mechanical hard**

### Planning subtype

Common planning subtypes are:
- **threshold hard**
- **long-duration hard**
- **specific hard**
- **sharp hard**

Interpretation:
- the high-level stress class tells you what kind of strain is dominant
- the planning subtype tells you what job the session is trying to do
- these are nested labels, not competing taxonomies

Clarification on H1 vs H2:
- H1 sessions (threshold, long-duration) carry their dominant cost through sustained metabolic demand — cardiovascular stress, lactate accumulation, or prolonged aerobic duration
- H2 sessions (sharp, VO2-range) carry their dominant cost through neuromuscular demand at high velocities — movement mechanics, force production per stride, and speed economy
- H2 does not mean "higher injury risk than H1"; long-duration H1 work typically carries the highest cumulative bone-loading cost in a running build precisely because of its duration and running-specific mechanical repetition
- use the H1/H2 label to understand what the session is primarily stressing, not to rank absolute injury or fatigue risk across subtypes

The event overlay defines what `specific hard` means.
The philosophy overlay defines which subtypes are usually more central.

## Progression control

### 1) Baseline

Define:
- **baseline_primary_specific_load = average of the last 2-3 relevant weeks**

This is the current reference point for specific-load progression.

### 2) Weekly primary-specific-load progression

The main lens should be:
- percentage increase relative to baseline

But it should always be checked against:
- absolute resulting load
- current durability state
- whether other progression variables are also rising at the same time

Important rule:
- do not progress multiple major constraints aggressively at once unless the active build explicitly says that cost is intended and currently tolerable

### 3) Specificity-ratio progression

Progress specificity_ratio only when:
- the current structure is being absorbed coherently
- recovery is acceptable
- the athlete-state overlay does not indicate that the ratio itself is currently the main risk

### 4) Key-duration-anchor progression

Progress a key duration anchor only when:
- the last exposure was absorbed acceptably
- next-day and 48-hour response were acceptable
- the rest of the structure still supports the next week

Hold or regress when the duration anchor is being "completed" but not absorbed.

## What a good week looks like

A good week should generally:
- meet or approach the intended weekly anchors
- use intentionally chosen hard-session types
- preserve spacing and density
- keep support work purposeful
- satisfy the event overlay's definition of specificity
- end in a state that still supports the next week

This matters:
- a good week is not merely a week that avoids disaster
- it is a week that advances the active event build while preserving future buildability

## Alert system

### Soft alerts

Soft alerts should trigger review and suggested adjustment, not aggressive correction.

Typical soft-alert patterns:
- a meaningful but not extreme jump in primary_specific_load
- density drifting toward the upper bound of what the structure can absorb
- a key duration anchor progressing faster than planned but still potentially recoverable
- support work starting to distort the structure rather than help it

### Hard alerts

Hard alerts should trigger enforced correction or clear constraint behavior.

Typical hard-alert patterns:
- a primary_specific_load jump that is mechanically or structurally unreasonable
- progression of a key duration anchor despite poor readiness
- meaningful stress stacked inside inadequate spacing
- moderate work drifting into extra hard work
- repeated density drift that the system is not absorbing

### Alert philosophy

- soft alerts = review, suggest, monitor
- hard alerts = constrain, redirect, or reduce

This keeps the system useful without making it hysterical.

### Default response logic

These are default responses, not rigid prescriptions.

After a **soft alert**, the system should usually:
- hold the relevant progression variable
- freeze the implicated key anchor for the next exposure
- reduce the next 7-day primary_specific_load target modestly or replace the next hard session with support-modality work if that better protects structure

After a **hard alert**, the system should usually:
- replace the next hard session with support-modality work or recovery-oriented support
- freeze primary_specific_load progression and the implicated duration / specificity progression
- require one clean local-spacing cycle before re-progressing

Alert sensitivity may be tightened by the athlete-state overlay.
Event and philosophy overlays may add higher-salience watchouts within those constraints.

## Readiness signal doctrine

External readiness signals are supporting context, not primary planning inputs. Weekly build structure anchored to total_load and primary_specific_load targets is the primary planning signal.

### Tracked signals and their role

**HRV** is the most sensitive daily readiness marker. Use it as a trend, not an absolute:
- single-day suppression in an otherwise stable block: note it, proceed with the planned session, monitor next-day response
- 3+ consecutive days meaningfully below individual baseline: treat as a soft alert — consider substituting the next hard session or reducing its scope before proceeding
- acute sharp drop combined with poor mechanical feel or illness signs: treat as a hard alert — replace the next hard session with support or recovery work

**RHR** is a slower-moving but more robust fatigue signal:
- single-day elevation above individual baseline: attentive but not actionable on its own
- RHR elevated for 2+ days alongside suppressed HRV: soft alert, especially if accompanied by heavier-than-expected legs or mood change
- RHR elevated for 3+ days without clear cause: investigate — this pattern can precede illness or over-accumulation

**Sleep** signals should be interpreted by pattern, not single night:
- one short or poor-quality night: proceed normally, flag for next-day awareness
- consistently short duration (below individual norm) for 2+ nights: take it seriously — sleep debt compounds metabolic and mechanical recovery more than HRV alone
- poor sleep score despite adequate duration: look for the profile pattern; fragmented architecture is more meaningful than a raw score number
- chronic poor sleep across a build block: this degrades absorption and should factor into whether the weekly load target is realistic

### Response rules

Readiness signals interact with the alert system, not replace it:
- a soft alert from readiness alone (one suppressed signal) should rarely override a planned session — adjust scope or swap to a lower-cost equivalent if warranted
- a compound signal (HRV + RHR + poor sleep + heavy legs on the same day) should be treated as a soft alert even if each individual metric is borderline
- only a clear compound pattern over multiple days, or a signal accompanied by obvious physical cause (illness, known overreach), should rise to hard alert behavior
- when in doubt, a reduced version of the planned session beats a full replacement — preserves structure without ignoring the signal

## Generic phase framework

Use these generic phases:

1. **Return / Re-entry**
2. **Base / Capacity Build**
3. **Specificity**
4. **Peak**
5. **Taper**

Phase transitions should be interpreted through:
- event timing
- life constraints
- recent 2-4 week load
- current limiter / durability status
- recovery status
- whether the current phase has already done its job

The event overlay defines:
- what specificity means
- what work must be "in the bank"
- what a good week looks like in later phases

Core periodization rule:
- phases should shift emphasis, not erase every non-dominant quality
- even when one lane is central, some broader mix should still appear from time to time if it improves build continuity and later readiness

For dense descriptions of what each phase is trying to do, see:
- `training-phase-doctrine.md`

For more explicit transition questions, see:
- `training-phase-transition-checklists.md`

## What this system is trying to prevent

This doctrine exists to avoid:
- total load hiding insufficient specific readiness
- the engine outrunning current durability
- hidden medium-hard drift
- density patterns that make the next key session or next week non-viable
- philosophy preferences overriding body-state reality
- importing one event's logic unchanged into another event

## Short version

Establish weekly total_load and primary_specific_load anchors before making day-level recommendations. Map the core terms to the actual metrics in the active build declaration. Let the core define semantics, control logic, and precedence. Let the athlete-state overlay tighten the plan when the body demands it. Let the event overlay define specificity and what a good week means. Let the philosophy overlay choose stimulus mix inside those constraints. Progress specific load, specificity, and key duration anchors only when the structure is being absorbed. Let alerts distinguish noise from real drift, and let future buildability matter as much as the current week.

# Training Control System Doctrine

## Purpose

This document is the **main source of truth** for Matt's training planning logic.

It is not a rigid rules engine. It is meant to function as:

1. **Ex-ante planning guidance**
   - to shape future sessions, weeks, and blocks
2. **Post-processing interpretation**
   - to evaluate whether actual training distribution and progression are coherent
3. **Control logic**
   - to decide when to progress, hold, redirect load, or alert

The goal is not to remove judgment. The goal is to make judgment more consistent.

## Document roles

To avoid duplication and drift, use the documents this way:

- `training-history-memo.md` = background, history, injuries, prior build lessons
- `training-control-system-doctrine.md` = main planning doctrine and control logic
- `training-recent-cache.md` = short-term cache of current anchors, recent findings, and temporary interpretations

Other planning docs should be treated as secondary or transitional unless explicitly refreshed.

## Core Athlete Model

This system assumes the following:

- aerobic engine: **high**
- total load tolerance: **high**
- historical mileage capacity: **high**
- current limiter: **mechanical durability**

Therefore the central planning asymmetry is:
- **fitness is not the main limiter**
- **durability is the main limiter**

This means the system must treat total fitness support and running progression as related but distinct problems.

## Core Definitions

- **total_TSS** = total aerobic load from running + x-train
- **rTSS** = running-specific load
- **run_ratio** = rTSS / total_TSS

Interpretation:
- **total_TSS** drives aerobic fitness and global training load
- **rTSS** drives running progression, durability stress, and much of the injury-risk signal
- **run_ratio** describes how much of total load is currently being carried by running rather than cross-training

## Primary Planning Principle

The system must treat **rTSS as the primary constraint variable**.

That means:
- total_TSS can remain high
- x-train can be used strategically to support fitness
- but rTSS progression must be controlled carefully

In short:
- **total_TSS supports the engine**
- **rTSS constrains progression**

## Optimization Objective

The system is not merely trying to avoid mistakes.
It is trying to produce:

- the **highest usable marathon fitness**
- with the **largest sustainable running share**
- while preserving durability
- and using x-train to support aerobic load when running cannot yet carry enough of it

In practice, the build should aim to be:
- aerobically big
- structurally coherent
- marathon-relevant
- durable enough to express race fitness

Important interpretation:
- **total_TSS** is not just tolerated load; it is aerobic support capital
- **rTSS** is not just a risk variable; it is also the main vehicle of marathon-specific adaptation
- the goal is to increase the amount of useful running the body can absorb, not merely to keep running small and safe

## Weekly Anchor Principle

This is central to the method.

Before making recommendations, first establish or verify:
- projected **weekly total_TSS**
- projected **weekly rTSS**

Those weekly anchors should be inferred from:
- athlete level (VDOT max is a useful proxy)
- current phase in the cycle
- load from the last 2-4 weeks
- injury status / durability status
- recovery status
- Temperance context when available

Planning implication:
- daily suggestions should be judged relative to those weekly anchors, not in isolation
- recommendations should not be made from local intuition alone when the global weekly context is unclear

## Hierarchy of Priorities

When tradeoffs appear, use this order:

1. protect durability
2. progress running load sensibly
3. progress long-run structure appropriately
4. maintain / build aerobic load through x-train when needed
5. add density or complexity only when the system is stable

If there is a conflict, durability wins.

## Stochastic Load Model

Daily load should be treated as sampled, not fixed.

Useful load classes:
- **Easy**: centered around ~10% of weekly baseline load
- **Moderate**: centered around ~14%
- **Hard**: centered around ~18%

These are not deterministic quotas. They are load-distribution classes.

Important principle:
- sampled load is only a **proposal**
- constraints are **authoritative**

Meaning:
1. the system may propose a daily load from a stochastic model
2. that proposal must then be accepted, reduced, or redirected based on durability constraints

This preserves useful variation without allowing randomness to override control logic.

## 3-Day / 9-Day Structure

### 1) The 3-day logic

The 3-day concept should be treated as a **spacing principle**, not a fixed sequence.

It does **not** mean:
- easy, then moderate, then hard, forever

It **does** mean:
- preserve roughly **3 days between the hardest run-stress days** when possible
- avoid clustering meaningful run stress too tightly
- use the spacing to protect durability and reduce mechanical stacking

The day labels easy / moderate / hard should therefore be treated as **load classes**, not mandatory positions in a repeating pattern.

### 2) Hard day types

Hard days can be understood as two categories:
- **H1 = metabolic hard** (threshold, VO2, harder aerobic quality)
- **H2 = mechanical hard** (especially long run)

This distinction matters because a session can be metabolically hard without carrying the same mechanical cost as a long run.

### 3) Hard x-train in the cycle

Do **not** automatically panic if one of the in-between days contains a hard x-train session.

That can be acceptable if:
- there is still at least one easy / recovery / rest or very low load day compensating within the cycle
- the mechanical stress from running remains appropriately spaced
- the block still protects durability rather than quietly accumulating hidden fatigue

### 4) Rolling 9-day view

The system should evaluate density over a **rolling 9-day window**, not only through rigid calendar weeks.

Use the 9-day lens to assess:
- threshold density
- hard-day spacing
- cumulative mechanical stress
- run_ratio evolution
- drift in load distribution

## 3-Day Load Heuristic

A useful heuristic is:
- expected 3-day load ≈ **42%** of weekly target load
- normal band ≈ **38-48%**

This is a **soft planning guide** and a **post-processing distribution check**.
It is **not** a rigid quota.

Interpretation:
- a single cycle outside the band is not automatically a problem
- repeated drift matters more than one-off noise
- this metric should trigger **review**, not automatic panic

## Drift and Persistence Logic

### Drift levels

**Normal**
- within **38-48%**

**Soft drift**
- **35-38%** or **48-52%**
- acceptable occasionally

**Hard drift**
- below **35%** or above **52%**

### Persistence

- **1 off-target cycle** → ignore unless other signals are bad
- **2 consecutive off-target cycles** → soft alert
- **3+ consecutive off-target cycles** → hard alert

This prevents the system from becoming too reactive to normal training noise.

## rTSS Progression Doctrine

### 1) Baseline

Define:
- **baseline_rTSS = average of the last 2-3 weeks of running rTSS**

This is the current mechanical reference point.

### 2) Weekly rTSS increase

The primary way to judge rTSS progression should be **percentage increase relative to baseline**, not absolute growth alone.

Preferred framing:
- **normal progression:** roughly +5% to +10%
- **conditional high end:** roughly +10% to +15% when the system is stable
- **hard alert zone:** jumps that are clearly too large relative to baseline, especially when they also create concerning absolute mechanical stress

Important nuance:
- percentage growth is the main lens
- however, when baseline rTSS is still low (for example during return phases), percentage jumps can look large without necessarily being dangerous in absolute terms
- therefore, low-baseline situations should use an **absolute-number sanity check** alongside the percentage rule
- in those cases, a relatively high percentage jump may still be acceptable if the resulting absolute rTSS remains mechanically reasonable

### 3) run_ratio progression

Suggested run_ratio progression:
- **+3 to +5 percentage points every 1-2 weeks**, only if mechanically stable

Suggested phase bands:
- **early:** 20-30%
- **mid:** 30-45%
- **specific:** 45-60%

Important nuance:
- these are **phase descriptors**, not fixed calendar targets
- movement across them must be interpreted through event timing, life constraints, durability, recovery, and recent load context

## Session Taxonomy Doctrine

The planning system should not think only in terms of load quantity. It should also understand what each session type is trying to do.

Each session bucket should be understood along three dimensions:
- **load class**
- **development role**
- **structural role**

That means each bucket should imply:
- purpose
- typical role in the week or block
- common examples
- what it is trying to develop
- common failure mode
- how it relates to weekly anchors

### Easy bucket

Easy sessions are not dead sessions. They are what make the harder and more productive sessions usable.

#### 1) Recovery easy
Purpose:
- absorb prior work
- preserve spacing
- keep fatigue moving down

Typical examples:
- very easy run
- easy elliptical
- short easy support session
- rest or near-rest substitute

Common mistake:
- turning it into hidden moderate work

#### 2) Support easy
Purpose:
- add aerobic load without distorting the week
- help reach weekly TSS anchor
- preserve rTSS restraint when needed

Typical examples:
- easy x-train
- easy double
- short easy run plus additional x-train

Common mistake:
- dismissing it as useless because it is not hard

#### 3) Structural easy
Purpose:
- preserve rhythm and frequency
- support consistency
- create better spacing between key run-stress days

Typical examples:
- short easy run between harder days
- x-train filler that helps keep the 3-day structure coherent

Common mistake:
- overbuilding it until it no longer behaves like an easy day

### Moderate bucket

Moderate work is useful because it can be productive without being structurally expensive — but only if it remains truly sub-threshold.

#### 1) Steady aerobic moderate
Purpose:
- build aerobic strength
- add useful load
- sit between pure recovery and real quality

Typical examples:
- steady aerobic run below threshold
- moderately strong x-train support
- longer aerobic double support

Common mistake:
- letting it drift too close to threshold

#### 2) Volume-support moderate
Purpose:
- help hit the weekly TSS anchor
- keep total load high when rTSS must remain capped

Typical examples:
- longer x-train session at honest aerobic effort
- split x-train day with one easy and one moderate segment

Common mistake:
- stacking too many of them so the week becomes medium-hard everywhere

#### 3) Transitional moderate
Purpose:
- bridge between easier and harder days
- maintain rhythm without forcing full recovery or full stress

Typical examples:
- controlled steady run
- moderate x-train inserted in a 3-day structure

Common mistake:
- treating it as free load when cumulative fatigue is already high

### Hard bucket

Hard sessions should be chosen intentionally by **type**, not merely counted.

#### 1) Threshold hard
Purpose:
- improve strong aerobic power
- improve lactate control / high-end aerobic support
- create one of the main quality stimuli of the week

Typical examples:
- cruise intervals
- longer threshold reps
- sustained LT work
- controlled threshold doubles only when clearly earned

What it develops:
- aerobic strength near threshold
- sustainable quality density
- performance support without pure top-end stress

Main mistake:
- too much density
- repeating it too often
- letting moderate days drift into extra threshold

Planning role:
- usually one of the default hard options
- powerful, but must be constrained by spacing and density rules

#### 2) Long-run hard
Purpose:
- build long-duration durability
- increase fatigue resistance
- make marathon-specific work possible later

Typical examples:
- long easy progression
- long run at controlled IF
- long run with moderate finish once earned

What it develops:
- structural durability
- long-duration metabolic support
- marathon fatigue tolerance

Main mistake:
- progressing too quickly
- treating it like just another hard session
- stacking it too close to other run-stress days

Planning role:
- usually the most important mechanical hard of the week or block
- should receive special protection inside the planning structure

#### 3) Specific / marathon-oriented hard
Purpose:
- convert general fitness into marathon-usable fitness
- teach the body to operate efficiently around marathon demands
- make the block more race-relevant

Typical examples:
- marathon-pace segments
- marathon-effort long-run blocks
- longer sustained work below threshold but above ordinary steady

What it develops:
- marathon economy
- marathon durability
- race-specific fuel / utilization and fatigue handling

Main mistake:
- introducing it too early
- using too much of it before the durability base exists
- confusing it with threshold volume

Planning role:
- becomes more central as the cycle moves toward specific and peak phases

#### 4) VO2 / sharp-intensity hard
Purpose:
- preserve range
- provide occasional top-end stimulus
- maintain coordination / speed support
- prevent the system from becoming too flat

Typical examples:
- short controlled VO2 reps
- hill reps
- controlled faster intervals
- strides may contribute here, though they do not always count as a full hard session

What it develops:
- top-end aerobic power
- speed support
- recruitment / neuromuscular sharpness

Main mistake:
- overusing it
- making it a dominant pattern
- paying too much durability cost for too little marathon value

Planning role:
- useful but secondary
- should support the block, not dominate it

## Long-Run Doctrine

Long runs are one of the main mechanical signals in the system.

### Staging

**Stage 0**
- 75-90 min
- IF ~0.70-0.73

**Stage 1**
- 90-110 min
- IF ~0.72-0.75

**Stage 2**
- 1h45-2h
- IF ~0.74-0.78

**Stage 3**
- 2h-2h15
- may include blocks around ~0.80-0.85 if the system is ready

### Progression rules

- progress only after **1-2 successful exposures**
- hold if the previous exposure achieved the planned load but cost too much mechanically
- regress if next-day or 48-hour mechanics deteriorate
- every **3-4 long runs**, schedule a **down long run** at about **70-80%** of prior duration/load

### Placement

- default placement should be **weekend (Sat/Sun)**
- this is a strong planning preference, not sacred law

Practical exception:
- if the structure implies a Friday hard session that would compress the weekend badly, it may be better to move that hard session to **Thursday**, use **Friday as rest or very low load**, and preserve the weekend long-run anchor

## Threshold and Quality Doctrine

### Density limits

- maximum **2 threshold exposures per rolling 9 days**
- minimum **48h spacing** between threshold sessions
- preferably **no more than 1 threshold exposure per 3-day block**

### Reintroduction order

Quality should usually progress in this order:

1. aerobic steady
2. short LT intervals
3. longer LT work
4. marathon-pace work
5. limited VO2 work
6. double threshold only if clearly stable

### Moderate-day discipline

Moderate days must remain truly moderate.

Working principle:
- moderate sessions should **not drift into threshold**
- if they do, the system should conceptually treat them as hard sessions

This matters because hidden density is often more dangerous than obvious density.

## Intensity Mix Doctrine

Low intensity remains essential and often necessary.

However:
- support work does not always need to collapse into the lowest possible intensity if it is being performed through low-impact x-train
- for this athlete, the most valuable non-long-run quality is generally **threshold / strong aerobic work** rather than frequent sharp anaerobic work
- high-intensity work may be used sparingly to preserve range, coordination, and speed support, but should not dominate the structure
- moderate work must remain clearly sub-threshold unless the plan explicitly intends otherwise

This means the system should seek a good mix of stimuli across the block rather than flattening everything into one repeated intensity lane.

## Stimulus Mix Doctrine

A coherent week or block should usually preserve exposure to several broad capacities:

- aerobic support load
- steady / strong aerobic durability
- threshold strength
- long-duration durability
- race-specific readiness
- and optionally occasional top-end touch

This does **not** mean equal shares. It means the block should not become overconcentrated in only one lane.

Common failure modes to avoid:
- everything becomes medium
- all hard work becomes threshold
- all support work becomes junk or filler
- the long run becomes the only true durability stimulus
- x-train becomes endless volume with no structure
- sharp work becomes too frequent relative to marathon value

A good block usually has:
- enough easy / support work to hold structure together
- enough moderate / aerobic work to keep TSS productive
- one or two meaningful hard stimuli of different types
- long-run progression as a major pillar
- increasing specificity as the race approaches
- only restrained use of sharp intensity

## Support Work Doctrine

Support work should be treated as purposeful, not as filler.

Support work may serve one or more of these jobs:
- preserve rhythm
- build aerobic load
- help weekly total_TSS reach target
- protect rTSS constraints
- improve the quality of the next hard day
- absorb the previous hard day

The main distinction is:
- meaningful support work helps the structure
- empty filler adds time without a clear purpose
- hidden extra fatigue looks like support work but behaves like extra stress

## Doubles Doctrine

Doubles should not be treated as inherently bad. For Matt, they can be an intelligent way to break down larger work into more manageable pieces, especially when total daily work exceeds about **1 hour**.

Doubles are especially useful when they improve:
- durability management
- session quality
- anchor-hitting efficiency
- spacing
- absorption

Useful application:
- instead of prescribing one very long continuous easy support session by default, consider splitting the work into pieces such as:
  - one easier session
  - plus one moderate support session

This can make the load easier to absorb while still achieving the intended total TSS.

Preference rule:
- when a support day is accumulating a lot of non-running load, Matt may prefer something like **1h easier + 30min moderate** rather than a single **1h50 easy** block
- the main exception is when there is a specific reason to preserve one continuous stimulus, such as:
  - a true long run
  - a deliberately long continuous aerobic stimulus
  - a session where uninterrupted durability or steady-state exposure is the actual goal

Warning:
- doubles should not exist merely to inflate load without structural logic

## X-Train Role Doctrine

X-train is not just backup. It is an active control and optimization tool.

It can serve at least four roles:

### 1) Load support
Used to keep total_TSS high when rTSS must remain controlled.

### 2) Spacing support
Used to preserve the 3-day structure without adding more run stress.

### 3) Moderate aerobic support
Used to make non-running support work more productive than pure soft recovery when impact is not the limiter.

### 4) Durability bridge
Used when the athlete has engine capacity that exceeds current run tolerance.

Planning implication:
- x-train should be used proactively when it improves structure, supports anchors, or protects durability
- not merely reactively after something has already gone wrong

## Modality Allocation Doctrine

The system must decide how target load splits into:
- running (rTSS)
- x-train (TSS without equivalent running stress)

Core rules:
- if fatigue rises, shift load toward elliptical / x-train
- if durability risk rises, reduce rTSS and preserve fitness through lower-impact load
- if the system is stable, gradually increase running share

Always enforce:
- weekly rTSS constraints
- run_ratio constraints

Interpretation:
- x-train is not just backup
- it is an active control tool for keeping fitness high while durability catches up

## What a Good Week Looks Like

A good week should generally look like this:
- it meets or approaches the intended **weekly total_TSS** and **weekly rTSS** anchors
- the running share is appropriate for the phase and durability state
- the hard sessions are intentionally chosen by type, not randomly accumulated
- the long run is placed and scaled coherently
- the easy and moderate support work helps the structure rather than distorting it
- there is enough stimulus diversity to move fitness forward
- the week ends in a state that still allows the next week to function

This is important:
- a good week is not merely a week that avoids disaster
- it is a week that advances marathon-relevant fitness while preserving the ability to keep building

## Alert System

### Soft alerts

Soft alerts should trigger review and suggested adjustment, not aggressive correction.

Trigger examples:
- run_ratio jump > +5 percentage points in one week
- long run increase > +15 min or >10% duration
- 2 consecutive cycles outside the 38-48% band
- threshold density approaching the upper bound
- x-train carrying >80% of total load for an extended period without intended reason

### Hard alerts

Hard alerts should trigger enforced correction or clear constraint behavior.

Trigger examples:
- weekly rTSS increase that is too large relative to baseline and also mechanically unreasonable in absolute terms
- long-run progression violates staging or occurs despite poor mechanical readiness
- long run repeatedly placed outside default weekend logic without good reason
- mechanical stress stacked inside 48h
- 3+ cycles outside the intended load band
- moderate day drifts above its intended intensity ceiling

### Alert philosophy

- soft alerts = review, suggest, monitor
- hard alerts = constrain, redirect, or reduce

This keeps the system useful without making it hysterical.

## Macro Phase Map to July 12

The phase map should organize the build, but phase shifts should be interpreted through:
- event timing
- life constraints
- recent 2-4 week load
- durability status
- recovery status
- whether the current phase has already done its job

In other words:
- phases should not be treated as rigid calendar flips
- but they also should not be treated as if durability alone decides everything
- progression is planned around events and life constraints while still respecting durability and recovery constraints

### Phase 1 — Return / Consolidation (2-3 weeks)
- low run_ratio (~20-30%)
- long runs in Stage 0-1
- minimal threshold
- focus on consistency, tolerance, and clean mechanical response

**Optimize:**
- consistency
- safe reintroduction of rTSS
- tolerance to repeated running
- preservation of aerobic support through x-train

### Transition logic
Move on when consistency and basic run tolerance are back, and the limiting question is no longer “can I run consistently at all?” but “how do I now expand durability intelligently?”

### Phase 2 — Durability Build (4-6 weeks)
- run_ratio ~30-40%
- long runs build toward Stage 2
- light threshold introduction
- maintain high total_TSS
- main aim: get durability closer to the engine

**Optimize:**
- higher sustainable run_ratio
- long-run progression
- high aerobic support while rTSS rises
- first useful quality without destabilizing the week

### Transition logic
Move on when long-run progression is functioning, running load is being absorbed coherently, and more marathon-specific work would now be productive rather than premature.

### Phase 3 — Marathon Specific (4-5 weeks)
- run_ratio ~40-55%
- long runs reach Stage 3 when earned
- more marathon-pace work
- gradually reduce dependence on x-train if running is stable

**Optimize:**
- conversion of aerobic base into marathon-usable work
- more race-relevant long-run structure
- rising specificity without losing control of density

### Transition logic
Move on when enough key marathon-specific work is already in the bank and the best next step is to stabilize and sharpen rather than continue building.

### Phase 4 — Peak (2-3 weeks)
- stabilize rTSS rather than chasing constant increase
- maximize specificity
- reduce randomness slightly
- prioritize usable fitness, not just high numbers

**Optimize:**
- usable race fitness
- stable specific work
- sharpening without extra chaos

### Transition logic
This is the most event-tied phase before taper. It should give way when reducing fatigue becomes more useful than preserving build load.

### Phase 5 — Taper (10-14 days)
- reduce total_TSS
- maintain some intensity
- reduce mechanical cost
- preserve readiness without accumulating fatigue

**Optimize:**
- freshness with retention of rhythm and confidence

### Phase transition note
For more explicit transition checklists, see:
- `training-phase-transition-checklists.md`

## What This System Is Trying to Prevent

This doctrine exists to avoid known failure modes:
- high total load that hides insufficient durability
- total fitness outpacing leg resilience
- too much threshold density
- hidden moderate-to-hard drift
- extra weekend stress on top of already dense quality structure
- oversized hero-day experiments
- using the calendar to force progression the body has not yet earned

## Short Version

Use total_TSS to support fitness and rTSS to constrain progression. Treat rTSS as the primary durability-control variable. Always establish weekly total_TSS and weekly rTSS anchors before making daily recommendations. Optimize for the biggest marathon-relevant week the body can currently absorb. Think in rolling 3-day spacing and 9-day density, not rigid weekly formulas. Use stochastic load as a proposal model, not an authority. Progress run_ratio slowly and only when durability allows. Keep long-run progression staged and earned. Control threshold density explicitly. Use x-train strategically to preserve fitness while durability catches up. Use doubles intelligently when they improve structure, and aim for a balanced stimulus mix across the block. Let alerts distinguish noise from real drift. Let phase planning guide the build, but let events, life constraints, recent load, and durability determine how transitions are interpreted.

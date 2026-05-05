# Temperance Methodology

**Purpose:** Design guidelines, metric rationale, and gap analysis for the autonomous LLM coaching system.

This document is the authoritative reference for methodology decisions. It covers what's implemented, why each choice was made, what's ad-hoc vs principled, and what must be built for a credible autonomous long-horizon coach.

---

## 1. Metric Inventory

### 1.1 TSS — Training Stress Score

**hrTSS (when HR is available):**
```
hrTSS = duration_s × (avg_hr / lthr)² / 3600 × 100
```

**rTSS (running/treadmill when pace is available):**
```
rTSS = duration_s × (tp_pace / avg_pace)² / 3600 × 100
```

**Status:** Published standard (Coggan/Allen, *Training and Racing with a Power Meter*, 2010). The dual-path selection (rTSS preferred for running when pace is available, hrTSS as fallback) is sound and common in practice.

**Watch:** `hrTSS` uses average HR, not normalized power equivalents, so it underweights intensity bursts. An athlete doing 10×400m repeats with lots of slow recovery gets the same hrTSS as someone doing a sustained tempo at the same average HR. This is an inherent limitation of mean-HR TSS — not a bug, but the coach should be aware.

---

### 1.2 Performance Trend

Built from four normalized components:

- efficiency trend from pace-vs-heart-strain evidence
- threshold trend from LT pace movement
- quality confirmation from strong recent sessions
- durability support from repeatable specific load

**Status:** Custom composite built for the question "am I performing better relative to strain?"

**Design rule:** This is not a load metric. It should not rise simply because TSS rises.

---

### 1.3 Readiness

Built from three components:

- acute strain
- carryover friction from clustered hard work
- optional recovery response from wellness data

**Status:** Custom state score built for the question "how ready am I to absorb or execute quality work right now?"

**Design rule:** Higher means more ready. Missing wellness data should reduce richness, not break the metric.

---

### 1.4 Tissue Load Risk

Built from four components:

- run-specific ramp
- single-run spike versus recent tolerance
- load concentration from long-run share and hard-run clustering
- optional wellness friction

**Status:** Custom running-specific risk composite.

**Design rule:** This should respond to mechanically risky running structure, not generic total training load alone.

---

### 1.5 Durability

Built from three components:

- single-run tolerance
- weekly specific tolerance
- specific-load consistency

**Status:** Custom capability score.

**Design rule:** Higher means the athlete is demonstrating more repeatable running-specific load tolerance, not merely accumulating more training volume.

---

### 1.6 Mechanical Load

```
mechanical_load = distance_m
    × pace_factor^1.35
    × hill_factor
    × step_factor
    × stride_factor
    × power_factor
    × intensity_bag

intensity_bag = 0.55 × zone_factor + 0.45 × rtss_factor
```

**Status:** Custom composite. Not a published formula.

**What's principled:** Using distance as the base and multiplying by biomechanical factors is consistent with the literature on running economy and tissue stress. The `^1.35` pace exponent captures the non-linear relationship between speed and mechanical demand. Separating hill stress and stride mechanics from pace is well-motivated.

**What's ad-hoc:** The exact weights (0.55, 0.45), the exponent `1.35`, and the individual factor formulas are not externally validated. The `intensity_bag` mixing rTSS and zone time is particularly ad-hoc — it conflates physiological intensity (rTSS) with distribution (zones) without a clear mechanistic rationale.

**For the LLM coach:** Treat mechanical_load as a relative trend signal, not an absolute threshold. It is meaningful for comparing "this week's mechanical demand vs last month" for the same athlete. Do not compare across athletes or to external benchmarks.

---

### 1.7 Durability (100-day rTSS EMA)

```
durability = rTSS EMA with 100-day window
```

**Status:** Custom. Not a published metric name or formula.

**Rationale:** Intended to capture long-term running robustness — a slowly-responding baseline of mechanical load the athlete can absorb. The 100-day window is unusually long (standard EMA windows for endurance training are 7, 28, or 42 days). The concept is loosely motivated by Seiler's work on long-term training adaptation, but the specific formula is original.

**Weakness:** With a 100-day window, durability is barely responsive to current block choices. It moves on the scale of seasons, not training blocks. Useful as a background fitness context but should not be used for week-to-week prescription decisions.

---

### 1.8 Pounding (7-day rTSS EMA)

```
pounding = rTSS EMA with 7-day window
```

**Status:** Custom naming, standard window. Equivalent to the "acute" signal from ACWR but scoped to running mechanical load only. Directly useful for managing injury risk over a week.

---

### 1.9 VDOT

Derived from Jack Daniels' running formula (published, widely used). Maps recent race/time trial performance to estimated aerobic capacity and pace zones.

**Status:** Published standard.

**Watch:** VDOT is calibrated to race performance. If the athlete has not done a recent time trial or race, VDOT will be stale. The LLM coach should flag stale VDOT when making pace prescriptions.

---

### 1.10 Specificity Ratio (spec=0.8)

```
effective_rtss = tss × 0.8   (for all non-running activities)
```

Used to convert non-running TSS into a running-equivalent load for distance/pace proxies.

**Status:** Completely ad-hoc. Hardcoded constant with no per-sport calibration.

**Consequence:** Cycling, swimming, strength, yoga, and cross-training all get treated as 80% running-specific. A 100-TSS cycling ride and a 100-TSS swim both produce the same proxy distance. This is wrong in principle but tolerable if the LLM coach knows not to use proxy distances for cross-sport planning decisions.

**For the LLM coach:** Never use `distance_proxy_km` for non-running activities in planning decisions. Use TSS directly.

---

### 1.11 TRIMP Models (Disabled)

Bannister TRIMP and Edwards zone-based TRIMP are implemented in `temperance/models.py` but explicitly zeroed out in `analytics.py` ("disabled in curve-first v1"). The plan was to enable them once LT curve calibration was stable.

**Status:** Intentionally disabled, not removed.

**Implication:** Currently, activities without pace data (cycling, swimming, strength) are stress-quantified only through hrTSS. Once TRIMP is re-enabled, non-running activities will have a second load signal that accounts for HR zone distribution rather than just mean HR. This will change coaching brief outputs materially when it ships.

---

## 2. Methodology Choices

### 2.1 EMA Implementation vs Coggan PMC

As documented in §1.2, the code uses `2/(N+1)` alpha rather than `1-exp(-1/TC)`. This is approximately 2× more responsive.

**Decision point:** If the goal is to match TrainingPeaks outputs for cross-reference, switch to `1-exp(-1/TC)`. If the goal is a more responsive system tuned to this athlete, keep the current formula and document the divergence explicitly. Do not silently keep both; the LLM coach needs to know which standard it's working under.

**Recommendation:** Keep the current formula (it is more responsive and may suit a shorter planning horizon), but add a named constant `ALPHA_MODE = "standard_ema"` with a comment explaining the divergence. The LLM coach should cite this when discussing TSB ranges.

---

### 2.2 ACWR Chronic Window (42d vs 28d)

Standard ACWR literature uses 28-day chronic. This system uses 42-day (same as CTL).

**Consequence:** A 42-day chronic window makes the metric more stable. Ramping load over 3-4 weeks will produce a lower ACWR reading than with a 28-day window, meaning the system is less sensitive to short-term spikes. The inflection points in the overreach accumulator (§1.4) are calibrated to this window.

**Recommendation:** Keep 42-day. It is a deliberate choice to align ACWR with the fitness baseline rather than a shorter recovery window. Document explicitly that ACWR thresholds from published studies using 28-day chronic do not apply without adjustment.

---

### 2.3 Single Planning Methodology

`temperance/planning/methodologies.py` registers exactly one methodology: "Rolling 3-Day Cycle" (easy/moderate/hard steps, 9-day default horizon). This is the entire planning engine for session generation.

**For a local daily assistant:** adequate for simple session suggestions.

**For an autonomous long-horizon coach:** critically insufficient. The coach needs:
- Block periodization (3-4 week mesocycles with a recovery week)
- Polarized vs pyramidal intensity distribution models
- Phase-specific methodology switching (Base: high volume + polarized; Build: threshold + specificity; Peak: sharpening + taper)
- The ability to declare a methodology not just as a pattern template but as a target state (e.g., "80% easy / 20% quality" as a weekly distribution target)

---

### 2.4 Piecewise Linear Threshold Curves

LT pace and LTHR are tracked as timestamped point sequences, interpolated via `merge_asof` backward-fill. This means each activity is evaluated against the threshold value that was most recently calibrated before that activity's date.

**Status:** Well-designed. This is the right approach for handling threshold drift over a training career without retroactively re-scoring all historical activities.

**Gap:** There is no mechanism for the LLM coach to query "how has threshold pace changed over the past 12 months?" or "when was the last threshold calibration point?" These are direct inputs to a phase-transition evaluation (am I getting faster at threshold? Is the LT curve moving?). Add a dedicated MCP tool or analytics summary for threshold progression.

---

### 2.5 Session Stress Classification

`compute_toughness_score()` uses weights: load 0.45, intensity 0.40, duration 0.15. The score maps to Easy/Moderate/Hard via thresholds in `StressProfile`.

**What's principled:** Weighting intensity heavily (0.40) is consistent with how most coaches think about "hard" sessions — a 60-minute threshold run is harder than a 90-minute easy run even if TSS is similar. The bucket adjustment (intervals/tempo +0.06, long +0.05) correctly captures qualitative session type differences beyond the raw metrics.

**What's ad-hoc:** The specific weights (0.45/0.40/0.15) and thresholds in StressProfile are not calibrated to athlete outcomes. They are plausible defaults.

**For the LLM coach:** Use Easy/Moderate/Hard as planning primitives (spacing, density), not as precise physiological descriptors. A session classified as Hard is a planning input ("no second Hard session within 48h"), not a physiology claim.

---

## 3. Verified Gaps

### 3.1 No Feedback Loop — Critical

**This is the most important gap for an autonomous long-horizon coach.**

The current system can:
- Read current fitness/fatigue/form
- Read wellness (HRV, sleep, perceived fatigue)
- Plan sessions based on doctrine overlays
- Return coaching briefs on demand

The current system cannot:
- Record what it recommended
- Compare planned load vs actual load
- Evaluate whether its prediction of athlete response matched reality
- Adjust doctrine parameters based on observed outcomes

An autonomous coach that cannot evaluate its own past recommendations is not coaching — it is answering the same question fresh every time. After 6 months of operation, it should know whether this athlete responds faster or slower than the CTL model predicts, whether their overreach threshold is 1.6 or 2.2, whether HRV dip X days post-hard-session is normal or a warning sign.

**What needs to be built:**

1. **Recommendation log** — a structured record of each coaching output: session prescribed, load predicted (TSS, rTSS, stress class), week projection (total load, hard session count).

2. **Outcome log** — actual activity vs recommendation: was the prescribed session completed? What was the actual TSS/rTSS? How did form respond 24-48h later?

3. **Prediction error tracking** — per block: "I predicted CTL would reach X by end of week 4. Actual CTL was Y. Delta = Z."

4. **Athlete response profile** — derived from outcome log: how many days does this athlete need between hard sessions? How does their HRV respond to overreach signals? At what ACWR does their form degrade?

Without this, the LLM is reading a sophisticated state snapshot but has no memory of cause-and-effect for this specific athlete.

---

### 3.2 Phase State Not Tracked Computationally

Training phase (Base/Build/Peak/Taper) is declared in the doctrine overlay files (`training-runtime-active.md`) and read by the LLM at query time. There is no computed phase state in the analytics layer, no phase transition history, and no phase confidence score.

**Consequence:** The LLM coach knows the declared phase but cannot assess whether the athlete's actual load pattern matches that phase, how long they have been in it, or whether the phase declaration is stale.

**What needs to be built:**

1. A `phase_history` table (or analytics summary): phase name, start date, end date, target load range, actual load range.

2. A phase consistency score: "declared Base phase for 5 weeks; actual easy:hard ratio is 62:38 vs target 80:20. Drift score: 0.7."

3. Phase transition readiness as a computed metric (currently exists only as a checklist document), surfaced to the MCP.

---

### 3.3 No Zone Distribution Summary at Block Level

HR zone percentages exist per activity. No aggregation exists at the weekly or block level as a training distribution metric.

**Why this matters:** The primary execution question for a polarized training philosophy is "what percentage of my time is in Zone 1 vs Zone 3+?" This cannot currently be answered from the coaching brief. The LLM must compute it manually from raw activity data, which is fragile and expensive.

**What needs to be built:**

- Weekly zone distribution summary: `zone_1_pct`, `zone_2_pct`, `zone_3_pct` aggregated across all activities for the trailing 4 and 8 weeks.
- Polarization index: `(zone_1_time + zone_3_time) / total_time` as a direct proxy for polarized vs threshold-dominated training.
- These should be first-class fields in `get_fitness_form` or a dedicated `get_training_distribution` MCP tool.

---

### 3.4 No Wellness-to-Load Correlation

Wellness data (HRV, sleep quality, perceived fatigue, resting HR) is collected and surfaced in coaching briefs. There is no computed correlation between wellness signals and subsequent load response.

**Why this matters:** An autonomous coach needs to know, for this athlete: "When HRV drops below X, how many days until form recovers? Does a poor sleep night shift the session stress classification threshold?" These questions require retrospective correlation, not just current snapshot reading.

**What needs to be built:**

- A wellness-lag correlation table: for each wellness signal, compute cross-correlation with form (TSB), fatigue (ATL), and subjective completion rate at 1-7 day lags.
- This should be updated automatically when new wellness and activity data is synced.
- Expose it via a `get_athlete_response_profile` MCP tool.

---

### 3.5 No Adherence / Completion Rate Tracking

There is no tracking of planned vs completed sessions, no streak metrics, and no completion rate per block. The coaching brief has no awareness of whether the athlete is consistently completing prescribed work or systematically skipping certain session types.

**Why this matters:** An autonomous coach that keeps prescribing threshold sessions without knowing the athlete never does them is broken. Adherence is a first-class input to the planning system.

**What needs to be built:**

- A `planned_vs_actual` table or log that maps prescription events to completion events.
- Session completion rate by type (Easy, Moderate, Hard, Long) per block.
- Adherence as a coaching brief field: "Completion rate: 78% overall, 54% Hard sessions."

---

### 3.6 No Mesocycle (Block) Representation

The system operates at the day and week level. There is no formal representation of mesocycles — 3-4 week blocks with a structured recovery week. Block-level periodization is the foundation of most evidence-based endurance training structures.

**Why this matters:** An autonomous coach making week-by-week decisions without knowing where it is in a 4-week block will recommend different things than one that knows "this is week 3 of a load block and week 4 is recovery week." The current doctrine files declare blocks informally in markdown, but this is not queryable or trackable.

**What needs to be built:**

- A `mesocycle` data model: block type (Load/Recovery/Peak), start date, end date, target weekly TSS range, actual weekly TSS per week, status (active/complete).
- `get_current_block` MCP tool returning the active mesocycle context.
- Block-level retrospective in coaching brief: "Block 3 of 4: Week 3. Target 520-560 TSS. Week 1 actual: 510. Week 2 actual: 540. Week 3 so far: 280."

---

### 3.7 Threshold Progression Not Surfaced to MCP

LT pace and LTHR curves track threshold over time, but there is no MCP tool that returns threshold progression history. The coaching brief has no visibility into whether threshold pace has improved, plateaued, or regressed over the current block.

**What needs to be built:**

- `get_threshold_progression` tool: returns LTHR and LT pace history as a time series with timestamps.
- Threshold trend computation: rate of change over last 8 and 16 weeks, plus a simple "improving/plateauing/regressing" classification.

---

### 3.8 TRIMP Re-Enable Path

TRIMP models are implemented but disabled. For a multi-sport athlete, re-enabling them would provide zone-distribution-weighted load quantification for cycling and swimming that is more accurate than mean-HR TSS. There should be a documented plan for when and how TRIMP gets re-enabled (threshold curve stability criterion, validation test).

---

### 3.9 Specificity Ratio (spec=0.8) Is Not Athlete-Configurable

Every non-running sport is treated as 80% running-specific. There is no per-sport, per-athlete, or per-block configuration. A summer base phase with heavy cycling might have a different specificity ratio than a peak running phase.

**Short-term fix:** Add a per-sport specificity map in athlete settings, defaulting to the current constant.

---

## 4. MCP-as-Coach Direction Assessment

### 4.1 Current State

The MCP is a well-structured state reader. It exposes:
- Current fitness/fatigue/form snapshot with all custom metrics
- Activity history with stress classification
- Wellness data
- Doctrine files (planning layers, overlays, active build declaration)
- Week outlook and planning primitives

The `get_coaching_brief` tool assembles these into a single context payload that an LLM can act on. This is the right foundation.

### 4.2 What's Working

- The doctrine layer system (invariant core → athlete-state overlay → event overlay → philosophy overlay) is sophisticated and correct. The LLM can read the reasoning contract from `training-llm-instructions.md` and knows exactly how to use the doctrine hierarchy.
- The `get_fitness_form` time series gives the LLM enough data to reason about trends, not just today's snapshot.
- Session stress classification (Easy/Moderate/Hard) with spacing/density doctrine gives the LLM a vocabulary for prescription that is aligned with how coaches think.

### 4.3 The Core Problem

**The MCP is a state reader, not a memory system.** Every LLM query starts from the same snapshot with no knowledge of:

1. What was recommended before
2. Whether recommendations were followed
3. How the athlete responded to past decisions
4. Whether the LLM's predictions were accurate

An autonomous long-horizon coach must be able to say: "Three weeks ago I recommended increasing threshold work. You completed 2 of 3 prescribed sessions. Your CTL grew from 68 to 74 as projected. Your HRV variability decreased 12%, which is more than I expected. I'm adjusting this week's load down by 8% based on that pattern."

None of that reasoning is currently possible.

### 4.4 Priority Build Order

To become an autonomous long-horizon coach, build these in order:

**Tier 1 — Required for basic autonomy (build first):**

1. **Recommendation log** — Every coaching output written to a structured log with date, prescribed sessions, predicted metrics, and reasoning. Exposed via `log_coaching_recommendation(date, prescriptions, predicted_tss, reasoning_summary)` MCP tool.

2. **Outcome reconciler** — After activity sync, compare log entries to actuals. Compute completion rate, load delta (predicted vs actual), and form delta (predicted vs actual 48h TSB). Store in a reconciliation table.

3. **`get_recommendation_history(days=28)` MCP tool** — Returns the last N days of recommendations + outcomes. This becomes the memory context for the autonomous coach.

**Tier 2 — Required for block-level autonomy:**

4. **Mesocycle model** — Data model + `get_current_block` tool as described in §3.6.

5. **Zone distribution summary** — Weekly and 4-week polarization index as described in §3.3.

6. **Threshold progression tool** — As described in §3.7.

**Tier 3 — Required for athlete-specific calibration:**

7. **Athlete response profile** — Wellness-load correlation + historical ACWR thresholds for this specific athlete (§3.4).

8. **Phase consistency score** — Declared phase vs actual load pattern alignment (§3.2).

9. **Adherence tracking** — Planned vs completed session log (§3.5).

### 4.5 Coaching Brief Evolution

The coaching brief should evolve through stages:

**Stage 1 (current):** Snapshot + doctrine context. LLM answers "what should I do today?" with no memory.

**Stage 2 (after Tier 1):** Snapshot + doctrine + recommendation history. LLM can compare past predictions to outcomes and adjust.

**Stage 3 (after Tier 2):** Snapshot + doctrine + history + block context + zone distribution. LLM can reason across the full training block, not just the current week.

**Stage 4 (after Tier 3):** All of the above + athlete-specific response profile. LLM uses a calibrated model of how this athlete responds to load, not population-level defaults.

---

## 5. Invariants for Future Changes

These constraints must hold across all methodology changes:

1. **TSS parity:** `get_fitness_form.weekly_baseline` must match "Athlete Progression" dashboard. Any change to the EMA formula or TSS computation that breaks this parity is a bug, not a feature.

2. **Doctrine precedence:** Changes to analytics outputs must not silently override the doctrine layer hierarchy (invariant core > athlete-state overlay > event overlay > philosophy overlay).

3. **Workout string round-trip fidelity:** Coaching output that includes workout strings must be reparseable. Do not generate prose that embeds workout structure informally.

4. **TRIMP re-enable must be an explicit migration:** Enabling TRIMP will change all historical hrTSS values for non-running activities. This requires a versioned migration, not a silent default change.

5. **Specificity ratio changes are athlete-state changes:** Changing `spec` from 0.8 to any other value changes all historical proxy distances for that athlete. Treat as a calibration event with a timestamp, like LTHR/LT curve points.

6. **Recommendation log entries are append-only:** Do not edit past recommendations to match what actually happened. The divergence between prediction and outcome is the signal.

---

*Last updated: 2026-04-19*

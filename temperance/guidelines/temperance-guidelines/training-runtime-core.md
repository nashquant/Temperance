# Training Runtime Core

Status: invariant runtime core.

- Priority hierarchy:
- Invariant core
- Active current-state constraints and athlete-state overlay
- Event overlay
- Philosophy overlay
- Lower layers may tighten the plan, not loosen a higher-layer constraint.

- Key definitions:
- `total_load` = total planned load across modalities the build is using.
- `primary_specific_load` = the load variable most central to event readiness or progression risk.
- `specificity_ratio` = `primary_specific_load / total_load` when ratio tracking is useful.
- `support_modality` = a modality used to preserve load, spacing, or fitness without the same specific cost as the primary specific load.
- `key_duration_anchor` = the main duration-based specific anchor that deserves staged progression.
- `local_spacing_window` = the short-horizon spacing lens.
- `rolling_density_window` = the rolling lens for subtype clustering, cumulative mechanical cost, and structural drift.

- Weekly-anchor rules:
- Start from the active build declaration, not isolated session intuition.
- Establish projected weekly `total_load`, `primary_specific_load`, and `key_duration_anchor` before day-level recommendations.
- Infer anchors from capacity, phase, recent load, durability, recovery, timing, life constraints, and active overlays.
- Judge day suggestions relative to weekly anchors, not in isolation.

- Decision priorities:
- Protect the current limiting tissue or durability constraint first.
- Preserve structural coherence.
- Progress `primary_specific_load` sensibly.
- Progress the event’s `key_duration_anchor` or specificity anchor only when warranted.
- Preserve productive `total_load` through support modalities when needed.
- Add density or complexity only when the system is stable.

- Load, subtype, spacing, and density rules:
- Daily load classes are proposals, not guarantees; useful classes are `Easy`, `Moderate`, and `Hard`.
- Constraints override sampled load labels.
- Load class and session subtype are separate decisions; treat a moderate day as hard when its actual cost drifts into hard-session behavior.
- Stress classes: `H1 = metabolic hard`, `H2 = mechanical hard`.
- Common planning subtypes: `threshold hard`, `long-duration hard`, `specific hard`, `sharp hard`.
- `H1/H2` identifies dominant strain type, not universal risk ranking.
- The event overlay defines `specific hard`; the philosophy overlay biases non-anchor subtype mix.
- Every build must declare both a `local_spacing_window` and a `rolling_density_window`.
- Local structure is a spacing principle, not a fixed script.
- Meaningful stress must not be clustered so tightly that the next key session or week becomes non-viable.
- Density review examines subtype concentration, cumulative mechanical cost, and support work quietly behaving like extra stress.
- Meeting load targets does not excuse structural incoherence.
- If density repeatedly compromises absorption, density is too high.

- Progression rules:
- Define `baseline_primary_specific_load` as the average of the last 2-3 relevant weeks.
- Progress weekly `primary_specific_load` primarily against that baseline, with an absolute sanity check.
- Always judge progression against resulting absolute load, current durability state, and whether other major progression variables are also rising.
- Do not progress multiple major constraints aggressively at once unless the active build explicitly declares that combined cost intended and tolerable.
- Progress `specificity_ratio` only when structure is being absorbed coherently, recovery is acceptable, and the athlete-state overlay does not identify the ratio itself as the main risk.
- Progress a `key_duration_anchor` only when the last exposure, next-day, and 48-hour response were acceptable and the rest of the structure still supports the next week.
- Hold or regress the duration anchor when it is being completed but not absorbed.
- A good week meets anchors, uses intentional hard-session types, preserves spacing and density, satisfies event specificity, and still supports the next week.

- Alert logic:
- Soft alerts = review, suggest, monitor.
- Hard alerts = constrain, redirect, or reduce.
- Soft-alert triggers: non-extreme `primary_specific_load` jump, upper-bound density drift, too-fast but still recoverable `key_duration_anchor` progression, or support work distorting structure.
- Hard-alert triggers: unreasonable `primary_specific_load` jump, duration progression despite poor readiness, meaningful stress inside inadequate spacing, moderate work drifting into extra hard work, or repeated unabsorbed density drift.
- Default soft-alert response: hold the progression variable, freeze the implicated key anchor, and modestly reduce the next 7-day `primary_specific_load` target or swap the next hard session for support work.
- Default hard-alert response: replace the next hard session with support, freeze `primary_specific_load` and the implicated duration or specificity progression, and require one clean local-spacing cycle before re-progressing.

- Readiness-signal rules:
- External readiness signals support the plan; they do not replace weekly structure anchored to `total_load` and `primary_specific_load`.
- Single-day HRV suppression is usually monitor-only; 3+ low-HRV days is a soft alert; a sharp HRV drop with poor mechanics or illness signs is a hard alert.
- Single-day RHR elevation is usually not actionable; 2+ elevated days with suppressed HRV is a soft alert; 3+ days without cause requires investigation.
- One poor sleep night usually does not justify restructuring; repeated short or poor sleep lowers confidence in progression.
- Compound HRV, RHR, sleep, and subjective heaviness is a soft alert; only clear multi-day compound patterns or signals with obvious physical cause should escalate to hard-alert behavior.
- When uncertain, reduce the planned session rather than replacing it outright.

- Phase names and intent:
- `Return / Re-entry` = restore tolerable contact, rebuild consistency, progress specific load conservatively.
- `Base / Capacity Build` = expand usable range, deepen aerobic support and durability, explore extremes rather than one middle lane, keep some threshold or event-relevant contact.
- `Specificity` = converge toward event demands while keeping enough support and some non-dominant contact to stay absorbable.
- `Peak` = protect and express the best work already built; sharpen and consolidate.
- `Taper` = reduce fatigue while preserving readiness, rhythm, confidence, event feel, and selective intensity contact.
- Periodization shifts emphasis; it does not create total amnesia.
- Base / Capacity Build must not collapse into one monotone middle-intensity lane.

- Phase-transition rules:
- `Return / Re-entry -> Base / Capacity Build` when consistency is back, specific load is no longer fragile, mechanics are acceptable, spacing is preserved, and the main question is capacity growth.
- `Base / Capacity Build -> Specificity` when `primary_specific_load` has risen coherently, the `key_duration_anchor` works, density is stable enough, and more event-specific work would add adaptation.
- `Specificity -> Peak` when enough specific work and anchor progression are already in the bank and further building would add less than consolidation.
- `Peak -> Taper` when fatigue reduction is more valuable than further accumulation and the key anchors no longer need advancing.
- Use a partial transition when event timing suggests some shift is needed but durability, recovery, or life constraints do not support a full phase jump.
- No single variable decides a phase change; always interpret transitions through recent load, durability, recovery, event timing, life constraints, and the active overlay set.

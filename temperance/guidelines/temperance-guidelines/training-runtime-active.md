# Training Runtime Active

Status: ephemeral active runtime.

This is the default current-state packet. Load it before broader roadmap or
history context.

- Active overlays:
- Athlete-state: `training-athlete-state-high-capacity-durability-limited.local.md`
- Event: `training-event-marathon-default.md`
- Philosophy: `training-philosophy-durability-threshold-support.local.md`

- Metric mapping:
- Core `total_load` -> weekly `total_TSS`
- Core `primary_specific_load` -> weekly `rTSS`
- Core `specificity_ratio` -> discount coefficient applied to x-train TSS when estimating x-train contribution to `primary_specific_load`
- Core `key_duration_anchor` -> long-run duration and long-run load
- Core `support_modality` -> elliptical, cycling, and other low-impact x-train
- Core `local_spacing_window` -> 3 days
- Core `rolling_density_window` -> 9 days

- Weekly anchors:
- Default weekly `total_TSS` anchor = 550
- Default weekly `rTSS` anchor = 150
- Current run-ratio anchor = about 27%
- Current long-run anchor = progressive rebuild, not a mature marathon long run yet

- Phase and objective:
- Generic phase = `Base / Capacity Build`
- Residual phase note = some late `Return / Re-entry` durability-rebuild features are still present
- Goal event = July 12, 2026 marathon
- Immediate objective = keep total load high, raise useful running gradually, and improve durability without letting the engine outpace the legs again

- Constraints and interpretation:
- Engine is not the limiter; durability is.
- High `total_TSS` is acceptable.
- Running load should rise more cautiously than total load.
- Do not force marathon-specific density early just because the engine can support it.
- Protect long-run progression and threshold density more than sharpness.
- Preserve high aerobic support while durability catches up.

- Hard-session emphasis and watchouts:
- Threshold and strong-aerobic work are central.
- Long-duration durability work is central.
- Marathon-oriented specific work should increase as the cycle advances.
- VO2 and sharp work are supporting only.
- Do not let moderate days drift into hidden threshold.
- Do not let high `total_TSS` hide insufficient run durability.
- Be cautious with threshold density and additive weekend load.
- Keep threshold, marathon-specific, and long-duration hard work balanced so one type does not dominate the block.
- Anchor every recommendation to projected weekly `total_TSS` and `rTSS` before judging a single day.

from __future__ import annotations

from temperance.planning.models import GeneratedWorkout, SessionCandidate


def render_generated_workout(
    candidate: SessionCandidate | None,
    *,
    target_tss: float,
    rest_label: str = "Rest",
) -> GeneratedWorkout:
    if candidate is None:
        return GeneratedWorkout(
            activity_text=rest_label,
            modality="rest",
            target_tss=float(target_tss),
            estimated_tss=0.0,
            source="policy",
        )
    return GeneratedWorkout(
        activity_text=str(candidate.activity_text or "").strip(),
        modality=str(candidate.modality or "").strip().lower() or "unknown",
        target_tss=float(target_tss),
        estimated_tss=float(candidate.estimated_tss),
        source=str(candidate.source or "candidate"),
    )

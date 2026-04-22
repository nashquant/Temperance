import type { CoachSnapshotResponse } from "@/features/coach-snapshot/types/coach-snapshot";

function formatShortDate(value: string | null): string {
  if (!value) return "-";
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(parsed);
}

function raceLabel(snapshot: CoachSnapshotResponse): string {
  const raceType = String(snapshot.next_race_type || "race");
  const cleanType = raceType.replace(/[_-]+/g, " ").trim();
  return `${cleanType || "race"} · ${formatShortDate(snapshot.next_race_date)}`;
}

export function CoachSnapshotChips({
  snapshot,
}: {
  snapshot: CoachSnapshotResponse;
}): JSX.Element {
  const baseChipClassName =
    "whitespace-nowrap rounded-full border px-2.5 py-1 text-xs text-muted-foreground";

  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span className={baseChipClassName}>
        {snapshot.current_phase ?? "-"}
      </span>
      <span className={baseChipClassName}>
        {raceLabel(snapshot)}
      </span>
      <span className={`${baseChipClassName} border-sky-300/30 bg-sky-300/8 font-mono text-sky-100`}>
        {typeof snapshot.days_to_race === "number"
          ? `D-${snapshot.days_to_race}`
          : "D-?"}
      </span>
      <span className={baseChipClassName}>
        {snapshot.next_phase ?? "-"}
      </span>
    </div>
  );
}

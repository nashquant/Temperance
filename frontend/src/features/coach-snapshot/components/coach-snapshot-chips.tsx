import type { CoachSnapshotResponse } from '@/features/coach-snapshot/types/coach-snapshot';

function formatDate(value: string | null): string {
  if (!value) return '-';
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(parsed);
}

function raceLabel(snapshot: CoachSnapshotResponse): string {
  const raceType = String(snapshot.next_race_type || 'race');
  const cleanType = raceType.replace(/[_-]+/g, ' ').trim();
  return `${cleanType || 'race'} on ${formatDate(snapshot.next_race_date)}`;
}

export function CoachSnapshotChips({ snapshot }: { snapshot: CoachSnapshotResponse }): JSX.Element {
  return (
    <div className="flex min-w-0 items-center gap-1.5">
      <span className="whitespace-nowrap rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
        Phase: {snapshot.current_phase ?? '-'}
      </span>
      <span className="whitespace-nowrap rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
        Goal: {raceLabel(snapshot)}
      </span>
      <span className="whitespace-nowrap rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
        {typeof snapshot.days_to_race === 'number' ? `D-${snapshot.days_to_race}` : 'D-?'}
      </span>
      <span className="whitespace-nowrap rounded-full border px-2.5 py-1 text-xs text-muted-foreground">
        Next: {snapshot.next_phase ?? '-'}
      </span>
    </div>
  );
}

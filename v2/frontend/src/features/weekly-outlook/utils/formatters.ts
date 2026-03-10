function safeDateFromIso(dayIso: string): Date | null {
  const raw = String(dayIso || '').trim();
  if (!raw) return null;
  const date = new Date(`${raw}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatMetricValue(value: number, metric: 'tss' | 'rtss' | 'distance'): string {
  if (metric === 'distance') {
    return `${value.toFixed(1)} km`;
  }

  return `${Math.round(value)} ${metric === 'rtss' ? 'rTSS' : 'TSS'}`;
}

export function formatDayLabel(dayIso: string): string {
  const date = safeDateFromIso(dayIso);
  if (!date) return dayIso || '-';
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    weekday: 'short',
  }).format(date);
}

export function formatRange(startIso: string, endIso: string): string {
  const start = safeDateFromIso(startIso);
  const end = safeDateFromIso(endIso);
  if (!start || !end) return 'Current week';

  const sameYear = start.getFullYear() === end.getFullYear();
  const formattedStart = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(sameYear ? {} : { year: 'numeric' }),
  }).format(start);

  const formattedEnd = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(end);

  return `${formattedStart} - ${formattedEnd}`;
}

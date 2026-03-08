export function formatMetricValue(value: number, metric: 'tss' | 'rtss' | 'distance'): string {
  if (metric === 'distance') {
    return `${value.toFixed(1)} km`;
  }

  return `${Math.round(value)} ${metric === 'rtss' ? 'rTSS' : 'TSS'}`;
}

export function formatDayLabel(dayIso: string): string {
  const date = new Date(`${dayIso}T00:00:00`);
  return new Intl.DateTimeFormat('en-US', {
    day: 'numeric',
    month: 'short',
    weekday: 'short',
  }).format(date);
}

export function formatRange(startIso: string, endIso: string): string {
  const start = new Date(`${startIso}T00:00:00`);
  const end = new Date(`${endIso}T00:00:00`);

  const formattedStart = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(start);

  const formattedEnd = new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(end);

  return `${formattedStart} - ${formattedEnd}`;
}

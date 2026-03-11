export function formatCompactDurationHours(hours: number | null | undefined): string {
  if (hours == null || !Number.isFinite(hours)) return '-';

  const totalMinutes = Math.max(0, Math.round(hours * 60));
  const wholeHours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (wholeHours > 0) {
    return minutes > 0 ? `${wholeHours}h${minutes}'` : `${wholeHours}h`;
  }

  return `${minutes}'`;
}

export function normalizeCompactDurationLabel(label: string | null | undefined): string {
  const cleaned = String(label || '').trim();
  if (!cleaned) return '';

  if (cleaned.includes("'") || cleaned.includes('"')) return cleaned;

  const compactMatch = cleaned.match(/^(\d+)h(?:\s+)?(\d+)m$/i);
  if (compactMatch) {
    const hours = Number(compactMatch[1]);
    const minutes = Number(compactMatch[2]);
    if (Number.isFinite(hours) && Number.isFinite(minutes)) {
      return minutes > 0 ? `${hours}h${minutes}'` : `${hours}h`;
    }
  }

  const hoursOnlyMatch = cleaned.match(/^(\d+)h$/i);
  if (hoursOnlyMatch) return `${hoursOnlyMatch[1]}h`;

  const minutesOnlyMatch = cleaned.match(/^(\d+)m$/i);
  if (minutesOnlyMatch) return `${minutesOnlyMatch[1]}'`;

  return cleaned;
}

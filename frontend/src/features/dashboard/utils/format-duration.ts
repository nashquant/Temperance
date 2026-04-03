/**
 * Format a duration in seconds to a compact `h' m'` string, e.g. "1h05'" or "23'".
 * Used for zone time labels and similar compact displays.
 */
export function formatZoneSeconds(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.round((total % 3600) / 60);
  if (h > 0) return `${h}h${String(m).padStart(2, '0')}'`;
  return `${m}'`;
}

/**
 * Format a duration in seconds to a compact `m's"` string, e.g. "23'45"" or "23'".
 * Used for chart labels where space is tight.
 */
export function formatDurationMS(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  if (secs === 0) return `${minutes}'`;
  return `${minutes}'${String(secs).padStart(2, '0')}"`;
}

/**
 * Format a duration in seconds to a verbose `Xh Ym Zs` string, e.g. "1h 23m 45s".
 * Used for activity detail displays where seconds matter.
 */
export function formatDurationHMS(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s}s`;
}

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

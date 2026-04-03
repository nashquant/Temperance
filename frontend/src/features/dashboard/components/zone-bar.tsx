import { zoneHexFromLabel, zoneTrackClassNames, zoneTrackFallbackClassName } from '@/features/dashboard/utils/intensity-palette';
import { formatZoneSeconds } from '@/features/dashboard/utils/format-duration';

interface ZoneBarProps {
  zone: string;
  seconds: number;
  pct: number;
  /** Tailwind class for the outer grid row, defaults to the summary card style. */
  className?: string;
}

export function ZoneBar({ zone, seconds, pct, className }: ZoneBarProps): JSX.Element {
  const hex = zoneHexFromLabel(zone);
  const fillWidth = pct > 0 ? Math.max(3, Math.min(100, pct)) : 0;

  return (
    <div
      className={
        className ??
        'grid grid-cols-[32px_minmax(36px,1fr)_42px_24px] items-center gap-1 text-[11px] leading-4 text-muted-foreground'
      }
    >
      <span className="inline-flex items-center gap-1 font-medium text-slate-200/92">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: hex }} />
        {zone}
      </span>
      <div className={`h-1.5 w-full overflow-hidden rounded-full border ${zoneTrackClassNames[zone] ?? zoneTrackFallbackClassName}`}>
        <div
          className="h-full rounded-full"
          style={{ backgroundColor: hex, width: `${fillWidth}%` }}
        />
      </div>
      <span className="text-right font-medium tabular-nums text-slate-200/92">{formatZoneSeconds(seconds)}</span>
      <span className="text-right tabular-nums">{Math.round(pct)}%</span>
    </div>
  );
}

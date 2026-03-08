import type { DashboardWeekSummary } from '@/features/dashboard/types/dashboard';

interface DashboardWeekSummaryCardProps {
  weekNumber: number;
  weekStart: string;
  weekEnd: string;
  summary: DashboardWeekSummary;
}

function fmtNumber(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '-';
  return Math.round(value).toString();
}

function fmtDuration(hours: number): string {
  return `${hours.toFixed(1)}h`;
}

function fmtSeconds(seconds: number): string {
  const totalMin = Math.max(0, Math.round(seconds / 60));
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

const zoneColors: Record<string, string> = {
  Z1: 'bg-emerald-500',
  Z2: 'bg-sky-500',
  Z3: 'bg-amber-500',
  Z4: 'bg-orange-500',
  Z5: 'bg-rose-500',
};

export function DashboardWeekSummaryCard({ weekNumber, weekStart, weekEnd, summary }: DashboardWeekSummaryCardProps): JSX.Element {
  return (
    <div className="rounded-xl border border-border/70 bg-card/70 p-3">
      <p className="text-xs font-medium text-muted-foreground">Week {weekNumber}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{weekStart} - {weekEnd}</p>

      <div className="mt-3 space-y-1.5 text-xs text-muted-foreground">
        <p>Time: <span className="font-semibold text-foreground">{fmtDuration(summary.duration_h)}</span></p>
        <p>Dist: <span className="font-semibold text-foreground">{fmtNumber(summary.distance_km)} km</span></p>
        <p>Eqv: <span className="font-semibold text-foreground">{fmtNumber(summary.distance_eqv_km)} km</span></p>
        <p>kcal: <span className="font-semibold text-foreground">{fmtNumber(summary.calories)}</span></p>
        <p>TSS: <span className="font-semibold text-foreground">{fmtNumber(summary.tss)}</span> | rTSS: <span className="font-semibold text-foreground">{fmtNumber(summary.rtss)}</span></p>
        <p>Fit: <span className="font-semibold text-foreground">{fmtNumber(summary.fitness)}</span> | Fatg: <span className="font-semibold text-foreground">{fmtNumber(summary.fatigue)}</span></p>
        <p>Ovr: <span className="font-semibold text-foreground">{fmtNumber(summary.overreach)}</span> | Risk: <span className="font-semibold text-foreground">{fmtNumber(summary.injury_risk)}</span></p>
      </div>

      <div className="mt-3 space-y-1.5 border-t border-border/70 pt-2">
        <p className="text-xs font-medium text-foreground">Zones</p>
        {summary.zones.map((zone) => (
          <div key={zone.zone} className="grid grid-cols-[24px_1fr_58px_42px] items-center gap-1.5 text-[11px] text-muted-foreground">
            <span>{zone.zone}</span>
            <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
              <div className={`h-full rounded-full ${zoneColors[zone.zone] ?? 'bg-slate-500'}`} style={{ width: `${Math.max(0, Math.min(100, zone.pct))}%` }} />
            </div>
            <span className="text-right">{fmtSeconds(zone.seconds)}</span>
            <span className="text-right">{zone.pct.toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

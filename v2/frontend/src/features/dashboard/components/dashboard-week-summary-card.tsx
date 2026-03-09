import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
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
  Z1: 'bg-slate-400',
  Z2: 'bg-sky-500',
  Z3: 'bg-amber-500',
  Z4: 'bg-rose-500',
  Z5: 'bg-violet-500',
};

export function DashboardWeekSummaryCard({ weekNumber, weekStart, weekEnd, summary }: DashboardWeekSummaryCardProps): JSX.Element {
  return (
    <Card className="rounded-xl border-border/80 bg-card/80 shadow-sm lg:h-[430px]">
      <CardContent className="flex h-full flex-col space-y-2 overflow-y-auto p-2">
        <div className="space-y-1">
          <Badge variant="outline" className="h-5 rounded-full px-2 text-[10px] font-semibold tracking-wide">
            Week {weekNumber}
          </Badge>
          <p className="text-[13px] font-medium leading-5 text-muted-foreground">
            {weekStart} - {weekEnd}
          </p>
        </div>

        <div className="grid grid-cols-[1fr_auto] gap-x-1 gap-y-0.5 text-[12px] leading-5">
          <p className="text-muted-foreground">Time</p>
          <p className="text-right font-semibold tabular-nums">{fmtDuration(summary.duration_h)}</p>
          <p className="text-muted-foreground">Dist</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.distance_km)} km</p>
          <p className="text-muted-foreground">Eqv</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.distance_eqv_km)} km</p>
          <p className="text-muted-foreground">kcal</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.calories)}</p>
          <p className="text-muted-foreground">TSS | rTSS</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.tss)} | {fmtNumber(summary.rtss)}</p>
          <p className="text-muted-foreground">Fit | Fatg</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.fitness)} | {fmtNumber(summary.fatigue)}</p>
          <p className="text-muted-foreground">Ovr | Risk</p>
          <p className="text-right font-semibold tabular-nums">{fmtNumber(summary.overreach)} | {fmtNumber(summary.injury_risk)}</p>
        </div>

        <Separator className="bg-border/70" />

        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Zones</p>
          {summary.zones.map((zone) => (
            <div key={zone.zone} className="grid grid-cols-[18px_minmax(36px,1fr)_42px_24px] items-center gap-1 text-[11px] leading-4 text-muted-foreground">
              <span>{zone.zone}</span>
              <div className="h-1.5 w-full overflow-hidden rounded-full border border-border/70 bg-muted/70">
                <div
                  className={`h-full rounded-full ${zoneColors[zone.zone] ?? 'bg-slate-500'}`}
                  style={{ width: `${zone.pct > 0 ? Math.max(3, Math.min(100, zone.pct)) : 0}%` }}
                />
              </div>
              <span className="text-right">{fmtSeconds(zone.seconds)}</span>
              <span className="text-right">{zone.pct.toFixed(0)}%</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

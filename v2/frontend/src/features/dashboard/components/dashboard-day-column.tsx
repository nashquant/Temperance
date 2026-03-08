import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { DashboardDayColumn as DashboardDayColumnType } from '@/features/dashboard/types/dashboard';

interface DashboardDayColumnProps {
  day: DashboardDayColumnType;
}

const intensityClasses: Record<string, string> = {
  green: 'border-slate-400/55 bg-slate-500/10',
  blue: 'border-sky-500/50 bg-sky-500/10',
  orange: 'border-amber-500/55 bg-amber-500/10',
  red: 'border-rose-500/50 bg-rose-500/10',
  purple: 'border-violet-500/50 bg-violet-500/10',
};

const plannedIntensityClasses: Record<string, string> = {
  green: 'border-slate-300/70 bg-slate-500/5',
  blue: 'border-sky-400/70 bg-sky-500/5',
  orange: 'border-amber-400/70 bg-amber-500/5',
  red: 'border-rose-400/70 bg-rose-500/5',
  purple: 'border-violet-400/70 bg-violet-500/5',
};

function fmtMeta(day: DashboardDayColumnType): string[] {
  const out: string[] = [];
  out.push(`${Math.round(day.meta.distance_eqv_km || 0)} km`);
  if ((day.meta.calories || 0) > 0) out.push(`${Math.round(day.meta.calories)} kcal`);
  if (day.meta.fitness !== null) out.push(`Fit ${Math.round(day.meta.fitness)}`);
  if (day.meta.fatigue !== null) out.push(`Fatigue ${Math.round(day.meta.fatigue)}`);
  if (day.meta.resting_hr !== null && day.meta.resting_hr > 0) out.push(`RHR ${Math.round(day.meta.resting_hr)}`);
  if (day.meta.stress_avg !== null && day.meta.stress_avg > 0) out.push(`Stress ${Math.round(day.meta.stress_avg)}`);
  if ((day.meta.planned_duration_s || 0) > 0) {
    out.push(`${Math.round(day.meta.planned_duration_s / 3600)}h`);
  }
  if ((day.meta.planned_if_pct || 0) > 0) out.push(`IF ${Math.round(day.meta.planned_if_pct)}%`);
  return out;
}

function formatActivityTitle(raw: string): string {
  const cleaned = String(raw || '').trim();
  if (!cleaned) return 'Activity';

  const normalized = cleaned.toLowerCase();
  if (normalized === 'treadmill_running' || normalized === 'treadmill run' || normalized === 'treadmillrunning') {
    return 'Treadmill';
  }

  return cleaned
    .replace(/[_-]+/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

export function DashboardDayColumn({ day }: DashboardDayColumnProps): JSX.Element {
  return (
    <Card
      className={cn(
        'rounded-xl border-border/80 bg-card/75 shadow-sm',
        day.is_today ? 'border-primary/70' : undefined,
      )}
    >
      <CardContent className="space-y-2 p-2.5">
        <div className="space-y-1">
          <div className="flex min-h-[24px] items-center justify-between gap-1.5">
            <p className={cn('truncate text-[13px] font-semibold leading-5', day.is_today ? 'text-primary' : 'text-foreground')}>
              {day.day_label}
            </p>
            {day.is_today ? (
              <Badge variant="outline" className="h-5 shrink-0 rounded-full px-2 text-[10px] font-semibold text-primary">
                Today
              </Badge>
            ) : null}
          </div>
          <p className="line-clamp-2 min-h-[34px] text-[12px] leading-[1.35] text-muted-foreground">{fmtMeta(day).join(' · ')}</p>
        </div>

        <Separator className="bg-border/70" />

        <div className="space-y-2">
          {day.actual_activities.map((activity) => (
            <div
              key={activity.activity_id}
              className={cn(
                'rounded-lg border p-2 text-[12px] leading-[1.35]',
                intensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
              )}
            >
              <p className="truncate font-semibold text-foreground">{formatActivityTitle(activity.sport)}</p>
              <p className="text-muted-foreground">
                {activity.duration_label} · {activity.distance_label}
              </p>
              <p className="text-muted-foreground">
                {activity.hr_label} · {activity.pace_label} · IF {Math.round(activity.if_pct)}%
              </p>
              <p className="font-semibold text-foreground">
                TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}
              </p>
            </div>
          ))}

          {day.planned_activities.map((activity) => (
            <div
              key={`${activity.day_utc}-${activity.line_no}`}
              className={cn(
                'rounded-lg border-2 border-dashed p-2 text-[12px] leading-[1.35]',
                plannedIntensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
              )}
            >
              <Badge variant="outline" className="mb-1 h-5 rounded-full px-2 text-[10px] font-semibold uppercase tracking-wide">
                Planned
              </Badge>
              <p className="truncate font-semibold text-foreground">{formatActivityTitle(activity.activity)}</p>
              <p className="text-muted-foreground">
                {activity.duration_label} · {Math.round(activity.distance_eqv_km)} km eqv.
              </p>
              <p className="text-muted-foreground">IF {Math.round(activity.if_pct)}%</p>
              <p className="font-semibold text-foreground">
                TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}
              </p>
            </div>
          ))}

          {day.actual_activities.length === 0 && day.planned_activities.length === 0 && day.is_past ? (
            <div className="rounded-lg border border-border/70 bg-muted/25 p-2 text-center text-[12px] text-muted-foreground">
              <p className="font-semibold text-foreground">Rest Day</p>
              <p>Rest is part of training.</p>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

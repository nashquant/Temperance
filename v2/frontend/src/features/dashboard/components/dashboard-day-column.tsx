import { cn } from '@/lib/utils';
import type { DashboardDayColumn as DashboardDayColumnType } from '@/features/dashboard/types/dashboard';

interface DashboardDayColumnProps {
  day: DashboardDayColumnType;
}

const intensityClasses: Record<string, string> = {
  green: 'border-emerald-500/50 bg-emerald-500/10',
  blue: 'border-sky-500/50 bg-sky-500/10',
  orange: 'border-orange-500/50 bg-orange-500/10',
  red: 'border-rose-500/50 bg-rose-500/10',
};

const plannedIntensityClasses: Record<string, string> = {
  green: 'border-emerald-400/70 bg-emerald-500/5',
  blue: 'border-sky-400/70 bg-sky-500/5',
  orange: 'border-orange-400/70 bg-orange-500/5',
  red: 'border-rose-400/70 bg-rose-500/5',
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

export function DashboardDayColumn({ day }: DashboardDayColumnProps): JSX.Element {
  return (
    <div className="space-y-2 rounded-xl border border-border/70 bg-card/50 p-2.5">
      <p className={cn('text-xs font-semibold', day.is_today ? 'text-primary' : 'text-foreground')}>{day.day_label}</p>
      <p className="line-clamp-3 min-h-[30px] text-[11px] text-muted-foreground">{fmtMeta(day).join(' · ')}</p>

      <div className="space-y-2">
        {day.actual_activities.map((activity) => (
          <div key={activity.activity_id} className={cn('rounded-lg border p-2 text-[11px]', intensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20')}>
            <p className="font-semibold text-foreground">{activity.sport}</p>
            <p className="text-muted-foreground">{activity.duration_label} · {activity.distance_label}</p>
            <p className="text-muted-foreground">{activity.hr_label} · {activity.pace_label} · IF {Math.round(activity.if_pct)}%</p>
            <p className="font-semibold text-foreground">TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}</p>
          </div>
        ))}

        {day.planned_activities.map((activity) => (
          <div
            key={`${activity.day_utc}-${activity.line_no}`}
            className={cn(
              'rounded-lg border-2 border-dashed p-2 text-[11px]',
              plannedIntensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
            )}
          >
            <p className="mb-1 inline-flex rounded-full border border-border/70 bg-muted/30 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Planned
            </p>
            <p className="font-semibold text-foreground">{activity.activity}</p>
            <p className="text-muted-foreground">{activity.duration_label} · {Math.round(activity.distance_eqv_km)} km eqv.</p>
            <p className="text-muted-foreground">IF {Math.round(activity.if_pct)}%</p>
            <p className="font-semibold text-foreground">TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}</p>
          </div>
        ))}

        {day.actual_activities.length === 0 && day.planned_activities.length === 0 && day.is_past ? (
          <div className="rounded-lg border border-border/70 bg-muted/20 p-2 text-center text-[11px] text-muted-foreground">
            <p className="font-semibold text-foreground">Rest Day</p>
            <p>Rest is part of training.</p>
          </div>
        ) : null}
      </div>
    </div>
  );
}

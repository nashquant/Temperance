import { X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { DashboardDayColumn as DashboardDayColumnType } from '@/features/dashboard/types/dashboard';

interface DashboardDayColumnProps {
  day: DashboardDayColumnType;
  onMarkPlannedDone?: (dayUtc: string, lineNo: number) => void;
  onSelectActivity?: (activityId: string) => void;
  markingPlannedDone?: boolean;
  userTimeZone?: string;
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
  const line1: string[] = [];
  const line2: string[] = [];
  const line3: string[] = [];

  line1.push(`${Math.round(day.meta.distance_eqv_km || 0)} km`);
  if ((day.meta.calories || 0) > 0) line1.push(`${Math.round(day.meta.calories)} kcal`);

  if (day.meta.fitness !== null) line2.push(`Fit ${Math.round(day.meta.fitness)}`);
  if (day.meta.fatigue !== null) line2.push(`Fatigue ${Math.round(day.meta.fatigue)}`);

  if (day.meta.resting_hr !== null && day.meta.resting_hr > 0) {
    line3.push(`RHR ${Math.round(day.meta.resting_hr)}`);
  }
  if (day.meta.stress_avg !== null && day.meta.stress_avg > 0) {
    line3.push(`Stress ${Math.round(day.meta.stress_avg)}`);
  }

  if (line2.length === 0 && (day.meta.planned_duration_s || 0) > 0) {
    line2.push(`${Math.round(day.meta.planned_duration_s / 3600)}h`);
  }
  if (line2.length < 2 && (day.meta.planned_if_pct || 0) > 0) {
    line2.push(`IF ${Math.round(day.meta.planned_if_pct)}%`);
  }
  if (line3.length === 0 && day.meta.show_fatigue_expected && day.meta.fatigue_expected !== null) {
    line3.push(`Fatigue exp ${Math.round(day.meta.fatigue_expected)}`);
  }

  return [line1.join(' · '), line2.join(' · '), line3.join(' · ')].filter(Boolean);
}

function formatActivityTitle(raw: string): string {
  const cleaned = String(raw || '').trim();
  if (!cleaned) return 'Activity';

  const normalized = cleaned.toLowerCase();
  if (normalized.includes('strength')) return 'Lift';
  if (normalized.includes('swim')) return 'Swim';
  if (normalized.includes('cycl')) return 'Bike';
  if (normalized === 'run' || normalized === 'running' || normalized.includes(' run')) return 'Run';
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

function compactLine(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => String(part || '').trim())
    .filter(Boolean)
    .map((part) => part.replace(/km\s*eqv\.?/gi, 'kmeq'))
    .join(' · ');
}

function deriveCompactTimeLabel(
  activity: DashboardDayColumnType['actual_activities'][number],
  userTimeZone?: string,
): string {
  const rawUtc = String(activity.start_time_utc || '').trim();
  if (rawUtc) {
    const parsed = new Date(rawUtc);
    if (!Number.isNaN(parsed.getTime())) {
      const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      const tz = String(userTimeZone || '').trim() || browserTz;
      try {
        const hh = new Intl.DateTimeFormat('en-US', {
          hour: 'numeric',
          hour12: false,
          timeZone: tz,
        }).format(parsed);
        const mm = new Intl.DateTimeFormat('en-US', {
          minute: '2-digit',
          hour12: false,
          timeZone: tz,
        }).format(parsed);
        const hour24 = Number(hh);
        const minute = Number(mm);
        if (!Number.isNaN(hour24) && !Number.isNaN(minute)) {
          const roundedHour24 = (hour24 + (minute >= 30 ? 1 : 0)) % 24;
          const suffix = roundedHour24 >= 12 ? 'pm' : 'am';
          const hour12 = roundedHour24 % 12 === 0 ? 12 : roundedHour24 % 12;
          return `@${hour12}${suffix}`;
        }
      } catch {
        const hour24 = parsed.getHours();
        const minute = parsed.getMinutes();
        const roundedHour24 = (hour24 + (minute >= 30 ? 1 : 0)) % 24;
        const suffix = roundedHour24 >= 12 ? 'pm' : 'am';
        const hour12 = roundedHour24 % 12 === 0 ? 12 : roundedHour24 % 12;
        return `@${hour12}${suffix}`;
      }
    }
  }
  const hhmm = String(activity.start_time_hhmm || '').trim();
  const fallbackMatch = hhmm.match(/^(\d{1,2}):(\d{2})$/);
  if (fallbackMatch) {
    const hour24 = Number(fallbackMatch[1]);
    const minute = Number(fallbackMatch[2]);
    if (!Number.isNaN(hour24) && !Number.isNaN(minute)) {
      const roundedHour24 = (hour24 + (minute >= 30 ? 1 : 0)) % 24;
      const suffix = roundedHour24 >= 12 ? 'pm' : 'am';
      const hour12 = roundedHour24 % 12 === 0 ? 12 : roundedHour24 % 12;
      return `@${hour12}${suffix}`;
    }
  }
  return '';
}

export function DashboardDayColumn({ day, onMarkPlannedDone, onSelectActivity, markingPlannedDone, userTimeZone }: DashboardDayColumnProps): JSX.Element {
  return (
    <Card
      className={cn(
        'rounded-xl border-border/80 bg-card/75 shadow-sm lg:h-[430px]',
        day.is_today ? 'border-primary/70' : undefined,
      )}
    >
      <CardContent className="flex h-full flex-col gap-2 p-2.5">
        <div className="space-y-1">
          <div className="flex min-h-[24px] items-center">
            <p className={cn('text-[13px] font-semibold leading-5', day.is_today ? 'text-primary' : 'text-foreground')}>
              {day.day_label}
            </p>
          </div>
          <div className="min-h-[50px] space-y-0.5 text-[12px] leading-[1.3] text-muted-foreground">
            {fmtMeta(day).map((line) => (
              <p key={line} className="truncate">
                {line}
              </p>
            ))}
          </div>
        </div>

        <Separator className="bg-border/70" />

        <div className="flex-1 space-y-2 overflow-y-auto pr-0.5">
          {day.actual_activities.map((activity) => (
            (() => {
              const timeLabel = deriveCompactTimeLabel(activity, userTimeZone);
              return (
                <div
                  key={activity.activity_id}
                  className={cn(
                    'flex h-[102px] cursor-pointer flex-col overflow-hidden rounded-lg border p-2 text-[12px] transition-colors hover:bg-white/5',
                    intensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
                  )}
                  onClick={() => onSelectActivity?.(activity.activity_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onSelectActivity?.(activity.activity_id);
                    }
                  }}
                >
                  <p className="truncate text-[13px] font-semibold leading-5 text-foreground">
                    {formatActivityTitle(activity.sport)}
                    {timeLabel ? ` ${timeLabel}` : ''}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[12px] leading-4 text-muted-foreground">
                    {compactLine([activity.duration_label, activity.distance_label])}
                  </p>
                  <p className="line-clamp-2 text-[12px] leading-4 text-muted-foreground">
                    {compactLine([activity.pace_label, `IF ${Math.round(activity.if_pct)}%`])}
                  </p>
                  <p className="mt-auto truncate text-[12px] font-semibold leading-4 text-foreground">
                    TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}
                  </p>
                </div>
              );
            })()
          ))}

          {day.planned_activities.map((activity) => (
            <div
              key={`${activity.day_utc}-${activity.line_no}`}
              className={cn(
                'relative flex h-[102px] flex-col overflow-hidden rounded-lg border-2 border-dashed p-2 text-[12px]',
                plannedIntensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
              )}
            >
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-1 top-1 h-5 w-5 rounded-full text-muted-foreground hover:text-foreground"
                onClick={() => onMarkPlannedDone?.(activity.day_utc, activity.line_no)}
                disabled={markingPlannedDone}
                aria-label="Mark planned activity as done"
              >
                <X className="h-3.5 w-3.5" />
              </Button>
              <p className="text-[13px] font-semibold leading-5 text-foreground">
                {formatActivityTitle(activity.activity)} <span className="text-muted-foreground">(P)</span>
              </p>
              <p className="line-clamp-2 text-[12px] leading-4 text-muted-foreground">
                {compactLine([activity.duration_label, `${Math.round(activity.distance_eqv_km)} kmeq`])}
              </p>
              <p className="line-clamp-2 text-[12px] leading-4 text-muted-foreground">
                {compactLine([activity.pace_label, `IF ${Math.round(activity.if_pct)}%`])}
              </p>
              <p className="mt-auto truncate text-[12px] font-semibold leading-4 text-foreground">
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

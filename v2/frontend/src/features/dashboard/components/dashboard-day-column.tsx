import { Check, Plus, RotateCcw, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { DashboardDayColumn as DashboardDayColumnType } from '@/features/dashboard/types/dashboard';

interface DashboardDayColumnProps {
  day: DashboardDayColumnType;
  onAddPlannedActivity?: (dayUtc: string) => void;
  onMarkPlannedDone?: (activity: DashboardDayColumnType['planned_activities'][number], index: number) => void;
  onDeletePlannedActivity?: (activity: DashboardDayColumnType['planned_activities'][number], index: number) => void;
  onDeleteCustomActivity?: (activity: DashboardDayColumnType['actual_activities'][number]) => void;
  onSelectActivity?: (activityId: string) => void;
  addingPlannedActivity?: boolean;
  markingPlannedDone?: boolean;
  deletingPlannedActivity?: boolean;
  deletingCustomActivity?: boolean;
  userTimeZone?: string;
  compactMobile?: boolean;
  undoPlannedActivity?: {
    dayUtc: string;
    lineNo: number;
    slotIndex: number;
    label: string;
  } | null;
  undoVisible?: boolean;
  onUndoPlannedActivity?: () => void;
}

const intensityClasses: Record<string, string> = {
  green: 'border-[rgba(143,155,173,0.58)] bg-[rgba(143,155,173,0.14)]',
  blue: 'border-[rgba(79,179,255,0.58)] bg-[rgba(79,179,255,0.14)]',
  orange: 'border-[rgba(240,166,58,0.6)] bg-[rgba(240,166,58,0.15)]',
  red: 'border-[rgba(239,106,106,0.58)] bg-[rgba(239,106,106,0.14)]',
  purple: 'border-[rgba(139,108,246,0.58)] bg-[rgba(139,108,246,0.14)]',
};

const plannedIntensityClasses: Record<string, string> = {
  green: 'border-[rgba(143,155,173,0.72)] bg-[rgba(143,155,173,0.08)]',
  blue: 'border-[rgba(79,179,255,0.72)] bg-[rgba(79,179,255,0.08)]',
  orange: 'border-[rgba(240,166,58,0.74)] bg-[rgba(240,166,58,0.08)]',
  red: 'border-[rgba(239,106,106,0.72)] bg-[rgba(239,106,106,0.08)]',
  purple: 'border-[rgba(139,108,246,0.72)] bg-[rgba(139,108,246,0.08)]',
};

const customBorderAccentClasses: Record<string, string> = {
  green: 'border-[rgba(143,155,173,0.74)] outline-[rgba(203,213,225,0.28)]',
  blue: 'border-[rgba(79,179,255,0.76)] outline-[rgba(125,211,252,0.3)]',
  orange: 'border-[rgba(240,166,58,0.76)] outline-[rgba(252,211,77,0.3)]',
  red: 'border-[rgba(239,106,106,0.74)] outline-[rgba(253,164,175,0.3)]',
  purple: 'border-[rgba(139,108,246,0.74)] outline-[rgba(196,181,253,0.3)]',
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
    return 'Tready';
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

export function DashboardDayColumn({
  day,
  onAddPlannedActivity,
  onMarkPlannedDone,
  onDeletePlannedActivity,
  onDeleteCustomActivity,
  onSelectActivity,
  addingPlannedActivity,
  markingPlannedDone,
  deletingPlannedActivity,
  deletingCustomActivity,
  userTimeZone,
  compactMobile = false,
  undoPlannedActivity,
  undoVisible = false,
  onUndoPlannedActivity,
}: DashboardDayColumnProps): JSX.Element {
  const activityCount = day.actual_activities.length + day.planned_activities.length;
  const shouldScrollActivities = activityCount > 3;
  const plannedCards: Array<
    | { type: 'activity'; activity: DashboardDayColumnType['planned_activities'][number]; index: number }
    | { type: 'undo'; slotIndex: number }
  > = day.planned_activities.map((activity, index) => ({ type: 'activity', activity, index }));

  if (undoPlannedActivity && undoPlannedActivity.dayUtc === day.day_utc) {
    const insertionIndex = Math.max(0, Math.min(undoPlannedActivity.slotIndex, plannedCards.length));
    plannedCards.splice(insertionIndex, 0, { type: 'undo', slotIndex: undoPlannedActivity.slotIndex });
  }

  return (
    <Card
      className={cn(
        'rounded-xl border-border/80 bg-card/75 shadow-sm',
        compactMobile ? 'w-[240px] shrink-0 min-h-[340px]' : 'sm:min-h-[340px] lg:h-[430px]',
        day.is_today ? 'border-primary/70' : undefined,
      )}
    >
      <CardContent className={cn('flex h-full flex-col', compactMobile ? 'gap-1.5 p-2' : 'gap-2 p-2.5')}>
        <div className="space-y-1">
          <div className="flex min-h-[24px] items-center">
            <p
              className={cn(
                compactMobile ? 'text-[12px] font-semibold leading-4' : 'text-[13px] font-semibold leading-5',
                day.is_today ? 'text-primary' : 'text-foreground',
              )}
            >
              {day.day_label}
            </p>
            {!day.is_past ? (
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto h-6 w-6 rounded-full text-muted-foreground hover:text-foreground"
                onClick={() => onAddPlannedActivity?.(day.day_utc)}
                disabled={addingPlannedActivity}
                aria-label={`Add planned activity for ${day.day_label}`}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            ) : null}
          </div>
          <div
            className={cn(
              'space-y-0.5 text-muted-foreground',
              compactMobile ? 'min-h-[40px] text-[11px] leading-[1.25]' : 'min-h-[50px] text-[12px] leading-[1.3]',
            )}
          >
            {fmtMeta(day).map((line) => (
              <p key={line} className="truncate">
                {line}
              </p>
            ))}
          </div>
        </div>

        <Separator className="bg-border/70" />

        <div
          className={cn(
            'flex-1 space-y-2',
            shouldScrollActivities
              ? 'overflow-visible sm:overflow-y-auto sm:pr-1 sm:[scrollbar-width:none] sm:[-ms-overflow-style:none] sm:[&::-webkit-scrollbar]:hidden'
              : 'overflow-visible',
          )}
        >
          {day.actual_activities.map((activity) => (
            (() => {
              const timeLabel = activity.is_custom ? '' : deriveCompactTimeLabel(activity, userTimeZone);
              return (
                <div
                  key={activity.activity_id}
                  className={cn(
                    'relative flex cursor-pointer flex-col overflow-hidden rounded-lg border transition-colors hover:bg-white/5',
                    compactMobile ? 'h-[88px] p-1.5 text-[11px]' : 'h-[102px] p-2 text-[12px]',
                    activity.is_custom ? 'border-2 border-dashed outline outline-1 outline-offset-[-3px] outline-dotted' : undefined,
                    intensityClasses[activity.intensity] ?? 'border-border/70 bg-muted/20',
                    activity.is_custom ? customBorderAccentClasses[activity.intensity] : undefined,
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
                  {activity.is_custom ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute -right-0.5 -top-0.5 h-4 w-4 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteCustomActivity?.(activity);
                      }}
                      disabled={deletingCustomActivity}
                      aria-label="Delete custom activity"
                    >
                      <X className="h-1.75 w-1.75" />
                    </Button>
                  ) : null}
                  <p className={cn('truncate font-semibold text-foreground', compactMobile ? 'text-[12px] leading-4' : 'text-[13px] leading-5')}>
                    {formatActivityTitle(activity.sport)}
                    {activity.is_custom ? '(C)' : ''}
                    {!activity.is_custom && timeLabel ? ` ${timeLabel}` : ''}
                  </p>
                  <p className={cn('mt-0.5 line-clamp-2 font-medium tracking-[0.01em] text-slate-300/92', compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]')}>
                    {compactLine([activity.duration_label, activity.distance_label])}
                  </p>
                  <p className={cn('line-clamp-2 font-medium tracking-[0.01em] text-slate-300/92', compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]')}>
                    {compactLine([activity.pace_label, `IF ${Math.round(activity.if_pct)}%`])}
                  </p>
                  <p className={cn('mt-auto truncate font-semibold text-foreground/95', compactMobile ? 'text-[10px] leading-4' : 'text-[11px] leading-4')}>
                    TSS {Math.round(activity.tss)} · rTSS {Math.round(activity.rtss)}
                  </p>
                </div>
              );
            })()
          ))}

          {plannedCards.map((item) =>
            item.type === 'undo' ? (
              <div
                key={`undo-${day.day_utc}-${undoPlannedActivity?.lineNo ?? item.slotIndex}`}
                className={cn(
                  'relative flex flex-col overflow-hidden rounded-lg border-2 border-dashed border-sky-300/35 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),rgba(15,23,42,0.45)] transition-all duration-200',
                  compactMobile ? 'h-[88px] px-2 pb-2 pt-1.5 text-[11px]' : 'h-[102px] px-2.5 pb-2.5 pt-2 text-[12px]',
                  undoVisible ? 'opacity-100' : 'opacity-85',
                )}
              >
                <p className={cn('font-semibold text-sky-100', compactMobile ? 'text-[12px] leading-4' : 'text-[13px] leading-5')}>
                  {undoPlannedActivity?.label ?? 'Activity removed'}
                </p>
                <p className={cn('mt-1 line-clamp-2 text-slate-300/78', compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]')}>
                  Tap undo to restore this card in place.
                </p>
                <div className="mt-auto">
                  <Button
                    variant="outline"
                    className="h-7 rounded-lg border-sky-300/25 bg-sky-300/8 px-2.5 text-[11px] font-medium text-sky-100 hover:bg-sky-300/14"
                    onClick={onUndoPlannedActivity}
                  >
                    <RotateCcw className="mr-1.5 h-3 w-3" />
                    Undo
                  </Button>
                </div>
              </div>
            ) : (
              <div
                key={`${item.activity.day_utc}-${item.activity.line_no}`}
                className={cn(
                  'relative flex cursor-pointer flex-col overflow-hidden rounded-lg border-2 border-dashed transition-colors hover:bg-white/5',
                  compactMobile ? 'h-[88px] px-2 pb-2 pt-1.5 text-[11px]' : 'h-[102px] px-2.5 pb-2.5 pt-2 text-[12px]',
                  plannedIntensityClasses[item.activity.intensity] ?? 'border-border/70 bg-muted/20',
                )}
                onClick={() => onSelectActivity?.(item.activity.activity_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    onSelectActivity?.(item.activity.activity_id);
                  }
                }}
              >
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute -left-0.5 -top-0.5 h-4 w-4 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                  onClick={(event) => {
                    event.stopPropagation();
                    onMarkPlannedDone?.(item.activity, item.index);
                  }}
                  disabled={markingPlannedDone}
                  aria-label="Mark planned activity as done"
                >
                  <Check className="h-1.75 w-1.75" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute -right-0.5 -top-0.5 h-4 w-4 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                  onClick={(event) => {
                    event.stopPropagation();
                    onDeletePlannedActivity?.(item.activity, item.index);
                  }}
                  disabled={deletingPlannedActivity}
                  aria-label="Delete planned activity"
                >
                  <X className="h-1.75 w-1.75" />
                </Button>
                <p className={cn('truncate font-semibold text-foreground', compactMobile ? 'text-[12px] leading-4' : 'text-[13px] leading-5')}>
                  {formatActivityTitle(item.activity.activity)} <span className="text-muted-foreground">(P)</span>
                </p>
                <p className={cn('line-clamp-2 font-medium tracking-[0.01em] text-slate-300/92', compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]')}>
                  {compactLine([item.activity.duration_label, `${Math.round(item.activity.distance_eqv_km)} kmeq`])}
                </p>
                <p className={cn('line-clamp-2 font-medium tracking-[0.01em] text-slate-300/92', compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]')}>
                  {compactLine([item.activity.pace_label, `IF ${Math.round(item.activity.if_pct)}%`])}
                </p>
                <p className={cn('mt-auto truncate font-semibold tracking-[0.02em] text-foreground/95', compactMobile ? 'text-[10px] leading-4' : 'text-[11px] leading-4')}>
                  TSS {Math.round(item.activity.tss)} · rTSS {Math.round(item.activity.rtss)}
                </p>
              </div>
            ),
          )}

          {day.actual_activities.length === 0 && day.planned_activities.length === 0 && day.is_past ? (
            <div className={cn('rounded-lg border border-border/70 bg-muted/25 p-2 text-center text-muted-foreground', compactMobile ? 'text-[11px]' : 'text-[12px]')}>
              <p className="font-semibold text-foreground">Rest Day</p>
              <p>Rest is part of training.</p>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

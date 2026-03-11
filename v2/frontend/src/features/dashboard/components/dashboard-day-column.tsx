import { Activity, Check, Clock3, Gauge, HeartPulse, Plus, Route, RotateCcw, X } from 'lucide-react';

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
  onDeleteCustomActivity?: (activity: DashboardDayColumnType['actual_activities'][number], index: number) => void;
  onSelectActivity?: (activityId: string) => void;
  addingPlannedActivity?: boolean;
  markingPlannedDone?: boolean;
  deletingPlannedActivity?: boolean;
  deletingCustomActivity?: boolean;
  userTimeZone?: string;
  compactMobile?: boolean;
  mobileFullWidth?: boolean;
  undoActivity?: {
    dayUtc: string;
    lineNo: number;
    slotIndex: number;
    label: string;
    lane: 'planned' | 'actual';
  } | null;
  undoVisible?: boolean;
  onUndoActivity?: () => void;
}

const intensityClasses: Record<string, string> = {
  green: 'border-[rgba(205,213,225,0.5)] bg-[linear-gradient(180deg,rgba(203,213,225,0.16),rgba(15,23,42,0.24))]',
  blue: 'border-[rgba(79,179,255,0.48)] bg-[linear-gradient(180deg,rgba(79,179,255,0.14),rgba(15,23,42,0.24))]',
  orange: 'border-[rgba(240,166,58,0.5)] bg-[linear-gradient(180deg,rgba(240,166,58,0.15),rgba(15,23,42,0.24))]',
  red: 'border-[rgba(239,106,106,0.48)] bg-[linear-gradient(180deg,rgba(239,106,106,0.14),rgba(15,23,42,0.24))]',
  purple: 'border-[rgba(139,108,246,0.48)] bg-[linear-gradient(180deg,rgba(139,108,246,0.14),rgba(15,23,42,0.24))]',
};

const plannedIntensityClasses: Record<string, string> = {
  green: 'border-[rgba(205,213,225,0.66)] bg-[linear-gradient(180deg,rgba(203,213,225,0.12),rgba(15,23,42,0.2))]',
  blue: 'border-[rgba(79,179,255,0.6)] bg-[linear-gradient(180deg,rgba(79,179,255,0.1),rgba(15,23,42,0.2))]',
  orange: 'border-[rgba(240,166,58,0.62)] bg-[linear-gradient(180deg,rgba(240,166,58,0.1),rgba(15,23,42,0.2))]',
  red: 'border-[rgba(239,106,106,0.6)] bg-[linear-gradient(180deg,rgba(239,106,106,0.1),rgba(15,23,42,0.2))]',
  purple: 'border-[rgba(139,108,246,0.6)] bg-[linear-gradient(180deg,rgba(139,108,246,0.1),rgba(15,23,42,0.2))]',
};

const customBorderAccentClasses: Record<string, string> = {
  green: 'border-[rgba(205,213,225,0.92)] outline-[rgba(241,245,249,0.38)]',
  blue: 'border-[rgba(79,179,255,0.76)] outline-[rgba(125,211,252,0.3)]',
  orange: 'border-[rgba(240,166,58,0.76)] outline-[rgba(252,211,77,0.3)]',
  red: 'border-[rgba(239,106,106,0.74)] outline-[rgba(253,164,175,0.3)]',
  purple: 'border-[rgba(139,108,246,0.74)] outline-[rgba(196,181,253,0.3)]',
};

function fmtMeta(day: DashboardDayColumnType): Array<{ key: string; label: string; value: string; tone: string }> {
  const parts: Array<{ key: string; label: string; value: string; tone: string }> = [];
  parts.push({
    key: 'distance',
    label: 'Dist',
    value: `${Math.round(day.meta.distance_eqv_km || 0)} km`,
    tone: 'text-emerald-200/88',
  });
  const hasFatigueExpected = Boolean(day.meta.show_fatigue_expected && day.meta.fatigue_expected !== null);
  if (hasFatigueExpected) {
    parts.push({
      key: 'fatg',
      label: 'fatg',
      value: `${Math.round(day.meta.fatigue_expected ?? 0)}`,
      tone: 'text-rose-200/88',
    });
  } else if (day.meta.fatigue !== null) {
    parts.push({
      key: 'fatg',
      label: 'fatg',
      value: `${Math.round(day.meta.fatigue)}`,
      tone: 'text-rose-200/88',
    });
  }
  return parts;
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

function isRunningLikeSport(raw: string): boolean {
  const normalized = String(raw || '').trim().toLowerCase();
  return (
    normalized.includes('run') ||
    normalized.includes('treadmill') ||
    normalized.includes('track')
  );
}

function compactLine(parts: Array<string | null | undefined>): string {
  return parts
    .map((part) => String(part || '').trim())
    .filter(Boolean)
    .map((part) => part.replace(/\/km\b/gi, '').replace(/km\s*eqv\.?/gi, 'km'))
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

function activityTypeLabel(isCustom: boolean): string {
  return isCustom ? 'Custom' : 'Done';
}

function metricPillLabel(value: string | null | undefined): string | null {
  const cleaned = String(value || '').trim();
  return cleaned ? cleaned : null;
}

function shortWeekday(dayUtc: string, fallback: string): string {
  const parsed = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return fallback;
  return new Intl.DateTimeFormat('en-US', { weekday: 'short' }).format(parsed);
}

function formatTssLabel(tss: number, rtss: number, showBoth: boolean, runningLike = false): string {
  const roundedTss = Math.round(tss);
  const roundedRtss = Math.round(rtss);
  if (!showBoth) return `TSS ${roundedTss}`;
  return runningLike ? `rTSS ${roundedRtss}(${roundedTss})` : `TSS ${roundedTss}(${roundedRtss})`;
}

function dayNumber(dayUtc: string): string {
  const parsed = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return '--';
  return new Intl.DateTimeFormat('en-US', { day: '2-digit' }).format(parsed);
}

function MetricRow({
  icon,
  text,
  compactMobile = false,
}: {
  icon: JSX.Element;
  text: string;
  compactMobile?: boolean;
}): JSX.Element | null {
  const cleaned = text.trim();
  if (!cleaned) return null;
  return (
    <p
      className={cn(
        'inline-flex min-w-0 items-center gap-1 font-medium tracking-[0.01em] text-slate-300/92',
        compactMobile ? 'text-[9.5px] leading-[1.18]' : 'text-[10.5px] leading-[1.24]',
      )}
    >
      {icon}
      <span className="truncate">{cleaned}</span>
    </p>
  );
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
  mobileFullWidth = false,
  undoActivity,
  undoVisible = false,
  onUndoActivity,
}: DashboardDayColumnProps): JSX.Element {
  const activityCount = day.actual_activities.length + day.planned_activities.length;
  const metaItems = fmtMeta(day);
  const shouldScrollActivities = activityCount > 3;
  const actualCards: Array<
    | { type: 'activity'; activity: DashboardDayColumnType['actual_activities'][number]; index: number }
    | { type: 'undo'; slotIndex: number }
  > = day.actual_activities.map((activity, index) => ({ type: 'activity', activity, index }));
  const plannedCards: Array<
    | { type: 'activity'; activity: DashboardDayColumnType['planned_activities'][number]; index: number }
    | { type: 'undo'; slotIndex: number }
  > = day.planned_activities.map((activity, index) => ({ type: 'activity', activity, index }));

  if (undoActivity && undoActivity.dayUtc === day.day_utc) {
    const laneCards = undoActivity.lane === 'actual' ? actualCards : plannedCards;
    const insertionIndex = Math.max(0, Math.min(undoActivity.slotIndex, laneCards.length));
    laneCards.splice(insertionIndex, 0, { type: 'undo', slotIndex: undoActivity.slotIndex });
  }

  const cardClassName = cn(
    'overflow-hidden rounded-[1.25rem] border border-[rgba(51,65,85,0.72)] bg-[linear-gradient(180deg,rgba(10,18,33,0.99),rgba(6,12,23,0.98))] shadow-[0_20px_44px_rgba(2,6,23,0.36),inset_0_1px_0_rgba(255,255,255,0.05),inset_0_0_0_1px_rgba(15,23,42,0.75)]',
    compactMobile
      ? mobileFullWidth
        ? 'w-full min-w-0'
        : 'w-[240px] shrink-0 min-h-[340px]'
      : 'sm:min-h-[340px] lg:h-[430px]',
    day.is_today && !compactMobile
      ? 'border-[rgba(79,70,229,0.58)] shadow-[0_24px_50px_rgba(2,6,23,0.44),inset_0_1px_0_rgba(255,255,255,0.08),inset_0_0_0_1px_rgba(129,140,248,0.18)]'
      : undefined,
  );

  const contentClassName = cn(
    'relative flex h-full flex-col',
    compactMobile && mobileFullWidth ? 'gap-1.5 p-2' : 'gap-2 p-2.5',
  );

  return (
    <Card className={cardClassName}>
      <CardContent className={contentClassName}>
        <div className="pointer-events-none absolute inset-x-0 top-0 h-16 bg-[linear-gradient(180deg,rgba(96,165,250,0.07),rgba(168,85,247,0.05)_38%,transparent)]" />
        <div className="relative rounded-[1rem] border border-[rgba(71,85,105,0.55)] bg-[linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.02))] px-2 py-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.06),inset_0_0_0_1px_rgba(15,23,42,0.42),0_10px_24px_rgba(2,6,23,0.18)] backdrop-blur-sm">
          <div className="pointer-events-none absolute inset-x-4 top-0 h-px bg-gradient-to-r from-transparent via-[rgba(125,211,252,0.22)] to-transparent" />
          <div className="pointer-events-none absolute inset-y-3 left-0 w-px bg-gradient-to-b from-transparent via-[rgba(129,140,248,0.14)] to-transparent" />
          <div className="pointer-events-none absolute inset-y-3 right-0 w-px bg-gradient-to-b from-transparent via-[rgba(192,132,252,0.12)] to-transparent" />
          <div className="space-y-0.5">
            <div className="flex min-h-[24px] items-center gap-1.5">
              <div className="min-w-0">
                <div className="inline-flex items-baseline gap-1.5">
                  <p
                    className={cn(
                      compactMobile ? 'text-[15px] font-semibold leading-4' : 'text-[17px] font-semibold leading-5',
                      day.is_today ? 'text-primary' : 'text-foreground',
                    )}
                  >
                    {dayNumber(day.day_utc)}
                  </p>
                  <p
                    className={cn(
                      compactMobile ? 'text-[11px] font-medium leading-4' : 'text-[11.5px] font-medium leading-5',
                      'uppercase tracking-[0.14em] text-slate-400/88',
                    )}
                  >
                    {shortWeekday(day.day_utc, day.day_label)}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="ml-auto h-6 w-6 rounded-full border border-white/8 bg-white/[0.025] text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] hover:bg-white/[0.05] hover:text-foreground"
                onClick={() => onAddPlannedActivity?.(day.day_utc)}
                disabled={addingPlannedActivity}
                aria-label={`Add activity for ${shortWeekday(day.day_utc, day.day_label)}`}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
            </div>
            <div className="flex items-center gap-2 overflow-hidden text-[10px] leading-4">
              {metaItems.map((item) => (
                <div key={item.key} className={cn('inline-flex min-w-0 items-center gap-1', item.tone)}>
                  {item.key === 'distance' ? <Route className="h-3 w-3 shrink-0" /> : <HeartPulse className="h-3 w-3 shrink-0" />}
                  <span className="truncate text-slate-300/88">
                    {item.value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <Separator className={cn('bg-gradient-to-r from-transparent via-white/8 to-transparent', compactMobile && mobileFullWidth ? 'opacity-60' : undefined)} />

        <div
          className={cn(
            'flex-1 space-y-2',
            shouldScrollActivities
              ? compactMobile
                ? 'overflow-visible'
                : 'overflow-visible sm:overflow-y-auto sm:pr-1 sm:[scrollbar-width:none] sm:[-ms-overflow-style:none] sm:[&::-webkit-scrollbar]:hidden'
              : 'overflow-visible',
          )}
        >
          {actualCards.map((item) =>
            item.type === 'undo' ? (
              <div
                key={`undo-actual-${day.day_utc}-${undoActivity?.lineNo ?? item.slotIndex}`}
                className={cn(
                  'relative flex flex-col overflow-hidden rounded-lg border-2 border-dashed border-sky-300/35 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),rgba(15,23,42,0.45)] transition-all duration-200',
                  compactMobile ? 'h-[88px] px-2 pb-2 pt-1.5 text-[11px]' : 'h-[102px] px-2.5 pb-2.5 pt-2 text-[12px]',
                  undoVisible ? 'opacity-100' : 'opacity-85',
                )}
              >
                <p className={cn('font-semibold text-sky-100', compactMobile ? 'text-[12px] leading-4' : 'text-[13px] leading-5')}>
                  {undoActivity?.label ?? 'Activity removed'}
                </p>
                <div className="mt-auto">
                  <Button
                    variant="outline"
                    className="h-7 rounded-lg border-sky-300/25 bg-sky-300/8 px-2.5 text-[11px] font-medium text-sky-100 hover:bg-sky-300/14"
                    onClick={onUndoActivity}
                  >
                    <RotateCcw className="mr-1.5 h-3 w-3" />
                    Undo
                  </Button>
                </div>
              </div>
            ) : (
            (() => {
              const activity = item.activity;
              const timeLabel = activity.is_custom ? '' : deriveCompactTimeLabel(activity, userTimeZone);
              if (compactMobile && mobileFullWidth) {
                const metricPills = [
                  metricPillLabel(activity.duration_label),
                  metricPillLabel(activity.distance_label),
                  metricPillLabel(activity.pace_label),
                  metricPillLabel(`TSS ${Math.round(activity.tss)}`),
                  metricPillLabel(`rTSS ${Math.round(activity.rtss)}`),
                  activity.vdot != null ? metricPillLabel(`VDOT ${Math.round(activity.vdot)}`) : null,
                ].filter((pill): pill is string => Boolean(pill));
                return (
                  <div
                    key={activity.activity_id}
                    className={cn(
                      'relative overflow-hidden rounded-[1rem] border shadow-[0_10px_22px_rgba(2,6,23,0.18)]',
                      'px-2 py-1.5',
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
                    <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),transparent)]" />
                    {activity.is_custom ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="absolute right-1.5 top-1.5 h-5 w-5 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                        onClick={(event) => {
                          event.stopPropagation();
                          onDeleteCustomActivity?.(activity, item.index);
                        }}
                        disabled={deletingCustomActivity}
                        aria-label="Delete custom activity"
                      >
                        <X className="h-2.5 w-2.5" />
                      </Button>
                    ) : null}
                    <div className="flex items-start gap-2 pr-6">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[12px] font-semibold leading-4 text-foreground">
                          {formatActivityTitle(activity.sport)}
                          {timeLabel ? ` ${timeLabel}` : ''}
                        </p>
                        <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-slate-400/90">
                          {activityTypeLabel(Boolean(activity.is_custom))}
                        </p>
                      </div>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {metricPills.slice(0, 5).map((pill) => (
                        <span
                          key={`${activity.activity_id}-${pill}`}
                          className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9.5px] font-medium leading-none text-slate-300/92"
                        >
                          {pill}
                        </span>
                      ))}
                      <span className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9.5px] font-medium leading-none text-slate-300/92">
                        IF {Math.round(activity.if_pct)}%
                      </span>
                    </div>
                  </div>
                );
              }
              const runningLike = isRunningLikeSport(activity.sport);
              return (
                <div
                  key={activity.activity_id}
                  className={cn(
                    'relative flex cursor-pointer flex-col overflow-hidden rounded-[1rem] border shadow-[0_10px_22px_rgba(2,6,23,0.18)] transition-all duration-200 hover:-translate-y-[1px] hover:bg-white/[0.045] hover:shadow-[0_16px_28px_rgba(2,6,23,0.24)]',
                    compactMobile ? 'h-[82px] p-1.5 text-[11px]' : 'h-[94px] p-2 text-[12px]',
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
                  <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),transparent)]" />
                  {activity.is_custom ? (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="absolute -right-0.5 -top-0.5 h-4 w-4 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeleteCustomActivity?.(activity, item.index);
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
                  <div className={compactMobile ? 'mt-1 space-y-0.5' : 'mt-1.5 space-y-0.5'}>
                    <MetricRow
                      compactMobile={compactMobile}
                      icon={<Clock3 className="h-2.5 w-2.5 shrink-0 text-cyan-300/80" />}
                      text={compactLine([activity.duration_label, activity.distance_label])}
                    />
                    <MetricRow
                      compactMobile={compactMobile}
                      icon={<Gauge className="h-2.5 w-2.5 shrink-0 text-amber-300/80" />}
                      text={compactLine([activity.pace_label, `IF ${Math.round(activity.if_pct)}%`, activity.vdot != null ? `VDOT ${Math.round(activity.vdot)}` : null])}
                    />
                  </div>
                  <p className={cn('mt-auto inline-flex min-w-0 items-center gap-1 truncate font-semibold text-foreground/95', compactMobile ? 'text-[10px] leading-4' : 'text-[11px] leading-4')}>
                    <Activity className="h-2.5 w-2.5 shrink-0 text-blue-300/80" />
                    <span className="truncate">
                      {formatTssLabel(activity.tss, activity.rtss, !activity.is_custom && runningLike, runningLike)}
                    </span>
                  </p>
                </div>
              );
            })()
          ))}

          {plannedCards.map((item) =>
            item.type === 'undo' ? (
              <div
                key={`undo-planned-${day.day_utc}-${undoActivity?.lineNo ?? item.slotIndex}`}
                className={cn(
                  'relative flex flex-col overflow-hidden rounded-lg border-2 border-dashed border-sky-300/35 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),rgba(15,23,42,0.45)] transition-all duration-200',
                  compactMobile ? 'h-[88px] px-2 pb-2 pt-1.5 text-[11px]' : 'h-[102px] px-2.5 pb-2.5 pt-2 text-[12px]',
                  undoVisible ? 'opacity-100' : 'opacity-85',
                )}
              >
                <p className={cn('font-semibold text-sky-100', compactMobile ? 'text-[12px] leading-4' : 'text-[13px] leading-5')}>
                  {undoActivity?.label ?? 'Activity removed'}
                </p>
                <div className="mt-auto">
                  <Button
                    variant="outline"
                    className="h-7 rounded-lg border-sky-300/25 bg-sky-300/8 px-2.5 text-[11px] font-medium text-sky-100 hover:bg-sky-300/14"
                    onClick={onUndoActivity}
                  >
                    <RotateCcw className="mr-1.5 h-3 w-3" />
                    Undo
                  </Button>
                </div>
              </div>
            ) : (
              compactMobile && mobileFullWidth ? (
                (() => {
                  const metricPills = [
                    metricPillLabel(item.activity.duration_label),
                    metricPillLabel(`${Math.round(item.activity.distance_eqv_km)} km`),
                    metricPillLabel(item.activity.pace_label),
                    metricPillLabel(`TSS ${Math.round(item.activity.tss)}`),
                    metricPillLabel(`rTSS ${Math.round(item.activity.rtss)}`),
                    metricPillLabel(`IF ${Math.round(item.activity.if_pct)}%`),
                  ].filter((pill): pill is string => Boolean(pill));
                  return (
                <div
                  key={`${item.activity.day_utc}-${item.activity.line_no}`}
                  className={cn(
                    'relative overflow-hidden rounded-[1rem] border-2 border-dashed shadow-[0_10px_22px_rgba(2,6,23,0.18)]',
                    'px-2 py-1.5',
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
                  <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),transparent)]" />
                  <div className="absolute right-1.5 top-1.5 flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                      onClick={(event) => {
                        event.stopPropagation();
                        onMarkPlannedDone?.(item.activity, item.index);
                      }}
                      disabled={markingPlannedDone}
                      aria-label="Mark planned activity as done"
                    >
                      <Check className="h-2.5 w-2.5" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 shrink-0 rounded-full border border-white/10 bg-[linear-gradient(180deg,rgba(51,65,85,0.38),rgba(15,23,42,0.26))] text-slate-300 shadow-[0_3px_8px_rgba(15,23,42,0.16)] backdrop-blur-sm transition-colors hover:border-white/18 hover:bg-[linear-gradient(180deg,rgba(71,85,105,0.42),rgba(30,41,59,0.3))] hover:text-white"
                      onClick={(event) => {
                        event.stopPropagation();
                        onDeletePlannedActivity?.(item.activity, item.index);
                      }}
                      disabled={deletingPlannedActivity}
                      aria-label="Delete planned activity"
                    >
                      <X className="h-2.5 w-2.5" />
                    </Button>
                  </div>
                  <div className="min-w-0 pr-12">
                    <p className="truncate text-[12px] font-semibold leading-4 text-foreground">
                      {formatActivityTitle(item.activity.activity)}
                    </p>
                    <p className="mt-0.5 text-[10px] font-medium uppercase tracking-[0.08em] text-slate-400/90">
                      Planned
                    </p>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {metricPills.map((pill) => (
                      <span
                        key={`${item.activity.day_utc}-${item.activity.line_no}-${pill}`}
                        className="rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[9.5px] font-medium leading-none text-slate-300/92"
                      >
                        {pill}
                      </span>
                    ))}
                  </div>
                </div>
                  );
                })()
              ) : (
              <div
                key={`${item.activity.day_utc}-${item.activity.line_no}`}
                className={cn(
                  'relative flex cursor-pointer flex-col overflow-hidden rounded-[1rem] border-2 border-dashed shadow-[0_10px_22px_rgba(2,6,23,0.18)] transition-all duration-200 hover:-translate-y-[1px] hover:bg-white/[0.045] hover:shadow-[0_16px_28px_rgba(2,6,23,0.24)]',
                  compactMobile ? 'h-[82px] px-2 pb-1.5 pt-1.5 text-[11px]' : 'h-[94px] px-2.5 pb-2 pt-2 text-[12px]',
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
                <div className="pointer-events-none absolute inset-x-0 top-0 h-6 bg-[linear-gradient(180deg,rgba(255,255,255,0.04),transparent)]" />
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
                <div className={compactMobile ? 'mt-1 space-y-0.5' : 'mt-1.5 space-y-0.5'}>
                  <MetricRow
                    compactMobile={compactMobile}
                    icon={<Route className="h-2.5 w-2.5 shrink-0 text-emerald-300/80" />}
                    text={compactLine([item.activity.duration_label, `${Math.round(item.activity.distance_eqv_km)} km`])}
                  />
                  <MetricRow
                    compactMobile={compactMobile}
                    icon={<Gauge className="h-2.5 w-2.5 shrink-0 text-amber-300/80" />}
                    text={compactLine([item.activity.pace_label, `IF ${Math.round(item.activity.if_pct)}%`])}
                  />
                </div>
                <p className={cn('mt-auto inline-flex min-w-0 items-center gap-1 truncate font-semibold tracking-[0.02em] text-foreground/95', compactMobile ? 'text-[10px] leading-4' : 'text-[11px] leading-4')}>
                  <Activity className="h-2.5 w-2.5 shrink-0 text-blue-300/80" />
                  <span className="truncate">{formatTssLabel(item.activity.tss, item.activity.rtss, false)}</span>
                </p>
              </div>
              )
            ),
          )}

          {day.actual_activities.length === 0 && day.planned_activities.length === 0 && day.is_past ? (
            <div className={cn('rounded-[0.95rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-2 text-center text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]', compactMobile ? 'text-[11px]' : 'text-[12px]')}>
              <p className="font-semibold text-foreground">Rest Day</p>
              <p>Rest is part of training.</p>
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

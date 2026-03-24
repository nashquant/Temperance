import { Activity, Check, Clock3, Gauge, HeartPulse, Plus, Route, RotateCcw, Zap, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';
import type { DashboardDayColumn as DashboardDayColumnType } from '@/features/dashboard/types/dashboard';
import { normalizeCompactDurationLabel } from '@/features/dashboard/utils/format-duration';

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
  green:
    'border-[rgba(186,198,212,0.2)] bg-[linear-gradient(180deg,rgba(31,37,45,0.985),rgba(14,18,25,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.24)]',
  blue:
    'border-[rgba(125,146,173,0.2)] bg-[linear-gradient(180deg,rgba(26,32,42,0.985),rgba(10,14,22,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.24)]',
  orange:
    'border-[rgba(157,135,109,0.22)] bg-[linear-gradient(180deg,rgba(42,34,29,0.985),rgba(18,14,13,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.24)]',
  red:
    'border-[rgba(155,118,123,0.22)] bg-[linear-gradient(180deg,rgba(43,30,34,0.985),rgba(18,12,15,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.24)]',
  purple:
    'border-[rgba(131,127,177,0.2)] bg-[linear-gradient(180deg,rgba(34,29,51,0.985),rgba(12,13,23,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.24)]',
};

const plannedIntensityClasses: Record<string, string> = {
  green:
    'border-[rgba(191,201,214,0.22)] bg-[linear-gradient(180deg,rgba(34,40,48,0.985),rgba(15,19,27,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.22)]',
  blue:
    'border-[rgba(130,150,177,0.22)] bg-[linear-gradient(180deg,rgba(29,36,46,0.985),rgba(11,15,24,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.22)]',
  orange:
    'border-[rgba(157,136,110,0.22)] bg-[linear-gradient(180deg,rgba(45,37,32,0.985),rgba(19,16,15,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.22)]',
  red:
    'border-[rgba(157,121,126,0.22)] bg-[linear-gradient(180deg,rgba(45,32,35,0.985),rgba(18,13,16,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.22)]',
  purple:
    'border-[rgba(135,130,178,0.22)] bg-[linear-gradient(180deg,rgba(36,31,53,0.985),rgba(13,14,24,0.99))] shadow-[0_12px_24px_rgba(2,6,23,0.22)]',
};

const customBorderAccentClasses: Record<string, string> = {
  green: 'border-[rgba(221,229,238,0.72)] ring-1 ring-inset ring-white/10',
  blue: 'border-[rgba(120,198,255,0.72)] ring-1 ring-inset ring-sky-200/14',
  orange: 'border-[rgba(245,186,95,0.72)] ring-1 ring-inset ring-amber-200/14',
  red: 'border-[rgba(246,135,135,0.72)] ring-1 ring-inset ring-rose-200/14',
  purple: 'border-[rgba(168,139,250,0.72)] ring-1 ring-inset ring-violet-200/14',
};

type DayMetaItem = {
  key: string;
  icon: 'distance' | 'fitness' | 'fatigue';
  value: string;
};

function fmtMeta(day: DashboardDayColumnType): DayMetaItem[] {
  const items: DayMetaItem[] = [
    {
      key: 'distance',
      icon: 'distance',
      value: `${Math.round(day.meta.distance_eqv_km || 0)}km`,
    },
  ];

  const fitnessValue = day.meta.show_fatigue_expected && day.meta.fitness_expected !== null
    ? day.meta.fitness_expected
    : day.meta.fitness;
  if (fitnessValue !== null) {
    items.push({
      key: 'fitness',
      icon: 'fitness',
      value: `${Math.round(fitnessValue)}`,
    });
  }

  const fatigueValue = day.meta.show_fatigue_expected && day.meta.fatigue_expected !== null
    ? day.meta.fatigue_expected
    : day.meta.fatigue;
  if (fatigueValue !== null) {
    items.push({
      key: 'fatigue',
      icon: 'fatigue',
      value: `${Math.round(fatigueValue)}`,
    });
  }

  return items;
}

function formatActivityTitle(raw: string): string {
  const cleaned = String(raw || '').trim();
  if (!cleaned) return 'Activity';

  const normalized = cleaned.toLowerCase();
  if (normalized.includes('strength')) return 'Lift';
  if (normalized.includes('swim')) return 'Swim';
  if (normalized.includes('cycl')) return 'Bike';
  if (normalized.includes('ellipt')) return 'Ellip';
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

function compactDistanceLabel(label: string | null | undefined): string {
  return String(label || '').trim().replace(/\/km\b/gi, '').replace(/km\s*eqv\.?/gi, 'km');
}

function formatEquivalentDistance(distanceEqvKm: number, runningLike: boolean): string {
  return `${Math.round(distanceEqvKm)} ${runningLike ? 'km' : "km'"}`;
}

function compactPaceLabel(label: string | null | undefined): string {
  const cleaned = String(label || '').trim().replace(/\/km\b/gi, '');
  return cleaned.replace(/(\d{1,2}):(\d{2})/, "$1'$2''");
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

function activityTypeLabel(isCustom: boolean): string | null {
  return isCustom ? 'Custom' : null;
}

function metricPillLabel(value: string | null | undefined): string | null {
  const cleaned = String(value || '').trim();
  return cleaned ? cleaned : null;
}

function formatIfPctLabel(ifPct: number): string {
  return `${Math.round(ifPct)}%`;
}

function formatVdotLabel(vdot: number): string {
  return `${Math.round(vdot)}v.`;
}

type MetricBadgeTone = 'duration' | 'distance' | 'pace' | 'load' | 'if' | 'vdot';

interface MetricBadgeItem {
  tone: MetricBadgeTone;
  label: string;
}

function metricBadgeIcon(tone: MetricBadgeTone): JSX.Element {
  switch (tone) {
    case 'duration':
      return <Clock3 className="h-2.5 w-2.5 shrink-0 text-cyan-300/80" />;
    case 'distance':
      return <Route className="h-2.5 w-2.5 shrink-0 text-emerald-300/80" />;
    case 'pace':
      return <Gauge className="h-2.5 w-2.5 shrink-0 text-violet-300/80" />;
    case 'load':
      return <Activity className="h-2.5 w-2.5 shrink-0 text-blue-300/80" />;
    case 'if':
      return <Zap className="h-2.5 w-2.5 shrink-0 text-amber-300/80" />;
    case 'vdot':
      return <Gauge className="h-2.5 w-2.5 shrink-0 text-sky-300/80" />;
  }
}

function MetricBadge({ item }: { item: MetricBadgeItem }): JSX.Element {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-white/8 bg-white/[0.04] px-1.5 py-0.5 text-[10px] font-medium leading-none text-slate-300/92">
      {metricBadgeIcon(item.tone)}
      {item.label}
    </span>
  );
}

function formatTssLabel(tss: number, rtss: number, showBoth: boolean, runningLike = false): string {
  const roundedTss = Math.round(tss);
  const roundedRtss = Math.round(rtss);
  if (!showBoth) return `TSS ${roundedTss}`;
  return runningLike ? `rTSS ${roundedRtss}(${roundedTss})` : `TSS ${roundedTss}(${roundedRtss})`;
}

function primaryLoadLabel(tss: number, rtss: number, runningLike: boolean): string {
  return runningLike ? `rTSS ${Math.round(rtss)}` : `TSS ${Math.round(tss)}`;
}

function mobileActivitySectionLabel(day: DashboardDayColumnType): string {
  const count = day.actual_activities.length + day.planned_activities.length;
  if (count === 0 && day.is_past) return 'Rest';
  if (count === 1) return '1 activity';
  return `${count} activities`;
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
        compactMobile ? 'text-[10px] leading-[1.18]' : 'text-[11px] leading-[1.24]',
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
  const desktopMetaItems = metaItems.filter((item) => item.icon === 'fitness' || item.icon === 'fatigue');
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
    'rounded-xl border-border/80 bg-card/75 shadow-sm',
    compactMobile
      ? mobileFullWidth
        ? 'w-full min-w-0'
        : 'w-[240px] shrink-0 min-h-[340px]'
      : 'sm:min-h-[340px] lg:h-[430px]',
    day.is_today ? 'border-primary/70' : undefined,
  );

  const contentClassName = cn(
    'flex h-full flex-col',
    compactMobile ? 'gap-1.5 p-2' : 'gap-2 p-2.5',
  );

  return (
    <Card className={cardClassName}>
      <CardContent className={contentClassName}>
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
            <Button
              variant="ghost"
              size="icon"
              className="ml-auto h-6 w-6 rounded-full text-muted-foreground hover:text-foreground"
              onClick={() => onAddPlannedActivity?.(day.day_utc)}
              disabled={addingPlannedActivity}
              aria-label={`Add activity for ${day.day_label}`}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
          {compactMobile ? (
            <div
              className={cn(
                'flex min-h-[20px] flex-nowrap items-center gap-2 overflow-hidden text-muted-foreground',
                compactMobile ? 'text-[10.5px] leading-[1.2]' : 'text-[11px] leading-[1.25]',
              )}
            >
              {metaItems.map((item) => (
                <div key={item.key} className="inline-flex min-w-0 shrink items-center gap-1 whitespace-nowrap">
                  {item.icon === 'distance' ? <Route className="h-3 w-3 text-emerald-300/90" /> : null}
                  {item.icon === 'fitness' ? <Gauge className="h-3 w-3 text-sky-300/90" /> : null}
                  {item.icon === 'fatigue' ? <HeartPulse className="h-3 w-3 text-rose-300/90" /> : null}
                  <span className="font-medium text-slate-200/92 tabular-nums">{item.value}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-start">
              <div className="flex flex-wrap items-center gap-2 text-[12px] leading-[1.2] text-slate-300/84">
                {desktopMetaItems.map((item, index) => (
                  <div key={item.key} className="inline-flex items-center gap-1 whitespace-nowrap">
                    {item.icon === 'fitness' ? <Gauge className="h-3 w-3 text-sky-300/90" /> : null}
                    {item.icon === 'fatigue' ? <HeartPulse className="h-3 w-3 text-rose-300/90" /> : null}
                    <span className="font-medium tabular-nums text-slate-100/92">{item.value}</span>
                    {index < desktopMetaItems.length - 1 ? <span className="text-slate-500/80">•</span> : null}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className={cn(compactMobile && mobileFullWidth ? 'px-1' : undefined)}>
          <Separator
            className={cn(
              'bg-gradient-to-r from-transparent via-white/8 to-transparent',
              compactMobile && mobileFullWidth
                ? 'h-px bg-gradient-to-r from-transparent via-sky-200/18 to-transparent opacity-100'
                : undefined,
            )}
          />
        </div>

        <div
          className={cn(
            'flex-1',
            shouldScrollActivities
              ? compactMobile
                ? 'overflow-visible'
                : 'overflow-visible sm:overflow-y-auto sm:pr-1 sm:[scrollbar-width:none] sm:[-ms-overflow-style:none] sm:[&::-webkit-scrollbar]:hidden'
              : 'overflow-visible',
          )}
        >
          <div
            className={cn(
              'space-y-2',
              compactMobile && mobileFullWidth
                ? 'rounded-[1.1rem] border border-white/8 bg-[linear-gradient(180deg,rgba(2,6,23,0.34),rgba(15,23,42,0.16))] px-2 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]'
                : undefined,
            )}
          >
            {compactMobile && mobileFullWidth ? (
              <div className="flex items-center gap-2 px-0.5">
                <span className="h-px flex-1 bg-gradient-to-r from-sky-300/35 to-transparent" />
                <p className="shrink-0 text-[9px] font-semibold uppercase tracking-[0.22em] text-slate-400/88">
                  {mobileActivitySectionLabel(day)}
                </p>
                <span className="h-px flex-1 bg-gradient-to-l from-fuchsia-300/25 to-transparent" />
              </div>
            ) : null}
          {actualCards.map((item) =>
            item.type === 'undo' ? (
              <div
                key={`undo-actual-${day.day_utc}-${undoActivity?.lineNo ?? item.slotIndex}`}
                className={cn(
                  'relative flex flex-col overflow-hidden rounded-lg border border-sky-300/35 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),rgba(15,23,42,0.45)] transition-all duration-200',
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
              const runningLike = isRunningLikeSport(activity.sport);
              const timeLabel = activity.is_custom ? '' : deriveCompactTimeLabel(activity, userTimeZone);
              const durationLabel = normalizeCompactDurationLabel(activity.duration_label);
              const kindLabel = activityTypeLabel(Boolean(activity.is_custom));
              if (compactMobile && mobileFullWidth) {
                const metricPills: MetricBadgeItem[] = [
                  metricPillLabel(durationLabel) ? { tone: 'duration', label: metricPillLabel(durationLabel)! } : null,
                  metricPillLabel(compactDistanceLabel(activity.distance_label))
                    ? { tone: 'distance', label: metricPillLabel(compactDistanceLabel(activity.distance_label))! }
                    : null,
                  metricPillLabel(compactPaceLabel(activity.pace_label))
                    ? { tone: 'pace', label: metricPillLabel(compactPaceLabel(activity.pace_label))! }
                    : null,
                  metricPillLabel(primaryLoadLabel(activity.tss, activity.rtss, runningLike))
                    ? { tone: 'load', label: metricPillLabel(primaryLoadLabel(activity.tss, activity.rtss, runningLike))! }
                    : null,
                ].filter((pill): pill is MetricBadgeItem => Boolean(pill));
                return (
                  <div
                    key={activity.activity_id}
                    className={cn(
                      'relative overflow-hidden rounded-[1rem] border shadow-[0_10px_22px_rgba(2,6,23,0.18)]',
                      'px-2 py-1.5',
                      activity.is_custom ? 'border-[1.5px]' : undefined,
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
                    <div className="min-w-0 pr-6">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-[13px] font-semibold leading-4.5 text-foreground">
                          {formatActivityTitle(activity.sport)}
                          {timeLabel ? ` ${timeLabel}` : ''}
                        </p>
                        {kindLabel ? (
                          <p className="mt-0.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-slate-400/90">
                            {kindLabel}
                          </p>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {metricPills.slice(0, 5).map((pill) => (
                        <MetricBadge key={`${activity.activity_id}-${pill.tone}-${pill.label}`} item={pill} />
                      ))}
                      <div className="flex flex-col gap-1">
                        {activity.vdot != null ? (
                          <MetricBadge item={{ tone: 'vdot', label: formatVdotLabel(activity.vdot) }} />
                        ) : null}
                        <MetricBadge item={{ tone: 'if', label: formatIfPctLabel(activity.if_pct) }} />
                      </div>
                    </div>
                  </div>
                );
              }
              return (
                <div
                  key={activity.activity_id}
                  className={cn(
                    'relative flex cursor-pointer flex-col overflow-hidden rounded-lg border transition-colors hover:bg-white/5',
                    compactMobile ? 'h-[82px] p-1.5 text-[11px]' : 'h-[102px] p-2 text-[12px]',
                    activity.is_custom ? 'border-[1.5px]' : undefined,
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
                        onDeleteCustomActivity?.(activity, item.index);
                      }}
                      disabled={deletingCustomActivity}
                      aria-label="Delete custom activity"
                    >
                      <X className="h-1.75 w-1.75" />
                    </Button>
                  ) : null}
                  <div className="flex min-w-0 items-center">
                    <p className={cn('truncate font-semibold text-foreground', compactMobile ? 'text-[12.5px] leading-4.5' : 'text-[14px] leading-5')}>
                      {formatActivityTitle(activity.sport)}
                      {activity.is_custom ? '(C)' : ''}
                      {!activity.is_custom && timeLabel ? ` ${timeLabel}` : ''}
                    </p>
                  </div>
                  <div className={compactMobile ? 'mt-1 space-y-0.5' : 'mt-1.5 space-y-0.5'}>
                    <MetricRow
                      compactMobile={compactMobile}
                      icon={<Clock3 className="h-2.5 w-2.5 shrink-0 text-cyan-300/80" />}
                      text={compactLine([durationLabel, activity.distance_label])}
                    />
                    <MetricRow
                      compactMobile={compactMobile}
                      icon={<Gauge className="h-2.5 w-2.5 shrink-0 text-amber-300/80" />}
                      text={compactLine([activity.pace_label, formatIfPctLabel(activity.if_pct), activity.vdot != null ? formatVdotLabel(activity.vdot) : null])}
                    />
                  </div>
                  <p className={cn('mt-auto inline-flex min-w-0 items-center gap-1 truncate font-semibold text-foreground/95', compactMobile ? 'text-[10.5px] leading-4' : 'text-[11.5px] leading-[1.25]')}>
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
                  'relative flex flex-col overflow-hidden rounded-lg border border-sky-300/35 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),rgba(15,23,42,0.45)] transition-all duration-200',
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
                  const durationLabel = normalizeCompactDurationLabel(item.activity.duration_label);
                  const runningLike = isRunningLikeSport(item.activity.activity);
                  const metricPills: MetricBadgeItem[] = [
                    metricPillLabel(durationLabel) ? { tone: 'duration', label: metricPillLabel(durationLabel)! } : null,
                    metricPillLabel(formatEquivalentDistance(item.activity.distance_eqv_km, runningLike))
                      ? { tone: 'distance', label: metricPillLabel(formatEquivalentDistance(item.activity.distance_eqv_km, runningLike))! }
                      : null,
                    metricPillLabel(compactPaceLabel(item.activity.pace_label))
                      ? { tone: 'pace', label: metricPillLabel(compactPaceLabel(item.activity.pace_label))! }
                      : null,
                    metricPillLabel(primaryLoadLabel(item.activity.tss, item.activity.rtss, runningLike))
                      ? { tone: 'load', label: metricPillLabel(primaryLoadLabel(item.activity.tss, item.activity.rtss, runningLike))! }
                      : null,
                  ].filter((pill): pill is MetricBadgeItem => Boolean(pill));
                  return (
                <div
                  key={`${item.activity.day_utc}-${item.activity.line_no}`}
                  className={cn(
                    'relative overflow-hidden rounded-[1rem] border shadow-[0_10px_22px_rgba(2,6,23,0.18)]',
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
                    <div className="flex min-w-0 items-center">
                      <p className="truncate text-[13px] font-semibold leading-4.5 text-foreground">
                        {formatActivityTitle(item.activity.activity)}
                      </p>
                    </div>
                    <p className="mt-0.5 text-[10.5px] font-medium uppercase tracking-[0.08em] text-slate-400/90">
                      Planned
                    </p>
                  </div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {metricPills.map((pill) => (
                      <MetricBadge key={`${item.activity.day_utc}-${item.activity.line_no}-${pill.tone}-${pill.label}`} item={pill} />
                    ))}
                    <MetricBadge item={{ tone: 'if', label: formatIfPctLabel(item.activity.if_pct) }} />
                  </div>
                </div>
                  );
                })()
              ) : (
                (() => {
                  const durationLabel = normalizeCompactDurationLabel(item.activity.duration_label);
                  const runningLike = isRunningLikeSport(item.activity.activity);
                  return (
                    <div
                      key={`${item.activity.day_utc}-${item.activity.line_no}`}
                      className={cn(
                        'relative flex cursor-pointer flex-col overflow-hidden rounded-lg border transition-colors hover:bg-white/5',
                        compactMobile ? 'h-[82px] px-2 pb-1.5 pt-1.5 text-[11px]' : 'h-[102px] px-2.5 pb-2.5 pt-2 text-[12px]',
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
                      <div className="flex min-w-0 items-center">
                        <p className={cn('truncate font-semibold text-foreground', compactMobile ? 'text-[12.5px] leading-4.5' : 'text-[14px] leading-5')}>
                          {formatActivityTitle(item.activity.activity)} <span className="text-muted-foreground">(P)</span>
                        </p>
                      </div>
                      <div className={compactMobile ? 'mt-1 space-y-0.5' : 'mt-1.5 space-y-0.5'}>
                        <MetricRow
                          compactMobile={compactMobile}
                          icon={<Route className="h-2.5 w-2.5 shrink-0 text-emerald-300/80" />}
                          text={compactLine([durationLabel, formatEquivalentDistance(item.activity.distance_eqv_km, runningLike)])}
                        />
                        <MetricRow
                          compactMobile={compactMobile}
                          icon={<Gauge className="h-2.5 w-2.5 shrink-0 text-amber-300/80" />}
                          text={compactLine([item.activity.pace_label, `${Math.round(item.activity.if_pct)}%`])}
                        />
                      </div>
                      <p className={cn('mt-auto inline-flex min-w-0 items-center gap-1 truncate font-semibold tracking-[0.02em] text-foreground/95', compactMobile ? 'text-[10.5px] leading-4' : 'text-[11.5px] leading-[1.25]')}>
                        <Activity className="h-2.5 w-2.5 shrink-0 text-blue-300/80" />
                        <span className="truncate">{primaryLoadLabel(item.activity.tss, item.activity.rtss, runningLike)}</span>
                      </p>
                    </div>
                  );
                })()
              )
            ),
          )}

          {day.actual_activities.length === 0 && day.planned_activities.length === 0 && day.is_past ? (
            <div className={cn(compactMobile ? 'rounded-[0.95rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.02))] p-2 text-center text-muted-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.05)]' : 'rounded-lg border border-border/70 bg-muted/25 p-2 text-center text-muted-foreground', compactMobile ? 'text-[11px]' : 'text-[12px]')}>
              <p className="font-semibold text-foreground">Rest Day</p>
              <p>Rest is part of training.</p>
            </div>
          ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

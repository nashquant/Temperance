import { useEffect, useRef } from 'react';
import { Activity, AlertTriangle, ChevronDown, Clock3, HeartPulse, Route } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { DashboardDayColumn } from '@/features/dashboard/components/dashboard-day-column';
import { DashboardWeekSummaryCard } from '@/features/dashboard/components/dashboard-week-summary-card';
import type { DashboardWeekRow } from '@/features/dashboard/types/dashboard';

interface DashboardWeekCardProps {
  week: DashboardWeekRow;
  onAddPlannedActivity?: (dayUtc: string) => void;
  onMarkPlannedDone?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number], index: number) => void;
  onDeletePlannedActivity?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number], index: number) => void;
  onDeleteCustomActivity?: (activity: DashboardWeekRow['days'][number]['actual_activities'][number], index: number) => void;
  onSelectActivity?: (activityId: string) => void;
  addingPlannedActivity?: boolean;
  markingPlannedDone?: boolean;
  deletingPlannedActivity?: boolean;
  deletingCustomActivity?: boolean;
  userTimeZone?: string;
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

function shortDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { day: '2-digit', month: 'short' });
}

function fmtNumber(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '-';
  return Math.round(value).toString();
}

function fmtDuration(hours: number): string {
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  return `${hours.toFixed(1)}h`;
}

function MobileWeekSummary({ week }: { week: DashboardWeekRow }): JSX.Element {
  const summary = week.summary;

  return (
    <Card className="overflow-hidden rounded-xl border-border/80 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.12),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.9))] shadow-sm">
      <CardContent className="space-y-3 p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <Badge variant="outline" className="h-5 rounded-full px-2 text-[10px] font-semibold tracking-wide">
              Week {week.week_number}
            </Badge>
            <p className="text-sm font-medium text-foreground">
              {shortDay(week.week_start)} - {shortDay(week.week_end)}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-right">
            <div>
              <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">TSS</p>
              <p className="text-sm font-semibold text-foreground">{fmtNumber(summary.tss)}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-[0.08em] text-slate-400">rTSS</p>
              <p className="text-sm font-semibold text-foreground">{fmtNumber(summary.rtss)}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-2">
            <p className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-300/90">
              <Clock3 className="h-3 w-3" />
              Time
            </p>
            <p className="mt-1 text-base font-semibold text-foreground">{fmtDuration(summary.duration_h)}</p>
          </div>
          <div className="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-2">
            <p className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-300/90">
              <Route className="h-3 w-3" />
              Dist
            </p>
            <p className="mt-1 text-base font-semibold text-foreground">{fmtNumber(summary.distance_eqv_km)} km</p>
          </div>
        </div>

        <details className="group rounded-lg border border-white/8 bg-white/[0.025] px-2.5 py-2">
          <summary className="flex cursor-pointer list-none items-center justify-between text-[11px] font-medium uppercase tracking-[0.08em] text-slate-300/90">
            Week Details
            <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          </summary>
          <div className="mt-2 grid grid-cols-[1fr_auto] gap-x-2 gap-y-1 text-[11px]">
            <p className="inline-flex items-center gap-1 text-slate-300/90"><Activity className="h-3 w-3" />TSS | rTSS</p>
            <p className="text-right font-medium text-foreground/95">{fmtNumber(summary.tss)} | {fmtNumber(summary.rtss)}</p>
            <p className="inline-flex items-center gap-1 text-slate-300/90"><HeartPulse className="h-3 w-3" />Fit | Fatg</p>
            <p className="text-right font-medium text-foreground/95">{fmtNumber(summary.fitness)} | {fmtNumber(summary.fatigue)}</p>
            <p className="inline-flex items-center gap-1 text-slate-300/90"><AlertTriangle className="h-3 w-3" />Ovr | Risk</p>
            <p className="text-right font-medium text-foreground/95">{fmtNumber(summary.overreach)} | {fmtNumber(summary.injury_risk)}</p>
          </div>
        </details>
      </CardContent>
    </Card>
  );
}

export function DashboardWeekCard({
  week,
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
  undoActivity,
  undoVisible,
  onUndoActivity,
}: DashboardWeekCardProps): JSX.Element {
  const mobileRailRef = useRef<HTMLDivElement | null>(null);
  const centeredTodayRef = useRef<string>('');

  useEffect(() => {
    const todayIndex = week.days.findIndex((day) => day.is_today);
    if (todayIndex < 0) return;
    if (centeredTodayRef.current === week.week_start) return;
    const rail = mobileRailRef.current;
    if (!rail) return;
    const todayCard = rail.querySelector<HTMLElement>(`[data-day-utc="${week.days[todayIndex].day_utc}"]`);
    if (!todayCard) return;

    const nextLeft = Math.max(
      0,
      todayCard.offsetLeft - (rail.clientWidth / 2 - todayCard.clientWidth / 2),
    );

    rail.scrollTo({ left: nextLeft, behavior: 'smooth' });
    centeredTodayRef.current = week.week_start;
  }, [week.days, week.week_start]);

  return (
    <div className="rounded-2xl bg-[linear-gradient(135deg,rgba(56,189,248,0.45),rgba(168,85,247,0.26),rgba(245,158,11,0.3))] p-[1px] shadow-[0_10px_30px_rgba(2,6,23,0.5)]">
      <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_8%_10%,rgba(56,189,248,0.1),transparent_40%),radial-gradient(circle_at_88%_90%,rgba(168,85,247,0.11),transparent_45%)] shadow-inner">
        <CardContent className="p-1.5">
          <div className="space-y-1.5 sm:hidden">
            <MobileWeekSummary week={week} />
            <div
              ref={mobileRailRef}
              className="-mx-1.5 overflow-x-auto px-1.5 pb-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
            >
              <div className="flex gap-2">
                {week.days.map((day) => (
                  <div key={day.day_utc} data-day-utc={day.day_utc}>
                    <DashboardDayColumn
                      day={day}
                      onAddPlannedActivity={onAddPlannedActivity}
                      onMarkPlannedDone={onMarkPlannedDone}
                      onDeletePlannedActivity={onDeletePlannedActivity}
                      onDeleteCustomActivity={onDeleteCustomActivity}
                      onSelectActivity={onSelectActivity}
                      addingPlannedActivity={addingPlannedActivity}
                      markingPlannedDone={markingPlannedDone}
                      deletingPlannedActivity={deletingPlannedActivity}
                      deletingCustomActivity={deletingCustomActivity}
                      userTimeZone={userTimeZone}
                      undoActivity={undoActivity}
                      undoVisible={undoVisible}
                      onUndoActivity={onUndoActivity}
                      compactMobile
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="hidden gap-1.5 sm:grid lg:grid-cols-[1.15fr_repeat(7,minmax(0,1fr))] sm:items-start">
            <DashboardWeekSummaryCard
              weekNumber={week.week_number}
              weekStart={shortDay(week.week_start)}
              weekEnd={shortDay(week.week_end)}
              summary={week.summary}
            />
            {week.days.map((day) => (
              <DashboardDayColumn
                key={day.day_utc}
                day={day}
                onAddPlannedActivity={onAddPlannedActivity}
                onMarkPlannedDone={onMarkPlannedDone}
                onDeletePlannedActivity={onDeletePlannedActivity}
                onDeleteCustomActivity={onDeleteCustomActivity}
                onSelectActivity={onSelectActivity}
                addingPlannedActivity={addingPlannedActivity}
                markingPlannedDone={markingPlannedDone}
                deletingPlannedActivity={deletingPlannedActivity}
                deletingCustomActivity={deletingCustomActivity}
                userTimeZone={userTimeZone}
                undoActivity={undoActivity}
                undoVisible={undoVisible}
                onUndoActivity={onUndoActivity}
              />
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

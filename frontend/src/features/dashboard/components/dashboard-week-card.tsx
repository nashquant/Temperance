import { Activity, AlertTriangle, ChevronDown, Clock3, Gauge, HeartPulse, Route } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { DashboardDayColumn } from '@/features/dashboard/components/dashboard-day-column';
import { DashboardWeekSummaryCard } from '@/features/dashboard/components/dashboard-week-summary-card';
import type { DashboardWeekRow } from '@/features/dashboard/types/dashboard';
import { formatCompactDurationHours } from '@/features/dashboard/utils/format-duration';

interface DashboardWeekCardProps {
  week: DashboardWeekRow;
  onAddPlannedActivity?: (dayUtc: string) => void;
  onMarkPlannedDone?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number], index: number) => void;
  onDeletePlannedActivity?: (activity: DashboardWeekRow['days'][number]['planned_activities'][number], index: number) => void;
  onDeleteCustomActivity?: (activity: DashboardWeekRow['days'][number]['actual_activities'][number], index: number) => void;
  onToggleActivityInvalid?: (activity: DashboardWeekRow['days'][number]['actual_activities'][number], nextInvalid: boolean) => void;
  onSelectActivity?: (activityId: string) => void;
  addingPlannedActivity?: boolean;
  markingPlannedDone?: boolean;
  deletingPlannedActivity?: boolean;
  deletingCustomActivity?: boolean;
  togglingActivityInvalid?: boolean;
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

function shortDayWithYear(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function fmtNumber(value: number | null): string {
  if (value === null || Number.isNaN(value)) return '-';
  return Math.round(value).toString();
}

function MobileWeekSummary({ week }: { week: DashboardWeekRow }): JSX.Element {
  const summary = week.summary;

  return (
    <Card className="overflow-hidden rounded-xl border-border/80 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.12),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(15,23,42,0.9))] shadow-sm">
      <CardContent className="space-y-3 p-2.5 sm:p-3">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1">
            <Badge variant="outline" className="h-5 rounded-full px-2 text-[10px] font-semibold tracking-wide">
              Week {week.week_number}
            </Badge>
            <p className="text-sm font-medium text-foreground">
              {shortDay(week.week_start)} - {shortDayWithYear(week.week_end)}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-x-3 gap-y-1 text-right">
            <div>
              <p className="inline-flex items-center justify-end gap-1 text-[10px] uppercase tracking-[0.08em] text-sky-300/90">
                <Gauge className="h-3 w-3" />
                VDOT
              </p>
              <p className="text-sm font-semibold text-sky-100/92">{fmtNumber(summary.vdot_max)}</p>
            </div>
            <div>
              <p className="inline-flex items-center justify-end gap-1 text-[10px] uppercase tracking-[0.08em] text-blue-300/90">
                <Activity className="h-3 w-3" />
                TSS
              </p>
              <p className="text-sm font-semibold text-blue-100/92">{fmtNumber(summary.tss)}</p>
            </div>
            <div>
              <p className="inline-flex items-center justify-end gap-1 text-[10px] uppercase tracking-[0.08em] text-blue-300/90">
                <Activity className="h-3 w-3" />
                rTSS
              </p>
              <p className="text-sm font-semibold text-blue-100/92">{fmtNumber(summary.rtss)}</p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-2">
            <p className="inline-flex items-center gap-1 text-[11px] font-medium text-cyan-200/92">
              <Clock3 className="h-3 w-3 text-cyan-300/90" />
              Time
            </p>
            <p className="mt-1 text-base font-semibold text-cyan-100/92">{formatCompactDurationHours(summary.duration_h)}</p>
          </div>
          <div className="rounded-lg border border-white/8 bg-white/[0.03] px-2.5 py-2">
            <p className="inline-flex items-center gap-1 text-[11px] font-medium text-lime-200/92">
              <Route className="h-3 w-3 text-lime-300/90" />
              Dist
            </p>
            <p className="mt-1 text-base font-semibold text-lime-100/92">{fmtNumber(summary.distance_eqv_km)} km</p>
          </div>
        </div>

        <details className="group rounded-lg border border-white/8 bg-white/[0.025] px-2.5 py-2">
          <summary className="flex cursor-pointer list-none items-center justify-between text-[11px] font-medium uppercase tracking-[0.08em] text-slate-300/90">
            Week Details
            <ChevronDown className="h-3.5 w-3.5 transition-transform group-open:rotate-180" />
          </summary>
          <div className="mt-2 grid grid-cols-[1fr_auto] gap-x-2 gap-y-1 text-[11px]">
            <p className="inline-flex items-center gap-1 text-blue-200/92"><Activity className="h-3 w-3 text-blue-300/90" />TSS | rTSS</p>
            <p className="text-right font-medium text-blue-100/92">{fmtNumber(summary.tss)} | {fmtNumber(summary.rtss)}</p>
            <p className="inline-flex items-center gap-1 text-rose-200/92"><HeartPulse className="h-3 w-3 text-rose-300/90" />Fit | Fatg</p>
            <p className="text-right font-medium text-rose-100/92">{fmtNumber(summary.fitness)} | {fmtNumber(summary.fatigue)}</p>
            <p className="inline-flex items-center gap-1 text-orange-200/92"><AlertTriangle className="h-3 w-3 text-orange-300/90" />Ovr | Risk</p>
            <p className="text-right font-medium text-orange-100/92">{fmtNumber(summary.overreach)} | {fmtNumber(summary.injury_risk)}</p>
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
  onToggleActivityInvalid,
  onSelectActivity,
  addingPlannedActivity,
  markingPlannedDone,
  deletingPlannedActivity,
  deletingCustomActivity,
  togglingActivityInvalid,
  userTimeZone,
  undoActivity,
  undoVisible,
  onUndoActivity,
}: DashboardWeekCardProps): JSX.Element {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-[linear-gradient(135deg,rgba(37,99,235,0.34),rgba(79,70,229,0.28)_48%,rgba(147,51,234,0.24))] p-[1.5px] shadow-[0_16px_38px_rgba(2,6,23,0.42)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_14%_18%,rgba(96,165,250,0.22),transparent_30%),radial-gradient(circle_at_84%_14%,rgba(168,85,247,0.18),transparent_28%),linear-gradient(180deg,rgba(255,255,255,0.05),transparent_22%,transparent_78%,rgba(15,23,42,0.12))]" />
      <div className="pointer-events-none absolute inset-x-10 top-0 h-px bg-gradient-to-r from-transparent via-white/18 to-transparent" />
      <Card className="relative overflow-hidden rounded-2xl border border-[rgba(51,65,85,0.76)] bg-[linear-gradient(180deg,rgba(9,16,29,0.99),rgba(6,11,22,0.97))] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),inset_0_0_0_1px_rgba(15,23,42,0.72)]">
        <CardContent className="relative p-1 sm:p-1.5">
          <div className="pointer-events-none absolute inset-[1px] rounded-[calc(1rem-1px)] bg-[radial-gradient(circle_at_10%_18%,rgba(59,130,246,0.14),transparent_24%),radial-gradient(circle_at_88%_16%,rgba(147,51,234,0.14),transparent_24%),linear-gradient(180deg,rgba(255,255,255,0.025),transparent_20%,transparent_78%,rgba(15,23,42,0.12))]" />
          <div className="pointer-events-none absolute inset-x-16 top-[1px] h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />
          <div className="relative space-y-1.5 sm:hidden">
            <MobileWeekSummary week={week} />
            <div className="-mx-0.5 grid gap-1.5 pb-1">
              {week.days.map((day) => (
                <DashboardDayColumn
                  key={day.day_utc}
                  day={day}
                  onAddPlannedActivity={onAddPlannedActivity}
                  onMarkPlannedDone={onMarkPlannedDone}
                  onDeletePlannedActivity={onDeletePlannedActivity}
                  onDeleteCustomActivity={onDeleteCustomActivity}
                  onToggleActivityInvalid={onToggleActivityInvalid}
                  onSelectActivity={onSelectActivity}
                  addingPlannedActivity={addingPlannedActivity}
                  markingPlannedDone={markingPlannedDone}
                  deletingPlannedActivity={deletingPlannedActivity}
                  deletingCustomActivity={deletingCustomActivity}
                  togglingActivityInvalid={togglingActivityInvalid}
                  userTimeZone={userTimeZone}
                  undoActivity={undoActivity}
                  undoVisible={undoVisible}
                  onUndoActivity={onUndoActivity}
                  compactMobile
                  mobileFullWidth
                />
              ))}
            </div>
          </div>

          <div className="relative hidden gap-1.5 sm:grid lg:grid-cols-[1.15fr_repeat(7,minmax(0,1fr))] sm:items-start">
            <DashboardWeekSummaryCard
              weekNumber={week.week_number}
              weekStart={shortDay(week.week_start)}
              weekEnd={shortDayWithYear(week.week_end)}
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
                onToggleActivityInvalid={onToggleActivityInvalid}
                onSelectActivity={onSelectActivity}
                addingPlannedActivity={addingPlannedActivity}
                markingPlannedDone={markingPlannedDone}
                deletingPlannedActivity={deletingPlannedActivity}
                deletingCustomActivity={deletingCustomActivity}
                togglingActivityInvalid={togglingActivityInvalid}
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

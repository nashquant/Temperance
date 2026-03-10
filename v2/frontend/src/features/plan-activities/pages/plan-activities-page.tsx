import { useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { PlannedWeekChart } from '@/features/plan-activities/components/planned-week-chart';
import { PlannedWeekSelector } from '@/features/plan-activities/components/planned-week-selector';
import { usePlanActivitiesQuery } from '@/features/plan-activities/hooks/use-plan-activities-query';
import {
  deletePlannedActivity,
  ingestPlannedActivities,
  setPlannedManualDone,
  updatePlannedWorkout,
} from '@/features/plan-activities/services/plan-activities-api';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';
import { queryClient } from '@/lib/query-client';

function dayLabel(isoDay: string): string {
  return new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', month: 'short' }).format(
    new Date(`${isoDay}T00:00:00`),
  );
}

export function PlanActivitiesPage(): JSX.Element {
  return <PlanActivitiesSection />;
}

interface PlanActivitiesSectionProps {
  embedded?: boolean;
}

export function PlanActivitiesSection({ embedded = false }: PlanActivitiesSectionProps): JSX.Element {
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const { session, profile } = useAuth();
  const query = usePlanActivitiesQuery(4);
  const [metric, setMetric] = useState<PlannedMetricView>('tss');
  const [selectedWeek, setSelectedWeek] = useState<string>('');
  const [entryText, setEntryText] = useState('');
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [rowSaveResults, setRowSaveResults] = useState<Record<string, { tone: 'error' | 'success'; message: string }>>({});

  const refetchPlan = async () => {
    await queryClient.invalidateQueries({ queryKey: ['plan-activities'] });
  };

  const manualDoneMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo, manualDone }: { dayUtc: string; lineNo: number; manualDone: boolean }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await setPlannedManualDone({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        manualDone,
      });
    },
    onSuccess: refetchPlan,
  });

  const deleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deletePlannedActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: refetchPlan,
  });

  const ingestMutation = useMutation({
    mutationFn: async (text: string) => {
      if (!session?.token) throw new Error('Missing auth token');
      return ingestPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: text,
      });
    },
    onSuccess: async (response) => {
      await refetchPlan();
      if (response.errors.length > 0 && response.saved_count <= 0) {
        setIngestResult(response.errors[0] ?? 'Unable to save planned activities.');
      } else if (response.errors.length > 0) {
        setIngestResult(`Saved ${response.saved_count}. Some entries were skipped.`);
      } else {
        setIngestResult(`Saved ${response.saved_count} planned activit${response.saved_count === 1 ? 'y' : 'ies'}.`);
      }
      if (response.saved_count > 0) setEntryText('');
    },
    onError: (error) => {
      setIngestResult(error instanceof Error ? error.message : 'Unable to save planned activities.');
    },
  });

  const workoutUpdateMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo, workoutText, manualDone }: { dayUtc: string; lineNo: number; workoutText: string; manualDone: boolean }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await updatePlannedWorkout({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        workoutText,
        manualDone,
      });
    },
    onSuccess: async (_response, variables) => {
      const rowKey = `${variables.dayUtc}-${variables.lineNo}`;
      setRowSaveResults((previous) => ({
        ...previous,
        [rowKey]: {
          tone: 'success',
          message: 'Saved.',
        },
      }));
      await refetchPlan();
    },
    onError: (error, variables) => {
      const rowKey = `${variables.dayUtc}-${variables.lineNo}`;
      setRowSaveResults((previous) => ({
        ...previous,
        [rowKey]: {
          tone: 'error',
          message: error instanceof Error ? error.message : 'Unable to save planned activity.',
        },
      }));
    },
  });

  const weeks = query.data?.weeks ?? [];
  const today = new Date();
  const currentWeekStartDate = new Date(today);
  const dayOffset = (currentWeekStartDate.getDay() + 6) % 7;
  currentWeekStartDate.setDate(currentWeekStartDate.getDate() - dayOffset);
  const currentWeekStart = `${currentWeekStartDate.getFullYear()}-${String(currentWeekStartDate.getMonth() + 1).padStart(2, '0')}-${String(currentWeekStartDate.getDate()).padStart(2, '0')}`;
  const defaultWeek = weeks.find((week) => week.week_start === currentWeekStart)?.week_start ?? weeks[0]?.week_start ?? '';
  const effectiveWeek = selectedWeek || defaultWeek;
  const selectedWeekMeta = weeks.find((week) => week.week_start === effectiveWeek);

  const selectedRows = useMemo(() => {
    if (!query.data || !effectiveWeek) return [];
    return query.data.rows.filter((row) => {
      const day = new Date(`${row.day_utc}T00:00:00`);
      const start = new Date(`${effectiveWeek}T00:00:00`);
      const end = new Date(start);
      end.setDate(end.getDate() + 6);
      return day >= start && day <= end;
    });
  }, [effectiveWeek, query.data]);

  useEffect(() => {
    const next: Record<string, string> = {};
    selectedRows.forEach((row) => {
      next[`${row.day_utc}-${row.line_no}`] = row.workout_text;
    });
    setEditValues(next);
  }, [selectedRows]);

  const chartRows = useMemo(() => {
    if (!effectiveWeek) return [];
    const start = new Date(`${effectiveWeek}T00:00:00`);
    return Array.from({ length: 7 }).map((_, index) => {
      const d = new Date(start);
      d.setDate(start.getDate() + index);
      const iso = d.toISOString().slice(0, 10);
      const rowValue = selectedRows
        .filter((row) => row.day_utc === iso)
        .reduce((sum, row) => sum + Number(row[metric] ?? 0), 0);
      const tssBasis = selectedRows
        .filter((row) => row.day_utc === iso)
        .reduce((sum, row) => sum + Number(row.tss ?? 0), 0);
      return {
        dayLabel: dayLabel(iso),
        value: rowValue,
        tssBasis,
      };
    });
  }, [effectiveWeek, metric, selectedRows]);

  const goalItems = query.data
    ? [
        { label: 'TSS Goal', value: Math.round(query.data.goals.tss).toString() },
        { label: 'rTSS Goal', value: Math.round(query.data.goals.rtss).toString() },
        { label: 'Distance Goal', value: `${Math.round(query.data.goals.distance_eqv_km)} km` },
      ]
    : [];

  const selectedWeekItems = selectedWeekMeta
    ? [
        { label: 'Week', value: selectedWeekMeta.week_label },
        { label: 'Activities', value: String(selectedWeekMeta.planned_activities) },
        { label: 'Duration', value: `${selectedWeekMeta.duration_h.toFixed(1)}h` },
        { label: 'TSS', value: String(Math.round(selectedWeekMeta.tss)) },
        { label: 'rTSS', value: String(Math.round(selectedWeekMeta.rtss)) },
        { label: 'Dist Eqv', value: `${selectedWeekMeta.distance_eqv_km.toFixed(1)} km` },
      ]
    : [];

  return (
    <section className="space-y-6">
      <div>
        {embedded ? (
          <h2 className="text-xl font-semibold tracking-tight">Plan Activities</h2>
        ) : (
          <h1 className="text-2xl font-semibold tracking-tight">Plan Activities</h1>
        )}
      </div>

      {!query.isLoading && !query.isError && query.data ? (
        <>
          <Card className={`${surfaceClassName} sm:hidden`}>
            <CardContent className="grid gap-2 p-4">
              {goalItems.map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.label}</p>
                  <p className="text-sm font-semibold text-slate-50">{item.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          <div className="hidden flex-wrap items-center gap-2 sm:flex">
            <Badge variant="outline">TSS goal: {Math.round(query.data.goals.tss)}</Badge>
            <Badge variant="outline">rTSS goal: {Math.round(query.data.goals.rtss)}</Badge>
            <Badge variant="outline">Distance goal: {Math.round(query.data.goals.distance_eqv_km)} km</Badge>
          </div>
        </>
      ) : null}

      <Card className={surfaceClassName}>
        <CardContent className="space-y-4 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200/80">Add Planned Activity</p>
          <textarea
            className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
            value={entryText}
            onChange={(event) => setEntryText(event.target.value)}
          />
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">Multiple entries are supported with new lines, `;`, or `,`.</p>
            <div className="flex items-center gap-2">
            <Button onClick={() => ingestMutation.mutate(entryText)} disabled={ingestMutation.isPending || !entryText.trim()}>
              {ingestMutation.isPending ? 'Saving...' : 'Save'}
            </Button>
            {ingestResult ? <p className="text-xs text-muted-foreground">{ingestResult}</p> : null}
            </div>
          </div>
        </CardContent>
      </Card>

      {query.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-56 w-full" />
        </div>
      ) : null}

      {query.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load planned activities</AlertTitle>
          <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          {weeks.length === 0 ? (
              <Card className={surfaceClassName}>
                <CardContent className="p-8 text-sm text-slate-300/72">No planned activities found in this time window.</CardContent>
              </Card>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                <PlannedWeekSelector weeks={weeks} value={effectiveWeek} onValueChange={(next) => setSelectedWeek(next)} />
              </div>

              {selectedWeekMeta ? (
                <Card className={surfaceClassName}>
                  <CardContent className="p-4">
                    <div className="grid gap-2 md:hidden">
                      {selectedWeekItems.map((item) => (
                        <div
                          key={item.label}
                          className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5"
                        >
                          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.label}</p>
                          <p className="text-sm font-semibold text-slate-50 text-right">{item.value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="hidden gap-3 md:grid md:grid-cols-6">
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">Week</p><p className="font-medium text-foreground">{selectedWeekMeta.week_label}</p></div>
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">Activities</p><p className="font-medium text-foreground">{selectedWeekMeta.planned_activities}</p></div>
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">Duration</p><p className="font-medium text-foreground">{selectedWeekMeta.duration_h.toFixed(1)}h</p></div>
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">TSS</p><p className="font-medium text-foreground">{Math.round(selectedWeekMeta.tss)}</p></div>
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">rTSS</p><p className="font-medium text-foreground">{Math.round(selectedWeekMeta.rtss)}</p></div>
                      <div className="rounded-xl border border-white/10 bg-black/15 p-3"><p className="text-xs text-slate-300/72">Dist Eqv</p><p className="font-medium text-foreground">{selectedWeekMeta.distance_eqv_km.toFixed(1)} km</p></div>
                    </div>
                  </CardContent>
                </Card>
              ) : null}

              <PlannedWeekChart data={chartRows} metric={metric} onMetricChange={setMetric} />

              <Card className={surfaceClassName}>
                <CardContent className="p-0">
                  <div className="overflow-x-auto rounded-2xl pb-1">
                    <table className="min-w-[980px] w-full table-fixed text-sm">
                      <colgroup>
                        <col className="w-[64px]" />
                        <col className="w-[108px]" />
                        <col className="w-[120px]" />
                        <col className="w-auto" />
                        <col className="w-[82px]" />
                        <col className="w-[82px]" />
                        <col className="w-[104px]" />
                        <col className="w-[74px]" />
                        <col className="w-[148px]" />
                      </colgroup>
                      <thead className="bg-white/5 text-slate-300/72">
                        <tr>
                          <th className="px-2 py-2 text-left sm:px-3">Done</th>
                          <th className="px-2 py-2 text-left sm:px-3">Day</th>
                          <th className="px-2 py-2 text-left sm:px-3">Activity</th>
                          <th className="px-2 py-2 text-left sm:px-3">Workout</th>
                          <th className="px-2 py-2 text-right sm:px-3">TSS</th>
                          <th className="px-2 py-2 text-right sm:px-3">rTSS</th>
                          <th className="px-2 py-2 text-right sm:px-3">Dist Eqv</th>
                          <th className="px-2 py-2 text-right sm:px-3">IF</th>
                          <th className="px-2 py-2 text-center sm:px-3">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedRows.map((row) => {
                          const rowKey = `${row.day_utc}-${row.line_no}`;
                          return (
                            <tr key={rowKey} className="border-t border-white/10">
                              <td className="px-2 py-2 sm:px-3">
                                <input
                                  className="h-4 w-4 accent-sky-400"
                                  type="checkbox"
                                  checked={row.manual_done}
                                  onChange={(event) =>
                                    manualDoneMutation.mutate({
                                      dayUtc: row.day_utc,
                                      lineNo: row.line_no,
                                      manualDone: event.target.checked,
                                    })
                                  }
                                />
                              </td>
                              <td className="px-2 py-2 sm:px-3">{dayLabel(row.day_utc)}</td>
                              <td className="px-2 py-2 sm:px-3">{row.activity}</td>
                              <td className="px-2 py-2 sm:px-3">
                                <input
                                  className="min-w-[260px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
                                  value={editValues[rowKey] ?? ''}
                                  onChange={(event) => {
                                    setEditValues((previous) => ({ ...previous, [rowKey]: event.target.value }));
                                    setRowSaveResults((previous) => {
                                      if (!(rowKey in previous)) return previous;
                                      const next = { ...previous };
                                      delete next[rowKey];
                                      return next;
                                    });
                                  }}
                                />
                                {rowSaveResults[rowKey] ? (
                                  <p
                                    className={`mt-1 text-xs ${
                                      rowSaveResults[rowKey]?.tone === 'error' ? 'text-red-400' : 'text-slate-300/72'
                                    }`}
                                  >
                                    {rowSaveResults[rowKey]?.message}
                                  </p>
                                ) : null}
                              </td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.tss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.rtss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.distance_eqv_km.toFixed(1)} km</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.if_proxy_pct.toFixed(0)}%</td>
                              <td className="px-2 py-2 text-right sm:px-3">
                                <div className="flex justify-end gap-1.5">
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="px-2.5 text-slate-200 hover:bg-white/10 hover:text-white"
                                    onClick={() =>
                                      workoutUpdateMutation.mutate({
                                        dayUtc: row.day_utc,
                                        lineNo: row.line_no,
                                        workoutText: editValues[rowKey] ?? row.workout_text,
                                        manualDone: row.manual_done,
                                      })
                                    }
                                  >
                                    Save
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    className="px-2.5 text-slate-300 hover:bg-rose-500/12 hover:text-rose-100"
                                    onClick={() => {
                                      if (window.confirm('Delete this planned activity?')) {
                                        deleteMutation.mutate({ dayUtc: row.day_utc, lineNo: row.line_no });
                                      }
                                    }}
                                  >
                                    Delete
                                  </Button>
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                        {selectedRows.length === 0 ? (
                          <tr>
                            <td colSpan={9} className="px-3 py-6 text-center text-sm text-slate-300/60">
                              No planned activities in the selected week.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </>
      ) : null}
    </section>
  );
}

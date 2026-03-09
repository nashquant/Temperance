import { useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { PlannedMetricSelector } from '@/features/plan-activities/components/planned-metric-selector';
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
  const { session, profile } = useAuth();
  const query = usePlanActivitiesQuery(4);
  const [metric, setMetric] = useState<PlannedMetricView>('tss');
  const [selectedWeek, setSelectedWeek] = useState<string>('');
  const [entryText, setEntryText] = useState('');
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});

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
      if (response.errors.length > 0) {
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
    onSuccess: refetchPlan,
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

  return (
    <section className="space-y-6">
      <div>
        {embedded ? (
          <h2 className="text-xl font-semibold tracking-tight">Plan Activities</h2>
        ) : (
          <h1 className="text-2xl font-semibold tracking-tight">Plan Activities</h1>
        )}
      </div>

      <Card>
        <CardContent className="space-y-3 p-4">
          <p className="text-sm font-medium">Quick add planned activities</p>
          <textarea
            className="min-h-[88px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm"
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
            value={entryText}
            onChange={(event) => setEntryText(event.target.value)}
          />
          <div className="flex items-center gap-2">
            <Button onClick={() => ingestMutation.mutate(entryText)} disabled={ingestMutation.isPending || !entryText.trim()}>
              {ingestMutation.isPending ? 'Saving...' : 'Save planned entry'}
            </Button>
            {ingestResult ? <p className="text-xs text-muted-foreground">{ingestResult}</p> : null}
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
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">TSS goal: {Math.round(query.data.goals.tss)}</Badge>
            <Badge variant="outline">rTSS goal: {Math.round(query.data.goals.rtss)}</Badge>
            <Badge variant="outline">Distance goal: {Math.round(query.data.goals.distance_eqv_km)} km</Badge>
          </div>

          {weeks.length === 0 ? (
            <Card>
              <CardContent className="p-8 text-sm text-muted-foreground">No planned activities found in this time window.</CardContent>
            </Card>
          ) : (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <PlannedWeekSelector weeks={weeks} value={effectiveWeek} onValueChange={(next) => setSelectedWeek(next)} />
                <PlannedMetricSelector value={metric} onValueChange={setMetric} />
              </div>

              {selectedWeekMeta ? (
                <Card>
                  <CardContent className="p-4">
                    <div className="grid gap-3 md:grid-cols-6">
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">Week</p><p className="font-medium">{selectedWeekMeta.week_label}</p></div>
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">Activities</p><p className="font-medium">{selectedWeekMeta.planned_activities}</p></div>
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">Duration</p><p className="font-medium">{selectedWeekMeta.duration_h.toFixed(1)}h</p></div>
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">TSS</p><p className="font-medium">{Math.round(selectedWeekMeta.tss)}</p></div>
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">rTSS</p><p className="font-medium">{Math.round(selectedWeekMeta.rtss)}</p></div>
                      <div className="rounded border p-3"><p className="text-xs text-muted-foreground">Dist Eqv</p><p className="font-medium">{selectedWeekMeta.distance_eqv_km.toFixed(1)} km</p></div>
                    </div>
                  </CardContent>
                </Card>
              ) : null}

              <PlannedWeekChart data={chartRows} metric={metric} />

              <Card>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/60 text-muted-foreground">
                        <tr>
                          <th className="px-3 py-2 text-left">Done</th>
                          <th className="px-3 py-2 text-left">Day</th>
                          <th className="px-3 py-2 text-left">Activity</th>
                          <th className="px-3 py-2 text-left">Workout</th>
                          <th className="px-3 py-2 text-right">TSS</th>
                          <th className="px-3 py-2 text-right">rTSS</th>
                          <th className="px-3 py-2 text-right">Dist Eqv</th>
                          <th className="px-3 py-2 text-right">IF</th>
                          <th className="px-3 py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedRows.map((row) => {
                          const rowKey = `${row.day_utc}-${row.line_no}`;
                          return (
                            <tr key={rowKey} className="border-t">
                              <td className="px-3 py-2">
                                <input
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
                              <td className="px-3 py-2">{dayLabel(row.day_utc)}</td>
                              <td className="px-3 py-2">{row.activity}</td>
                              <td className="px-3 py-2">
                                <input
                                  className="w-full min-w-[320px] rounded border border-input bg-transparent px-2 py-1"
                                  value={editValues[rowKey] ?? ''}
                                  onChange={(event) =>
                                    setEditValues((previous) => ({ ...previous, [rowKey]: event.target.value }))
                                  }
                                />
                              </td>
                              <td className="px-3 py-2 text-right">{Math.round(row.tss)}</td>
                              <td className="px-3 py-2 text-right">{Math.round(row.rtss)}</td>
                              <td className="px-3 py-2 text-right">{row.distance_eqv_km.toFixed(1)} km</td>
                              <td className="px-3 py-2 text-right">{row.if_proxy_pct.toFixed(0)}%</td>
                              <td className="px-3 py-2 text-right">
                                <div className="flex justify-end gap-1">
                                  <Button
                                    variant="ghost"
                                    size="sm"
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

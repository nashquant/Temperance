import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import {
  secondaryPageActionButtonClassName,
  secondaryPageInsetClassName,
  secondaryPageMutedInsetClassName,
  secondaryPageSurfaceClassName,
  secondaryPageTextAreaClassName,
} from '@/components/ui/secondary-page';
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
import type { PlannedActivityRow, PlannedMetricView } from '@/features/plan-activities/types/plan-activities';
import { queryClient } from '@/lib/query-client';

function dayLabel(isoDay: string): string {
  return new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' }).format(
    new Date(`${isoDay}T00:00:00Z`),
  );
}

function addDaysToIsoDay(isoDay: string, days: number): string {
  const [year, month, day] = isoDay.split('-').map((value) => Number(value));
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

export function PlanActivitiesPage(): JSX.Element {
  return <PlanActivitiesSection />;
}

interface PlanActivitiesSectionProps {
  embedded?: boolean;
}

export function PlanActivitiesSection({ embedded = false }: PlanActivitiesSectionProps): JSX.Element {
  const deleteUndoWindowMs = 6000;
  const { session, profile } = useAuth();
  const query = usePlanActivitiesQuery(4);
  const [metric, setMetric] = useState<PlannedMetricView>('tss');
  const [selectedWeek, setSelectedWeek] = useState<string>('');
  const [entryText, setEntryText] = useState('');
  const [ingestResult, setIngestResult] = useState<string | null>(null);
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [rowSaveResults, setRowSaveResults] = useState<Record<string, { tone: 'error' | 'success'; message: string }>>({});
  const [pendingDelete, setPendingDelete] = useState<{ id: number; row: PlannedActivityRow } | null>(null);
  const [deleteResult, setDeleteResult] = useState<string | null>(null);
  const [copyResult, setCopyResult] = useState<string | null>(null);
  const pendingDeleteTimerRef = useRef<number | null>(null);
  const pendingDeleteRef = useRef<{ id: number; row: PlannedActivityRow } | null>(null);
  const sanitizedRows = useMemo(
    () =>
      (query.data?.rows ?? []).filter((row) => {
        const workoutText = String(row.workout_text ?? '').trim();
        const activityLabel = String(row.activity ?? '').trim();
        return workoutText.length > 0 || activityLabel.length > 0;
      }),
    [query.data?.rows],
  );

  const refetchPlan = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['weekly-outlook'] }),
    ]);
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
    if (!effectiveWeek) return [];
    const weekEnd = addDaysToIsoDay(effectiveWeek, 6);
    return sanitizedRows.filter((row) => {
      return row.day_utc >= effectiveWeek && row.day_utc <= weekEnd;
    });
  }, [effectiveWeek, sanitizedRows]);

  useEffect(() => {
    const next: Record<string, string> = {};
    selectedRows.forEach((row) => {
      next[`${row.day_utc}-${row.line_no}`] = row.workout_text;
    });
    setEditValues(next);
  }, [selectedRows]);

  const chartRows = useMemo(() => {
    if (!effectiveWeek) return [];
    return Array.from({ length: 7 }).map((_, index) => {
      const iso = addDaysToIsoDay(effectiveWeek, index);
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

  const selectedWeekClipboardText = useMemo(() => {
    return selectedRows
      .slice()
      .sort((left, right) => {
        if (left.day_utc !== right.day_utc) return left.day_utc.localeCompare(right.day_utc);
        return left.line_no - right.line_no;
      })
      .map((row) => {
        const rowKey = `${row.day_utc}-${row.line_no}`;
        const workoutText = String(editValues[rowKey] ?? row.workout_text ?? '').trim();
        return workoutText ? `${row.day_utc}: ${workoutText}` : '';
      })
      .filter(Boolean)
      .join('\n');
  }, [editValues, selectedRows]);

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

  const clearPendingDeleteTimer = () => {
    if (pendingDeleteTimerRef.current) {
      window.clearTimeout(pendingDeleteTimerRef.current);
      pendingDeleteTimerRef.current = null;
    }
  };

  const finalizePendingDelete = async (candidate: { id: number; row: PlannedActivityRow }) => {
    try {
      await deleteMutation.mutateAsync({
        dayUtc: candidate.row.day_utc,
        lineNo: candidate.row.line_no,
      });
      setDeleteResult(`Deleted ${candidate.row.activity || 'planned activity'}.`);
    } catch (error) {
      setDeleteResult(error instanceof Error ? error.message : 'Unable to delete planned activity.');
      setPendingDelete((current) => (current?.id === candidate.id ? null : current));
      pendingDeleteRef.current = null;
      return;
    }
    setPendingDelete((current) => (current?.id === candidate.id ? null : current));
    pendingDeleteRef.current = null;
  };

  const queueDelete = (row: PlannedActivityRow) => {
    clearPendingDeleteTimer();
    const existingPendingDelete = pendingDeleteRef.current;
    if (existingPendingDelete) {
      void finalizePendingDelete(existingPendingDelete);
    }
    const candidate = { id: Date.now(), row };
    pendingDeleteRef.current = candidate;
    setPendingDelete(candidate);
    setDeleteResult(null);
    pendingDeleteTimerRef.current = window.setTimeout(() => {
      if (pendingDeleteRef.current?.id !== candidate.id) return;
      void finalizePendingDelete(candidate);
    }, deleteUndoWindowMs);
  };

  const handleUndoDelete = () => {
    clearPendingDeleteTimer();
    pendingDeleteRef.current = null;
    setPendingDelete(null);
    setDeleteResult(null);
  };

  useEffect(() => () => {
    clearPendingDeleteTimer();
  }, []);

  const handleCopyWeekToClipboard = async () => {
    const payload = selectedWeekClipboardText.trim();
    if (!payload) {
      setCopyResult('No planned activities to copy for this week.');
      return;
    }
    try {
      await navigator.clipboard.writeText(payload);
      setCopyResult(`Copied ${selectedRows.length} planned activit${selectedRows.length === 1 ? 'y' : 'ies'} to clipboard.`);
    } catch {
      setCopyResult('Unable to copy the current week to clipboard.');
    }
  };

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
          <Card className={`${secondaryPageSurfaceClassName} sm:hidden`}>
            <CardContent className="grid gap-2 p-4">
              {goalItems.map((item) => (
                <div
                  key={item.label}
                  className={`flex items-center justify-between ${secondaryPageMutedInsetClassName} px-3 py-2.5`}
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

      <Card className={secondaryPageSurfaceClassName}>
        <CardContent className="space-y-3 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-3 sm:space-y-4 sm:p-5">
          <h2 className="text-lg font-semibold text-foreground">Add Planned Activity</h2>
          <textarea
            className={`min-h-[104px] ${secondaryPageTextAreaClassName} sm:min-h-[120px]`}
            placeholder="e.g. 3Mar26: 80min elliptical @140bpm; 2026-03-26: 10min run @4:50 + 5x6min @3:40/km"
            value={entryText}
            onChange={(event) => setEntryText(event.target.value)}
          />
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
            <p className="text-xs text-muted-foreground">Multiple entries are supported with new lines, `;`, or `,`.</p>
            <div className="flex w-full flex-col items-stretch gap-2 sm:w-auto sm:flex-row sm:items-center">
              <Button className={`${secondaryPageActionButtonClassName} w-full sm:w-auto`} onClick={() => ingestMutation.mutate(entryText)} disabled={ingestMutation.isPending || !entryText.trim()}>
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

      {deleteResult ? (
        <Alert className="border-white/15 bg-white/[0.03] text-slate-100">
          <AlertTitle>Delete status</AlertTitle>
          <AlertDescription>{deleteResult}</AlertDescription>
        </Alert>
      ) : null}

      {copyResult ? (
        <Alert className="border-white/15 bg-white/[0.03] text-slate-100">
          <AlertTitle>Clipboard</AlertTitle>
          <AlertDescription>{copyResult}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          {weeks.length === 0 ? (
              <Card className={secondaryPageSurfaceClassName}>
                <CardContent className="p-8 text-sm text-slate-300/72">No planned activities found in this time window.</CardContent>
              </Card>
          ) : (
            <>
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                <PlannedWeekSelector weeks={weeks} value={effectiveWeek} onValueChange={(next) => setSelectedWeek(next)} />
                <Button
                  variant="outline"
                  className="border-white/10 bg-black/15"
                  onClick={() => void handleCopyWeekToClipboard()}
                  disabled={!selectedWeekClipboardText.trim()}
                >
                  Copy Week To Clipboard
                </Button>
              </div>

              {selectedWeekMeta ? (
                <Card className={secondaryPageSurfaceClassName}>
                  <CardContent className="p-4">
                    <div className="grid gap-2 md:hidden">
                      {selectedWeekItems.map((item) => (
                        <div
                          key={item.label}
                          className={`flex items-center justify-between ${secondaryPageMutedInsetClassName} px-3 py-2.5`}
                        >
                          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.label}</p>
                          <p className="text-sm font-semibold text-slate-50 text-right">{item.value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="hidden gap-3 md:grid md:grid-cols-6">
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">Week</p><p className="font-medium text-foreground">{selectedWeekMeta.week_label}</p></div>
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">Activities</p><p className="font-medium text-foreground">{selectedWeekMeta.planned_activities}</p></div>
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">Duration</p><p className="font-medium text-foreground">{selectedWeekMeta.duration_h.toFixed(1)}h</p></div>
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">TSS</p><p className="font-medium text-foreground">{Math.round(selectedWeekMeta.tss)}</p></div>
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">rTSS</p><p className="font-medium text-foreground">{Math.round(selectedWeekMeta.rtss)}</p></div>
                      <div className={`${secondaryPageInsetClassName} p-3`}><p className="text-xs text-slate-300/72">Dist Eqv</p><p className="font-medium text-foreground">{selectedWeekMeta.distance_eqv_km.toFixed(1)} km</p></div>
                    </div>
                  </CardContent>
                </Card>
              ) : null}

              <PlannedWeekChart data={chartRows} metric={metric} onMetricChange={setMetric} />

              <Card className={secondaryPageSurfaceClassName}>
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
                          const workoutText = editValues[rowKey] ?? '';
                          const isDirty = workoutText !== row.workout_text;
                          const isPendingDelete =
                            pendingDelete?.row.day_utc === row.day_utc && pendingDelete.row.line_no === row.line_no;
                          const isSavingRow =
                            workoutUpdateMutation.isPending
                            && workoutUpdateMutation.variables?.dayUtc === row.day_utc
                            && workoutUpdateMutation.variables?.lineNo === row.line_no;
                          return (
                            <tr key={rowKey} className={`border-t border-white/10 ${isPendingDelete ? 'bg-rose-500/8' : ''}`}>
                              <td className="px-2 py-2 sm:px-3">
                                <input
                                  className="h-4 w-4 accent-sky-400"
                                  type="checkbox"
                                  checked={row.manual_done}
                                  disabled={isPendingDelete}
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
                                  className={`min-w-[260px] w-full rounded-xl border px-3 py-2 text-sm outline-none transition ${isPendingDelete ? 'border-rose-400/20 bg-rose-500/8 text-slate-400' : 'border-white/10 bg-black/20 text-foreground focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20'}`}
                                  value={workoutText}
                                  disabled={isPendingDelete}
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
                                {isPendingDelete ? <p className="mt-1 text-xs text-rose-200/85">Delete pending. Undo is available in Actions.</p> : null}
                              </td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.tss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{Math.round(row.rtss)}</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.distance_eqv_km.toFixed(1)} km</td>
                              <td className="px-2 py-2 text-right sm:px-3">{row.if_proxy_pct.toFixed(0)}%</td>
                              <td className="px-2 py-2 text-right sm:px-3">
                                <div className="flex justify-end gap-1.5">
                                  <Button
                                    variant={isDirty ? 'default' : 'outline'}
                                    size="sm"
                                    className={isDirty ? 'px-2.5' : 'border-white/10 px-2.5 text-slate-200 hover:bg-white/10 hover:text-white'}
                                    disabled={!isDirty || isSavingRow || isPendingDelete}
                                    onClick={() =>
                                      workoutUpdateMutation.mutate({
                                        dayUtc: row.day_utc,
                                        lineNo: row.line_no,
                                        workoutText,
                                        manualDone: row.manual_done,
                                      })
                                    }
                                  >
                                    {isSavingRow ? 'Saving...' : isDirty ? 'Save' : 'Saved'}
                                  </Button>
                                  {isPendingDelete ? (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="border-amber-200/40 px-2.5 text-amber-50 hover:bg-amber-500/15"
                                      onClick={handleUndoDelete}
                                    >
                                      Undo
                                    </Button>
                                  ) : (
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="border-rose-400/25 px-2.5 text-rose-100 hover:bg-rose-500/12 hover:text-rose-50"
                                      onClick={() => queueDelete(row)}
                                    >
                                      Delete
                                    </Button>
                                  )}
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

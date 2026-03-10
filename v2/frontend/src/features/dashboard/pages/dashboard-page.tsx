import { useMutation } from '@tanstack/react-query';
import { startTransition, useEffect, useMemo, useRef, useState } from 'react';
import { RotateCcw } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { deleteCustomActivity, ingestCustomActivities } from '@/features/custom-activities/services/custom-activities-api';
import { ActivitySplitsDrawer } from '@/features/dashboard/components/activity-splits-drawer';
import { DashboardWeekCard } from '@/features/dashboard/components/dashboard-week-card';
import { useDashboardQuery } from '@/features/dashboard/hooks/use-dashboard-query';
import { getDashboard } from '@/features/dashboard/services/dashboard-api';
import type { DashboardResponse } from '@/features/dashboard/types/dashboard';
import {
  deletePlannedActivity,
  ingestPlannedActivities,
  setPlannedManualDone,
} from '@/features/plan-activities/services/plan-activities-api';
import { queryClient } from '@/lib/query-client';

function timeHintFromWorkoutText(workoutText: string): 'AM' | 'PM' | null {
  const match = String(workoutText || '').match(/(^|[^A-Za-z0-9_])(AM|PM)([^A-Za-z0-9_]|$)/i);
  if (!match) return null;
  const hint = String(match[2] || '').toUpperCase();
  return hint === 'AM' || hint === 'PM' ? hint : null;
}

function plannedCardIsVisible(
  dayUtc: string,
  workoutText: string,
  now: Date,
): boolean {
  const day = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(day.getTime())) return true;

  const expiry = new Date(day);
  const hint = timeHintFromWorkoutText(workoutText);
  if (hint === 'AM') {
    expiry.setHours(12, 0, 0, 0);
  } else if (hint === 'PM') {
    expiry.setHours(21, 0, 0, 0);
  } else {
    expiry.setDate(expiry.getDate() + 1);
    expiry.setHours(0, 0, 0, 0);
  }
  return now.getTime() < expiry.getTime();
}

function isTodayOrPast(dayUtc: string): boolean {
  const selected = new Date(`${dayUtc}T00:00:00`);
  if (Number.isNaN(selected.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  selected.setHours(0, 0, 0, 0);
  return selected.getTime() <= today.getTime();
}

export function DashboardPage(): JSX.Element {
  const dashboardPageSize = 10;
  const dashboardYearWindowWeeks = 52;
  const dashboardMaxWeeks = 52;
  const { session, profile } = useAuth();
  const [visibleWeeks, setVisibleWeeks] = useState(dashboardPageSize);
  const [selectedYearWindow, setSelectedYearWindow] = useState('0');
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const [addActivityDayUtc, setAddActivityDayUtc] = useState<string | null>(null);
  const [addActivityText, setAddActivityText] = useState('');
  const [addActivityMode, setAddActivityMode] = useState<'planned' | 'custom'>('planned');
  const [addActivityResult, setAddActivityResult] = useState<string | null>(null);
  const [undoState, setUndoState] = useState<{
    id: number;
    dayUtc?: string;
    lineNo?: number;
    slotIndex?: number;
    label: string;
    action: (() => Promise<void>) | null;
  } | null>(null);
  const [undoVisible, setUndoVisible] = useState(false);
  const weekRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastAnchoredWeekRef = useRef<string>('');
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
  const undoTimerRef = useRef<number | null>(null);
  const undoDismissTimerRef = useRef<number | null>(null);
  const selectedYearWindowIndex = useMemo(() => {
    const parsed = Number(selectedYearWindow);
    if (!Number.isFinite(parsed) || parsed < 0) return 0;
    return parsed;
  }, [selectedYearWindow]);
  const weekOffset = selectedYearWindowIndex * dashboardYearWindowWeeks;
  const query = useDashboardQuery(visibleWeeks, 'all', weekOffset);
  const userTimeZone = useMemo(() => {
    const profileAny = profile as unknown as Record<string, unknown> | null;
    const tzFromProfile =
      String(profileAny?.timezone || profileAny?.user_timezone || profileAny?.tz || '').trim();
    if (tzFromProfile) return tzFromProfile;
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  }, [profile]);
  const canAddCustomForComposer = useMemo(
    () => Boolean(addActivityDayUtc && isTodayOrPast(addActivityDayUtc)),
    [addActivityDayUtc],
  );
  const refreshDashboardViews = async () => {
    await Promise.all([
      query.refetch(),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      queryClient.invalidateQueries({ queryKey: ['planned-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['custom-activities'] }),
      queryClient.invalidateQueries({ queryKey: ['week-outlook'] }),
      queryClient.invalidateQueries({ queryKey: ['data-extract-status'] }),
    ]);
  };
  const patchDashboardCaches = (
    updater: (payload: DashboardResponse) => DashboardResponse,
  ) => {
    queryClient.setQueriesData<DashboardResponse>(
      { queryKey: ['dashboard', profile?.owner] },
      (current) => (current ? updater(current) : current),
    );
  };
  const removeCustomActivityLocally = (dayUtc: string, lineNo: number) => {
    patchDashboardCaches((payload) => ({
      ...payload,
      weeks: payload.weeks.map((week) => ({
        ...week,
        days: week.days.map((day) =>
          day.day_utc === dayUtc
            ? {
                ...day,
                actual_activities: day.actual_activities.filter(
                  (activity) => !(activity.is_custom && activity.day_utc === dayUtc && activity.line_no === lineNo),
                ),
              }
            : day,
        ),
      })),
    }));
  };
  const removePlannedActivityLocally = (dayUtc: string, lineNo: number) => {
    patchDashboardCaches((payload) => ({
      ...payload,
      weeks: payload.weeks.map((week) => ({
        ...week,
        days: week.days.map((day) =>
          day.day_utc === dayUtc
            ? {
                ...day,
                planned_activities: day.planned_activities.filter(
                  (activity) => !(activity.day_utc === dayUtc && activity.line_no === lineNo),
                ),
              }
            : day,
        ),
      })),
    }));
  };
  const markPlannedDoneLocally = (dayUtc: string, lineNo: number) => {
    removePlannedActivityLocally(dayUtc, lineNo);
  };
  const showUndo = ({
    label,
    action,
    dayUtc,
    lineNo,
    slotIndex,
  }: {
    label: string;
    action: () => Promise<void>;
    dayUtc?: string;
    lineNo?: number;
    slotIndex?: number;
  }) => {
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
    }
    const id = Date.now();
    setUndoState({ id, dayUtc, lineNo, slotIndex, label, action });
    window.requestAnimationFrame(() => setUndoVisible(true));
    undoTimerRef.current = window.setTimeout(() => {
      setUndoVisible(false);
      undoDismissTimerRef.current = window.setTimeout(() => {
        setUndoState((current) => (current?.id === id ? null : current));
        undoDismissTimerRef.current = null;
      }, 220);
      undoTimerRef.current = null;
    }, 9000);
  };
  useEffect(() => () => {
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
    }
  }, []);
  const handleUndo = async () => {
    const pending = undoState;
    if (!pending) return;
    if (undoTimerRef.current) {
      window.clearTimeout(undoTimerRef.current);
      undoTimerRef.current = null;
    }
    if (undoDismissTimerRef.current) {
      window.clearTimeout(undoDismissTimerRef.current);
      undoDismissTimerRef.current = null;
    }
    setUndoVisible(false);
    window.setTimeout(() => setUndoState(null), 180);
    await pending.action?.();
  };
  const plannedDoneMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await setPlannedManualDone({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
        manualDone: true,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
      setAddActivityDayUtc(null);
      setAddActivityText('');
      setAddActivityMode('planned');
    },
  });
  const plannedDeleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deletePlannedActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
    },
  });
  const plannedCreateMutation = useMutation({
    mutationFn: async ({
      dayUtc,
      workoutText,
      mode,
    }: {
      dayUtc: string;
      workoutText: string;
      mode: 'planned' | 'custom';
    }) => {
      if (!session?.token) throw new Error('Missing auth token');
      if (mode === 'custom') {
        return ingestCustomActivities({
          token: session.token,
          owner: profile?.owner,
          entryText: `${dayUtc}: ${workoutText}`,
        });
      }
      return ingestPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: `${dayUtc}: ${workoutText}`,
      });
    },
    onSuccess: async (response, variables) => {
      if (response.errors.length > 0 && response.saved_count <= 0) {
        setAddActivityResult(response.errors[0] ?? `Unable to save ${variables.mode} activity.`);
        return;
      }
      await refreshDashboardViews();
      setAddActivityResult(null);
      setAddActivityDayUtc(null);
      setAddActivityText('');
      setAddActivityMode('planned');
    },
    onError: (error) => {
      setAddActivityResult(error instanceof Error ? error.message : 'Unable to save activity.');
    },
  });
  const customDeleteMutation = useMutation({
    mutationFn: async ({ dayUtc, lineNo }: { dayUtc: string; lineNo: number }) => {
      if (!session?.token) throw new Error('Missing auth token');
      await deleteCustomActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc,
        lineNo,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
    },
  });
  const displayWeeks = useMemo(() => {
    if (!query.data?.weeks) return [];
    const now = new Date();
    return query.data.weeks.map((week) => ({
      ...week,
      days: week.days.map((day) => ({
        ...day,
        planned_activities: day.planned_activities.filter((activity) =>
          plannedCardIsVisible(day.day_utc, activity.workout_text, now),
        ),
      })),
    }));
  }, [query.data?.weeks]);

  const sortedWeeks = useMemo(() => {
    if (displayWeeks.length === 0) return [];
    return [...displayWeeks].sort((a, b) => {
      const aTs = Date.parse(a.week_start);
      const bTs = Date.parse(b.week_start);
      if (Number.isNaN(aTs) && Number.isNaN(bTs)) return 0;
      if (Number.isNaN(aTs)) return 1;
      if (Number.isNaN(bTs)) return -1;
      return bTs - aTs;
    });
  }, [displayWeeks]);

  const totalYearWindows = useMemo(() => {
    const weeksTotal = Math.max(Number(query.data?.weeks_total ?? 0), 0);
    return Math.max(1, Math.ceil(weeksTotal / dashboardYearWindowWeeks));
  }, [dashboardYearWindowWeeks, query.data?.weeks_total, sortedWeeks.length]);

  const currentWeekStart = useMemo(() => {
    if (sortedWeeks.length === 0) return '';

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const current = sortedWeeks.find((week) => {
      const start = new Date(`${week.week_start}T00:00:00`);
      const end = new Date(`${week.week_end}T00:00:00`);
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return false;
      start.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      return today >= start && today <= end;
    });
    if (current) return current.week_start;

    const pastOrCurrent = sortedWeeks
      .map((week) => ({ weekStart: week.week_start, ts: Date.parse(week.week_start) }))
      .filter((item) => !Number.isNaN(item.ts) && item.ts <= today.getTime())
      .sort((a, b) => b.ts - a.ts);
    if (pastOrCurrent.length > 0) return pastOrCurrent[0].weekStart;

    return sortedWeeks[0]?.week_start ?? '';
  }, [sortedWeeks]);

  useEffect(() => {
    if (!currentWeekStart) return;
    if (lastAnchoredWeekRef.current === currentWeekStart) return;
    const node = weekRefs.current[currentWeekStart];
    if (!node) return;
    node.scrollIntoView({ block: 'start', behavior: 'auto' });
    lastAnchoredWeekRef.current = currentWeekStart;
  }, [currentWeekStart]);

  useEffect(() => {
    if (!session?.token) return;
    if (!query.data?.has_more_weeks) return;
    const nextWeeks = Math.min(visibleWeeks + dashboardPageSize, dashboardMaxWeeks);
    if (nextWeeks <= visibleWeeks) return;

    void queryClient.prefetchQuery({
      queryKey: ['dashboard', profile?.owner, nextWeeks, weekOffset, 'all'],
      queryFn: async () =>
        getDashboard({
          token: session.token,
          owner: profile?.owner,
          weeks: nextWeeks,
          weekOffset,
        }),
      staleTime: 0,
    });
  }, [dashboardMaxWeeks, dashboardPageSize, profile?.owner, query.data?.has_more_weeks, session?.token, visibleWeeks, weekOffset]);

  useEffect(() => {
    setVisibleWeeks(dashboardYearWindowWeeks);
  }, [dashboardYearWindowWeeks, weekOffset]);

  useEffect(() => {
    const node = loadMoreRef.current;
    if (!node) return;
    if (!query.data?.has_more_weeks) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (!entry?.isIntersecting) return;
        if (query.isFetching) return;
        const nextWeeks = Math.min(visibleWeeks + dashboardPageSize, dashboardMaxWeeks);
        if (nextWeeks <= visibleWeeks) return;
        startTransition(() => {
          setVisibleWeeks(nextWeeks);
        });
      },
      { rootMargin: '900px 0px' },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [dashboardMaxWeeks, dashboardPageSize, query.data?.has_more_weeks, query.isFetching, visibleWeeks]);

  return (
    <section className="space-y-6">
      {query.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-[360px] w-full" />
          <Skeleton className="h-[360px] w-full" />
        </div>
      ) : null}

      {query.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load dashboard</AlertTitle>
          <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          {query.data.weeks.length === 0 ? (
            <div className="rounded-xl border border-border/70 bg-card/40 p-8 text-sm text-muted-foreground">
              No dashboard weeks available.
            </div>
          ) : (
            <div className="space-y-4">
              {totalYearWindows > 1 ? (
                <div className="flex justify-end">
                  <div className="w-full max-w-[220px]">
                    <Select value={selectedYearWindow} onValueChange={setSelectedYearWindow}>
                      <SelectTrigger className="w-full max-w-[220px]">
                        <SelectValue placeholder="Select year window" />
                      </SelectTrigger>
                      <SelectContent>
                        {Array.from({ length: totalYearWindows }).map((_, index) => (
                          <SelectItem key={index} value={String(index)}>
                            {index === 0 ? 'Latest year' : `${index}-${index + 1} years ago`}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ) : null}
              {sortedWeeks.map((week) => (
                <div
                  key={week.week_start}
                  ref={(node) => {
                    weekRefs.current[week.week_start] = node;
                  }}
                >
                  <DashboardWeekCard
                    week={week}
                    onAddPlannedActivity={(dayUtc) => {
                      setAddActivityDayUtc(dayUtc);
                      setAddActivityText('');
                      setAddActivityMode('planned');
                      setAddActivityResult(null);
                    }}
                    onMarkPlannedDone={(activity, index) =>
                      (() => {
                        markPlannedDoneLocally(activity.day_utc, activity.line_no);
                        showUndo({
                          dayUtc: activity.day_utc,
                          lineNo: activity.line_no,
                          slotIndex: index,
                          label: 'Marked',
                          action: async () => {
                            if (!session?.token) throw new Error('Missing auth token');
                            await setPlannedManualDone({
                              token: session.token,
                              owner: profile?.owner,
                              dayUtc: activity.day_utc,
                              lineNo: activity.line_no,
                              manualDone: false,
                            });
                            await refreshDashboardViews();
                          },
                        });
                        plannedDoneMutation.mutate({ dayUtc: activity.day_utc, lineNo: activity.line_no }, { onError: () => void refreshDashboardViews() });
                      })()
                    }
                    onDeletePlannedActivity={(activity, index) =>
                      (() => {
                        removePlannedActivityLocally(activity.day_utc, activity.line_no);
                        showUndo({
                          dayUtc: activity.day_utc,
                          lineNo: activity.line_no,
                          slotIndex: index,
                          label: 'Deleted',
                          action: async () => {
                            if (!session?.token) throw new Error('Missing auth token');
                            await ingestPlannedActivities({
                              token: session.token,
                              owner: profile?.owner,
                              entryText: `${activity.day_utc}: ${activity.workout_text}`,
                            });
                            await refreshDashboardViews();
                          },
                        });
                        plannedDeleteMutation.mutate({ dayUtc: activity.day_utc, lineNo: activity.line_no }, { onError: () => void refreshDashboardViews() });
                      })()
                    }
                    onDeleteCustomActivity={(activity) =>
                      activity.day_utc && activity.line_no
                        ? (() => {
                            removeCustomActivityLocally(activity.day_utc, activity.line_no);
                            if (activity.activity_text) {
                              showUndo({
                                label: 'Deleted',
                                action: async () => {
                                  if (!session?.token) throw new Error('Missing auth token');
                                  await ingestCustomActivities({
                                    token: session.token,
                                    owner: profile?.owner,
                                    entryText: `${activity.day_utc}: ${activity.activity_text}`,
                                  });
                                  await refreshDashboardViews();
                                },
                              });
                            }
                            customDeleteMutation.mutate(
                              { dayUtc: activity.day_utc, lineNo: activity.line_no },
                              { onError: () => void refreshDashboardViews() },
                            );
                          })()
                        : undefined
                    }
                    onSelectActivity={(activityId) => setSelectedActivityId(activityId)}
                    addingPlannedActivity={plannedCreateMutation.isPending}
                    markingPlannedDone={plannedDoneMutation.isPending}
                    deletingPlannedActivity={plannedDeleteMutation.isPending}
                    deletingCustomActivity={customDeleteMutation.isPending}
                    userTimeZone={userTimeZone}
                    undoPlannedActivity={
                      undoState?.dayUtc && typeof undoState.lineNo === 'number' && typeof undoState.slotIndex === 'number'
                        ? {
                            dayUtc: undoState.dayUtc,
                            lineNo: undoState.lineNo,
                            slotIndex: undoState.slotIndex,
                            label: undoState.label,
                          }
                        : null
                    }
                    undoVisible={undoVisible}
                    onUndoPlannedActivity={() => void handleUndo()}
                  />
                </div>
              ))}
              {query.data.has_more_weeks ? <div ref={loadMoreRef} className="h-8 w-full" aria-hidden="true" /> : null}
            </div>
          )}
        </>
      ) : null}
      <ActivitySplitsDrawer
        activityId={selectedActivityId}
        open={Boolean(selectedActivityId)}
        onClose={() => setSelectedActivityId(null)}
      />
      {addActivityDayUtc ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <button
            type="button"
            className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
            aria-label="Close activity composer"
            onClick={() => {
              if (plannedCreateMutation.isPending) return;
              setAddActivityDayUtc(null);
              setAddActivityText('');
              setAddActivityMode('planned');
              setAddActivityResult(null);
            }}
          />
          <div className="relative z-10 w-full max-w-xl rounded-2xl border border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_38%),linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] p-5 shadow-[0_24px_80px_rgba(0,0,0,0.45)]">
            <div className="space-y-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-200/80">Add Activity</p>
              <h3 className="text-lg font-semibold text-foreground">{addActivityDayUtc}</h3>
              <p className="text-sm text-muted-foreground">
                {addActivityMode === 'planned'
                  ? 'Enter the planned workout string for this date.'
                  : 'Enter the custom activity string for this date.'}{' '}
                Example: `80min elliptical @140bpm` or `10min run @4:50 + 5x6min @3:40/km`
              </p>
              {!canAddCustomForComposer ? (
                <p className="text-xs text-muted-foreground">Custom activities can only be added for today or past dates.</p>
              ) : null}
            </div>

            <div className="mt-4 space-y-3">
              <div className="inline-flex rounded-xl border border-white/10 bg-black/20 p-1">
                <button
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-sm transition ${
                    addActivityMode === 'planned'
                      ? 'bg-white/10 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => {
                    setAddActivityMode('planned');
                    setAddActivityResult(null);
                  }}
                  disabled={plannedCreateMutation.isPending}
                >
                  Planned
                </button>
                <button
                  type="button"
                  className={`rounded-lg px-3 py-1.5 text-sm transition ${
                    addActivityMode === 'custom'
                      ? 'bg-white/10 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                  onClick={() => {
                    setAddActivityMode('custom');
                    setAddActivityResult(null);
                  }}
                  disabled={plannedCreateMutation.isPending || !canAddCustomForComposer}
                >
                  Custom
                </button>
              </div>
              <textarea
                className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
                value={addActivityText}
                onChange={(event) => {
                  if (addActivityResult) setAddActivityResult(null);
                  setAddActivityText(event.target.value);
                }}
                placeholder={addActivityMode === 'planned' ? 'Type the planned workout...' : 'Type the custom activity...'}
                autoFocus
              />
              {addActivityResult ? (
                <p className="text-sm text-red-400">
                  {addActivityResult}
                </p>
              ) : null}
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-muted-foreground">
                  This will be saved directly to the selected day as a {addActivityMode} activity.
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setAddActivityDayUtc(null);
                      setAddActivityText('');
                      setAddActivityMode('planned');
                      setAddActivityResult(null);
                    }}
                    disabled={plannedCreateMutation.isPending}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      const workoutText = addActivityText.trim();
                      if (!workoutText || !addActivityDayUtc) return;
                      plannedCreateMutation.mutate({ dayUtc: addActivityDayUtc, workoutText, mode: addActivityMode });
                    }}
                    disabled={plannedCreateMutation.isPending || !addActivityText.trim()}
                  >
                    {plannedCreateMutation.isPending ? 'Saving...' : `Save ${addActivityMode} activity`}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
      {undoState ? (
        <div
          className={`fixed bottom-5 right-5 z-50 w-full max-w-[320px] transition-all duration-200 ${
            undoVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
          }`}
        >
        <div className="rounded-2xl border border-white/8 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.1),transparent_40%),linear-gradient(180deg,rgba(15,23,42,0.9),rgba(2,6,23,0.96))] p-2.5 shadow-[0_16px_36px_rgba(2,6,23,0.28)] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-200/64">Dashboard Action</p>
              <p className="truncate text-[13px] text-slate-100/92">{undoState.label}</p>
            </div>
            <Button
              variant="outline"
              className="shrink-0 rounded-xl border-white/8 bg-white/5 text-slate-100 hover:bg-white/10"
              onClick={async () => {
                await handleUndo();
              }}
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5 text-sky-200/80" />
              Undo
            </Button>
          </div>
        </div>
        </div>
      ) : null}
    </section>
  );
}

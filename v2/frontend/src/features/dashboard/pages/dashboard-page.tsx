import { useMutation } from '@tanstack/react-query';
import { startTransition, useEffect, useMemo, useRef, useState } from 'react';

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
  const weekRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastAnchoredWeekRef = useRef<string>('');
  const loadMoreRef = useRef<HTMLDivElement | null>(null);
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
        await ingestCustomActivities({
          token: session.token,
          owner: profile?.owner,
          entryText: `${dayUtc}: ${workoutText}`,
        });
        return;
      }
      await ingestPlannedActivities({
        token: session.token,
        owner: profile?.owner,
        entryText: `${dayUtc}: ${workoutText}`,
      });
    },
    onSuccess: async () => {
      await refreshDashboardViews();
      setAddActivityDayUtc(null);
      setAddActivityText('');
      setAddActivityMode('planned');
    },
  });
  const customDeleteMutation = useMutation({
    mutationFn: async ({ activityId }: { activityId: string }) => {
      if (!session?.token) throw new Error('Missing auth token');
      const match = String(activityId).match(/^custom-(\d{4}-\d{2}-\d{2})-(\d+)$/);
      if (!match) throw new Error('Invalid custom activity id');
      await deleteCustomActivity({
        token: session.token,
        owner: profile?.owner,
        dayUtc: match[1],
        lineNo: Number(match[2]),
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
                      <SelectTrigger>
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
                      setAddActivityMode(isTodayOrPast(dayUtc) ? 'planned' : 'planned');
                    }}
                    onMarkPlannedDone={(dayUtc, lineNo) => plannedDoneMutation.mutate({ dayUtc, lineNo })}
                    onDeletePlannedActivity={(dayUtc, lineNo) => plannedDeleteMutation.mutate({ dayUtc, lineNo })}
                    onDeleteCustomActivity={(activityId) => customDeleteMutation.mutate({ activityId })}
                    onSelectActivity={(activityId) => setSelectedActivityId(activityId)}
                    addingPlannedActivity={plannedCreateMutation.isPending}
                    markingPlannedDone={plannedDoneMutation.isPending}
                    deletingPlannedActivity={plannedDeleteMutation.isPending}
                    deletingCustomActivity={customDeleteMutation.isPending}
                    userTimeZone={userTimeZone}
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
                  onClick={() => setAddActivityMode('planned')}
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
                  onClick={() => setAddActivityMode('custom')}
                  disabled={plannedCreateMutation.isPending || !canAddCustomForComposer}
                >
                  Custom
                </button>
              </div>
              <textarea
                className="min-h-[120px] w-full rounded-xl border border-white/10 bg-black/20 px-3 py-3 text-sm text-foreground outline-none transition focus:border-sky-300/40 focus:ring-2 focus:ring-sky-300/20"
                value={addActivityText}
                onChange={(event) => setAddActivityText(event.target.value)}
                placeholder={addActivityMode === 'planned' ? 'Type the planned workout...' : 'Type the custom activity...'}
                autoFocus
              />
              {plannedCreateMutation.isError ? (
                <p className="text-sm text-red-400">
                  {plannedCreateMutation.error instanceof Error ? plannedCreateMutation.error.message : 'Unable to save activity.'}
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
    </section>
  );
}

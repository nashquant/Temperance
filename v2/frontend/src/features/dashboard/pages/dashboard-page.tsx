import { useMutation } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { ActivitySplitsDrawer } from '@/features/dashboard/components/activity-splits-drawer';
import { DashboardWeekCard } from '@/features/dashboard/components/dashboard-week-card';
import { useDashboardQuery } from '@/features/dashboard/hooks/use-dashboard-query';
import { deletePlannedActivity, setPlannedManualDone } from '@/features/plan-activities/services/plan-activities-api';
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

export function DashboardPage(): JSX.Element {
  const { session, profile } = useAuth();
  const [visibleWeeks, setVisibleWeeks] = useState(6);
  const [selectedActivityId, setSelectedActivityId] = useState<string | null>(null);
  const weekRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const lastAnchoredWeekRef = useRef<string>('');
  const query = useDashboardQuery(visibleWeeks, 'all');
  const userTimeZone = useMemo(() => {
    const profileAny = profile as unknown as Record<string, unknown> | null;
    const tzFromProfile =
      String(profileAny?.timezone || profileAny?.user_timezone || profileAny?.tz || '').trim();
    if (tzFromProfile) return tzFromProfile;
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
  }, [profile]);
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
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['planned-activities'] }),
        queryClient.invalidateQueries({ queryKey: ['week-outlook'] }),
      ]);
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
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
        queryClient.invalidateQueries({ queryKey: ['planned-activities'] }),
        queryClient.invalidateQueries({ queryKey: ['week-outlook'] }),
      ]);
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
              {sortedWeeks.map((week) => (
                <div
                  key={week.week_start}
                  ref={(node) => {
                    weekRefs.current[week.week_start] = node;
                  }}
                >
                  <DashboardWeekCard
                    week={week}
                    onMarkPlannedDone={(dayUtc, lineNo) => plannedDoneMutation.mutate({ dayUtc, lineNo })}
                    onDeletePlannedActivity={(dayUtc, lineNo) => plannedDeleteMutation.mutate({ dayUtc, lineNo })}
                    onSelectActivity={(activityId) => setSelectedActivityId(activityId)}
                    markingPlannedDone={plannedDoneMutation.isPending}
                    deletingPlannedActivity={plannedDeleteMutation.isPending}
                    userTimeZone={userTimeZone}
                  />
                </div>
              ))}
              {query.data.has_more_weeks ? (
                <div className="flex justify-center">
                  <Button
                    variant="outline"
                    onClick={() => setVisibleWeeks((previous) => Math.min(previous + 6, 52))}
                    disabled={query.isFetching}
                  >
                    Load older weeks
                  </Button>
                </div>
              ) : null}
            </div>
          )}
        </>
      ) : null}
      <ActivitySplitsDrawer
        activityId={selectedActivityId}
        open={Boolean(selectedActivityId)}
        onClose={() => setSelectedActivityId(null)}
      />
    </section>
  );
}

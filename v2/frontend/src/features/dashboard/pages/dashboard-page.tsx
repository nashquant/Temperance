import { useMutation } from '@tanstack/react-query';
import { useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/hooks/use-auth';
import { DashboardWeekCard } from '@/features/dashboard/components/dashboard-week-card';
import { useDashboardQuery } from '@/features/dashboard/hooks/use-dashboard-query';
import { setPlannedManualDone } from '@/features/plan-activities/services/plan-activities-api';
import { queryClient } from '@/lib/query-client';

export function DashboardPage(): JSX.Element {
  const { session, profile } = useAuth();
  const [visibleWeeks, setVisibleWeeks] = useState(6);
  const query = useDashboardQuery(visibleWeeks, 'all');
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
  const sortedWeeks = useMemo(() => {
    if (!query.data?.weeks) return [];

    return [...query.data.weeks].sort((a, b) => {
      const aTs = Date.parse(a.week_start);
      const bTs = Date.parse(b.week_start);
      if (Number.isNaN(aTs) && Number.isNaN(bTs)) return 0;
      if (Number.isNaN(aTs)) return 1;
      if (Number.isNaN(bTs)) return -1;
      return bTs - aTs;
    });
  }, [query.data?.weeks]);

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
                <DashboardWeekCard
                  key={week.week_start}
                  week={week}
                  onMarkPlannedDone={(dayUtc, lineNo) => plannedDoneMutation.mutate({ dayUtc, lineNo })}
                  markingPlannedDone={plannedDoneMutation.isPending}
                />
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
    </section>
  );
}

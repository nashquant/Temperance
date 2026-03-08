import { useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { DashboardWeekCard } from '@/features/dashboard/components/dashboard-week-card';
import { useDashboardQuery } from '@/features/dashboard/hooks/use-dashboard-query';
import type { DashboardSportFilter } from '@/features/dashboard/types/dashboard';

export function DashboardPage(): JSX.Element {
  const [visibleWeeks, setVisibleWeeks] = useState(6);
  const [sportFilter, setSportFilter] = useState<DashboardSportFilter>('all');
  const query = useDashboardQuery(visibleWeeks, sportFilter);

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">Activity Dashboard view from v1, rebuilt with v2 components.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2">
            <p className="text-sm text-muted-foreground">Activity</p>
            <Select value={sportFilter} onValueChange={(value) => setSportFilter(value as DashboardSportFilter)}>
              <SelectTrigger className="w-[150px]"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All</SelectItem>
                <SelectItem value="running">Running</SelectItem>
                <SelectItem value="treadmill">Treadmill</SelectItem>
                <SelectItem value="cycling">Cycling</SelectItem>
                <SelectItem value="elliptical">Elliptical</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>Refresh</Button>
        </div>
      </div>

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
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">Activities: {query.data.summary.activities}</Badge>
            <Badge variant="outline">TSS: {Math.round(query.data.summary.tss)}</Badge>
            <Badge variant="outline">rTSS: {Math.round(query.data.summary.rtss)}</Badge>
            <Badge variant="outline">Distance Eqv: {Math.round(query.data.summary.distance_eqv_km)} km</Badge>
          </div>

          {query.data.weeks.length === 0 ? (
            <div className="rounded-xl border border-border/70 bg-card/40 p-8 text-sm text-muted-foreground">
              No dashboard weeks available.
            </div>
          ) : (
            <div className="space-y-4">
              {query.data.weeks.map((week) => (
                <DashboardWeekCard key={week.week_start} week={week} />
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

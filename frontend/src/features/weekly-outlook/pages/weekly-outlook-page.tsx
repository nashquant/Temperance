import { useEffect, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { CompareSelector } from '@/features/weekly-outlook/components/compare-selector';
import { WeeklyOutlookChartCard } from '@/features/weekly-outlook/components/weekly-outlook-chart-card';
import { WeeklySummaryCards } from '@/features/weekly-outlook/components/weekly-summary-cards';
import { useWeeklyOutlookQuery } from '@/features/weekly-outlook/hooks/use-weekly-outlook-query';
import type { WeeklyCompare, WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';
import { formatRange } from '@/features/weekly-outlook/utils/formatters';

export function WeeklyOutlookPage(): JSX.Element {
  return <WeeklyOutlookSection />;
}

interface WeeklyOutlookSectionProps {
  embedded?: boolean;
}

export function WeeklyOutlookSection({ embedded = false }: WeeklyOutlookSectionProps): JSX.Element {
  const [metric, setMetric] = useState<WeeklyMetric>('tss');
  const [compare, setCompare] = useState<WeeklyCompare>('planned');
  const [weekView, setWeekView] = useState<'current' | 'previous'>('current');
  const query = useWeeklyOutlookQuery(metric, compare);
  const previousWeekStart = query.data ? shiftWeekStart(query.data.weekStart, -7) : undefined;
  const previousQuery = useWeeklyOutlookQuery(metric, compare, previousWeekStart, {
    enabled: previousWeekStart !== undefined,
  });
  const activeQuery = weekView === 'previous' ? previousQuery : query;
  const displayedData = activeQuery.data;
  const isEmpty = displayedData !== undefined && displayedData.chartRows.length === 0;
  const showEmbeddedHeaderRow = !embedded || !displayedData;

  useEffect(() => {
    setWeekView('current');
  }, [metric, compare]);

  return (
    <section className={embedded ? 'space-y-4' : 'space-y-6'}>
      <div className={embedded ? 'space-y-3' : 'space-y-4'}>
        {!activeQuery.isLoading && !activeQuery.isError && displayedData ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-2">
              <CompareSelector value={compare} onValueChange={setCompare} />
              <div className="flex flex-col items-start gap-2">
                <Badge variant="outline">{`Week: ${formatRange(displayedData.weekStart, displayedData.weekEnd)}`}</Badge>
                <Badge variant="secondary">
                  {displayedData.compare === 'planned'
                    ? 'Comparison: Planned week'
                    : `Comparison: ${formatRange(displayedData.compareWeekStart, displayedData.compareWeekEnd)}`}
                </Badge>
              </div>
            </div>
          </div>
        ) : null}

        {showEmbeddedHeaderRow ? (
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            {embedded ? null : (
              <div>
                <h1 className="text-2xl font-semibold tracking-tight">Weekly Outlook</h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  Compare current week performance against plan or historical benchmark.
                </p>
              </div>
            )}

            {!displayedData ? (
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:gap-2">
                <CompareSelector value={compare} onValueChange={setCompare} />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      {activeQuery.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : null}

      {activeQuery.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load weekly outlook</AlertTitle>
          <AlertDescription>
            {activeQuery.error instanceof Error ? activeQuery.error.message : 'Unexpected error while requesting data.'}
          </AlertDescription>
        </Alert>
      ) : null}

      {!activeQuery.isLoading && !activeQuery.isError && displayedData ? (
        <>
          {isEmpty ? (
            <Card>
              <CardContent className="p-8">
                <p className="text-sm text-muted-foreground">No week data available for this metric and owner scope.</p>
              </CardContent>
            </Card>
          ) : (
            <>
              <WeeklySummaryCards data={displayedData} selectedMetric={metric} />
              <WeeklyOutlookChartCard
                data={displayedData}
                metric={metric}
                onMetricChange={setMetric}
                weekView={weekView}
                onWeekViewChange={setWeekView}
              />
            </>
          )}
        </>
      ) : null}
    </section>
  );
}

function shiftWeekStart(weekStart: string, days: number): string {
  const baseDate = new Date(`${weekStart}T00:00:00`);
  baseDate.setDate(baseDate.getDate() + days);
  const year = baseDate.getFullYear();
  const month = `${baseDate.getMonth() + 1}`.padStart(2, '0');
  const day = `${baseDate.getDate()}`.padStart(2, '0');
  return `${year}-${month}-${day}`;
}

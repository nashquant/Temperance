import { RefreshCcw } from 'lucide-react';
import { useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { MetricSelector } from '@/features/weekly-outlook/components/metric-selector';
import { WeeklyOutlookChartCard } from '@/features/weekly-outlook/components/weekly-outlook-chart-card';
import { WeeklySummaryCards } from '@/features/weekly-outlook/components/weekly-summary-cards';
import { useWeeklyOutlookQuery } from '@/features/weekly-outlook/hooks/use-weekly-outlook-query';
import type { WeeklyMetric } from '@/features/weekly-outlook/types/weekly-outlook';
import { formatRange } from '@/features/weekly-outlook/utils/formatters';

export function WeeklyOutlookPage(): JSX.Element {
  const [metric, setMetric] = useState<WeeklyMetric>('tss');
  const query = useWeeklyOutlookQuery(metric);

  const isEmpty = query.data !== undefined && query.data.chartRows.length === 0;

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Weekly Outlook</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Compare current week performance against plan or historical benchmark.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <MetricSelector value={metric} onValueChange={setMetric} />
          <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {query.isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-96 w-full" />
        </div>
      ) : null}

      {query.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load weekly outlook</AlertTitle>
          <AlertDescription>
            {query.error instanceof Error ? query.error.message : 'Unexpected error while requesting data.'}
          </AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          <div className="flex items-center gap-2">
            <Badge variant="outline">Week {formatRange(query.data.weekStart, query.data.weekEnd)}</Badge>
            <Badge variant="secondary">Comparison: {query.data.compareLabel}</Badge>
          </div>

          {isEmpty ? (
            <Card>
              <CardContent className="p-8">
                <p className="text-sm text-muted-foreground">No week data available for this metric and owner scope.</p>
              </CardContent>
            </Card>
          ) : (
            <>
              <WeeklySummaryCards data={query.data} selectedMetric={metric} />
              <WeeklyOutlookChartCard data={query.data} metric={metric} />
            </>
          )}
        </>
      ) : null}
    </section>
  );
}

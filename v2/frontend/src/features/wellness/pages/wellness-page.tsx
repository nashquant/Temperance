import { useMemo, useState } from 'react';
import { RefreshCcw } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ProgressionLineChartCard } from '@/features/athlete-progression/components/progression-line-chart-card';
import { useWellnessQuery } from '@/features/wellness/hooks/use-wellness-query';
import type { WellnessAggregation } from '@/features/wellness/types';

function formatDay(iso: string, aggregation: WellnessAggregation): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(aggregation === 'daily' ? { weekday: 'short' as const } : {}),
  }).format(d);
}

function fmt(value: number | null | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-';
  return `${Math.round(value)}`;
}

export function WellnessPage(): JSX.Element {
  const [days, setDays] = useState(365);
  const [aggregation, setAggregation] = useState<WellnessAggregation>('weekly');
  const query = useWellnessQuery(days, aggregation);

  const chartData = useMemo(() => {
    return (query.data?.points ?? []).map((row) => ({
      ...row,
      label: formatDay(row.period_start, aggregation),
    }));
  }, [aggregation, query.data?.points]);

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Wellness</h1>
        <div className="flex items-center gap-2">
          <Select value={String(days)} onValueChange={(value) => setDays(Number(value))}>
            <SelectTrigger className="w-[130px]"><SelectValue placeholder="Lookback" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="90">3 months</SelectItem>
              <SelectItem value="180">6 months</SelectItem>
              <SelectItem value="365">1 year</SelectItem>
              <SelectItem value="730">2 years</SelectItem>
              <SelectItem value="3000">ALL</SelectItem>
            </SelectContent>
          </Select>
          <Select value={aggregation} onValueChange={(value) => setAggregation(value as WellnessAggregation)}>
            <SelectTrigger className="w-[120px]"><SelectValue placeholder="Aggregation" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
            <RefreshCcw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {query.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : null}

      {query.isError ? (
        <Alert className="border-red-300 text-red-700 dark:border-red-900 dark:text-red-300">
          <AlertTitle>Unable to load wellness</AlertTitle>
          <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Sleep Score</p><p className="text-2xl font-semibold">{fmt(query.data.summary.latest_sleep_score)}</p></CardContent></Card>
            <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Resting HR</p><p className="text-2xl font-semibold">{fmt(query.data.summary.latest_resting_hr)}</p></CardContent></Card>
            <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Stress Avg</p><p className="text-2xl font-semibold">{fmt(query.data.summary.latest_stress_avg)}</p></CardContent></Card>
            <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Training Readiness</p><p className="text-2xl font-semibold">{fmt(query.data.summary.latest_training_readiness)}</p></CardContent></Card>
            <Card><CardContent className="p-3"><p className="text-xs text-muted-foreground">Body Battery (End)</p><p className="text-2xl font-semibold">{fmt(query.data.summary.latest_body_battery_end)}</p></CardContent></Card>
          </div>

          {chartData.length === 0 ? (
            <Card><CardContent className="p-8 text-sm text-muted-foreground">No wellness data available for this selection.</CardContent></Card>
          ) : (
            <div className="grid gap-4">
              <ProgressionLineChartCard
                title="Recovery Scores"
                data={chartData}
                yLabel="Score"
                series={[
                  { key: 'sleep_score', label: 'Sleep Score', color: '#22c55e' },
                  { key: 'training_readiness', label: 'Training Readiness', color: '#60a5fa' },
                ]}
              />

              <ProgressionLineChartCard
                title="Stress & Resting HR"
                data={chartData}
                yLabel="Level"
                series={[
                  { key: 'stress_avg', label: 'Stress Avg', color: '#f59e0b' },
                  { key: 'resting_hr', label: 'Resting HR', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Sleep Architecture (hours)"
                data={chartData}
                yLabel="Hours"
                series={[
                  { key: 'sleep_duration_h', label: 'Sleep Total', color: '#38bdf8', dashed: true },
                  { key: 'deep_sleep_h', label: 'Deep', color: '#6366f1' },
                  { key: 'rem_sleep_h', label: 'REM', color: '#a855f7' },
                  { key: 'light_sleep_h', label: 'Light', color: '#22c55e' },
                ]}
              />

              <ProgressionLineChartCard
                title="Body Battery & HRV"
                data={chartData}
                yLabel="Index"
                series={[
                  { key: 'body_battery_end', label: 'Body Battery End', color: '#22c55e' },
                  { key: 'body_battery_avg', label: 'Body Battery Avg', color: '#14b8a6' },
                  { key: 'hrv_status', label: 'HRV Status', color: '#f97316' },
                ]}
              />

              <ProgressionLineChartCard
                title="Steps vs Calories"
                data={chartData}
                yLabel="Steps"
                rightAxisLabel="Calories"
                series={[
                  { key: 'steps', label: 'Steps', color: '#60a5fa', yAxisId: 'left' },
                  { key: 'calories_total', label: 'Calories', color: '#f59e0b', yAxisId: 'right' },
                ]}
              />
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

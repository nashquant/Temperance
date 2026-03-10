import { useMemo, useState } from 'react';

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
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const [days, setDays] = useState(30);
  const [aggregation, setAggregation] = useState<WellnessAggregation>('daily');
  const query = useWellnessQuery(days, aggregation);

  const chartData = useMemo(() => {
    return (query.data?.points ?? []).map((row) => ({
      ...row,
      label: formatDay(row.period_start, aggregation),
    }));
  }, [aggregation, query.data?.points]);

  const summaryItems = useMemo(
    () => [
      { label: 'Sleep Score', value: fmt(query.data?.summary.latest_sleep_score) },
      { label: 'RHR', value: fmt(query.data?.summary.latest_resting_hr) },
      { label: 'Stress', value: fmt(query.data?.summary.latest_stress_avg) },
      { label: 'Readiness', value: fmt(query.data?.summary.latest_training_readiness) },
      { label: 'Battery (End)', value: fmt(query.data?.summary.latest_body_battery_end) },
    ],
    [
      query.data?.summary.latest_body_battery_end,
      query.data?.summary.latest_resting_hr,
      query.data?.summary.latest_sleep_score,
      query.data?.summary.latest_stress_avg,
      query.data?.summary.latest_training_readiness,
    ],
  );

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">Wellness</h1>
        <div className="flex items-center gap-2">
          <Select value={String(days)} onValueChange={(value) => setDays(Number(value))}>
            <SelectTrigger className="w-[130px]"><SelectValue placeholder="Lookback" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="30">1 month</SelectItem>
              <SelectItem value="90">3 months</SelectItem>
              <SelectItem value="180">6 months</SelectItem>
              <SelectItem value="365">1 year</SelectItem>
              <SelectItem value="730">2 years</SelectItem>
              <SelectItem value="3000">ALL</SelectItem>
            </SelectContent>
          </Select>
          <div className="inline-flex rounded-lg border border-white/10 bg-black/15 p-1">
            <Button
              variant={aggregation === 'weekly' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-8 rounded-md px-2.5 text-xs"
              onClick={() => setAggregation('weekly')}
            >
              Weekly
            </Button>
            <Button
              variant={aggregation === 'daily' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-8 rounded-md px-2.5 text-xs"
              onClick={() => setAggregation('daily')}
            >
              Daily
            </Button>
          </div>
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
          <Card className={`${surfaceClassName} md:hidden`}>
            <CardContent className="grid gap-2 p-4">
              {summaryItems.map((item) => (
                <div
                  key={item.label}
                  className="flex items-center justify-between rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5"
                >
                  <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.label}</p>
                  <p className="text-lg font-semibold text-slate-50">{item.value}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="hidden gap-3 md:grid md:grid-cols-2 xl:grid-cols-5">
            {summaryItems.map((item) => (
              <Card key={item.label} className={surfaceClassName}>
                <CardContent className="p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200/78">{item.label}</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-50">{item.value}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {chartData.length === 0 ? (
            <Card className={surfaceClassName}><CardContent className="p-8 text-sm text-slate-300/72">No wellness data available for this selection.</CardContent></Card>
          ) : (
            <div className="grid gap-4">
              <ProgressionLineChartCard
                title="Recovery Scores"
                data={chartData}
                yLabel="Score"
                series={[
                  { key: 'sleep_score', label: 'Sleep Score', color: '#22c55e' },
                  { key: 'training_readiness', label: 'Readiness', color: '#60a5fa' },
                ]}
              />

              <ProgressionLineChartCard
                title="Stress & Resting HR"
                data={chartData}
                yLabel="Level"
                series={[
                  { key: 'stress_avg', label: 'Stress', color: '#f59e0b' },
                  { key: 'resting_hr', label: 'RHR', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Sleep Patterns"
                data={chartData}
                yLabel="Hours"
                series={[
                  { key: 'sleep_duration_h', label: 'Total', color: '#38bdf8', dashed: true },
                  { key: 'deep_sleep_h', label: 'Deep', color: '#6366f1' },
                  { key: 'rem_sleep_h', label: 'REM', color: '#a855f7' },
                  { key: 'light_sleep_h', label: 'Light', color: '#22c55e' },
                ]}
              />

              <ProgressionLineChartCard
                title="Battery & HRV"
                data={chartData}
                yLabel="Index"
                series={[
                  { key: 'body_battery_end', label: 'Battery End', color: '#22c55e' },
                  { key: 'body_battery_avg', label: 'Battery Avg', color: '#14b8a6' },
                  { key: 'hrv_status', label: 'HRV', color: '#f97316' },
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

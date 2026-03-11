import { useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ProgressionLineChartCard } from '@/features/athlete-progression/components/progression-line-chart-card';
import { useWellnessQuery } from '@/features/wellness/hooks/use-wellness-query';
import type { WellnessAggregation } from '@/features/wellness/types';

const WELLNESS_CHART_COLORS = {
  blue: '#60a5fa',
  blueAlt: '#60a5fa',
  blueDeep: '#c4b5fd',
  blueSoft: '#60a5fa',
  purpleSoft: '#c4b5fd',
  gray: '#f87171',
  graySoft: '#cbd5e1',
  grayDeep: '#dc2626',
} as const;

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
  const summaryCardClassName =
    'group relative overflow-hidden rounded-[1.4rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,rgba(96,165,250,0.18),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.98),rgba(2,6,23,0.94))] shadow-[0_20px_48px_rgba(2,6,23,0.34)]';
  const [days, setDays] = useState(30);
  const [aggregation, setAggregation] = useState<WellnessAggregation>('weekly');
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
            <CardContent className="grid gap-3 p-4">
              {summaryItems.map((item) => (
                <div
                  key={item.label}
                  className="relative overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.055),rgba(255,255,255,0.02))] px-3 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]"
                >
                  <div className="pointer-events-none absolute inset-x-3 top-0 h-px bg-gradient-to-r from-transparent via-sky-200/30 to-transparent" />
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200/72">{item.label}</p>
                      <p className="mt-1 text-[10px] uppercase tracking-[0.22em] text-slate-500/90">Latest</p>
                    </div>
                    <p className="text-xl font-semibold tracking-tight text-slate-50">{item.value}</p>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <div className="hidden gap-3 md:grid md:grid-cols-2 xl:grid-cols-5">
            {summaryItems.map((item) => (
              <Card key={item.label} className={summaryCardClassName}>
                <CardContent className="relative p-5">
                  <div className="pointer-events-none absolute inset-x-5 top-0 h-px bg-gradient-to-r from-transparent via-sky-200/34 to-transparent" />
                  <div className="absolute right-4 top-4 h-10 w-10 rounded-full bg-sky-300/8 blur-2xl transition-opacity duration-300 group-hover:opacity-100" />
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-sky-200/76">{item.label}</p>
                      <p className="mt-2 text-[10px] uppercase tracking-[0.26em] text-slate-500/90">Latest snapshot</p>
                    </div>
                    <div className="mt-1 h-2.5 w-2.5 rounded-full bg-sky-300/70 shadow-[0_0_14px_rgba(125,211,252,0.55)]" />
                  </div>
                  <p className="mt-6 text-3xl font-semibold tracking-[-0.03em] text-slate-50">{item.value}</p>
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
                  { key: 'sleep_score', label: 'Sleep Score', color: WELLNESS_CHART_COLORS.blue },
                  { key: 'training_readiness', label: 'Readiness', color: WELLNESS_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Stress & Resting HR"
                data={chartData}
                yLabel="Level"
                series={[
                  { key: 'stress_avg', label: 'Stress', color: WELLNESS_CHART_COLORS.grayDeep },
                  { key: 'resting_hr', label: 'RHR', color: WELLNESS_CHART_COLORS.blueAlt },
                ]}
              />

              <ProgressionLineChartCard
                title="Sleep Patterns"
                data={chartData}
                yLabel={aggregation === 'weekly' ? 'Avg Hours' : 'Hours'}
                series={[
                  { key: 'sleep_duration_h', label: 'Total', color: WELLNESS_CHART_COLORS.graySoft, dashed: true },
                  { key: 'deep_sleep_h', label: 'Deep', color: WELLNESS_CHART_COLORS.blue },
                  { key: 'rem_sleep_h', label: 'REM', color: WELLNESS_CHART_COLORS.purpleSoft },
                  { key: 'light_sleep_h', label: 'Light', color: WELLNESS_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Battery & HRV"
                data={chartData}
                yLabel="Index"
                series={[
                  { key: 'body_battery_end', label: 'Battery End', color: WELLNESS_CHART_COLORS.blue },
                  { key: 'body_battery_avg', label: 'Battery Avg', color: WELLNESS_CHART_COLORS.purpleSoft },
                  { key: 'hrv_status', label: 'HRV', color: WELLNESS_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Steps vs Calories"
                data={chartData}
                yLabel="Steps"
                rightAxisLabel="Calories"
                series={[
                  { key: 'steps', label: 'Steps', color: WELLNESS_CHART_COLORS.blue, yAxisId: 'left' },
                  { key: 'calories_total', label: 'Calories', color: WELLNESS_CHART_COLORS.gray, yAxisId: 'right' },
                ]}
              />
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

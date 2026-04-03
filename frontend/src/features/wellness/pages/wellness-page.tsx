import { useDeferredValue, useMemo, useState } from 'react';

import { AnalyticsToolbar } from '@/components/ui/analytics-toolbar';
import { QueryShell } from '@/components/ui/query-shell';
import {
  SecondaryPageHeader,
  SecondaryStatCard,
  SurfaceCard,
} from '@/components/ui/secondary-page';
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
  const [days, setDays] = useState(30);
  const [aggregation, setAggregation] = useState<WellnessAggregation>('weekly');
  const query = useWellnessQuery(days, aggregation);

  const chartData = useMemo(() => {
    return (query.data?.points ?? []).map((row) => ({
      ...row,
      label: formatDay(row.period_start, aggregation),
    }));
  }, [aggregation, query.data?.points]);
  const deferredChartData = useDeferredValue(chartData);

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
      <SecondaryPageHeader
        title="Wellness"
        description="Track recovery signals alongside training so the readiness context matches the rest of the app."
        actions={(
          <AnalyticsToolbar
            days={days}
            onDaysChange={setDays}
            aggregation={aggregation}
            onAggregationChange={setAggregation}
            compactLabels={false}
          />
        )}
      />

      <QueryShell isLoading={query.isLoading} isError={query.isError} error={query.error} errorTitle="Unable to load wellness">
      {query.data ? (
        <>
          <SurfaceCard contentClassName="p-4">
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-5">
                {summaryItems.map((item) => (
                  <SecondaryStatCard
                    key={item.label}
                    label={item.label}
                    meta="Latest snapshot"
                    value={item.value}
                    className="min-h-[104px]"
                  />
                ))}
              </div>
          </SurfaceCard>

          {chartData.length === 0 ? (
            <SurfaceCard contentClassName="p-8 text-sm text-slate-300/72">No wellness data available for this selection.</SurfaceCard>
          ) : (
            <div className="grid gap-4">
              <ProgressionLineChartCard
                title="Recovery Scores"
                data={deferredChartData}
                yLabel="Score"
                series={[
                  { key: 'sleep_score', label: 'Sleep Score', color: WELLNESS_CHART_COLORS.blue },
                  { key: 'training_readiness', label: 'Readiness', color: WELLNESS_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Stress & Resting HR"
                data={deferredChartData}
                yLabel="Level"
                series={[
                  { key: 'stress_avg', label: 'Stress', color: WELLNESS_CHART_COLORS.grayDeep },
                  { key: 'resting_hr', label: 'RHR', color: WELLNESS_CHART_COLORS.blueAlt },
                ]}
              />

              <ProgressionLineChartCard
                title="Sleep Patterns"
                data={deferredChartData}
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
                data={deferredChartData}
                yLabel="Index"
                series={[
                  { key: 'body_battery_end', label: 'Battery End', color: WELLNESS_CHART_COLORS.blue },
                  { key: 'body_battery_avg', label: 'Battery Avg', color: WELLNESS_CHART_COLORS.purpleSoft },
                  { key: 'hrv_status', label: 'HRV', color: WELLNESS_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Steps vs Calories"
                data={deferredChartData}
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
      </QueryShell>
    </section>
  );
}

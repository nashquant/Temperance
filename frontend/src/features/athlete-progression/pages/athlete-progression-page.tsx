import { useDeferredValue, useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { AnalyticsToolbar } from '@/components/ui/analytics-toolbar';
import { QueryShell } from '@/components/ui/query-shell';
import { SecondaryPageHeader } from '@/components/ui/secondary-page';
import { ProgressionLineChartCard } from '@/features/athlete-progression/components/progression-line-chart-card';
import { useAthleteProgressionQuery } from '@/features/athlete-progression/hooks/use-athlete-progression-query';
import type { ProgressionAggregation } from '@/features/athlete-progression/types/athlete-progression';

const PROGRESSION_CHART_COLORS = {
  blue: '#60a5fa',
  blueAlt: '#60a5fa',
  blueDeep: '#c4b5fd',
  blueSoft: '#60a5fa',
  purpleSoft: '#c4b5fd',
  gray: '#f87171',
  graySoft: '#cbd5e1',
  grayDeep: '#dc2626',
  redMuted: '#fb7185',
} as const;

function formatDay(iso: string, aggregation: ProgressionAggregation): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    ...(aggregation === 'daily' ? { weekday: 'short' as const } : {}),
  }).format(d);
}

export function AthleteProgressionPage(): JSX.Element {
  const [days, setDays] = useState(365);
  const [aggregation, setAggregation] = useState<ProgressionAggregation>('weekly');
  const [includeCurrentPeriod, setIncludeCurrentPeriod] = useState(false);

  const query = useAthleteProgressionQuery(days, aggregation, 'all');
  const currentWeekStart = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const dayOffset = (today.getDay() + 6) % 7;
    today.setDate(today.getDate() - dayOffset);
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  }, []);
  const currentDay = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
  }, []);

  const chartData = useMemo(() => {
    const rawPoints = query.data?.points ?? [];
    const filteredPoints = rawPoints.filter((row) => {
      if (includeCurrentPeriod) return true;
      if (aggregation === 'weekly') return row.period_start !== currentWeekStart;
      return row.period_start !== currentDay;
    });
    return filteredPoints.map((row) => ({
      ...row,
      label: formatDay(row.period_start, aggregation),
    }));
  }, [aggregation, currentDay, currentWeekStart, includeCurrentPeriod, query.data?.points]);

  const normalizedChartData = useMemo(() => {
    return chartData.map((row) => {
      const rawTarget = Number(row.target_tss ?? 0);
      return {
        ...row,
        stress_target_tss: rawTarget,
        pounding_target_tss: aggregation === 'weekly' ? rawTarget / 7 : rawTarget,
      };
    });
  }, [aggregation, chartData]);
  const deferredNormalizedChartData = useDeferredValue(normalizedChartData);
  const hasVdotData = useMemo(
    () => normalizedChartData.some((row) => Number.isFinite(Number(row.vdot_max ?? row.vdot)) && Number(row.vdot_max ?? row.vdot) > 0),
    [normalizedChartData],
  );
  const vdotEligibility = query.data?.vdot_eligibility;

  return (
    <section className="space-y-6">
      <SecondaryPageHeader
        title="Athlete Progression"
        description="Review long-term training load, fitness, and durability using the same page shell as the rest of the analytics tabs."
        actions={(
          <AnalyticsToolbar
            days={days}
            onDaysChange={setDays}
            aggregation={aggregation}
            onAggregationChange={setAggregation}
            compactLabels={false}
            currentPeriodControl={{
              value: includeCurrentPeriod,
              onValueChange: setIncludeCurrentPeriod,
              includeLabel: 'T',
              excludeLabel: 'T-1',
              includeAriaLabel: 'Include current period',
              excludeAriaLabel: 'Show completed periods only',
            }}
          />
        )}
      />

      <QueryShell isLoading={query.isLoading} isError={query.isError} error={query.error} errorTitle="Unable to load athlete progression">
      {query.data ? (
        <>
          {normalizedChartData.length === 0 ? (
            <Card><CardContent className="p-8 text-sm text-muted-foreground">No progression data available for this selection.</CardContent></Card>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              <ProgressionLineChartCard
                title="Stress Score: TSS vs rTSS"
                data={deferredNormalizedChartData}
                yLabel={aggregation === 'weekly' ? 'Weekly Stress' : 'Daily Stress'}
                targetKey="stress_target_tss"
                targetLabel={aggregation === 'weekly' ? 'Weekly Target' : 'Daily Target'}
                series={[
                  { key: 'tss', label: 'TSS', color: PROGRESSION_CHART_COLORS.blue },
                  { key: 'rtss', label: 'rTSS', color: PROGRESSION_CHART_COLORS.gray },
                ]}
              />

              <ProgressionLineChartCard
                title="Durability vs Pounding"
                data={deferredNormalizedChartData}
                yLabel="Load"
                targetKey="pounding_target_tss"
                targetLabel="Daily Target"
                series={[
                  { key: 'durability', label: 'Durability', color: PROGRESSION_CHART_COLORS.blueAlt },
                  { key: 'pounding', label: 'Pounding', color: PROGRESSION_CHART_COLORS.redMuted },
                ]}
              />

              <ProgressionLineChartCard
                title="Distance vs Dist Eqv"
                data={deferredNormalizedChartData}
                yLabel="km"
                targetKey="target_distance_km"
                targetLabel="Distance Target"
                series={[
                  { key: 'distance_km', label: 'Distance', color: PROGRESSION_CHART_COLORS.blueAlt },
                  { key: 'distance_eqv_km', label: 'Dist Eqv', color: PROGRESSION_CHART_COLORS.graySoft, dashed: true, strokeOpacity: 0.85, dotOpacity: 0.4 },
                ]}
              />

              <ProgressionLineChartCard
                title="Fitness vs Fatigue"
                data={deferredNormalizedChartData}
                yLabel="Load"
                series={[
                  { key: 'fitness', label: 'Fitness', color: PROGRESSION_CHART_COLORS.blue },
                  { key: 'fatigue', label: 'Fatigue', color: PROGRESSION_CHART_COLORS.grayDeep },
                ]}
              />

              <ProgressionLineChartCard
                title="Overreach vs Injury Risk"
                data={deferredNormalizedChartData}
                yLabel="Risk"
                series={[
                  { key: 'overreach', label: 'Overreach', color: PROGRESSION_CHART_COLORS.blue },
                  { key: 'injury_risk', label: 'Injury Risk', color: PROGRESSION_CHART_COLORS.grayDeep },
                ]}
              />

              <ProgressionLineChartCard
                title="Garmin TL vs Total Calories"
                data={deferredNormalizedChartData}
                yLabel="Training Load"
                rightAxisLabel="Calories"
                series={[
                  { key: 'training_load_garmin', label: 'Garmin TL', color: PROGRESSION_CHART_COLORS.blue, yAxisId: 'left' },
                  { key: 'calories_total', label: 'Calories', color: PROGRESSION_CHART_COLORS.gray, yAxisId: 'right' },
                ]}
              />

              <ProgressionLineChartCard
                title="Time in Zones"
                data={deferredNormalizedChartData}
                yLabel="Hours"
                series={[
                  { key: 'zone_low_aerobic_h', label: 'Easy', color: PROGRESSION_CHART_COLORS.blueSoft },
                  { key: 'zone_moderate_aerobic_h', label: 'Steady', color: PROGRESSION_CHART_COLORS.gray },
                  { key: 'zone_high_aerobic_h', label: 'Interval', color: PROGRESSION_CHART_COLORS.blueDeep },
                  { key: 'zone_total_h', label: 'Total', color: PROGRESSION_CHART_COLORS.graySoft, dashed: true },
                ]}
              />

              {hasVdotData ? (
                <ProgressionLineChartCard
                  title="VDOT Evolution"
                  data={deferredNormalizedChartData}
                  yLabel="VDOT"
                  series={[
                    { key: 'vdot', label: 'VDOT', color: PROGRESSION_CHART_COLORS.gray, dashed: true, strokeOpacity: 0.3, dotOpacity: 0.25, strokeWidth: 1.5 },
                    { key: 'vdot_max', label: 'VDOT Max', color: PROGRESSION_CHART_COLORS.blue, strokeWidth: 3 },
                  ]}
                />
              ) : (
                <Alert className="border-amber-300 text-amber-700 dark:border-amber-900 dark:text-amber-300">
                  <AlertTitle>VDOT Evolution</AlertTitle>
                  <AlertDescription>
                    No eligible activity found in this range. VDOT needs a single running/treadmill activity with distance and duration, and IF above 90%.
                    {vdotEligibility
                      ? ` Max single-activity IF: ${Math.round(Number(vdotEligibility.max_single_activity_if_pct || 0))}% · max single-activity rTSS: ${Math.round(Number(vdotEligibility.max_single_activity_rtss || 0))}.`
                      : ''}
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
        </>
      ) : null}
      </QueryShell>
    </section>
  );
}

import { useMemo, useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ProgressionLineChartCard } from '@/features/athlete-progression/components/progression-line-chart-card';
import { useAthleteProgressionQuery } from '@/features/athlete-progression/hooks/use-athlete-progression-query';
import type { ProgressionAggregation } from '@/features/athlete-progression/types/athlete-progression';

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

  const query = useAthleteProgressionQuery(days, aggregation, 'all');

  const chartData = useMemo(() => {
    return (query.data?.points ?? []).map((row) => ({
      ...row,
      label: formatDay(row.period_start, aggregation),
    }));
  }, [aggregation, query.data?.points]);

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
  const hasVdotData = useMemo(
    () => normalizedChartData.some((row) => Number.isFinite(Number(row.vdot_max ?? row.vdot)) && Number(row.vdot_max ?? row.vdot) > 0),
    [normalizedChartData],
  );
  const vdotEligibility = query.data?.vdot_eligibility;

  return (
    <section className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Athlete Progression</h1>
        </div>
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
          <Select value={aggregation} onValueChange={(value) => setAggregation(value as ProgressionAggregation)}>
            <SelectTrigger className="w-[120px]"><SelectValue placeholder="Aggregation" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="weekly">Weekly</SelectItem>
              <SelectItem value="daily">Daily</SelectItem>
            </SelectContent>
          </Select>
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
          <AlertTitle>Unable to load athlete progression</AlertTitle>
          <AlertDescription>{query.error instanceof Error ? query.error.message : 'Unexpected error.'}</AlertDescription>
        </Alert>
      ) : null}

      {!query.isLoading && !query.isError && query.data ? (
        <>
          {normalizedChartData.length === 0 ? (
            <Card><CardContent className="p-8 text-sm text-muted-foreground">No progression data available for this selection.</CardContent></Card>
          ) : (
            <div className="grid gap-4">
              <ProgressionLineChartCard
                title="Stress Score: TSS vs rTSS"
                data={normalizedChartData}
                yLabel={aggregation === 'weekly' ? 'Weekly Stress' : 'Daily Stress'}
                targetKey="stress_target_tss"
                targetLabel={aggregation === 'weekly' ? 'Weekly Target' : 'Daily Target'}
                series={[
                  { key: 'tss', label: 'TSS', color: '#60a5fa' },
                  { key: 'rtss', label: 'rTSS', color: '#f59e0b' },
                ]}
              />

              <ProgressionLineChartCard
                title="Bounce vs Pounding"
                data={normalizedChartData}
                yLabel="Load"
                targetKey="pounding_target_tss"
                targetLabel="Daily Target"
                series={[
                  { key: 'leg_elasticity', label: 'Bounce', color: '#22c55e' },
                  { key: 'pounding', label: 'Pounding', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Distance vs Dist Eqv"
                data={normalizedChartData}
                yLabel="km"
                targetKey="target_distance_km"
                targetLabel="Distance Target"
                series={[
                  { key: 'distance_km', label: 'Distance', color: '#38bdf8' },
                  { key: 'distance_eqv_km', label: 'Dist Eqv', color: '#22c55e' },
                ]}
              />

              <ProgressionLineChartCard
                title="Fitness vs Fatigue"
                data={normalizedChartData}
                yLabel="Load"
                series={[
                  { key: 'fitness', label: 'Fitness', color: '#22c55e' },
                  { key: 'fatigue', label: 'Fatigue', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Overreach vs Injury Risk"
                data={normalizedChartData}
                yLabel="Risk"
                series={[
                  { key: 'overreach', label: 'Overreach', color: '#60a5fa' },
                  { key: 'injury_risk', label: 'Injury Risk', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Garmin TL vs Total Calories"
                data={normalizedChartData}
                yLabel="Training Load"
                rightAxisLabel="Calories"
                series={[
                  { key: 'training_load_garmin', label: 'Garmin TL', color: '#60a5fa', yAxisId: 'left' },
                  { key: 'calories_total', label: 'Total Calories', color: '#f59e0b', yAxisId: 'right' },
                ]}
              />

              <ProgressionLineChartCard
                title="Time in Zones"
                data={normalizedChartData}
                yLabel="Hours"
                series={[
                  { key: 'zone_low_aerobic_h', label: 'Easy', color: '#60a5fa' },
                  { key: 'zone_moderate_aerobic_h', label: 'Steady', color: '#facc15' },
                  { key: 'zone_high_aerobic_h', label: 'Interval', color: '#ef4444' },
                  { key: 'zone_total_h', label: 'Total Time', color: '#cbd5e1', dashed: true },
                ]}
              />

              {hasVdotData ? (
                <ProgressionLineChartCard
                  title="VDOT Evolution"
                  data={normalizedChartData}
                  yLabel="VDOT"
                  series={[
                    { key: 'vdot', label: 'VDOT', color: '#94a3b8', dashed: true, strokeOpacity: 0.6, dotOpacity: 0.45 },
                    { key: 'vdot_max', label: 'VDOT Max', color: '#f97316' },
                  ]}
                />
              ) : (
                <Alert className="border-amber-300 text-amber-700 dark:border-amber-900 dark:text-amber-300">
                  <AlertTitle>VDOT Evolution</AlertTitle>
                  <AlertDescription>
                    No eligible activity found in this range. VDOT needs a single running/treadmill activity with distance and duration, and IF above 80%.
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
    </section>
  );
}

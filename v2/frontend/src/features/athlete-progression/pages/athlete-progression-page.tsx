import { useMemo, useState } from 'react';
import { RefreshCcw } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
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
import type {
  ProgressionActivityFilter,
  ProgressionAggregation,
} from '@/features/athlete-progression/types/athlete-progression';

interface InjuryOverlay {
  start: string;
  end: string;
  severity: 'injury' | 'light_injury';
  label?: string;
}

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
  const [activityFilter, setActivityFilter] = useState<ProgressionActivityFilter>('all');

  const query = useAthleteProgressionQuery(days, aggregation, activityFilter);

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
        stress_target_tss: aggregation === 'weekly' ? rawTarget : rawTarget / 7,
        pounding_target_tss: rawTarget / 7,
      };
    });
  }, [aggregation, chartData]);

  const injuryOverlays = useMemo(() => {
    const windows = query.data?.injury_windows ?? [];
    if (windows.length === 0 || normalizedChartData.length === 0) return [];
    const bucketSizeDays = aggregation === 'weekly' ? 7 : 1;
    const buckets = normalizedChartData
      .map((row) => {
        const start = String(row.period_start ?? '');
        if (!start) return null;
        const startDate = new Date(`${start}T00:00:00`);
        if (Number.isNaN(startDate.getTime())) return null;
        const endExclusive = new Date(startDate);
        endExclusive.setDate(endExclusive.getDate() + bucketSizeDays);
        return {
          key: start,
          startMs: startDate.getTime(),
          endExclusiveMs: endExclusive.getTime(),
        };
      })
      .filter((bucket): bucket is { key: string; startMs: number; endExclusiveMs: number } => bucket !== null)
      .sort((a, b) => a.startMs - b.startMs);
    if (buckets.length === 0) return [];

    const overlays: InjuryOverlay[] = [];
    windows.forEach((window) => {
      const start = String(window.start || '');
      const end = String(window.end || '');
      if (!start || !end) return;
      const startDate = new Date(`${start}T00:00:00`);
      const endDate = new Date(`${end}T00:00:00`);
      if (Number.isNaN(startDate.getTime()) || Number.isNaN(endDate.getTime())) return;
      const injuryStartMs = startDate.getTime();
      const injuryEndExclusive = new Date(endDate);
      injuryEndExclusive.setDate(injuryEndExclusive.getDate() + 1);
      const injuryEndExclusiveMs = injuryEndExclusive.getTime();
      if (injuryStartMs >= injuryEndExclusiveMs) return;

      const overlappingBuckets = buckets.filter(
        (bucket) => bucket.startMs < injuryEndExclusiveMs && bucket.endExclusiveMs > injuryStartMs,
      );
      if (overlappingBuckets.length === 0) return;

      overlays.push({
        start: overlappingBuckets[0].key,
        end: overlappingBuckets[overlappingBuckets.length - 1].key,
        severity: window.severity,
        label: window.label,
      });
    });
    return overlays;
  }, [normalizedChartData, query.data?.injury_windows]);

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
              <SelectItem value="90">90 days</SelectItem>
              <SelectItem value="180">180 days</SelectItem>
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
          <Select value={activityFilter} onValueChange={(value) => setActivityFilter(value as ProgressionActivityFilter)}>
            <SelectTrigger className="w-[160px]"><SelectValue placeholder="Activity" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Activities</SelectItem>
              <SelectItem value="all_running">All Running</SelectItem>
              <SelectItem value="running">Running</SelectItem>
              <SelectItem value="treadmill">Treadmill</SelectItem>
              <SelectItem value="cycling">Cycling</SelectItem>
              <SelectItem value="elliptical">Elliptical</SelectItem>
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
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'tss', label: 'TSS', color: '#60a5fa' },
                  { key: 'rtss', label: 'rTSS', color: '#f59e0b' },
                ]}
              />

              <ProgressionLineChartCard
                title="Leg Elasticity vs Pounding"
                data={normalizedChartData}
                yLabel="Load"
                targetKey="pounding_target_tss"
                targetLabel="Daily Target"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'leg_elasticity', label: 'Leg Elasticity', color: '#22c55e' },
                  { key: 'pounding', label: 'Pounding', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Distance vs Distance Eqv"
                data={normalizedChartData}
                yLabel="km"
                targetKey="target_distance_km"
                targetLabel="Distance Target"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'distance_km', label: 'Distance', color: '#38bdf8' },
                  { key: 'distance_eqv_km', label: 'Distance Eqv', color: '#22c55e' },
                ]}
              />

              <ProgressionLineChartCard
                title="Fitness vs Fatigue"
                data={normalizedChartData}
                yLabel="Load"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'fitness', label: 'Fitness', color: '#22c55e' },
                  { key: 'fatigue', label: 'Fatigue', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Overreach vs Injury Risk"
                data={normalizedChartData}
                yLabel="Risk"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'overreach', label: 'Overreach', color: '#60a5fa' },
                  { key: 'injury_risk', label: 'Injury Risk', color: '#ef4444' },
                ]}
              />

              <ProgressionLineChartCard
                title="Garmin Training Load vs Total Calories"
                data={normalizedChartData}
                yLabel="Training Load"
                rightAxisLabel="Calories"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'training_load_garmin', label: 'Garmin Training Load', color: '#60a5fa', yAxisId: 'left' },
                  { key: 'calories_total', label: 'Total Calories', color: '#f59e0b', yAxisId: 'right' },
                ]}
              />

              <ProgressionLineChartCard
                title="HR Zone Time (hours)"
                data={normalizedChartData}
                yLabel="Hours"
                injuryOverlays={injuryOverlays}
                series={[
                  { key: 'zone_low_aerobic_h', label: 'Low Aerobic', color: '#60a5fa' },
                  { key: 'zone_moderate_aerobic_h', label: 'Moderate Aerobic', color: '#facc15' },
                  { key: 'zone_high_aerobic_h', label: 'High Aerobic', color: '#ef4444' },
                  { key: 'zone_total_h', label: 'Total Time', color: '#cbd5e1', dashed: true },
                ]}
              />
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

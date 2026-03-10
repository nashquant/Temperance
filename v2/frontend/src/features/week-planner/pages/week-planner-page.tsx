import { useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { useCustomActivitiesQuery } from '@/features/custom-activities/hooks/use-custom-activities-query';
import { PlannedWeekChart } from '@/features/plan-activities/components/planned-week-chart';
import { PlanActivitiesSection } from '@/features/plan-activities/pages/plan-activities-page';
import { WeeklyOutlookSection } from '@/features/weekly-outlook/pages/weekly-outlook-page';

export function WeekPlannerPage(): JSX.Element {
  const customActivitiesQuery = useCustomActivitiesQuery();
  const [selectedWeekStart, setSelectedWeekStart] = useState('');
  const customWeeks = customActivitiesQuery.data?.weeks ?? [];
  const selectedWeek = useMemo(() => {
    if (customWeeks.length === 0) return null;
    if (!selectedWeekStart) return customWeeks[0];
    return customWeeks.find((week) => week.week_start === selectedWeekStart) ?? customWeeks[0];
  }, [customWeeks, selectedWeekStart]);

  const rowsForWeek = useMemo(() => {
    if (!selectedWeek) return [];
    const start = new Date(`${selectedWeek.week_start}T00:00:00`);
    const end = new Date(`${selectedWeek.week_end}T23:59:59`);
    return (customActivitiesQuery.data?.rows ?? []).filter((row) => {
      const day = new Date(`${row.day_utc}T12:00:00`);
      return day >= start && day <= end;
    });
  }, [customActivitiesQuery.data?.rows, selectedWeek]);

  const dailySeries = useMemo(() => {
    if (!selectedWeek) return { tss: [], rtss: [], distance_eqv_km: [] };
    const start = new Date(`${selectedWeek.week_start}T00:00:00`);
    const labels = Array.from({ length: 7 }).map((_, index) => {
      const day = new Date(start);
      day.setDate(start.getDate() + index);
      const iso = day.toISOString().slice(0, 10);
      const dayLabel = new Intl.DateTimeFormat('en-US', { weekday: 'short', day: 'numeric', month: 'short' }).format(day);
      return { iso, dayLabel };
    });
    const mapMetric = (metric: 'tss' | 'rtss' | 'distance_eqv_km') =>
      labels.map((label) => ({
        dayLabel: label.dayLabel,
        value: rowsForWeek
          .filter((row) => row.day_utc === label.iso)
          .reduce((sum, row) => sum + Number(row[metric] ?? 0), 0),
        tssBasis: rowsForWeek
          .filter((row) => row.day_utc === label.iso)
          .reduce((sum, row) => sum + Number(row.tss ?? 0), 0),
      }));
    return {
      tss: mapMetric('tss'),
      rtss: mapMetric('rtss'),
      distance_eqv_km: mapMetric('distance_eqv_km'),
    };
  }, [rowsForWeek, selectedWeek]);

  return (
    <section className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Week Planner</h1>
        <p className="mt-1 text-sm text-muted-foreground">Weekly outlook plus planned activities in one place.</p>
      </div>

      <WeeklyOutlookSection embedded />

      <Separator />

      <PlanActivitiesSection embedded />

      <Separator />

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-xl font-semibold tracking-tight">Custom Activities (Selected Week)</h2>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {selectedWeek ? (
              <>
                <Badge variant="outline" className="rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide">
                  {selectedWeek.custom_activities} activities
                </Badge>
                <Badge variant="outline" className="rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide">
                  TSS {Math.round(selectedWeek.tss)}
                </Badge>
                <Badge variant="outline" className="rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide">
                  rTSS {Math.round(selectedWeek.rtss)}
                </Badge>
                <Badge variant="outline" className="rounded-full px-2.5 py-1 text-[10px] font-semibold tracking-wide">
                  Dist {Math.round(selectedWeek.distance_eqv_km)} kmeq
                </Badge>
              </>
            ) : null}
            <Select
              value={selectedWeek?.week_start ?? ''}
              onValueChange={(value) => setSelectedWeekStart(value)}
              disabled={customWeeks.length === 0}
            >
              <SelectTrigger className="w-[240px]">
                <SelectValue placeholder="Select week" />
              </SelectTrigger>
              <SelectContent>
                {customWeeks.map((week) => (
                  <SelectItem key={week.week_start} value={week.week_start}>
                    {week.week_start} - {week.week_end}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {selectedWeek ? (
          <>
            <div className="grid gap-4 xl:grid-cols-3">
              <PlannedWeekChart data={dailySeries.tss} metric="tss" />
              <PlannedWeekChart data={dailySeries.distance_eqv_km} metric="distance_eqv_km" />
              <PlannedWeekChart data={dailySeries.rtss} metric="rtss" />
            </div>
          </>
        ) : (
          <p className="text-sm text-muted-foreground">No custom activities found.</p>
        )}
      </section>
    </section>
  );
}

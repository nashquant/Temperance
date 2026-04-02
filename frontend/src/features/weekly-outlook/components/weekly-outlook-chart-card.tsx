import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { ChartCard } from '@/components/ui/chart-card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { MetricSelector } from '@/features/weekly-outlook/components/metric-selector';
import type { WeeklyMetric, WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookChartCardProps {
  data: WeeklyOutlookViewModel;
  metric: WeeklyMetric;
  onMetricChange: (value: WeeklyMetric) => void;
  weekView: 'current' | 'previous';
  onWeekViewChange: (value: 'current' | 'previous') => void;
}

export function WeeklyOutlookChartCard({
  data,
  metric,
  onMetricChange,
  weekView,
  onWeekViewChange,
}: WeeklyOutlookChartCardProps): JSX.Element {
  return (
    <ChartCard
      toolbar={
        <>
          <MetricSelector value={metric} onValueChange={onMetricChange} showLabel={false} compact />
          <ToggleGroup
            type="single"
            value={weekView}
            onValueChange={(next) => {
              if (next) onWeekViewChange(next as 'current' | 'previous');
            }}
            className="w-auto"
          >
            <ToggleGroupItem value="current" size="sm" className="h-7">Curr</ToggleGroupItem>
            <ToggleGroupItem value="previous" size="sm" className="h-7">Prev</ToggleGroupItem>
          </ToggleGroup>
        </>
      }
    >
        <GroupedBarChart
          data={data.chartRows}
          metric={metric}
          currentLabel="Current week"
          compareLabel={data.compareLabel}
          heightClassName="h-[220px]"
        />
    </ChartCard>
  );
}

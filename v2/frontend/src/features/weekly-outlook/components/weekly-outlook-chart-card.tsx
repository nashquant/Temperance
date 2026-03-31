import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Card, CardContent } from '@/components/ui/card';
import { secondaryPageSurfaceClassName } from '@/components/ui/secondary-page';
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
    <Card className={secondaryPageSurfaceClassName}>
      <CardContent className="px-4 pb-4 pt-5">
        <div className="mb-3 flex items-start justify-between gap-3">
          <MetricSelector value={metric} onValueChange={onMetricChange} showLabel={false} compact />
          <ToggleGroup
            type="single"
            value={weekView}
            onValueChange={(next) => {
              if (next) onWeekViewChange(next as 'current' | 'previous');
            }}
            className="w-auto"
          >
            <ToggleGroupItem
              value="current"
              size="sm"
              className="h-7"
            >
              Curr
            </ToggleGroupItem>
            <ToggleGroupItem
              value="previous"
              size="sm"
              className="h-7"
            >
              Prev
            </ToggleGroupItem>
          </ToggleGroup>
        </div>
        <GroupedBarChart
          data={data.chartRows}
          metric={metric}
          currentLabel="Current week"
          compareLabel={data.compareLabel}
          heightClassName="h-[220px]"
        />
      </CardContent>
    </Card>
  );
}

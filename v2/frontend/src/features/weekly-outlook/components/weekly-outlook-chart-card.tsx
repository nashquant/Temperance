import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { secondaryPageInsetClassName, secondaryPageSurfaceClassName } from '@/components/ui/secondary-page';
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
          <div className={`${secondaryPageInsetClassName} inline-flex p-1`}>
            <Button
              variant={weekView === 'current' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 rounded-md px-2.5 text-xs"
              onClick={() => onWeekViewChange('current')}
            >
              Curr
            </Button>
            <Button
              variant={weekView === 'previous' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 rounded-md px-2.5 text-xs"
              onClick={() => onWeekViewChange('previous')}
            >
              Prev
            </Button>
          </div>
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

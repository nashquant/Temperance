import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="px-4 pb-4 pt-5">
        <div className="mb-3 flex items-start justify-between gap-3">
          <MetricSelector value={metric} onValueChange={onMetricChange} showLabel={false} compact />
          <div className="inline-flex rounded-lg border border-white/10 bg-black/15 p-1">
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

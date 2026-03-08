import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Card, CardContent } from '@/components/ui/card';
import type { WeeklyMetric, WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookChartCardProps {
  data: WeeklyOutlookViewModel;
  metric: WeeklyMetric;
}

export function WeeklyOutlookChartCard({ data, metric }: WeeklyOutlookChartCardProps): JSX.Element {
  return (
    <Card>
      <CardContent className="p-4">
        <GroupedBarChart
          data={data.chartRows}
          metric={metric}
          currentLabel="Current week"
          compareLabel={data.compareLabel}
        />
      </CardContent>
    </Card>
  );
}

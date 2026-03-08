import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { WeeklyMetric, WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookChartCardProps {
  data: WeeklyOutlookViewModel;
  metric: WeeklyMetric;
}

export function WeeklyOutlookChartCard({ data, metric }: WeeklyOutlookChartCardProps): JSX.Element {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Daily comparison</CardTitle>
        <CardDescription>Side-by-side bars for current week and {data.compareLabel.toLowerCase()}.</CardDescription>
      </CardHeader>
      <CardContent>
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

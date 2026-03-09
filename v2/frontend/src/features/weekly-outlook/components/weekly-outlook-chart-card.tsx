import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Card, CardContent } from '@/components/ui/card';
import type { WeeklyMetric, WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookChartCardProps {
  data: WeeklyOutlookViewModel;
  metric: WeeklyMetric;
}

export function WeeklyOutlookChartCard({ data, metric }: WeeklyOutlookChartCardProps): JSX.Element {
  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
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

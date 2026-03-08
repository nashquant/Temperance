import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { type WeeklyMetric, type WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';
import { formatMetricValue } from '@/features/weekly-outlook/utils/formatters';

interface WeeklySummaryCardsProps {
  data: WeeklyOutlookViewModel;
  selectedMetric: WeeklyMetric;
}

export function WeeklySummaryCards({ data, selectedMetric }: WeeklySummaryCardsProps): JSX.Element {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground">Current week total</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatMetricValue(data.totals.current, selectedMetric)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground">Comparison total</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatMetricValue(data.totals.compare, selectedMetric)}</p>
          <p className="mt-1 text-xs text-muted-foreground">{data.compareLabel}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground">Remaining to plan</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{formatMetricValue(data.totals.remainingToGo, selectedMetric)}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm text-muted-foreground">Goal progress</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">{data.totals.progressPct}%</p>
          <p className="mt-1 text-xs text-muted-foreground">
            {data.totals.projectedFinish !== null
              ? `Projected: ${formatMetricValue(data.totals.projectedFinish, selectedMetric)}`
              : 'Projection not available'}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

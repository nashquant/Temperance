import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { type WeeklyMetric, type WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';
import { formatMetricValue } from '@/features/weekly-outlook/utils/formatters';

interface WeeklySummaryCardsProps {
  data: WeeklyOutlookViewModel;
  selectedMetric: WeeklyMetric;
}

export function WeeklySummaryCards({ data, selectedMetric }: WeeklySummaryCardsProps): JSX.Element {
  const comparisonDeltaPct =
    data.totals.compare > 0 ? Math.round(((data.totals.current - data.totals.compare) / data.totals.compare) * 100) : null;
  const comparisonDeltaLabel =
    comparisonDeltaPct === null ? null : `${comparisonDeltaPct > 0 ? '+' : ''}${comparisonDeltaPct}%`;
  const surfaceClassName =
    'overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]';
  const titleClassName = 'text-sm text-slate-300/80';
  const valueClassName = 'text-2xl font-semibold text-foreground';
  const metaClassName = 'mt-1 text-xs text-slate-300/70';

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card className={surfaceClassName}>
        <CardHeader className="pb-3">
          <CardTitle className={titleClassName}>Current week total</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={valueClassName}>{formatMetricValue(data.totals.current, selectedMetric)}</p>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardHeader className="pb-3">
          <CardTitle className={titleClassName}>Comparison total</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={valueClassName}>
            {formatMetricValue(data.totals.compare, selectedMetric)}
            {comparisonDeltaLabel ? (
              <span className="ml-2 text-base font-medium text-slate-300/72">({comparisonDeltaLabel})</span>
            ) : null}
          </p>
          <p className={metaClassName}>{data.compareLabel}</p>
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardHeader className="pb-3">
          <CardTitle className={titleClassName}>Remaining to go</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={valueClassName}>
            {data.compare === 'planned' ? formatMetricValue(data.totals.remainingToGo, selectedMetric) : '-'}
          </p>
          {data.compare === 'planned' && data.totals.estimatedFatigueEow !== null ? (
            <p className={metaClassName}>
              {`Estimated fatigue EoW: ${Math.round(data.totals.estimatedFatigueEow)} TSS`}
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card className={surfaceClassName}>
        <CardHeader className="pb-3">
          <CardTitle className={titleClassName}>Goal progress</CardTitle>
        </CardHeader>
        <CardContent>
          <p className={valueClassName}>{data.totals.progressPct}%</p>
          {data.compare === 'planned' ? (
            <p className={metaClassName}>
              {data.totals.projectedFinish !== null
                ? `Projected: ${formatMetricValue(data.totals.projectedFinish, selectedMetric)}`
                : 'Projection not available'}
            </p>
          ) : null}
        </CardContent>
      </Card>

    </div>
  );
}

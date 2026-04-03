import { SecondaryPageSectionCard, SecondaryStatCard } from '@/components/ui/secondary-page';
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
  const summaryItems = [
    {
      title: 'Current week total',
      value: formatMetricValue(data.totals.current, selectedMetric),
      meta: null,
    },
    {
      title: 'Comparison total',
      value: formatMetricValue(data.totals.compare, selectedMetric),
      valueSuffix: comparisonDeltaLabel ? `(${comparisonDeltaLabel})` : null,
      meta: data.compareLabel,
    },
    {
      title: 'Remaining to go',
      value: data.compare === 'planned' ? formatMetricValue(data.totals.remainingToGo, selectedMetric) : '-',
      meta:
        data.compare === 'planned' && data.totals.estimatedFatigueEow !== null
          ? `Estimated fatigue EoW: ${Math.round(data.totals.estimatedFatigueEow)} TSS`
          : null,
    },
    {
      title: 'Goal progress',
      value: `${data.totals.progressPct}%`,
      meta:
        data.compare === 'planned'
          ? data.totals.projectedFinish !== null
            ? `Projected: ${formatMetricValue(data.totals.projectedFinish, selectedMetric)}`
            : 'Projection not available'
          : null,
    },
  ];

  return (
    <SecondaryPageSectionCard contentClassName="p-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {summaryItems.map((item) => (
          <SecondaryStatCard
            key={item.title}
            label={item.title}
            meta={item.meta}
            value={
              <>
                {item.value}
                {item.valueSuffix ? <span className="ml-2 text-sm font-medium text-slate-300/72">{item.valueSuffix}</span> : null}
              </>
            }
          />
        ))}
      </div>
    </SecondaryPageSectionCard>
  );
}

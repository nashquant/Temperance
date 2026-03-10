import { Card, CardContent } from '@/components/ui/card';
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
    <>
      <Card className={`${surfaceClassName} md:hidden`}>
        <CardContent className="grid gap-2 p-4">
          {summaryItems.map((item) => (
            <div
              key={item.title}
              className="rounded-xl border border-white/8 bg-white/[0.03] px-3 py-2.5"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200/74">{item.title}</p>
                <p className="text-lg font-semibold text-slate-50 text-right">
                  {item.value}
                  {item.valueSuffix ? <span className="ml-1 text-sm font-medium text-slate-300/72">{item.valueSuffix}</span> : null}
                </p>
              </div>
              {item.meta ? <p className="mt-1 text-[11px] text-slate-300/66">{item.meta}</p> : null}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card className={`${surfaceClassName} hidden md:block`}>
        <CardContent className="p-4">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {summaryItems.map((item) => (
              <div key={item.title} className="rounded-xl border border-white/10 bg-black/15 p-3">
                <p className="text-xs text-slate-300/72">{item.title}</p>
                <p className="font-medium text-foreground">
                  {item.value}
                  {item.valueSuffix ? <span className="ml-2 text-sm font-medium text-slate-300/72">{item.valueSuffix}</span> : null}
                </p>
                {item.meta ? <p className="mt-1 text-xs text-slate-300/70">{item.meta}</p> : null}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </>
  );
}

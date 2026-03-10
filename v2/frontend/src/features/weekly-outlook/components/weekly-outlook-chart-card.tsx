import { useState } from 'react';

import { GroupedBarChart } from '@/components/charts/grouped-bar-chart';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import type { WeeklyMetric, WeeklyOutlookViewModel } from '@/features/weekly-outlook/types/weekly-outlook';

interface WeeklyOutlookChartCardProps {
  data: WeeklyOutlookViewModel;
  metric: WeeklyMetric;
}

export function WeeklyOutlookChartCard({ data, metric }: WeeklyOutlookChartCardProps): JSX.Element {
  const metricLabel = metric === 'distance' ? 'Distance' : metric === 'rtss' ? 'rTSS' : 'TSS';
  const [visibleSeries, setVisibleSeries] = useState<'current' | 'compare'>('current');

  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-foreground">{`Weekly ${metricLabel}`}</p>
          </div>
          <div className="inline-flex rounded-lg border border-white/10 bg-black/15 p-1">
            <Button
              variant={visibleSeries === 'current' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 rounded-md px-2.5 text-xs"
              onClick={() => setVisibleSeries('current')}
            >
              Current
            </Button>
            <Button
              variant={visibleSeries === 'compare' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 rounded-md px-2.5 text-xs"
              onClick={() => setVisibleSeries('compare')}
            >
              {data.compareLabel}
            </Button>
          </div>
        </div>
        <GroupedBarChart
          data={data.chartRows}
          metric={metric}
          currentLabel="Current week"
          compareLabel={data.compareLabel}
          visibleSeries={visibleSeries}
        />
      </CardContent>
    </Card>
  );
}

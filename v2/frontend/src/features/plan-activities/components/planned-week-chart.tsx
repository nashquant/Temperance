import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { Card, CardContent } from '@/components/ui/card';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedWeekChartRow {
  dayLabel: string;
  value: number;
}

interface PlannedWeekChartProps {
  data: PlannedWeekChartRow[];
  metric: PlannedMetricView;
}

function metricLabel(metric: PlannedMetricView): string {
  if (metric === 'rtss') return 'rTSS';
  if (metric === 'distance_eqv_km') return 'Dist Eqv (km)';
  if (metric === 'if_proxy_pct') return 'IF (%)';
  return 'TSS';
}

function formatValue(value: number, metric: PlannedMetricView): string {
  if (metric === 'distance_eqv_km') return `${value.toFixed(1)} km`;
  if (metric === 'if_proxy_pct') return `${value.toFixed(0)}%`;
  return `${Math.round(value)}`;
}

export function PlannedWeekChart({ data, metric }: PlannedWeekChartProps): JSX.Element {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} label={{ value: metricLabel(metric), angle: -90, position: 'insideLeft' }} />
              <Tooltip formatter={(value: number) => formatValue(value, metric)} />
              <Bar dataKey="value" fill="#34d399" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

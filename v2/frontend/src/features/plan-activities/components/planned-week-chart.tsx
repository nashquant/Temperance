import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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
  const valueLabelFormatter = (value: number) => (value > 0 ? formatValue(value, metric) : '');
  const getBarFill = (value: number): string => {
    if (metric !== 'tss' && metric !== 'rtss') return '#34d399';
    if (value > 150) return '#a855f7';
    if (value > 120) return '#ef4444';
    if (value > 80) return '#f97316';
    if (value > 50) return '#facc15';
    return '#22c55e';
  };

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
              <Bar dataKey="value" fill="#34d399" radius={[6, 6, 0, 0]}>
                {data.map((row) => (
                  <Cell key={`planned-week-bar-${row.dayLabel}`} fill={getBarFill(row.value)} />
                ))}
                <LabelList
                  dataKey="value"
                  position="top"
                  formatter={valueLabelFormatter}
                  style={{ fontSize: 13, fontWeight: 700, fill: '#e2e8f0' }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

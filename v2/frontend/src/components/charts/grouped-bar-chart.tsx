import { memo, useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { formatMetricValue } from '@/features/weekly-outlook/utils/formatters';

interface GroupedBarChartRow {
  label: string;
  current: number;
  compare: number;
}

interface GroupedBarChartProps {
  data: GroupedBarChartRow[];
  metric: 'tss' | 'rtss' | 'distance';
  currentLabel: string;
  compareLabel: string;
}

function GroupedBarChartComponent({
  data,
  metric,
  currentLabel,
  compareLabel,
}: GroupedBarChartProps): JSX.Element {
  const axisLabel = metric === 'distance' ? 'Distance (km)' : metric === 'rtss' ? 'rTSS' : 'TSS';

  const series = useMemo(
    () => [
      { dataKey: 'current', name: currentLabel, fill: '#3b82f6' },
      { dataKey: 'compare', name: compareLabel, fill: '#94a3b8' },
    ],
    [compareLabel, currentLabel],
  );

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={4} barCategoryGap="20%">
          <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} label={{ value: axisLabel, angle: -90, position: 'insideLeft' }} />
          <Tooltip
            formatter={(value: number) => formatMetricValue(value, metric)}
            contentStyle={{ borderRadius: '0.65rem', borderColor: '#cbd5e1' }}
          />
          <Legend />
          {series.map((item) => (
            <Bar key={item.dataKey} dataKey={item.dataKey} name={item.name} fill={item.fill} radius={[6, 6, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export const GroupedBarChart = memo(GroupedBarChartComponent);

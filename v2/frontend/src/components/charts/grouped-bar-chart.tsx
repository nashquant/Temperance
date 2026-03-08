import { memo, useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, LabelList, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

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
  const valueLabelFormatter = (value: number) => {
    if (value <= 0) return '';
    if (metric === 'distance') return value.toFixed(1);
    return String(Math.round(value));
  };

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
            <Bar key={item.dataKey} dataKey={item.dataKey} name={item.name} fill={item.fill} radius={[6, 6, 0, 0]}>
              <LabelList
                dataKey={item.dataKey}
                position="top"
                formatter={valueLabelFormatter}
                style={{ fontSize: 13, fontWeight: 700, fill: '#e2e8f0' }}
              />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export const GroupedBarChart = memo(GroupedBarChartComponent);

import { memo, useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

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

function GroupedBarTooltip({
  active,
  label,
  payload,
  metric,
}: TooltipProps<ValueType, NameType> & { metric: GroupedBarChartProps['metric'] }): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div className="min-w-[190px] rounded-lg border border-border/80 bg-background/95 p-3 shadow-2xl backdrop-blur">
      <p className="mb-2 text-xs font-semibold text-foreground">{String(label || '')}</p>
      <div className="space-y-1.5">
        {payload.map((entry) => (
          <div key={`${entry.name}-${entry.dataKey}`} className="flex items-center justify-between gap-3 text-xs">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="inline-block h-2 w-2 shrink-0 rounded-full"
                style={{ backgroundColor: String(entry.color || '#94a3b8') }}
              />
              <span className="truncate text-muted-foreground">{String(entry.name || '-')}</span>
            </div>
            <span className="shrink-0 font-semibold text-foreground">
              {formatMetricValue(Number(entry.value || 0), metric)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
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

  const getCurrentBarFill = (value: number): string => {
    if (metric !== 'tss' && metric !== 'rtss') return '#3b82f6';
    if (value > 150) return '#a855f7';
    if (value > 120) return '#ef4444';
    if (value > 80) return '#f97316';
    if (value > 50) return '#facc15';
    return '#22c55e';
  };

  return (
    <div className="h-[360px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={4} barCategoryGap="20%">
          <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} label={{ value: axisLabel, angle: -90, position: 'insideLeft' }} />
          <Tooltip
            content={<GroupedBarTooltip metric={metric} />}
            cursor={{ fill: 'rgba(148, 163, 184, 0.12)' }}
          />
          {series.map((item) => (
            <Bar key={item.dataKey} dataKey={item.dataKey} name={item.name} fill={item.fill} radius={[6, 6, 0, 0]}>
              {item.dataKey === 'current'
                ? data.map((row) => <Cell key={`${row.label}-current`} fill={getCurrentBarFill(row.current)} />)
                : null}
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

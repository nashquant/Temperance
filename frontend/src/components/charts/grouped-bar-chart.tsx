import { memo, useId, useMemo } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { intensityHexFromThreshold } from '@/features/dashboard/utils/intensity-palette';
import { formatMetricValue } from '@/features/weekly-outlook/utils/formatters';

interface GroupedBarChartRow {
  label: string;
  current: number;
  compare: number;
  currentTss: number;
}

interface GroupedBarChartProps {
  data: GroupedBarChartRow[];
  metric: 'tss' | 'rtss' | 'distance';
  currentLabel: string;
  compareLabel: string;
  heightClassName?: string;
}

function GroupedBarValueLabel({
  x,
  y,
  width,
  value,
  metric,
}: {
  x?: number | string;
  y?: number | string;
  width?: number | string;
  value?: number | string;
  metric: GroupedBarChartProps['metric'];
}): JSX.Element | null {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  const labelX = Number(x ?? 0) + Number(width ?? 0) / 2;
  const labelY = Math.max(Number(y ?? 0) - 10, 14);
  const text = metric === 'distance' ? numeric.toFixed(1) : String(Math.round(numeric));
  return (
    <text x={labelX} y={labelY} textAnchor="middle" fontSize={13} fontWeight={700} fill="#e2e8f0">
      {text}
    </text>
  );
}

function GroupedBarTooltip({
  active,
  label,
  payload,
  metric,
  getCurrentBarFill,
  compareFill,
}: TooltipProps<ValueType, NameType> & {
  metric: GroupedBarChartProps['metric'];
  getCurrentBarFill: (row: GroupedBarChartRow) => string;
  compareFill: string;
}): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as GroupedBarChartRow | undefined;

  return (
    <div className="min-w-[190px] rounded-xl border border-sky-300/15 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-3 shadow-2xl backdrop-blur">
      <p className="mb-2 text-xs font-semibold text-foreground">{String(label || '')}</p>
      <div className="space-y-1.5">
        {payload.map((entry) => {
          const isCurrent = String(entry.dataKey) === 'current';
          const color = isCurrent
            ? (row ? getCurrentBarFill(row) : String(entry.color || '#94a3b8'))
            : compareFill;
          return (
          <div key={`${entry.name}-${entry.dataKey}`} className="flex items-center justify-between gap-3 text-xs">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-[3px] border border-white/15"
                style={
                  isCurrent
                    ? { backgroundColor: color }
                    : {
                        backgroundColor: `${color}33`,
                        backgroundImage: `repeating-linear-gradient(135deg, ${color} 0 3px, transparent 3px 6px)`,
                      }
                }
              />
              <span className="truncate" style={{ color }}>{String(entry.name || '-')}</span>
            </div>
            <span className="shrink-0 font-semibold text-foreground">
              {formatMetricValue(Number(entry.value || 0), metric)}
            </span>
          </div>
        )})}
      </div>
    </div>
  );
}

function GroupedBarChartComponent({
  data,
  metric,
  currentLabel,
  compareLabel,
  heightClassName = 'h-[360px]',
}: GroupedBarChartProps): JSX.Element {
  const comparePatternId = useId().replace(/:/g, '');

  const series = useMemo(
    () => [
      { dataKey: 'current', name: currentLabel, fill: '#3b82f6' },
      { dataKey: 'compare', name: compareLabel, fill: '#94a3b8' },
    ],
    [compareLabel, currentLabel],
  );

  const getCurrentBarFill = (row: GroupedBarChartRow): string => {
    const thresholdBasis = metric === 'distance' ? row.currentTss : row.current;
    if (metric !== 'tss' && metric !== 'rtss' && metric !== 'distance') return '#3b82f6';
    return intensityHexFromThreshold(thresholdBasis);
  };

  return (
    <div className={`${heightClassName} w-full`}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barGap={4} barCategoryGap="20%" margin={{ top: 34, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <pattern id={comparePatternId} patternUnits="userSpaceOnUse" width="10" height="10" patternTransform="rotate(135)">
              <rect width="10" height="10" fill={series[1].fill} fillOpacity="0.18" />
              <line x1="0" y1="0" x2="0" y2="10" stroke={series[1].fill} strokeOpacity="0.62" strokeWidth="3" />
            </pattern>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(125,211,252,0.14)" />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: '#cbd5e1' }} axisLine={{ stroke: 'rgba(148,163,184,0.18)' }} tickLine={false} />
          <YAxis hide axisLine={false} tickLine={false} />
          <Tooltip
            content={
              <GroupedBarTooltip
                metric={metric}
                getCurrentBarFill={getCurrentBarFill}
                compareFill={series[1].fill}
              />
            }
            cursor={{ fill: 'rgba(56, 189, 248, 0.08)' }}
          />
          {series.map((item) => (
            <Bar key={item.dataKey} dataKey={item.dataKey} name={item.name} fill={item.fill} radius={[6, 6, 0, 0]}>
              {item.dataKey === 'current'
                ? data.map((row) => <Cell key={`${row.label}-current`} fill={getCurrentBarFill(row)} />)
                : data.map((row) => (
                    <Cell
                      key={`${row.label}-compare`}
                      fill={`url(#${comparePatternId})`}
                      stroke="rgba(226,232,240,0.22)"
                      strokeWidth={1}
                    />
                  ))}
              <LabelList
                dataKey={item.dataKey}
                position="top"
                content={(props) => <GroupedBarValueLabel {...props} metric={metric} />}
              />
            </Bar>
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export const GroupedBarChart = memo(GroupedBarChartComponent);

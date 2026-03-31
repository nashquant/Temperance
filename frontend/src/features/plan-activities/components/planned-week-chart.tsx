import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { Card, CardContent } from '@/components/ui/card';
import { secondaryPageSurfaceClassName } from '@/components/ui/secondary-page';
import { intensityHexFromThreshold } from '@/features/dashboard/utils/intensity-palette';
import { PlannedMetricSelector } from '@/features/plan-activities/components/planned-metric-selector';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedWeekChartRow {
  dayLabel: string;
  value: number;
  tssBasis: number;
}

interface PlannedWeekChartProps {
  data: PlannedWeekChartRow[];
  metric: PlannedMetricView;
  onMetricChange?: (value: PlannedMetricView) => void;
}

function metricLabel(metric: PlannedMetricView): string {
  if (metric === 'rtss') return 'rTSS';
  if (metric === 'distance_eqv_km') return 'Dist Eqv (km)';
  return 'TSS';
}

function formatValue(value: number, metric: PlannedMetricView): string {
  if (metric === 'distance_eqv_km') return `${value.toFixed(1)} km`;
  return `${Math.round(value)}`;
}

function PlannedWeekValueLabel({
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
  metric: PlannedMetricView;
}): JSX.Element | null {
  const numeric = Number(value ?? 0);
  if (!Number.isFinite(numeric) || numeric <= 0) return null;
  const labelX = Number(x ?? 0) + Number(width ?? 0) / 2;
  const labelY = Math.max(Number(y ?? 0) - 10, 14);
  return (
    <text
      x={labelX}
      y={labelY}
      textAnchor="middle"
      fontSize={13}
      fontWeight={700}
      fill="#e2e8f0"
    >
      {formatValue(numeric, metric)}
    </text>
  );
}

function PlannedWeekTooltip({
  active,
  label,
  payload,
  metric,
}: TooltipProps<ValueType, NameType> & { metric: PlannedMetricView }): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  const value = Number(payload[0]?.value ?? 0);

  return (
    <div className="min-w-[170px] rounded-xl border border-sky-300/15 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-3 shadow-2xl backdrop-blur">
      <p className="mb-2 text-xs font-semibold text-foreground">{String(label || '')}</p>
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="text-slate-300/85">{metricLabel(metric)}</span>
        <span className="font-semibold text-foreground">{formatValue(value, metric)}</span>
      </div>
    </div>
  );
}

export function PlannedWeekChart({ data, metric, onMetricChange }: PlannedWeekChartProps): JSX.Element {
  const getBarFill = (row: PlannedWeekChartRow): string => {
    const thresholdBasis =
      metric === 'tss'
        ? row.value
        : metric === 'rtss' || metric === 'distance_eqv_km'
          ? row.tssBasis
          : row.value;
    return intensityHexFromThreshold(thresholdBasis);
  };

  return (
    <Card className={secondaryPageSurfaceClassName}>
      <CardContent className="px-4 pb-4 pt-5">
        {onMetricChange ? (
          <div className="mb-3 flex items-start justify-between gap-3">
            <PlannedMetricSelector value={metric} onValueChange={onMetricChange} showLabel={false} compact />
          </div>
        ) : null}
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barCategoryGap="25%" margin={{ top: 38, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(125,211,252,0.14)" />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12, fill: '#cbd5e1' }} axisLine={{ stroke: 'rgba(148,163,184,0.18)' }} tickLine={false} />
              <YAxis hide axisLine={false} tickLine={false} />
              <Tooltip content={<PlannedWeekTooltip metric={metric} />} cursor={{ fill: 'rgba(56, 189, 248, 0.08)' }} />
              <Bar dataKey="value" fill="#34d399" radius={[6, 6, 0, 0]}>
                {data.map((row) => (
                  <Cell key={`planned-week-bar-${row.dayLabel}`} fill={getBarFill(row)} />
                ))}
                <LabelList
                  dataKey="value"
                  position="top"
                  content={(props) => <PlannedWeekValueLabel {...props} metric={metric} />}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

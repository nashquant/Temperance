import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { Card, CardContent } from '@/components/ui/card';
import type { PlannedMetricView } from '@/features/plan-activities/types/plan-activities';

interface PlannedWeekChartRow {
  dayLabel: string;
  value: number;
  tssBasis: number;
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

export function PlannedWeekChart({ data, metric }: PlannedWeekChartProps): JSX.Element {
  const valueLabelFormatter = (value: number) => (value > 0 ? formatValue(value, metric) : '');
  const getBarFill = (row: PlannedWeekChartRow): string => {
    const thresholdBasis =
      metric === 'tss'
        ? row.value
        : metric === 'rtss' || metric === 'distance_eqv_km'
          ? row.tssBasis
          : row.value;
    if (thresholdBasis > 150) return '#a855f7';
    if (thresholdBasis > 120) return '#ef4444';
    if (thresholdBasis > 80) return '#f97316';
    if (thresholdBasis > 50) return '#facc15';
    return '#22c55e';
  };

  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="p-4">
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barCategoryGap="25%">
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(125,211,252,0.14)" />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12, fill: '#cbd5e1' }} axisLine={{ stroke: 'rgba(148,163,184,0.18)' }} tickLine={false} />
              <YAxis tick={{ fontSize: 12, fill: '#cbd5e1' }} axisLine={false} tickLine={false} label={{ value: metricLabel(metric), angle: -90, position: 'insideLeft', style: { fill: '#94a3b8' } }} />
              <Tooltip content={<PlannedWeekTooltip metric={metric} />} cursor={{ fill: 'rgba(56, 189, 248, 0.08)' }} />
              <Bar dataKey="value" fill="#34d399" radius={[6, 6, 0, 0]}>
                {data.map((row) => (
                  <Cell key={`planned-week-bar-${row.dayLabel}`} fill={getBarFill(row)} />
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

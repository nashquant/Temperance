import {
  CartesianGrid,
  Label,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface SeriesConfig {
  key: string;
  label: string;
  color: string;
  yAxisId?: 'left' | 'right';
  dashed?: boolean;
  strokeOpacity?: number;
  dotOpacity?: number;
  strokeWidth?: number;
}

interface Props {
  title: string;
  data: Array<Record<string, number | string | null | undefined>>;
  yLabel: string;
  series: SeriesConfig[];
  targetKey?: string;
  targetLabel?: string;
  rightAxisLabel?: string;
}

const INTEGER_LIKE_KEYS = new Set([
  'tss',
  'rtss',
  'stress_target_tss',
  'pounding_target_tss',
  'sleep_score',
  'training_readiness',
  'resting_hr',
  'hrv_status',
  'stress_avg',
  'stress_max',
  'body_battery_start',
  'body_battery_end',
  'body_battery_avg',
  'respiration_avg',
  'steps',
  'intensity_minutes',
  'fitness',
  'fatigue',
  'overreach',
  'injury_risk',
  'leg_elasticity',
  'pounding',
  'vdot',
  'vdot_max',
  'training_load_garmin',
  'calories_total',
  '__target',
]);

const HOUR_LIKE_KEYS = new Set([
  'zone_low_aerobic_h',
  'zone_moderate_aerobic_h',
  'zone_high_aerobic_h',
  'zone_total_h',
  'sleep_duration_h',
  'deep_sleep_h',
  'rem_sleep_h',
  'light_sleep_h',
  'awake_h',
]);

function shouldUseIntegerFormat(dataKey: string): boolean {
  return INTEGER_LIKE_KEYS.has(String(dataKey || ''));
}

function shouldUseHourFormat(dataKey: string): boolean {
  return HOUR_LIKE_KEYS.has(String(dataKey || ''));
}

function formatHourLikeValue(value: number): string {
  if (value >= 1) return `${value.toFixed(1)}h`;
  return `${Math.round(value * 60)}'`;
}

function formatProgressionValue(value: unknown, dataKey?: string): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value ?? '-');
  if (shouldUseHourFormat(String(dataKey || ''))) return formatHourLikeValue(numeric);
  return shouldUseIntegerFormat(String(dataKey || '')) ? String(Math.round(numeric)) : numeric.toFixed(2);
}

function formatTooltipDateLabel(value: string): string {
  const raw = String(value || '');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return raw;
  const date = new Date(`${raw}T00:00:00`);
  if (Number.isNaN(date.getTime())) return raw;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(date);
}

function ProgressionTooltip({
  active,
  label,
  payload,
  targetKey,
}: TooltipProps<ValueType, NameType> & { targetKey?: string }): JSX.Element | null {
  const visiblePayload = (payload ?? []).filter((entry) => String(entry.dataKey || '') !== String(targetKey || ''));
  if (!active || visiblePayload.length === 0) return null;
  return (
    <div
      className="pointer-events-none inline-block w-fit max-w-[132px] rounded-lg border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.96),rgba(2,6,23,0.98))] px-2 py-1.5 shadow-[0_10px_26px_rgba(2,6,23,0.26)] backdrop-blur"
      style={{ transform: 'translate(calc(-50% - 20px), calc(-100% - 32px))' }}
    >
      <p className="mb-1 whitespace-nowrap text-[11px] font-semibold text-slate-100">{formatTooltipDateLabel(String(label || ''))}</p>
      <div className="space-y-1">
        {visiblePayload.map((entry) => (
          <div key={`${entry.name}-${entry.dataKey}`} className="flex items-center justify-between gap-2 text-[10px] leading-4">
            <span className="truncate font-medium" style={{ color: String(entry.color || '#cbd5e1') }}>
              {entry.name}
            </span>
            <span className="shrink-0 font-semibold" style={{ color: String(entry.color || '#e2e8f0') }}>
              {formatProgressionValue(entry.value, String(entry.dataKey || ''))}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ProgressionLineChartCard({
  title,
  data,
  yLabel,
  series,
  targetKey,
  targetLabel,
  rightAxisLabel,
}: Props): JSX.Element {
  const leftAxisUsesIntegers = series
    .filter((item) => (item.yAxisId ?? 'left') === 'left')
    .every((item) => shouldUseIntegerFormat(item.key))
    && (!targetKey || shouldUseIntegerFormat(targetKey));
  const rightAxisUsesIntegers = rightAxisLabel
    ? series
        .filter((item) => item.yAxisId === 'right')
        .every((item) => shouldUseIntegerFormat(item.key))
    : false;
  const leftAxisUsesHourFormat = series
    .filter((item) => (item.yAxisId ?? 'left') === 'left')
    .every((item) => shouldUseHourFormat(item.key));
  const rightAxisUsesHourFormat = rightAxisLabel
    ? series
        .filter((item) => item.yAxisId === 'right')
        .every((item) => shouldUseHourFormat(item.key))
    : false;
  const hasTargetSeries = targetKey
    ? data.some((row) => {
        const candidate = Number(row?.[targetKey] ?? 0);
        return Number.isFinite(candidate) && candidate > 0;
      })
    : false;
  const chartData = data.map((row) => {
    const nextRow: Record<string, number | string | null | undefined> = {
      ...row,
      _x: String(row.period_start ?? row.label ?? ''),
    };
    for (const item of series) {
      const raw = nextRow[item.key];
      if (raw == null || raw === '') {
        nextRow[item.key] = null;
        continue;
      }
      const parsed = Number(raw);
      nextRow[item.key] = Number.isFinite(parsed) ? parsed : null;
    }
    if (targetKey) {
      const rawTarget = nextRow[targetKey];
      if (rawTarget == null || rawTarget === '') {
        nextRow[targetKey] = null;
      } else {
        const parsedTarget = Number(rawTarget);
        nextRow[targetKey] = Number.isFinite(parsedTarget) ? parsedTarget : null;
      }
    }
    return nextRow;
  }) as Array<Record<string, number | string | null | undefined>>;
  const labelMap = new Map(chartData.map((row) => [String(row._x ?? ''), String(row['label'] ?? row._x ?? '')]));
  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-slate-200/88">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 14, right: 14, bottom: 6, left: 2 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(125,211,252,0.14)" />
              <XAxis
                dataKey="_x"
                type="category"
                tick={{ fontSize: 12, fill: '#cbd5e1' }}
                axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                tickLine={false}
                tickFormatter={(value) => labelMap.get(String(value)) ?? String(value)}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 12, fill: '#cbd5e1' }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(value) => {
                  const numeric = Number(value);
                  if (!Number.isFinite(numeric)) return String(value);
                  if (leftAxisUsesHourFormat) return formatHourLikeValue(numeric);
                  if (leftAxisUsesIntegers) return String(Math.round(numeric));
                  return String(value);
                }}
              >
                <Label value={yLabel} angle={-90} position="insideLeft" style={{ textAnchor: 'middle', fill: '#94a3b8' }} />
              </YAxis>
              {rightAxisLabel ? (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fontSize: 12, fill: '#cbd5e1' }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(value) => {
                    const numeric = Number(value);
                    if (!Number.isFinite(numeric)) return String(value);
                    if (rightAxisUsesHourFormat) return formatHourLikeValue(numeric);
                    if (rightAxisUsesIntegers) return String(Math.round(numeric));
                    return String(value);
                  }}
                />
              ) : null}
              <Tooltip
                content={<ProgressionTooltip targetKey={targetKey} />}
                labelFormatter={(value) => labelMap.get(String(value)) ?? String(value)}
                cursor={{ stroke: '#38bdf8', strokeOpacity: 0.3 }}
                allowEscapeViewBox={{ x: true, y: true }}
              />
              <Legend wrapperStyle={{ color: '#cbd5e1' }} />
              {series.map((item) => (
                <Line
                  key={item.key}
                  type="monotone"
                  dataKey={item.key}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={item.strokeWidth ?? 2}
                  yAxisId={item.yAxisId ?? 'left'}
                  strokeDasharray={item.dashed ? '5 5' : undefined}
                  strokeOpacity={item.strokeOpacity}
                  dot={{ r: 2.5, strokeWidth: 1, fill: item.color, fillOpacity: item.dotOpacity ?? item.strokeOpacity ?? 1, strokeOpacity: item.dotOpacity ?? item.strokeOpacity ?? 1 }}
                  activeDot={{ r: 4, fill: item.color, fillOpacity: item.dotOpacity ?? item.strokeOpacity ?? 1, strokeOpacity: item.dotOpacity ?? item.strokeOpacity ?? 1 }}
                  connectNulls
                />
              ))}
              {targetKey && hasTargetSeries ? (
                <Line
                  type="monotone"
                  dataKey={targetKey}
                  yAxisId="left"
                  stroke="#cbd5e1"
                  strokeOpacity={0.92}
                  strokeWidth={1.4}
                  strokeDasharray="5 5"
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                  legendType="none"
                  connectNulls
                />
              ) : null}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

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
}

interface Props {
  title: string;
  data: Array<Record<string, number | string>>;
  yLabel: string;
  series: SeriesConfig[];
  targetKey?: string;
  targetLabel?: string;
  rightAxisLabel?: string;
}

function ProgressionTooltip({
  active,
  label,
  payload,
}: TooltipProps<ValueType, NameType>): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="pointer-events-none min-w-[168px] -translate-x-1/2 -translate-y-[calc(100%+32px)] rounded-md border border-border/80 bg-background/95 p-2 shadow-xl backdrop-blur">
      <p className="mb-1 text-xs font-semibold text-foreground">{String(label || '')}</p>
      <div className="space-y-0.5">
        {payload.map((entry) => (
          <p key={`${entry.name}-${entry.dataKey}`} className="text-xs">
            <span className="font-medium" style={{ color: String(entry.color || '#cbd5e1') }}>
              {entry.name}
            </span>
            <span className="text-muted-foreground">: </span>
            <span className="font-semibold" style={{ color: String(entry.color || '#e2e8f0') }}>
              {typeof entry.value === 'number' ? entry.value.toFixed(2) : String(entry.value ?? '-')}
            </span>
          </p>
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
  const chartData = data.map((row) => ({
    ...row,
    _x: String(row.period_start ?? row.label ?? ''),
  })) as Array<Record<string, number | string>>;
  const labelMap = new Map(chartData.map((row) => [String(row._x ?? ''), String(row['label'] ?? row._x ?? '')]));
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div className="h-[280px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 14, right: 14, bottom: 6, left: 2 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
              <XAxis
                dataKey="_x"
                type="category"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => labelMap.get(String(value)) ?? String(value)}
              />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }}>
                <Label value={yLabel} angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
              </YAxis>
              {rightAxisLabel ? <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} /> : null}
              <Tooltip
                content={<ProgressionTooltip />}
                labelFormatter={(value) => labelMap.get(String(value)) ?? String(value)}
                cursor={{ stroke: '#94a3b8', strokeOpacity: 0.35 }}
                allowEscapeViewBox={{ x: true, y: true }}
              />
              <Legend />
              {targetKey ? (
                <ReferenceLine yAxisId="left" y={Number(data.at(-1)?.[targetKey] ?? 0)} stroke="#f59e0b" strokeDasharray="5 5" />
              ) : null}
              {series.map((item) => (
                <Line
                  key={item.key}
                  type="monotone"
                  dataKey={item.key}
                  name={item.label}
                  stroke={item.color}
                  strokeWidth={2}
                  dot={{ r: 2.5, strokeWidth: 1, fill: item.color }}
                  activeDot={{ r: 4 }}
                  yAxisId={item.yAxisId ?? 'left'}
                  strokeDasharray={item.dashed ? '5 5' : undefined}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

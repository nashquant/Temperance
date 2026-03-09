import {
  CartesianGrid,
  Label,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

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
  injuryOverlays?: Array<{
    start: string;
    end: string;
    severity: 'injury' | 'light_injury';
    label?: string;
  }>;
  targetKey?: string;
  targetLabel?: string;
  rightAxisLabel?: string;
}

export function ProgressionLineChartCard({
  title,
  data,
  yLabel,
  series,
  injuryOverlays,
  targetKey,
  targetLabel,
  rightAxisLabel,
}: Props): JSX.Element {
  const chartData = data.map((row) => ({
    ...row,
    _x: String(row.period_start ?? row.label ?? ''),
  })) as Array<Record<string, number | string>>;
  const labelMap = new Map(chartData.map((row) => [String(row._x ?? ''), String(row['label'] ?? row._x ?? '')]));
  const pointKeys = new Set(chartData.map((row) => String(row._x ?? '')));
  const mappedOverlays = (injuryOverlays ?? [])
    .map((overlay) => ({
      ...overlay,
      x1: String(overlay.start),
      x2: String(overlay.end),
    }))
    .filter(
      (overlay): overlay is { start: string; end: string; severity: 'injury' | 'light_injury'; label?: string; x1: string; x2: string } =>
        pointKeys.has(overlay.x1) && pointKeys.has(overlay.x2),
    );

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
              <Tooltip labelFormatter={(value) => labelMap.get(String(value)) ?? String(value)} />
              <Legend />
              {mappedOverlays.map((overlay, index) => (
                <ReferenceArea
                  key={`${overlay.start}-${overlay.end}-${index}`}
                  x1={overlay.x1}
                  x2={overlay.x2}
                  ifOverflow="extendDomain"
                  stroke={overlay.severity === 'injury' ? '#ef4444' : '#eab308'}
                  strokeOpacity={0.55}
                  fill={overlay.severity === 'injury' ? '#ef4444' : '#eab308'}
                  fillOpacity={0.24}
                />
              ))}
              {targetKey ? (
                <ReferenceLine yAxisId="left" y={Number(data.at(-1)?.[targetKey] ?? 0)} stroke="#f59e0b" strokeDasharray="5 5" label={targetLabel} />
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

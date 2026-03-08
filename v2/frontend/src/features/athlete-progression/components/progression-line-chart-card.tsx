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
  targetKey?: string;
  targetLabel?: string;
  rightAxisLabel?: string;
  injuryOverlays?: Array<{
    start: string;
    end: string;
    severity: 'injury' | 'light_injury';
    label?: string;
  }>;
}

export function ProgressionLineChartCard({
  title,
  data,
  yLabel,
  series,
  targetKey,
  targetLabel,
  rightAxisLabel,
  injuryOverlays = [],
}: Props): JSX.Element {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <div style={{ height: 280, width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 14, right: 14, bottom: 6, left: 2 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
              <XAxis
                dataKey="period_start"
                tick={{ fontSize: 12 }}
                tickFormatter={(value) => {
                  const d = new Date(`${String(value)}T00:00:00`);
                  if (Number.isNaN(d.getTime())) return String(value);
                  return new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' }).format(d);
                }}
              />
              <YAxis yAxisId="left" tick={{ fontSize: 12 }}>
                <Label value={yLabel} angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
              </YAxis>
              {rightAxisLabel ? <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} /> : null}
              <Tooltip
                labelFormatter={(value) => {
                  const d = new Date(`${String(value)}T00:00:00`);
                  if (Number.isNaN(d.getTime())) return String(value);
                  return new Intl.DateTimeFormat('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).format(d);
                }}
              />
              <Legend />
              {injuryOverlays.map((overlay, index) => (
                <ReferenceArea
                  key={`${overlay.start}-${overlay.end}-${overlay.severity}-${index}`}
                  x1={overlay.start}
                  x2={overlay.end}
                  yAxisId="left"
                  fill={overlay.severity === 'light_injury' ? '#facc15' : '#ef4444'}
                  fillOpacity={0.12}
                  strokeOpacity={0}
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

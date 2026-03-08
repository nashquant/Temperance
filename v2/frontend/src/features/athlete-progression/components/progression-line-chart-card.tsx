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

export function ProgressionLineChartCard({
  title,
  data,
  yLabel,
  series,
  targetKey,
  targetLabel,
  rightAxisLabel,
}: Props): JSX.Element {
  return (
    <div className="rounded-2xl bg-[linear-gradient(135deg,rgba(56,189,248,0.38),rgba(168,85,247,0.24),rgba(245,158,11,0.2))] p-[1px] shadow-[0_10px_26px_rgba(2,6,23,0.42)]">
      <Card className="rounded-2xl border-border/70 bg-[radial-gradient(circle_at_8%_10%,rgba(56,189,248,0.08),transparent_40%),radial-gradient(circle_at_88%_90%,rgba(168,85,247,0.12),transparent_45%)] shadow-inner">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        </CardHeader>
        <CardContent className="p-4 pt-0">
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 14, right: 14, bottom: 6, left: 2 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} strokeOpacity={0.25} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 12 }}>
                  <Label value={yLabel} angle={-90} position="insideLeft" style={{ textAnchor: 'middle' }} />
                </YAxis>
                {rightAxisLabel ? <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} /> : null}
                <Tooltip />
                <Legend />
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
    </div>
  );
}

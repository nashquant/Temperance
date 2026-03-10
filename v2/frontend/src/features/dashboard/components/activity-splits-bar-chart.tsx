import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { TooltipProps } from 'recharts';
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent';

import { Card, CardContent } from '@/components/ui/card';

type ActivitySplitsBarChartRow = {
  label: string;
  ifPct: number;
  type: string;
};

type ActivitySplitsBarChartProps = {
  data: ActivitySplitsBarChartRow[];
};

function getBarFill(ifPct: number): string {
  if (ifPct >= 100) return '#f87171';
  if (ifPct >= 90) return '#fb923c';
  if (ifPct >= 80) return '#facc15';
  if (ifPct >= 65) return '#38bdf8';
  return '#34d399';
}

function ActivitySplitsBarTooltip({
  active,
  label,
  payload,
}: TooltipProps<ValueType, NameType>): JSX.Element | null {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload as ActivitySplitsBarChartRow | undefined;
  if (!row) return null;

  return (
    <div className="min-w-[180px] rounded-xl border border-sky-300/15 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-3 shadow-2xl backdrop-blur">
      <p className="mb-2 text-xs font-semibold text-foreground">{String(label || '')}</p>
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Type</span>
          <span className="font-semibold text-foreground">{row.type || '-'}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">IF</span>
          <span className="font-semibold text-foreground">{Math.round(row.ifPct)}%</span>
        </div>
      </div>
    </div>
  );
}

export function ActivitySplitsBarChart({ data }: ActivitySplitsBarChartProps): JSX.Element | null {
  if (data.length === 0) return null;

  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="p-4">
        <div className="h-[220px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} barCategoryGap="18%">
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(125,211,252,0.14)" />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: '#cbd5e1' }}
                axisLine={{ stroke: 'rgba(148,163,184,0.18)' }}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 12, fill: '#cbd5e1' }}
                axisLine={false}
                tickLine={false}
                label={{ value: 'IF (%)', angle: -90, position: 'insideLeft', style: { fill: '#94a3b8' } }}
              />
              <Tooltip content={<ActivitySplitsBarTooltip />} cursor={{ fill: 'rgba(56, 189, 248, 0.08)' }} />
              <Bar dataKey="ifPct" radius={[6, 6, 0, 0]}>
                {data.map((row) => (
                  <Cell key={row.label} fill={getBarFill(row.ifPct)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

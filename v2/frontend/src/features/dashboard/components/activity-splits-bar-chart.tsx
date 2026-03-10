import { useMemo, useRef, useState } from 'react';
import { Gauge, Moon, Sparkles, Target, Waves } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { intensityHexFromKey, intensityHexFromThreshold } from '@/features/dashboard/utils/intensity-palette';

type ActivitySplitsBarChartRow = {
  label: string;
  ifPct: number;
  type: string;
  duration_s: number;
};

type ActivitySplitsBarChartProps = {
  data: ActivitySplitsBarChartRow[];
};

type ChartDatum = ActivitySplitsBarChartRow & {
  x0: number;
  x1: number;
  pctOfTotal: number;
};

type TooltipState = {
  datum: ChartDatum;
  x: number;
  y: number;
} | null;

function getBarFill(type: string, ifPct: number): string {
  const normalizedType = String(type || '').trim().toLowerCase();

  if (
    normalizedType.includes('vo2') ||
    normalizedType.includes('v02') ||
    normalizedType.includes('vo2max') ||
    normalizedType.includes('anaerobic')
  ) {
    return intensityHexFromKey('purple');
  }
  if (normalizedType.includes('threshold') || normalizedType.includes('tempo hard') || normalizedType.includes('hard')) {
    return intensityHexFromKey('red');
  }
  if (normalizedType.includes('steady') || normalizedType.includes('tempo') || normalizedType.includes('mod')) {
    return intensityHexFromKey('orange');
  }
  if (normalizedType.includes('easy') || normalizedType.includes('endurance') || normalizedType.includes('aerobic')) {
    return intensityHexFromKey('blue');
  }
  if (normalizedType.includes('recovery') || normalizedType.includes('recover') || normalizedType.includes('rest')) {
    return intensityHexFromKey('green');
  }

  return intensityHexFromThreshold(ifPct);
}

function getTypeVisual(type: string, ifPct: number): {
  icon: typeof Moon;
  color: string;
} {
  const normalizedType = String(type || '').trim().toLowerCase();

  if (
    normalizedType.includes('vo2') ||
    normalizedType.includes('v02') ||
    normalizedType.includes('vo2max') ||
    normalizedType.includes('anaerobic')
  ) {
    return { icon: Sparkles, color: intensityHexFromKey('purple') };
  }
  if (normalizedType.includes('threshold') || normalizedType.includes('tempo hard') || normalizedType.includes('hard')) {
    return { icon: Target, color: intensityHexFromKey('red') };
  }
  if (normalizedType.includes('steady') || normalizedType.includes('tempo') || normalizedType.includes('mod')) {
    return { icon: Gauge, color: intensityHexFromKey('orange') };
  }
  if (normalizedType.includes('easy') || normalizedType.includes('endurance') || normalizedType.includes('aerobic')) {
    return { icon: Waves, color: intensityHexFromKey('blue') };
  }
  if (normalizedType.includes('recovery') || normalizedType.includes('recover') || normalizedType.includes('rest')) {
    return { icon: Moon, color: intensityHexFromKey('green') };
  }

  const fallbackColor = intensityHexFromThreshold(ifPct);
  if (fallbackColor === intensityHexFromKey('purple')) return { icon: Sparkles, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('red')) return { icon: Target, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('orange')) return { icon: Gauge, color: fallbackColor };
  if (fallbackColor === intensityHexFromKey('blue')) return { icon: Waves, color: fallbackColor };
  return { icon: Moon, color: fallbackColor };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60);
  const secs = total % 60;
  if (secs === 0) return `${minutes}'`;
  return `${minutes}'${String(secs).padStart(2, '0')}"`;
}

function buildChartData(data: ActivitySplitsBarChartRow[]): ChartDatum[] {
  const sanitized = data
    .map((row) => ({
      ...row,
      duration_s: Math.max(0, Number(row.duration_s) || 0),
      ifPct: Math.max(0, Number(row.ifPct) || 0),
      type: String(row.type || ''),
    }))
    .filter((row) => row.duration_s > 0);

  const totalDuration = sanitized.reduce((sum, row) => sum + row.duration_s, 0);
  let cumulative = 0;

  return sanitized.map((row) => {
    const x0 = totalDuration > 0 ? cumulative / totalDuration : 0;
    cumulative += row.duration_s;
    const x1 = totalDuration > 0 ? cumulative / totalDuration : 1;
    return {
      ...row,
      x0,
      x1,
      pctOfTotal: totalDuration > 0 ? row.duration_s / totalDuration : 0,
    };
  });
}

function ActivitySplitsBarTooltip({ tooltip }: { tooltip: TooltipState }): JSX.Element | null {
  if (!tooltip) return null;
  const { datum, x, y } = tooltip;
  const typeVisual = getTypeVisual(datum.type, datum.ifPct);
  const TypeIcon = typeVisual.icon;

  return (
    <div
      className="pointer-events-none absolute z-10 min-w-[180px] rounded-xl border border-sky-300/15 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_45%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] p-3 text-xs shadow-2xl backdrop-blur"
      style={{
        left: x,
        top: y,
        transform: 'translate(-50%, calc(-100% - 10px))',
      }}
    >
      <p className="mb-2 text-xs font-semibold text-foreground">{datum.label}</p>
      <div className="space-y-1.5 text-xs">
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Type</span>
          <span className="inline-flex items-center gap-1.5 font-semibold text-foreground">
            <TypeIcon className="h-3.5 w-3.5" style={{ color: typeVisual.color }} />
            <span>{datum.type || '-'}</span>
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">Duration</span>
          <span className="font-semibold text-foreground">{formatDuration(datum.duration_s)}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">IF</span>
          <span className="font-semibold text-foreground">{Math.round(datum.ifPct)}%</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-slate-300/80">% Total</span>
          <span className="font-semibold text-foreground">{(datum.pctOfTotal * 100).toFixed(1)}%</span>
        </div>
      </div>
    </div>
  );
}

export function ActivitySplitsBarChart({ data }: ActivitySplitsBarChartProps): JSX.Element | null {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [tooltip, setTooltip] = useState<TooltipState>(null);
  const chartData = useMemo(() => buildChartData(data), [data]);

  if (chartData.length === 0) return null;

  const svgWidth = 1000;
  const svgHeight = 220;
  const margin = { top: 10, right: 10, bottom: 12, left: 10 };
  const innerWidth = svgWidth - margin.left - margin.right;
  const innerHeight = svgHeight - margin.top - margin.bottom;
  const yMax = Math.max(100, ...chartData.map((row) => row.ifPct));
  const axisY = margin.top + innerHeight;

  return (
    <Card className="overflow-hidden rounded-2xl border-border/70 bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] shadow-[0_18px_40px_rgba(2,6,23,0.32)]">
      <CardContent className="p-4">
        <div ref={containerRef} className="relative h-[220px] w-full" onMouseLeave={() => setTooltip(null)}>
          <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="h-full w-full" role="img" aria-label="Splits bar chart">
            {chartData.map((row) => {
              const x = margin.left + innerWidth * row.x0;
              const rawWidth = innerWidth * (row.x1 - row.x0);
              const width = Math.max(rawWidth - 1.5, 1);
              const barHeight = (row.ifPct / yMax) * innerHeight;
              const y = axisY - barHeight;
              const active = tooltip?.datum.label === row.label;

              return (
                <g key={row.label}>
                  <rect
                    x={x}
                    y={y}
                    width={width}
                    height={barHeight}
                    rx="3"
                    fill={getBarFill(row.type, row.ifPct)}
                    opacity={active ? 1 : 0.95}
                    stroke={active ? 'rgba(226,232,240,0.9)' : 'rgba(255,255,255,0.08)'}
                    strokeWidth={active ? 1.5 : 1}
                    onMouseMove={(event) => {
                      const bounds = containerRef.current?.getBoundingClientRect();
                      if (!bounds) return;
                      setTooltip({
                        datum: row,
                        x: clamp(event.clientX - bounds.left, 90, bounds.width - 90),
                        y: clamp(event.clientY - bounds.top, 20, bounds.height - 20),
                      });
                    }}
                  />
                  <line
                    x1={x + width}
                    y1={margin.top}
                    x2={x + width}
                    y2={axisY}
                    stroke="rgba(15,23,42,0.55)"
                    strokeWidth="1"
                  />
                </g>
              );
            })}
          </svg>
          <ActivitySplitsBarTooltip tooltip={tooltip} />
        </div>
      </CardContent>
    </Card>
  );
}
